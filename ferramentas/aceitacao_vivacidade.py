#!/usr/bin/env python3
"""NV-23 — aceitação integrada, read-only, da vivacidade causal.

Este módulo não cria runtime, scheduler, fila, evento ou decisão narrativa. Ele
reproduz dois episódios de aceitação sobre a fronteira NV-14 já existente,
valida uma cadeia causal semântica e ancora as regressões obrigatórias em testes
permanentes que já exercitam os produtores reais.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
from pathlib import Path
from typing import Any

import yaml

import fronteira_vivacidade as live
import mundo

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("tests/fixtures/aceitacao-vivacidade-episodios.yaml")
BUDGET = Path("baseline/aceitacao-vivacidade-orcamento.yaml")
ROLLOUT = Path("tests/fixtures/rollout-step11-mini.jsonl")
SCHEMA = 1

LOADED = "dia_carregado_circo"
CALM = "dia_legitimamente_calmo"
REQUIRED_ROLES = {"mensagem_comunicavel_vencida", "compromisso_temporal_vencido", "causa_sidequest_vencida"}
REQUIRED_SEMANTIC_EDGES = {
    ("clima_diario", "transito"),
    ("politica_civica", "entrega_publica"),
    ("presenca_incidental", "cena"),
    ("causa_sidequest", "sidequest"),
    ("mecanica_gate", "resultado_mecanico"),
    ("consequencia_relacional", "consequencia_futura"),
    ("consequencia_reputacao", "consequencia_futura"),
    ("permanencia_espacial", "consequencia_futura"),
}
REQUIRED_REGRESSIONS = {
    "comunicacao_resolvida_nao_desaparece",
    "permanencia_longa_local_nao_nulo",
    "causa_nv11_vencida_nao_silenciada",
    "iniciativa_elegivel_recebe_decisao",
    "sem_scan_global_ou_ia_por_npc",
    "turno_curto_economico",
    "turno_longo_reusa_fronteira",
    "projecao_limitada",
    "clima_alimenta_transito",
    "politica_entrega_por_canal_causal",
    "presenca_incidental_nao_fabrica_encontro",
    "mecanica_passa_pelo_gate",
    "reputacao_persiste_sem_score_oculto",
}


class AcceptanceError(ValueError):
    """Contrato da aceitação de vivacidade inválido."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AcceptanceError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, maximum: int = 1000) -> str:
    if not isinstance(value, str):
        raise AcceptanceError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise AcceptanceError(f"{label} deve ter 1..{maximum} caracteres")
    return result


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AcceptanceError(f"não foi possível ler {label}: {exc}") from exc
    return _map(data, label)


def load_fixture(repo: Path = ROOT) -> dict[str, Any]:
    data = _load_yaml(Path(repo) / FIXTURE, FIXTURE.as_posix())
    if data.get("schema_aceitacao_vivacidade") != SCHEMA:
        raise AcceptanceError("fixture de aceitação deve usar schema 1")
    episodes = _map(data.get("episodios"), "episodios")
    if set(episodes) != {LOADED, CALM}:
        raise AcceptanceError("fixture deve conter exatamente os episódios carregado e calmo")
    regressions = _map(data.get("regressoes"), "regressoes")
    if set(regressions) != REQUIRED_REGRESSIONS:
        missing = sorted(REQUIRED_REGRESSIONS - set(regressions))
        extra = sorted(set(regressions) - REQUIRED_REGRESSIONS)
        raise AcceptanceError(f"regressões divergentes; faltam={missing}, extras={extra}")
    return data


