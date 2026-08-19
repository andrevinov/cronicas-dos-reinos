#!/usr/bin/env python3
"""Gera ou valida a camada runtime derivada dos arquivos canônicos da campanha."""
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc


RUNTIME_VERSION = 2
CONTEXT_PATH = Path("runtime/contexto.yaml")
SCENE_PATH = Path("runtime/cena.yaml")
EVENTS_PATH = Path("runtime/eventos-pendentes.jsonl")

# Registro explícito e pequeno: só itens mágicos cujo estado deve aparecer no
# rodapé mecânico. Não há scan/inferência sobre o inventário.
FOOTER_MAGIC_ITEMS = {
    "broche_do_semblante_humilde": {
        "nome": "Broche do Semblante Humilde",
        "caminho_disponibilidade": "recursos.disponibilidades.broche_do_semblante_humilde",
        "efeito_temporario": "broche_do_semblante_humilde",
    }
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def tail_sentences(text: str | None, count: int, max_chars: int) -> str:
    """Retorna as últimas frases de um texto cronológico, com limite rígido de tamanho."""
    if not text:
        return ""
    normalized = " ".join(str(text).split())
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    selected = " ".join(sentences[-count:]).strip()
    if len(selected) <= max_chars:
        return selected
    clipped = selected[-max_chars:]
    first_space = clipped.find(" ")
    if first_space != -1:
        clipped = clipped[first_space + 1 :]
    return "… " + clipped.strip()


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} não é um mapeamento YAML")
    return value


def footer_magic_items(disponibilidades: dict[str, Any]) -> dict[str, Any]:
    """Projeta só o estado-base necessário ao rodapé, fora de ``recursos``.

    ``caminho_disponibilidade`` continua apontando para a árvore de recursos para
    que deltas pendentes de uso tenham precedência no overlay do próprio turno.
    """
    items = copy.deepcopy(FOOTER_MAGIC_ITEMS)
    for item_id, item in items.items():
        item["disponibilidade"] = copy.deepcopy(disponibilidades.get(item_id))
    return items


