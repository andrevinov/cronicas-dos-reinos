#!/usr/bin/env python3
"""Verificações baratas de integridade estrutural e semântica da campanha.

A baseline de 15/08/2026 é um artefato histórico imutável. Comparar o estado vivo
contra suas assertions continua disponível via `--baseline`, mas é uma operação
explícita para migração/campanha congelada — não uma invariável de jogo depois que
a campanha voltou a avançar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc

try:
    import continuidade_autoral
    import populacao
except ModuleNotFoundError:
    from ferramentas import continuidade_autoral, populacao

try:
    import gate_adnd
except ModuleNotFoundError:
    import importlib.util

    _gate_path = Path(__file__).with_name("gate_adnd.py")
    _gate_spec = importlib.util.spec_from_file_location("gate_adnd", _gate_path)
    if _gate_spec is None or _gate_spec.loader is None:
        raise
    gate_adnd = importlib.util.module_from_spec(_gate_spec)
    _gate_spec.loader.exec_module(gate_adnd)


try:
    import ruleset_5_5e
except ModuleNotFoundError:
    import importlib.util as _ruleset_importlib_util

    _ruleset_path = Path(__file__).with_name("ruleset_5_5e.py")
    _ruleset_spec = _ruleset_importlib_util.spec_from_file_location("ruleset_5_5e", _ruleset_path)
    if _ruleset_spec is None or _ruleset_spec.loader is None:
        raise
    ruleset_5_5e = _ruleset_importlib_util.module_from_spec(_ruleset_spec)
    _ruleset_spec.loader.exec_module(ruleset_5_5e)


class DuplicateKeyLoader(yaml.SafeLoader):
    """SafeLoader que recusa chaves YAML duplicadas silenciosamente."""


def _construct_mapping(loader: DuplicateKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)

AGENT_DOCS = (
    "docs/agente/fundamentos.md",
    "docs/agente/acesso-e-operacoes.md",
    "docs/agente/regras-e-rolagens.md",
    "docs/agente/narracao-e-mundo.md",
    "docs/agente/densidade-narrativa.md",
    "docs/agente/personagem-e-tempo.md",
    "docs/agente/pesquisa-e-manutencao.md",
)
AGENT_COVERAGE = "docs/agente/cobertura-agents-v1.yaml"
AGENTS_MAX_BYTES = 12 * 1024
AGENTS_MAX_LINES = 180
LEGACY_AGENT_SECTION_COUNT = 58
LEGACY_AGENT_SHA = "61ef9a4458d187e24bbe701f78c730e3218f9e42"

RUNTIME_CONTEXT = "runtime/contexto.yaml"
RUNTIME_SCENE = "runtime/cena.yaml"
RUNTIME_EVENTS = "runtime/eventos-pendentes.jsonl"
RUNTIME_MAX_BYTES = 8 * 1024
RUNTIME_VERSION = 2

HISTORICAL_BASELINE = Path("baseline/estado-logico-2026-08-15.yaml")
HISTORICAL_BASELINE_BLOB = "15859e4f2518ae9a4ea74cef1fcdbf242d2d8411"
HISTORICAL_BASELINE_ORIGIN = "815aa6e1ac3ad9ae1d59cc081914eb8d67cb5a58"

REQUIRED_PATHS = (
    "AGENTS.md",
    "README.md",
    "campanha.yaml",
    "estado/estado-atual.yaml",
    "estado/tempo.yaml",
    "estado/relacoes.yaml",
    "estado/medidores-npcs.yaml",
    "personagens/jogador/ficha.yaml",
    "personagens/jogador/conhecimento.md",
    "personagens/jogador/resumo-de-poderes.md",
    "narracao/guia-de-narrativa.md",
    "narracao/protocolo-de-sessao.md",
    "narracao/limites.md",
    "regras/fontes.md",
    "regras/dificuldade.md",
    "regras/progressao.md",
    "regras/regras-da-casa.md",
    "regras/resolucao-de-acoes.md",
    "regras/adaptacoes-mecanicas.yaml",
    "runtime/README.md",
    "narrador/continuidade-autoral.yaml",
    "narrador/populacao-canonica.yaml",
    RUNTIME_CONTEXT,
    RUNTIME_SCENE,
    RUNTIME_EVENTS,
    "ferramentas/gerar-runtime.py",
    "ferramentas/continuidade_autoral.py",
    "ferramentas/populacao.py",
    "ferramentas/texturas.py",
    "ferramentas/gate_adnd.py",
    "cenario/texturas/index.yaml",
    HISTORICAL_BASELINE.as_posix(),
    *AGENT_DOCS,
    AGENT_COVERAGE,
)

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".json", ".jsonl", ".txt"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=DuplicateKeyLoader)


def get_path(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def git_blob_id(data: bytes) -> str:
    """Calcula o object id SHA-1 de um blob Git sem depender do executável git."""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def validate_historical_baseline(repo: Path) -> list[str]:
    """Protege a evidência pré-refatoração sem congelar o estado vivo nela."""
    path = repo / HISTORICAL_BASELINE
    if not path.is_file():
        return [f"baseline histórica ausente: {HISTORICAL_BASELINE.as_posix()}"]
    raw = path.read_bytes()
    actual_blob = git_blob_id(raw)
    errors: list[str] = []
    if actual_blob != HISTORICAL_BASELINE_BLOB:
        errors.append(
            "baseline histórica foi alterada: "
            f"blob atual={actual_blob}, esperado={HISTORICAL_BASELINE_BLOB}"
        )
    try:
        snap = load_yaml(path)
    except Exception as exc:
        return errors + [f"baseline histórica inválida: {exc}"]
    if not isinstance(snap, dict):
        return errors + ["baseline histórica não é mapeamento YAML"]
    if snap.get("schema_version") != 1:
        errors.append(f"schema da baseline histórica inesperado: {snap.get('schema_version')!r}")
    origin = ((snap.get("git") or {}).get("commit_origem"))
    if origin != HISTORICAL_BASELINE_ORIGIN:
        errors.append(
            f"baseline histórica perdeu commit de origem: atual={origin!r}, esperado={HISTORICAL_BASELINE_ORIGIN!r}"
        )
    assertions = snap.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        errors.append("baseline histórica perdeu suas assertions de referência")
    return errors


def validate_agent_router(repo: Path, yaml_docs: dict[str, Any]) -> list[str]:
    """Garante que o roteador continue curto e que o manual legado tenha cobertura."""
    errors: list[str] = []
    agents_path = repo / "AGENTS.md"
    if agents_path.exists():
        raw = agents_path.read_bytes()
        if len(raw) > AGENTS_MAX_BYTES:
            errors.append(
                f"AGENTS.md excede o limite do roteador: {len(raw)} bytes > {AGENTS_MAX_BYTES}"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
        line_count = len(text.splitlines())
        if line_count > AGENTS_MAX_LINES:
            errors.append(
                f"AGENTS.md excede o limite de linhas do roteador: {line_count} > {AGENTS_MAX_LINES}"
            )
        required_markers = (
            "Nunca leia por precaução",
            "Se for suficiente, pare",
            "Economia de contexto não é economia de prosa",
            "runtime/contexto.yaml",
            "runtime/cena.yaml",
            "docs/agente/acesso-e-operacoes.md",
            "docs/agente/densidade-narrativa.md",
            "docs/agente/cobertura-agents-v1.yaml",
        )
        for marker in required_markers:
            if marker not in text:
                errors.append(f"AGENTS.md perdeu marcador operacional obrigatório: {marker!r}")

    coverage = yaml_docs.get(AGENT_COVERAGE)
    if not isinstance(coverage, dict):
        errors.append(f"mapa de cobertura ausente ou inválido: {AGENT_COVERAGE}")
        return errors

    origem = coverage.get("origem") or {}
    if origem.get("sha_blob") != LEGACY_AGENT_SHA:
        errors.append("mapa de cobertura não referencia o SHA do AGENTS legado esperado")
    if origem.get("secoes") != LEGACY_AGENT_SECTION_COUNT:
        errors.append("mapa de cobertura não declara as 58 seções do AGENTS legado")

    documentos = coverage.get("documentos") or {}
    secoes = coverage.get("secoes") or {}
    expected_sections = set(range(1, LEGACY_AGENT_SECTION_COUNT + 1))
    actual_sections = set(secoes.keys()) if isinstance(secoes, dict) else set()
    if actual_sections != expected_sections:
        missing = sorted(expected_sections - actual_sections)
        extra = sorted(actual_sections - expected_sections, key=str)
        errors.append(f"cobertura de AGENTS incompleta: ausentes={missing}, extras={extra}")

    if isinstance(secoes, dict) and isinstance(documentos, dict):
        for numero, chave_doc in secoes.items():
            destino = documentos.get(chave_doc)
            if not isinstance(destino, str):
                errors.append(f"seção {numero} aponta para documento lógico inexistente: {chave_doc!r}")
                continue
            if not (repo / destino).is_file():
                errors.append(f"seção {numero} aponta para arquivo ausente: {destino}")

    return errors


def validate_runtime(
    repo: Path,
    yaml_docs: dict[str, Any],
    estado: Any,
    tempo: Any,
    ficha: Any,
) -> list[str]:
    """Confere que a camada quente é pequena, derivada e coerente com o cânone."""
    errors: list[str] = []

    for rel in (RUNTIME_CONTEXT, RUNTIME_SCENE):
        path = repo / rel
        if path.exists() and path.stat().st_size > RUNTIME_MAX_BYTES:
            errors.append(
                f"runtime excede limite de tamanho em {rel}: {path.stat().st_size} bytes > {RUNTIME_MAX_BYTES}"
            )

    contexto = yaml_docs.get(RUNTIME_CONTEXT)
    cena = yaml_docs.get(RUNTIME_SCENE)
    if not isinstance(contexto, dict) or not isinstance(cena, dict):
        errors.append("runtime/contexto.yaml ou runtime/cena.yaml inválido")
        return errors

    for label, data in (("contexto", contexto), ("cena", cena)):
        if data.get("versao_runtime") != RUNTIME_VERSION:
            errors.append(f"versão de runtime inesperada em {label}: {data.get('versao_runtime')!r}")
        if data.get("natureza") != "derivado_descartavel":
            errors.append(f"runtime {label} perdeu marca de natureza derivada")

    if isinstance(estado, dict):
        state_campaign = estado.get("campanha") or {}
        state_person = estado.get("personagem") or {}
        state_location = estado.get("localizacao") or {}
        state_time = estado.get("tempo") or {}
        state_resources = estado.get("recursos") or {}
        state_pv = state_resources.get("pontos_de_vida") or {}
        state_focus = state_resources.get("focus") or {}
        state_money = state_resources.get("dinheiro") or {}

        checks = [
            ("sessão", (contexto.get("sessao") or {}).get("numero"), state_campaign.get("sessao_atual")),
            ("modo de cena", (contexto.get("sessao") or {}).get("modo_de_cena"), state_campaign.get("modo_de_cena_atual")),
            ("nome", (contexto.get("personagem") or {}).get("nome"), state_person.get("nome")),
            ("nível", (contexto.get("personagem") or {}).get("nivel"), state_person.get("nivel")),
            ("PV atuais", ((contexto.get("recursos") or {}).get("pv") or {}).get("atuais"), state_pv.get("atuais")),
            ("PV máximos", ((contexto.get("recursos") or {}).get("pv") or {}).get("maximos"), state_pv.get("maximos")),
            ("Focus atual", ((contexto.get("recursos") or {}).get("focus") or {}).get("atuais"), state_focus.get("atuais")),
            ("Focus máximo", ((contexto.get("recursos") or {}).get("focus") or {}).get("maximos"), state_focus.get("maximos")),
            ("CA", (contexto.get("recursos") or {}).get("ca"), state_resources.get("classe_de_armadura")),
            ("PO", (contexto.get("recursos") or {}).get("dinheiro_po"), state_money.get("po")),
            ("data", (contexto.get("tempo") or {}).get("data"), state_time.get("data_exata")),
            ("hora", (contexto.get("tempo") or {}).get("hora_aproximada"), state_time.get("hora_aproximada")),
            ("ponto exato", (contexto.get("localizacao") or {}).get("ponto_exato"), state_location.get("ponto_exato")),
            ("cena/sessão", cena.get("sessao"), state_campaign.get("sessao_atual")),
            ("cena/modo", cena.get("modo"), state_campaign.get("modo_de_cena_atual")),
            ("cena/ponto", (cena.get("localizacao") or {}).get("ponto_exato"), state_location.get("ponto_exato")),
        ]
        for label, actual, expected in checks:
            if actual != expected:
                errors.append(f"runtime divergiu do estado ({label}): runtime={actual!r}, estado={expected!r}")

    if isinstance(tempo, dict):
        raw_date = tempo.get("data_atual")
        date_from_time = raw_date if isinstance(raw_date, str) else ((raw_date or {}).get("valor"))
        runtime_date = (contexto.get("tempo") or {}).get("data")
        if date_from_time is not None and runtime_date != date_from_time:
            errors.append(f"runtime divergiu de estado/tempo.yaml na data: {runtime_date!r} != {date_from_time!r}")
        runtime_hour = (contexto.get("tempo") or {}).get("hora_aproximada")
        if tempo.get("hora_aproximada") is not None and runtime_hour != tempo.get("hora_aproximada"):
            errors.append(
                f"runtime divergiu de estado/tempo.yaml na hora: {runtime_hour!r} != {tempo.get('hora_aproximada')!r}"
            )

    if isinstance(ficha, dict):
        runtime_person = contexto.get("personagem") or {}
        if runtime_person.get("nome") != ((ficha.get("personagem") or {}).get("nome")):
            errors.append("runtime divergiu da ficha no nome do personagem")
        if runtime_person.get("nivel") != ((ficha.get("identidade") or {}).get("nivel")):
            errors.append("runtime divergiu da ficha no nível do personagem")

    events_path = repo / RUNTIME_EVENTS
    if events_path.exists():
        for number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"JSONL inválido em {RUNTIME_EVENTS}:{number}: {exc}")
                continue
            if not isinstance(event, dict):
                errors.append(f"evento em {RUNTIME_EVENTS}:{number} não é objeto JSON")

    return errors


def validate(repo: Path, baseline: Path | None = None) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED_PATHS:
        if not (repo / rel).exists():
            errors.append(f"arquivo obrigatório ausente: {rel}")

    errors.extend(validate_historical_baseline(repo))

    yaml_docs: dict[str, Any] = {}
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(repo).as_posix()
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                errors.append(f"UTF-8 inválido em {rel}: {exc}")
        if path.suffix.lower() in {".yaml", ".yml"}:
            try:
                yaml_docs[rel] = load_yaml(path)
            except Exception as exc:
                errors.append(f"YAML inválido em {rel}: {exc}")

    errors.extend(validate_agent_router(repo, yaml_docs))
    errors.extend(gate_adnd.validate_repository(repo, yaml_docs))
    errors.extend(ruleset_5_5e.validate(repo))

    continuity_result = continuidade_autoral.validate_repo(repo)
    errors.extend(
        f"continuidade autoral: {error}" for error in continuity_result["erros"]
    )
    population_result = populacao.validate_repo(repo)
    errors.extend(
        f"população canônica: {error}" for error in population_result["erros"]
    )

    campanha = yaml_docs.get("campanha.yaml")
    estado = yaml_docs.get("estado/estado-atual.yaml")
    tempo = yaml_docs.get("estado/tempo.yaml")
    ficha = yaml_docs.get("personagens/jogador/ficha.yaml")

    errors.extend(validate_runtime(repo, yaml_docs, estado, tempo, ficha))

    if isinstance(campanha, dict):
        refs = (((campanha.get("estrutura") or {}).get("arquivos_referenciados")) or {})
        if isinstance(refs, dict):
            for nome, rel in refs.items():
                if isinstance(rel, str) and not rel.startswith("books/") and not (repo / rel).exists():
                    errors.append(f"referência quebrada em campanha.yaml ({nome}): {rel}")

    if isinstance(estado, dict):
        sessao = ((estado.get("campanha") or {}).get("sessao_atual"))
        if isinstance(sessao, int):
            sessao_dir = repo / "sessoes" / f"{sessao:03d}"
            if not sessao_dir.is_dir():
                errors.append(f"pasta da sessão atual ausente: sessoes/{sessao:03d}")
            elif not (sessao_dir / "transcricao.md").exists():
                errors.append(f"transcrição da sessão atual ausente: sessoes/{sessao:03d}/transcricao.md")
        else:
            errors.append("estado/estado-atual.yaml não define campanha.sessao_atual como inteiro")

    if isinstance(estado, dict) and isinstance(ficha, dict):
        state_p = estado.get("personagem") or {}
        pairs = [
            ("nome", state_p.get("nome"), (ficha.get("personagem") or {}).get("nome")),
            ("nível", state_p.get("nivel"), (ficha.get("identidade") or {}).get("nivel")),
            ("classe", state_p.get("classe"), (ficha.get("identidade") or {}).get("classe")),
            ("subclasse", state_p.get("subclasse"), (ficha.get("identidade") or {}).get("subclasse")),
        ]
        for label, a, b in pairs:
            if a != b:
                errors.append(f"divergência de personagem ({label}): estado={a!r}, ficha={b!r}")

        combat = ficha.get("combate") or {}
        hp = combat.get("pontos_de_vida") or {}
        current_hp, max_hp = hp.get("atuais"), hp.get("maximos")
        if isinstance(current_hp, int) and isinstance(max_hp, int):
            if not 0 <= current_hp <= max_hp:
                errors.append(f"PV inválidos: {current_hp}/{max_hp}")
        else:
            errors.append("PV atuais/máximos não são inteiros na ficha")

        focus = ((ficha.get("recursos_de_classe") or {}).get("focus")) or {}
        current_focus, max_focus = focus.get("pontos_atuais"), focus.get("pontos_maximos")
        if isinstance(current_focus, int) and isinstance(max_focus, int):
            if not 0 <= current_focus <= max_focus:
                errors.append(f"Focus inválido: {current_focus}/{max_focus}")
        else:
            errors.append("Focus atual/máximo não é inteiro na ficha")

    if isinstance(campanha, dict) and isinstance(tempo, dict):
        periodo = (((campanha.get("cenario") or {}).get("periodo_historico")) or {}).get("valor")
        ano = tempo.get("ano_dr")
        if isinstance(ano, int) and isinstance(periodo, str) and str(ano) not in periodo:
            errors.append(f"ano do estado temporal ({ano}) diverge do período da campanha ({periodo!r})")

    if baseline is not None:
        try:
            snap = load_yaml(baseline)
        except Exception as exc:
            errors.append(f"baseline inválida: {exc}")
            snap = None
        if isinstance(snap, dict):
            sources = {
                "campanha.yaml": campanha,
                "estado/estado-atual.yaml": estado,
                "estado/tempo.yaml": tempo,
                "personagens/jogador/ficha.yaml": ficha,
            }
            for assertion in snap.get("assertions", []):
                if not isinstance(assertion, dict):
                    continue
                source = assertion.get("source")
                dotted = assertion.get("path")
                expected = assertion.get("expected")
                data = sources.get(source)
                if data is None:
                    errors.append(f"baseline aponta para fonte indisponível: {source}")
                    continue
                try:
                    actual = get_path(data, dotted)
                except KeyError:
                    errors.append(f"baseline não encontra {source}:{dotted}")
                    continue
                if actual != expected:
                    errors.append(
                        f"baseline divergiu em {source}:{dotted}: atual={actual!r}, esperado={expected!r}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "compara o estado atual ao snapshot lógico informado; usar apenas em migração "
            "deliberada/campanha congelada, não como gate permanente do jogo vivo"
        ),
    )
    parser.add_argument(
        "--verificar-baseline-historica",
        action="store_true",
        help="valida somente que a baseline pré-refatoração permanece byte a byte intacta",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()

    if args.verificar_baseline_historica:
        errors = validate_historical_baseline(repo)
        if errors:
            print("FALHA NA BASELINE HISTÓRICA")
            for error in errors:
                print(f"- {error}")
            return 1
        print(
            "OK — baseline histórica pré-refatoração permanece intacta: "
            f"{HISTORICAL_BASELINE_BLOB}"
        )
        return 0

    baseline = args.baseline.resolve() if args.baseline else None
    errors = validate(repo, baseline)
    if errors:
        print("FALHA DE INTEGRIDADE")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK — integridade estrutural e semântica verificada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