def load_budget(repo: Path = ROOT) -> dict[str, Any]:
    budget = _load_yaml(Path(repo) / BUDGET, BUDGET.as_posix())
    if budget.get("schema_orcamento_aceitacao_vivacidade") != SCHEMA:
        raise AcceptanceError("orçamento NV-23 deve usar schema 1")
    limits = _map(budget.get("limites"), "limites")
    expected_limits = {
        "max_candidatas": live.MAX_CANDIDATES,
        "max_bytes_projecao": live.MAX_OUTPUT_BYTES,
        "max_primarias_por_janela": 1,
        "chamadas_ia_por_npc": 0,
        "scans_globais_npc": 0,
    }
    for key, expected in expected_limits.items():
        if limits.get(key) != expected:
            raise AcceptanceError(f"orçamento {key} divergiu do runtime: {limits.get(key)} != {expected}")
    architecture = _map(budget.get("arquitetura"), "arquitetura")
    forbidden = ("scheduler_novo", "fila_nova", "hot_path_novo", "writer_novo")
    if any(architecture.get(key) is not False for key in forbidden):
        raise AcceptanceError("NV-23 não pode instalar scheduler, fila, hot path ou writer paralelos")
    if architecture.get("reusa_fronteira_vivacidade") is not True:
        raise AcceptanceError("NV-23 precisa reutilizar a fronteira de vivacidade existente")
    if architecture.get("aceitacao_read_only") is not True:
        raise AcceptanceError("checker de aceitação precisa permanecer read-only")
    permanent = _text(budget.get("teste_permanente"), "teste_permanente", 160)
    if "nv23" in permanent.lower() or "task" in permanent.lower():
        raise AcceptanceError("teste permanente deve receber nome de domínio, não nome de task/NV")
    return budget


def _windows(raw: Any) -> list[dict[str, Any]]:
    rows = _list(raw, "janelas")
    if not rows:
        raise AcceptanceError("episódio exige ao menos uma janela")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        row = _map(item, f"janelas[{index}]")
        if set(row) != {"gatilho", "periodo", "inicio", "fim"}:
            raise AcceptanceError(f"janelas[{index}] possui campos divergentes")
        result.append(copy.deepcopy(row))
    return result


def _semantic_graph(raw: Any, *, require_edges: bool = True) -> dict[str, Any]:
    nodes = _list(raw, "cadeia_semantica")
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(nodes):
        node = _map(item, f"cadeia_semantica[{index}]")
        if set(node) != {"id", "sistema", "causas", "evidencia"}:
            raise AcceptanceError("nó semântico exige id, sistema, causas e evidencia")
        node_id = _text(node.get("id"), "cadeia_semantica.id", 96)
        if node_id in by_id:
            raise AcceptanceError(f"nó semântico duplicado: {node_id}")
        causes = [_text(value, f"{node_id}.causas", 96) for value in _list(node.get("causas"), f"{node_id}.causas")]
        if len(causes) != len(set(causes)):
            raise AcceptanceError(f"{node_id}: causas duplicadas")
        by_id[node_id] = {
            "id": node_id,
            "sistema": _text(node.get("sistema"), f"{node_id}.sistema", 80),
            "causas": causes,
            "evidencia": _text(node.get("evidencia"), f"{node_id}.evidencia", 600),
        }
    for node in by_id.values():
        unknown = [cause for cause in node["causas"] if cause not in by_id]
        if unknown:
            raise AcceptanceError(f"{node['id']}: causas inexistentes: {unknown}")
    edges = {
        (by_id[cause]["sistema"], node["sistema"])
        for node in by_id.values()
        for cause in node["causas"]
    }
    missing = sorted(REQUIRED_SEMANTIC_EDGES - edges) if require_edges else []
    if missing:
        raise AcceptanceError(f"cadeia semântica não prova relações obrigatórias: {missing}")
    return {
        "nos": len(by_id),
        "sistemas": sorted({node["sistema"] for node in by_id.values()}),
        "arestas_obrigatorias": sorted(f"{a}->{b}" for a, b in REQUIRED_SEMANTIC_EDGES),
    }


