#!/usr/bin/env python3
"""Separa estado operacional atual de histórico acumulado sem perder o legado."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

LEGACY_STATE_BLOB = "740d15cc420385a44f86acbd7ca7b20ea4d3b8de"
LEGACY_TIME_BLOB = "cdad0c0233a9d4e90b96dd606831a59755f3f500"

STATE_PATH = Path("estado/estado-atual.yaml")
TIME_PATH = Path("estado/tempo.yaml")
ARCHIVE_STATE = Path("historico/legado/estado-acumulado-pre-etapa-5.yaml")
ARCHIVE_TIME = Path("historico/legado/tempo-acumulado-pre-etapa-5.yaml")
MANIFEST = Path("historico/legado/migracao-estado-v1.yaml")
RUNTIME_CONTEXT = Path("runtime/contexto.yaml")
RUNTIME_SCENE = Path("runtime/cena.yaml")

MAX_CURRENT_STATE_BYTES = 20 * 1024
MAX_CURRENT_TIME_BYTES = 8 * 1024


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)


def git_blob(path: Path, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "hash-object", path.as_posix()],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def tail_items(value: Any, limit: int = 12) -> list[Any]:
    if not isinstance(value, list):
        return []
    return deepcopy(value[-limit:])


def build_current_state(
    old_state: dict[str, Any],
    old_time: dict[str, Any],
    runtime_context: dict[str, Any],
    runtime_scene: dict[str, Any],
) -> dict[str, Any]:
    campanha = as_mapping(old_state.get("campanha"))
    personagem = as_mapping(old_state.get("personagem"))
    localizacao = as_mapping(old_state.get("localizacao"))
    tempo = as_mapping(old_state.get("tempo"))
    recursos = as_mapping(old_state.get("recursos"))

    current_location = {
        key: deepcopy(localizacao.get(key))
        for key in ("plano", "mundo", "continente", "regiao", "cidade", "area", "ponto_exato")
        if key in localizacao
    }
    current_location["descricao_operacional"] = runtime_scene.get("resumo_imediato") or ""

    current_time = {
        key: deepcopy(tempo.get(key))
        for key in (
            "ano_dr",
            "nome_do_ano",
            "data_exata",
            "calendario",
            "mes",
            "nome_sazonal_do_mes",
            "dia_do_mes",
            "dezena",
            "dia_da_dezena",
            "periodo_do_dia",
            "hora_aproximada",
            "clima",
        )
        if key in tempo
    }
    current_time["observacao"] = (
        "Estado temporal corrente. Cronologia detalhada e marcos anteriores foram movidos para "
        f"{ARCHIVE_TIME.as_posix()}."
    )
    current_time["prazo_relevante"] = runtime_scene.get("prazos_e_alertas") or ""

    current_resources = {
        key: deepcopy(recursos.get(key))
        for key in (
            "pontos_de_vida",
            "dados_de_vida",
            "ki",
            "classe_de_armadura",
            "deslocamento",
            "dinheiro",
        )
        if key in recursos
    }
    # A lista antiga era um diário cumulativo. Só preservamos o final operacional.
    current_resources["condicoes"] = tail_items(recursos.get("condicoes"), 12)

    result: dict[str, Any] = {
        "schema_estado": 1,
        "natureza": "estado_atual",
        "historico_acumulado": ARCHIVE_STATE.as_posix(),
        "campanha": deepcopy(campanha),
        "personagem": deepcopy(personagem),
        "localizacao": current_location,
        "tempo": current_time,
        "recursos": current_resources,
        "ponteiros": {
            "tempo_atual": TIME_PATH.as_posix(),
            "relacoes": "estado/relacoes.yaml",
            "medidores_npcs": "estado/medidores-npcs.yaml",
            "ficha": personagem.get("arquivo_ficha") or "personagens/jogador/ficha.yaml",
            "conhecimento": "personagens/jogador/conhecimento.md",
            "transcricao_atual": (runtime_context.get("ponteiros") or {}).get("transcricao_atual"),
        },
    }

    # Se existirem blocos compactos não reconhecidos, não os perdemos silenciosamente.
    known = {"campanha", "personagem", "localizacao", "tempo", "recursos"}
    extras = {key: deepcopy(value) for key, value in old_state.items() if key not in known}
    compact_extras: dict[str, Any] = {}
    for key, value in extras.items():
        rendered = dump_yaml(value).encode("utf-8")
        if len(rendered) <= 4096:
            compact_extras[key] = value
    if compact_extras:
        result["outros_estados_compactos"] = compact_extras

    return result


def build_current_time(
    old_state: dict[str, Any],
    old_time: dict[str, Any],
    runtime_context: dict[str, Any],
    runtime_scene: dict[str, Any],
) -> dict[str, Any]:
    state_time = as_mapping(old_state.get("tempo"))
    old_date = as_mapping(old_time.get("data_atual"))
    runtime_time = as_mapping(runtime_context.get("tempo"))

    date_current = {
        key: deepcopy(old_date.get(key))
        for key in (
            "status",
            "calendario",
            "valor",
            "mes",
            "nome_sazonal_do_mes",
            "dia_do_mes",
            "dezena",
            "dia_da_dezena",
            "feriado",
            "estacao",
        )
        if key in old_date
    }
    date_current["observacao"] = "Somente a data corrente; histórico temporal está arquivado."

    return {
        "schema_tempo": 1,
        "natureza": "tempo_atual",
        "historico_acumulado": ARCHIVE_TIME.as_posix(),
        "ano_dr": old_time.get("ano_dr") or state_time.get("ano_dr"),
        "nome_do_ano": old_time.get("nome_do_ano") or state_time.get("nome_do_ano"),
        "data_atual": date_current,
        "periodo_do_dia": runtime_time.get("periodo") or old_time.get("periodo_do_dia"),
        "hora_aproximada": runtime_time.get("hora_aproximada") or old_time.get("hora_aproximada"),
        "local_referencia": old_time.get("local_referencia") or (runtime_context.get("localizacao") or {}).get("cidade"),
        "clima": runtime_time.get("clima") or state_time.get("clima"),
        "prazo_relevante": runtime_scene.get("prazos_e_alertas") or "",
    }


def archive_and_write(repo: Path) -> None:
    state_path = repo / STATE_PATH
    time_path = repo / TIME_PATH
    archive_state = repo / ARCHIVE_STATE
    archive_time = repo / ARCHIVE_TIME
    manifest_path = repo / MANIFEST

    if manifest_path.exists():
        print("OK — migração da Etapa 5 já aplicada.")
        return

    old_state = as_mapping(load_yaml(state_path))
    old_time = as_mapping(load_yaml(time_path))
    runtime_context = as_mapping(load_yaml(repo / RUNTIME_CONTEXT))
    runtime_scene = as_mapping(load_yaml(repo / RUNTIME_SCENE))

    state_blob = git_blob(STATE_PATH, repo)
    time_blob = git_blob(TIME_PATH, repo)
    if state_blob != LEGACY_STATE_BLOB:
        raise RuntimeError(f"blob legado inesperado para estado: {state_blob}")
    if time_blob != LEGACY_TIME_BLOB:
        raise RuntimeError(f"blob legado inesperado para tempo: {time_blob}")

    archive_state.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(state_path, archive_state)
    shutil.move(time_path, archive_time)

    current_state = build_current_state(old_state, old_time, runtime_context, runtime_scene)
    current_time = build_current_time(old_state, old_time, runtime_context, runtime_scene)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(dump_yaml(current_state), encoding="utf-8")
    time_path.write_text(dump_yaml(current_time), encoding="utf-8")

    manifest = {
        "versao": 1,
        "etapa": 5,
        "descricao": "Separação entre estado corrente e histórico acumulado.",
        "arquivos_legados": {
            STATE_PATH.as_posix(): {
                "blob_original": state_blob,
                "arquivado_em": ARCHIVE_STATE.as_posix(),
            },
            TIME_PATH.as_posix(): {
                "blob_original": time_blob,
                "arquivado_em": ARCHIVE_TIME.as_posix(),
            },
        },
        "arquivos_correntes": [STATE_PATH.as_posix(), TIME_PATH.as_posix()],
        "regra": "Arquivos em historico/ são frios e não participam da leitura operacional padrão.",
    }
    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")
    print("OK — estado corrente separado do histórico acumulado.")


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    archive_state = repo / ARCHIVE_STATE
    archive_time = repo / ARCHIVE_TIME
    state_path = repo / STATE_PATH
    time_path = repo / TIME_PATH
    manifest_path = repo / MANIFEST

    for path in (archive_state, archive_time, state_path, time_path, manifest_path):
        if not path.is_file():
            errors.append(f"arquivo obrigatório da Etapa 5 ausente: {path.relative_to(repo)}")

    if errors:
        return errors

    if git_blob(ARCHIVE_STATE, repo) != LEGACY_STATE_BLOB:
        errors.append("arquivo histórico de estado não preserva exatamente o blob legado")
    if git_blob(ARCHIVE_TIME, repo) != LEGACY_TIME_BLOB:
        errors.append("arquivo histórico de tempo não preserva exatamente o blob legado")

    state = as_mapping(load_yaml(state_path))
    tempo = as_mapping(load_yaml(time_path))
    if state.get("natureza") != "estado_atual":
        errors.append("estado/estado-atual.yaml não está marcado como estado atual")
    if tempo.get("natureza") != "tempo_atual":
        errors.append("estado/tempo.yaml não está marcado como tempo atual")
    if state.get("historico_acumulado") != ARCHIVE_STATE.as_posix():
        errors.append("estado atual perdeu ponteiro para histórico acumulado")
    if tempo.get("historico_acumulado") != ARCHIVE_TIME.as_posix():
        errors.append("tempo atual perdeu ponteiro para histórico acumulado")

    if state_path.stat().st_size > MAX_CURRENT_STATE_BYTES:
        errors.append(
            f"estado atual voltou a crescer: {state_path.stat().st_size} > {MAX_CURRENT_STATE_BYTES} bytes"
        )
    if time_path.stat().st_size > MAX_CURRENT_TIME_BYTES:
        errors.append(
            f"tempo atual voltou a crescer: {time_path.stat().st_size} > {MAX_CURRENT_TIME_BYTES} bytes"
        )

    description = str((state.get("localizacao") or {}).get("descricao_operacional") or "")
    conditions = (state.get("recursos") or {}).get("condicoes") or []
    if len(description) > 2500:
        errors.append("descricao_operacional voltou a acumular histórico")
    if isinstance(conditions, list) and len(conditions) > 16:
        errors.append("recursos.condicoes voltou a funcionar como diário cumulativo")

    if "marcos_de_tempo" in tempo or "referencias_calendario" in tempo:
        errors.append("estado/tempo.yaml voltou a incorporar cronologia histórica")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()

    if args.check:
        errors = validate(repo)
        if errors:
            print("FALHA NA SEPARAÇÃO ESTADO/HISTÓRICO")
            for error in errors:
                print(f"- {error}")
            return 1
        print("OK — estado corrente está separado do histórico e o legado está preservado.")
        return 0

    try:
        archive_and_write(repo)
    except Exception as exc:
        print(f"FALHA NA MIGRAÇÃO — {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
