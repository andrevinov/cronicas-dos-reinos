#!/usr/bin/env python3
"""Verificações baratas de integridade estrutural e semântica da campanha."""
from __future__ import annotations

import argparse
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

    campanha = yaml_docs.get("campanha.yaml")
    estado = yaml_docs.get("estado/estado-atual.yaml")
    tempo = yaml_docs.get("estado/tempo.yaml")
    ficha = yaml_docs.get("personagens/jogador/ficha.yaml")

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