def _initiative(raw: Any, *, calm: bool) -> dict[str, Any]:
    data = _map(raw, "iniciativa")
    if set(data) != {"itens", "chamadas_ia_por_npc", "scans_globais_npc"}:
        raise AcceptanceError("iniciativa possui campos divergentes")
    if data["chamadas_ia_por_npc"] != 0 or data["scans_globais_npc"] != 0:
        raise AcceptanceError("iniciativa integrada não pode usar IA por NPC nem scan global")
    items = _list(data["itens"], "iniciativa.itens")
    if calm:
        if items:
            raise AcceptanceError("dia calmo não pode conter iniciativa elegível")
        return {"decisoes": 0, "apresentadas": 0}
    if not items:
        raise AcceptanceError("dia carregado precisa de iniciativa plausível")
    seen: set[str] = set()
    presented = 0
    for pos, raw_item in enumerate(items):
        item = _map(raw_item, f"iniciativa.itens[{pos}]")
        if set(item) != {"npc_id", "resultado", "motivo"}:
            raise AcceptanceError("decisão de iniciativa exige npc_id, resultado e motivo")
        npc_id = _text(item["npc_id"], "iniciativa.npc_id", 96)
        if npc_id in seen:
            raise AcceptanceError(f"iniciativa duplicada para {npc_id}")
        seen.add(npc_id)
        outcome = _text(item["resultado"], "iniciativa.resultado", 64)
        if outcome not in {"apresentada", "silencio_justificado", "adiada_por_pressao_superior", "nao_elegivel"}:
            raise AcceptanceError(f"resultado de iniciativa desconhecido: {outcome}")
        _text(item["motivo"], "iniciativa.motivo", 260)
        presented += outcome == "apresentada"
    if presented != 1:
        raise AcceptanceError("dia carregado deve saturar a janela com exatamente uma abertura apresentada")
    return {"decisoes": len(items), "apresentadas": presented}


def evaluate_episode(name: str, raw: Any) -> dict[str, Any]:
    episode = _map(raw, f"episodios.{name}")
    required = {"janelas", "consultas", "candidatas", "papeis", "iniciativa", "permanencia", "cadeia_semantica"}
    if set(episode) != required:
        raise AcceptanceError(f"{name}: campos divergentes")
    windows = _windows(episode["janelas"])
    checks = _list(episode["consultas"], f"{name}.consultas")
    candidates = _list(episode["candidatas"], f"{name}.candidatas")
    result = live.project_span(windows, candidates, checks)
    if live._size(result) > live.MAX_OUTPUT_BYTES:
        raise AcceptanceError(f"{name}: projeção excedeu orçamento da fronteira")
    if result["metricas"]["scheduler_novo"] or result["metricas"]["scan_global"] or result["metricas"]["chamadas_ia"]:
        raise AcceptanceError(f"{name}: fronteira introduziu trabalho proibido")

    calm = name == CALM
    initiative = _initiative(episode["iniciativa"], calm=calm)
    permanence = _map(episode["permanencia"], f"{name}.permanencia")
    if set(permanence) != {"local_id", "slot_id"}:
        raise AcceptanceError("permanencia exige local_id e slot_id")
    local_id = permanence.get("local_id")
    slot_id = permanence.get("slot_id")
    if calm:
        if candidates:
            raise AcceptanceError("dia calmo não pode ter candidata de vivacidade")
        if result.get("primeira_pressao_em") is not None:
            raise AcceptanceError("dia calmo não pode ter pressão primária")
        if result["metricas"]["primarias"] != 0:
            raise AcceptanceError("dia calmo não pode entregar pressão")
        if result["metricas"]["calmas"] != len(windows):
            raise AcceptanceError("cada janela do dia calmo precisa emitir recibo de calma")
        if result["pendentes_apos_alvo"]:
            raise AcceptanceError("dia calmo não pode produzir pendência")
        _text(local_id, "permanencia.local_id", 96)
        _text(slot_id, "permanencia.slot_id", 96)
        graph = _semantic_graph(episode["cadeia_semantica"], require_edges=False)
        return {
            "ok": True,
            "episodio": name,
            "calma_justificada": True,
            "janelas": len(windows),
            "recibos_calma": result["metricas"]["calmas"],
            "eventos_substantivos": 0,
            "iniciativa": initiative,
            "grafo_semantico": graph,
            "bytes": live._size(result),
        }

    _text(local_id, "permanencia.local_id", 96)
    _text(slot_id, "permanencia.slot_id", 96)
    roles = _map(episode["papeis"], f"{name}.papeis")
    if set(roles) != REQUIRED_ROLES:
        raise AcceptanceError(f"{name}: papéis causais obrigatórios divergiram")
    catalog_ids = {row["id"] for row in result["catalogo"]}
    if set(roles.values()) - catalog_ids:
        raise AcceptanceError(f"{name}: papel causal aponta candidata ausente")

    delivered = {
        decision["id"]
        for window in result["avaliacoes"]
        for decision in window["decisoes"]
        if decision["decisao"] == "entregue"
    }
    blocked = {
        decision["id"]
        for window in result["avaliacoes"]
        for decision in window["decisoes"]
        if decision["decisao"] == "bloqueada"
    }
    pending = set(result["pendentes_apos_alvo"])
    destinations = {}
    for candidate_id in sorted(catalog_ids):
        if candidate_id in delivered:
            destinations[candidate_id] = "entregue"
        elif candidate_id in blocked:
            destinations[candidate_id] = "bloqueada"
        elif candidate_id in pending:
            destinations[candidate_id] = "adiada"
        else:
            raise AcceptanceError(f"{name}: candidata desapareceu sem destino: {candidate_id}")
    for role, candidate_id in roles.items():
        if destinations.get(candidate_id) != "entregue":
            raise AcceptanceError(f"{name}: {role} não recebeu destino causal durante o dia")

    graph = _semantic_graph(episode["cadeia_semantica"])
    return {
        "ok": True,
        "episodio": name,
        "calma_justificada": False,
        "janelas": len(windows),
        "destinos": destinations,
        "pendentes_apos_alvo": sorted(pending),
        "iniciativa": initiative,
        "permanencia": {"local_id": local_id, "slot_id": slot_id},
        "grafo_semantico": graph,
        "bytes": live._size(result),
    }


