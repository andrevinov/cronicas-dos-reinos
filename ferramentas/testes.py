#!/usr/bin/env python3
"""Perfis simples de execução da suíte de testes.

Este runner não substitui o gate final. Ele só oferece atalhos de feedback local:

- ``fast``: subconjunto curto, determinístico e curado;
- ``domain``: arquivos ligados a um ou mais domínios;
- ``full``: exatamente o discovery integral usado pela CI.

A suíte completa continua sendo a autoridade antes de merge.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import unicodedata
import unittest
from pathlib import Path
from typing import Iterable, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

# Lista explícita, em vez de heurística por tempo: um teste só entra no perfil
# rápido depois de ser reconhecido como pequeno/determinístico. Isso evita que
# uma mudança futura de implementação faça um arquivo caro entrar silenciosamente.
FAST_FILES: tuple[str, ...] = (
    "test_adversarios.py",
    "test_ameacas.py",
    "test_analisar_rollout.py",
    "test_analisar_rollout_sistemas.py",
    "test_auditar_testes.py",
    "test_benchmark_rollouts.py",
    "test_ci_full_suite_ownership.py",
    "test_comparar_rollouts.py",
    "test_entrada.py",
    "test_mecanica_dnd_5_5e.py",
    "test_metodos_agentes.py",
    "test_politica_acesso.py",
    "test_poetry_setup.py",
    "test_preflight.py",
    "test_qualidade_abordagem.py",
    "test_rolar_lote.py",
    "test_rules_catalog.py",
    "test_tags_contextuais_tipadas.py",
    "test_transacoes.py",
    "test_test_execution_profiles.py",
    "test_test_policy_contract.py",
)

# Os domínios são deliberadamente sobrepostos: uma regressão pode pertencer a
# mais de uma área. Ao pedir vários domínios, os arquivos são deduplicados.
DOMAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "mecanica": (
        "test_adversarios.py",
        "test_ameacas.py",
        "test_mecanica_*.py",
        "test_ficha_ren.py",
        "test_cronica_mecanica.py",
        "test_gate_adnd.py",
        "test_rules*.py",
        "test_talentos_ren.py",
        "test_qualidade_abordagem.py",
        "test_migracao_ren_5_5e.py",
    ),
    "cronica": (
        "test_cronica*.py",
        "test_turno*.py",
        "test_entrada.py",
        "test_tempo_atomico.py",
        "test_diegetico.py",
    ),
    "sessoes": (
        "test_ciclo_sessoes.py",
        "test_memoria_sessoes.py",
        "test_checkpoint.py",
        "test_checkpoints_mundo.py",
        "test_unified_session_lifecycle.py",
        "test_auditoria_final.py",
    ),
    "sidequests": (
        "test_*sidequest*.py",
        "test_oportunidades.py",
        "test_quest_rewards_discoveries_losses.py",
        "test_canon_bridge*.py",
        "test_adversarial_integrity.py",
        "test_rede_protegida.py",
        "test_torneio_clandestino.py",
    ),
    "mundo": (
        "test_adversarios.py",
        "test_ameacas.py",
        "test_mundo*.py",
        "test_agentes*.py",
        "test_direcoes*.py",
        "test_eventos_mundo.py",
        "test_interacoes_mundo.py",
        "test_relogios.py",
        "test_pressao*.py",
        "test_microeventos*.py",
        "test_incidentes_mundo.py",
        "test_condicoes_mundo*.py",
        "test_continuidade_autoral.py",
        "test_presenca_incidental.py",
        "test_ecologia_local.py",
        "test_fase11_population.py",
        "test_marcos_aparicao.py",
        "test_entradas.py",
        "test_populacao_canonica.py",
        "test_rastros*.py",
        "test_recompensas.py",
        "test_aliados_contextuais.py",
        "test_contexto_cena*.py",
        "test_cena_mundo*.py",
        "test_arco_mundo.py",
        "test_arcos.py",
        "test_neutralizacao_ren.py",
        "test_npc_stubs.py",
        "test_iniciativa_social.py",
        "test_dialogo_relacional.py",
        "test_reputacao_publica.py",
        "test_estado_relacional.py",
        "test_progressao_juppongatana.py",
        "test_identidades*.py",
        "test_ciclo_npcs.py",
        "test_locais.py",
    ),
    "runtime": (
        "test_runtime.py",
        "test_contexto*.py",
        "test_memorias_fragmentadas.py",
        "test_estado_historico.py",
        "test_telemetria*.py",
        "test_auditar_testes.py",
        "test_congelamentos_estado_vivo.py",
        "test_historical_test_review.py",
        "test_preflight.py",
        "test_ci_full_suite_ownership.py",
        "test_poetry_setup.py",
        "test_auditoria_final.py",
    ),
}

DOMAIN_ALIASES = {
    "mecanica": "mecanica",
    "cronica": "cronica",
    "sessao": "sessoes",
    "sessoes": "sessoes",
    "sidequest": "sidequests",
    "sidequests": "sidequests",
    "mundo": "mundo",
    "runtime": "runtime",
}


class ProfileError(RuntimeError):
    """Perfil inválido ou desatualizado."""


def _ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_value.lower().strip().replace("-", "_").replace(" ", "_")


def normalize_domain(value: str) -> str:
    slug = _ascii_slug(value)
    try:
        return DOMAIN_ALIASES[slug]
    except KeyError as exc:
        available = ", ".join(DOMAIN_PATTERNS)
        raise ProfileError(f"domínio desconhecido: {value!r}. Opções: {available}") from exc


def _existing_test_file(repo: Path, name: str) -> Path:
    path = repo / "tests" / name
    if not path.is_file():
        raise ProfileError(f"perfil aponta para teste ausente: tests/{name}")
    return path


def fast_files(repo: Path = ROOT) -> list[Path]:
    return [_existing_test_file(repo, name) for name in FAST_FILES]


def domain_files(domains: Sequence[str], repo: Path = ROOT) -> list[Path]:
    tests_dir = repo / "tests"
    selected: set[Path] = set()
    normalized = [normalize_domain(domain) for domain in domains]
    for domain in normalized:
        for pattern in DOMAIN_PATTERNS[domain]:
            selected.update(path for path in tests_dir.glob(pattern) if path.is_file())
    if not selected:
        raise ProfileError(f"nenhum teste encontrado para: {', '.join(normalized)}")
    return sorted(selected)


def full_files(repo: Path = ROOT) -> list[Path]:
    """Arquivos descobertos pelo padrão padrão do unittest (`test*.py`)."""
    return sorted(path for path in (repo / "tests").glob("test*.py") if path.is_file())


def _iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def load_selected_suite(paths: Sequence[Path], repo: Path = ROOT) -> unittest.TestSuite:
    """Carrega arquivos selecionados e remove duplicações por test id."""
    root = str(repo)
    if root not in sys.path:
        sys.path.insert(0, root)

    tests_dir = repo / "tests"
    loader = unittest.TestLoader()
    unique: dict[str, unittest.TestCase] = {}
    for path in paths:
        discovered = loader.discover(str(tests_dir), pattern=path.name)
        for test in _iter_tests(discovered):
            unique.setdefault(test.id(), test)

    return unittest.TestSuite(unique[test_id] for test_id in sorted(unique))


def run_selected(paths: Sequence[Path], repo: Path = ROOT) -> int:
    suite = load_selected_suite(paths, repo)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def full_command() -> tuple[str, ...]:
    """Comando canônico da suíte integral; deve permanecer igual ao gate da CI."""
    return (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")


def run_full(repo: Path = ROOT) -> int:
    return subprocess.run(full_command(), cwd=repo, check=False).returncode


def _print_files(paths: Iterable[Path], repo: Path) -> None:
    for path in paths:
        print(path.relative_to(repo).as_posix())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="profile", required=True)

    fast = subparsers.add_parser("fast", help="feedback rápido e determinístico")
    fast.add_argument("--list", action="store_true", help="lista arquivos sem executar")

    domain = subparsers.add_parser("domain", help="executa um ou mais domínios relacionados")
    domain.add_argument("domains", nargs="+", help="mecânica, crônica, sessões, sidequests, mundo, runtime")
    domain.add_argument("--list", action="store_true", help="lista arquivos sem executar")

    full = subparsers.add_parser("full", help="executa absolutamente toda a suíte")
    full.add_argument("--list", action="store_true", help="lista arquivos descobertos sem executar")
    return parser


def main(argv: Sequence[str] | None = None, *, repo: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.profile == "fast":
            paths = fast_files(repo)
            if args.list:
                _print_files(paths, repo)
                return 0
            return run_selected(paths, repo)

        if args.profile == "domain":
            paths = domain_files(args.domains, repo)
            if args.list:
                _print_files(paths, repo)
                return 0
            return run_selected(paths, repo)

        if args.list:
            _print_files(full_files(repo), repo)
            return 0
        return run_full(repo)
    except ProfileError as exc:
        print(f"ERRO — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
