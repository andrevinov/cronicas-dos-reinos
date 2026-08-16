#!/usr/bin/env python3
"""Verificações baratas de integridade estrutural e semântica da campanha."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc


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
    "runtime/README.md",
    RUNTIME_CONTEXT,
    RUNTIME_SCENE,
    RUNTIME_EVENTS,
    "ferramentas/gerar-runtime.py",
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
            "runtime/contexto.yaml",
            "runtime/cena.yaml",
            "docs/agente/acesso-e-operacoes.md",
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
        state_ki = state_resources.get("ki") or {}
        state_money = state_resources.get("dinheiro") or {}

        checks = [
            ("sessão", (contexto.get("sessao") or {}).get("numero"), state_campaign.get("sessao_atual")),
            ("modo de cena", (contexto.get("sessao") or {}).get("modo_de_cena"), state_campaign.get("modo_de_cena_atual")),
            ("nome", (contexto.get("personagem") or {}).get("nome"), state_person.get("nome")),
            ("nível", (contexto.get("personagem") or {}).get("nivel"), state_person.get("nivel")),
            ("PV atuais", ((contexto.get("recursos") or {}).get("pv") or {}).get("atuais"), state_pv.get("atuais")),
            ("PV máximos", ((contexto.get("recursos") or {}).get("pv") or {}).get("maximos"), state_pv.get("maximos")),
            ("Ki atual", ((contexto.get("recursos") or {}).get("ki") or {}).get("atuais"), state_ki.get("atuais")),
            ("Ki máximo", ((contexto.get("recursos") or {}).get("ki") or {}).get("maximos"), state_ki.get("maximos")),
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

    # O arquivo separado de tempo ainda deve concordar com a projeção quente.
    if isinstance(tempo, dict):
        date_from_time = ((tempo.get("data_atual") or {}).get("valor"))
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

    # Cada linha não vazia do log precisa ser JSON válido e um objeto.
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

        ki = ((ficha.get("recursos_de_classe") or {}).get("ki")) or {}
        current_ki, max_ki = ki.get("pontos_atuais"), ki.get("pontos_maximos")
        if isinstance(current_ki, int) and isinstance(max_ki, int):
            if not 0 <= current_ki <= max_ki:
                errors.append(f"Ki inválido: {current_ki}/{max_ki}")
        else:
            errors.append("Ki atual/máximo não é inteiro na ficha")

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
    parser.add_argument("--baseline", type=Path, default=None, help="snapshot lógico a comparar")
    args = parser.parse_args()
    repo = args.repo.resolve()
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