def _class_test_functions(tree: ast.AST) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ClassDef):
            continue
        result[node.name] = {
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    return result


def validate_regression_anchors(repo: Path, regressions: Any) -> list[str]:
    entries = _map(regressions, "regressoes")
    checked: list[str] = []
    for key in sorted(entries):
        raw = _map(entries[key], f"regressoes.{key}")
        if set(raw) != {"arquivo", "classe", "teste"}:
            raise AcceptanceError(f"regressao {key} possui campos divergentes")
        relative = _text(raw["arquivo"], f"{key}.arquivo", 180)
        if not relative.startswith("tests/test_") or not relative.endswith(".py"):
            raise AcceptanceError(f"{key}: âncora precisa ser teste permanente")
        path = (Path(repo) / relative).resolve()
        root = Path(repo).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise AcceptanceError(f"{key}: arquivo de teste ausente: {relative}")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, SyntaxError) as exc:
            raise AcceptanceError(f"{key}: teste não pode ser inspecionado: {exc}") from exc
        classes = _class_test_functions(tree)
        class_name = _text(raw["classe"], f"{key}.classe", 120)
        test_name = _text(raw["teste"], f"{key}.teste", 180)
        if class_name not in classes or test_name not in classes[class_name]:
            raise AcceptanceError(f"{key}: âncora inexistente {class_name}.{test_name}")
        checked.append(f"{relative}::{class_name}.{test_name}")
    return checked


def _command_from_call(payload: dict[str, Any]) -> str:
    raw = payload.get("arguments")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("cmd"), str):
                return parsed["cmd"]
        except json.JSONDecodeError:
            return raw
    raw = payload.get("input")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("cmd"), str):
                return parsed["cmd"]
        except json.JSONDecodeError:
            return raw
    return ""