def build_runtime_from_documents(
    estado: dict[str, Any],
    tempo_arquivo: dict[str, Any],
    ficha: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Constrói runtime a partir de documentos já carregados.

    A função existe para que a consolidação transacional possa preparar e validar
    **todos** os arquivos novos antes de iniciar qualquer escrita canônica.
    """
    estado = require_mapping(estado, "estado atual")
    tempo_arquivo = require_mapping(tempo_arquivo, "tempo")
    ficha = require_mapping(ficha, "ficha")

    campanha = require_mapping(estado.get("campanha"), "estado.campanha")
    personagem = require_mapping(estado.get("personagem"), "estado.personagem")
    localizacao = require_mapping(estado.get("localizacao"), "estado.localizacao")
    tempo_estado = require_mapping(estado.get("tempo"), "estado.tempo")
    recursos = require_mapping(estado.get("recursos"), "estado.recursos")
    disponibilidades_raw = recursos.get("disponibilidades") or {}
    disponibilidades = require_mapping(disponibilidades_raw, "estado.recursos.disponibilidades")
    efeitos_temporarios_raw = estado.get("efeitos_temporarios")
    if efeitos_temporarios_raw is None:
        efeitos_temporarios: dict[str, Any] = {}
    else:
        efeitos_temporarios = require_mapping(efeitos_temporarios_raw, "estado.efeitos_temporarios")

    pv = require_mapping(recursos.get("pontos_de_vida"), "estado.recursos.pontos_de_vida")
    ki = require_mapping(recursos.get("ki"), "estado.recursos.ki")
    dinheiro = require_mapping(recursos.get("dinheiro"), "estado.recursos.dinheiro")

    sessao = campanha.get("sessao_atual")
    if not isinstance(sessao, int):
        raise ValueError("campanha.sessao_atual precisa ser inteiro")
    transcricao = f"sessoes/{sessao:03d}/transcricao.md"
    handoff = f"sessoes/{sessao:03d}/handoff.yaml"

    data = tempo_estado.get("data_exata") or ((tempo_arquivo.get("data_atual") or {}).get("valor"))
    hora = tempo_estado.get("hora_aproximada") or tempo_arquivo.get("hora_aproximada")
    periodo = tempo_estado.get("periodo_do_dia") or tempo_arquivo.get("periodo_do_dia")
    clima = tempo_estado.get("clima") or tempo_arquivo.get("clima")
    # Texto livre de prazos tinha duas cópias e já produziu divergência real em
    # checkpoint. A autoridade passa a ser estado/tempo.yaml; o campo legado do
    # estado atual é aceito apenas como fallback durante a migração.
    prazo_relevante = tempo_arquivo.get("prazo_relevante") or tempo_estado.get("prazo_relevante")

    contexto = {
        "versao_runtime": RUNTIME_VERSION,
        "natureza": "derivado_descartavel",
        "fontes_canonicas": {
            "estado": "estado/estado-atual.yaml",
            "tempo": "estado/tempo.yaml",
            "ficha": "personagens/jogador/ficha.yaml",
        },
        "sessao": {
            "numero": sessao,
            "status": campanha.get("status"),
            "modo_de_cena": campanha.get("modo_de_cena_atual"),
        },
        "personagem": {
            "nome": personagem.get("nome"),
            "nivel": personagem.get("nivel"),
            "classe": personagem.get("classe"),
            "subclasse": personagem.get("subclasse"),
        },
        "recursos": {
            "pv": {"atuais": pv.get("atuais"), "maximos": pv.get("maximos")},
            "ki": {"atuais": ki.get("atuais"), "maximos": ki.get("maximos")},
            "ca": recursos.get("classe_de_armadura"),
            "deslocamento": recursos.get("deslocamento"),
            "dinheiro_po": dinheiro.get("po"),
        },
        "tempo": {
            "data": data,
            "hora_aproximada": hora,
            "periodo": periodo,
            "clima": clima,
        },
        "localizacao": {
            key: localizacao.get(key)
            for key in ("plano", "mundo", "continente", "regiao", "cidade", "area", "ponto_exato")
        },
        # Estado exclusivo de apresentação fica fora de ``recursos`` para não
        # inflar/invadir o handoff de memória fria.
        "rodape": {"itens_magicos": footer_magic_items(disponibilidades)},
        "ponteiros": {
            "ficha": personagem.get("arquivo_ficha") or "personagens/jogador/ficha.yaml",
            "estado_completo": "estado/estado-atual.yaml",
            "tempo_completo": "estado/tempo.yaml",
            "relacoes": "estado/relacoes.yaml",
            "medidores_npcs": "estado/medidores-npcs.yaml",
            "conhecimento_de_ren": "personagens/jogador/conhecimento.md",
            "retomada": "ferramentas/contexto.py retomada",
            "indice_sessoes": "sessoes/index.yaml",
            "handoff_atual": handoff,
            "transcricao_fria": transcricao,
            "narrador": "narrador/",
            "regras": "regras/",
        },
    }
    if efeitos_temporarios:
        contexto["efeitos_temporarios"] = copy.deepcopy(efeitos_temporarios)

    cena = {
        "versao_runtime": RUNTIME_VERSION,
        "natureza": "derivado_descartavel",
        "sessao": sessao,
        "modo": campanha.get("modo_de_cena_atual"),
        "localizacao": {
            "area": localizacao.get("area"),
            "ponto_exato": localizacao.get("ponto_exato"),
        },
        "tempo": {"data": data, "hora_aproximada": hora},
        "mecanica_imediata": {
            "pv": f"{pv.get('atuais')}/{pv.get('maximos')}",
            "ki": f"{ki.get('atuais')}/{ki.get('maximos')}",
            "ca": recursos.get("classe_de_armadura"),
            "deslocamento": recursos.get("deslocamento"),
        },
        "resumo_imediato": tail_sentences(localizacao.get("descricao_operacional"), 8, 1800),
        "prazos_e_alertas": tail_sentences(prazo_relevante, 7, 1800),
        "consulta_profunda_somente_se_necessaria": {
            "estado": "estado/estado-atual.yaml",
            "handoff": handoff,
            "indice_sessoes": "sessoes/index.yaml",
            "transcricao_fria": transcricao,
            "relacoes": "estado/relacoes.yaml",
            "conhecimento": "personagens/jogador/conhecimento.md",
        },
    }
    if efeitos_temporarios:
        cena["efeitos_temporarios"] = copy.deepcopy(efeitos_temporarios)

    ficha_personagem = require_mapping(ficha.get("personagem"), "ficha.personagem")
    ficha_identidade = require_mapping(ficha.get("identidade"), "ficha.identidade")
    if ficha_personagem.get("nome") != personagem.get("nome"):
        raise ValueError("nome diverge entre estado e ficha")
    if ficha_identidade.get("nivel") != personagem.get("nivel"):
        raise ValueError("nível diverge entre estado e ficha")

    return contexto, cena


def build_runtime(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    estado = require_mapping(load_yaml(repo / "estado/estado-atual.yaml"), "estado atual")
    tempo_arquivo = require_mapping(load_yaml(repo / "estado/tempo.yaml"), "tempo")
    ficha = require_mapping(load_yaml(repo / "personagens/jogador/ficha.yaml"), "ficha")
    return build_runtime_from_documents(estado, tempo_arquivo, ficha)


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)


def check_runtime(repo: Path, expected_context: dict[str, Any], expected_scene: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for rel, expected in ((CONTEXT_PATH, expected_context), (SCENE_PATH, expected_scene)):
        path = repo / rel
        if not path.exists():
            errors.append(f"arquivo de runtime ausente: {rel.as_posix()}")
            continue
        try:
            actual = load_yaml(path)
        except Exception as exc:
            errors.append(f"runtime inválido em {rel.as_posix()}: {exc}")
            continue
        if actual != expected:
            errors.append(f"runtime desatualizado: {rel.as_posix()} (execute ferramentas/gerar-runtime.py)")
    if not (repo / EVENTS_PATH).exists():
        errors.append(f"arquivo de eventos pendentes ausente: {EVENTS_PATH.as_posix()}")
    return errors


def write_runtime(repo: Path, contexto: dict[str, Any], cena: dict[str, Any]) -> None:
    runtime = repo / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (repo / CONTEXT_PATH).write_text(dump_yaml(contexto), encoding="utf-8")
    (repo / SCENE_PATH).write_text(dump_yaml(cena), encoding="utf-8")
    events = repo / EVENTS_PATH
    if not events.exists():
        events.write_text("", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="não escreve; falha se runtime estiver desatualizado")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        contexto, cena = build_runtime(repo)
    except Exception as exc:
        print(f"FALHA AO GERAR RUNTIME — {exc}")
        return 1

    if args.check:
        errors = check_runtime(repo, contexto, cena)
        if errors:
            print("FALHA DE RUNTIME")
            for error in errors:
                print(f"- {error}")
            return 1
        print("OK — runtime corresponde às fontes canônicas.")
        return 0

    write_runtime(repo, contexto, cena)
    print("OK — runtime/contexto.yaml e runtime/cena.yaml regenerados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