def analyze_operational_rollout(repo: Path = ROOT) -> dict[str, Any]:
    path = Path(repo) / ROLLOUT
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"rollout operacional inválido: {exc}") from exc
    user_messages: list[str] = []
    calls: list[tuple[int, str]] = []
    outputs: list[tuple[int, str]] = []
    for index, row in enumerate(rows):
        payload = row.get("payload") if isinstance(row, dict) else None
        if not isinstance(payload, dict):
            continue
        if row.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = " ".join(
                str(item.get("text", ""))
                for item in payload.get("content") or []
                if isinstance(item, dict)
            ).strip()
            if text:
                user_messages.append(text)
        if row.get("type") == "response_item" and payload.get("type") in {"function_call", "custom_tool_call"}:
            command = _command_from_call(payload)
            if command:
                calls.append((index, command))
        if row.get("type") == "response_item" and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
            outputs.append((index, str(payload.get("output") or "")))

    intent = next((text for text in user_messages if "história" in text.lower() or "historia" in text.lower()), None)
    if intent is None:
        raise AcceptanceError("rollout não contém intenção narrativa explícita do usuário")

    def first_call(*needles: str) -> tuple[int, str] | None:
        for item in calls:
            lower = item[1].lower()
            if any(needle in lower for needle in needles):
                return item
        return None

    context = first_call("contexto.py status", "contexto status")
    mechanics = first_call("rolar-lote.py", "dados-lote", " rolar ")
    writer = first_call("turno.py registrar", "turno registrar", "cronica concluir")
    if context is None or mechanics is None or writer is None:
        raise AcceptanceError("rollout não contém a cadeia contexto -> mecânica -> writer")
    if not context[0] < mechanics[0] < writer[0]:
        raise AcceptanceError("rollout quebra a ordem semântica contexto -> mecânica -> writer")
    if not any(index > writer[0] and "turno transacional registrado" in text.lower() for index, text in outputs):
        raise AcceptanceError("rollout não comprova sucesso do writer após a decisão mecânica")
    return {
        "ok": True,
        "fonte": ROLLOUT.as_posix(),
        "intencao": intent,
        "cadeia_semantica": [
            {"etapa": "contexto", "comando": context[1]},
            {"etapa": "mecanica", "comando": mechanics[1]},
            {"etapa": "writer", "comando": writer[1]},
        ],
        "avaliacao": "ordem causal e sucesso do writer verificados no JSONL; não é cobertura de flags",
    }


def check(repo: Path = ROOT) -> dict[str, Any]:
    repo = Path(repo).resolve()
    try:
        fixture = load_fixture(repo)
        budget = load_budget(repo)
        loaded = evaluate_episode(LOADED, fixture["episodios"][LOADED])
        calm = evaluate_episode(CALM, fixture["episodios"][CALM])
        anchors = validate_regression_anchors(repo, fixture["regressoes"])
        rollout = analyze_operational_rollout(repo)
    except AcceptanceError as exc:
        return {"schema_aceitacao_vivacidade": SCHEMA, "ok": False, "erros": [str(exc)]}
    except live.LivenessBoundaryError as exc:
        return {"schema_aceitacao_vivacidade": SCHEMA, "ok": False, "erros": [f"fronteira: {exc}"]}
    return {
        "schema_aceitacao_vivacidade": SCHEMA,
        "ok": True,
        "erros": [],
        "episodios": {LOADED: loaded, CALM: calm},
        "regressoes_ancoradas": anchors,
        "rollout_semantico": rollout,
        "orcamento": {
            "max_candidatas": budget["limites"]["max_candidatas"],
            "max_bytes_projecao": budget["limites"]["max_bytes_projecao"],
            "segunda_orquestracao": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aceitação integrada de vivacidade NV-23")
    parser.add_argument("comando", choices=("check",))
    args = parser.parse_args()
    payload = check(ROOT)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
