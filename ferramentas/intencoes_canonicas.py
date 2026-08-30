#!/usr/bin/env python3
"""Task 39 — contrato de intenção canônica e reescrita.

Esta camada é fria e somente descreve o que cada batida futura precisa cumprir.
Ela NÃO reescreve o cânone, não cria side quests, não agenda nada e não possui
estado próprio. Sem rewrite futuro autorizado, o evento da Task 36 continua sendo
a realização padrão e segue pelo pipeline existente, sem custo adicional no hot path.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

import eventos_canonicos
import mundo

INDEX = Path("narrador/arcos/parte_1/intencoes-canonicas.yaml")
INTENTS_DIR = Path("narrador/arcos/parte_1/intencoes")
SCHEMA = 1
INTENT_SCHEMA = 1
ARC = eventos_canonicos.ARC
ALLOWED_REWRITE_MODES = {"satisfazer", "transformar", "adiar", "reancorar"}
INTENT_ID_RE = re.compile(r"^icp1-[a-z0-9_]{1,96}$")
EVENT_ID_RE = re.compile(r"^[a-z0-9_]{1,96}$")
MAX_CRITERIA = 4
MAX_GLOBAL_DELAY_HOURS = 7 * 24


class CanonicalIntentError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise CanonicalIntentError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalIntentError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CanonicalIntentError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanonicalIntentError(f"{label} deve ser texto não vazio")
    return value.strip()


def _integer(value: Any, label: str, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CanonicalIntentError(f"{label} deve ser inteiro >= {minimum}")
    if maximum is not None and value > maximum:
        raise CanonicalIntentError(f"{label} deve ser inteiro <= {maximum}")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise CanonicalIntentError(f"{label} deve ser booleano")
    return value


def _event_id(value: Any, label: str = "evento_id") -> str:
    value = _text(value, label)
    if not EVENT_ID_RE.fullmatch(value):
        raise CanonicalIntentError(f"{label} inválido: {value!r}")
    return value


def _intent_path(event_id: str) -> Path:
    return INTENTS_DIR / f"{_event_id(event_id)}.yaml"


def _parse_instant(value: Any, label: str) -> mundo.WorldInstant:
    value = _map(value, label)
    if set(value) != {"data", "hora"}:
        raise CanonicalIntentError(f"{label} deve conter exatamente data e hora")
    try:
        return mundo.parse_instant(
            _text(value["data"], label + ".data"),
            _text(value["hora"], label + ".hora"),
        )
    except mundo.WorldEngineError as exc:
        raise CanonicalIntentError(str(exc)) from exc


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), str(INDEX))
    expected_keys = {
        "schema_intencoes_canonicas_parte_1",
        "natureza",
        "arco",
        "fonte_eventos",
        "fronteira_de_instalacao",
        "passado_congelado",
        "raiz_intencoes",
        "modos_rewrite_permitidos",
        "regra_sem_rewrite",
        "cancelamento_silencioso",
        "atraso_maximo_global_horas",
    }
    if set(data) != expected_keys:
        missing = sorted(expected_keys - set(data))
        extra = sorted(set(data) - expected_keys)
        raise CanonicalIntentError(
            "índice Task39 divergente"
            + (f"; faltando: {', '.join(missing)}" if missing else "")
            + (f"; extras: {', '.join(extra)}" if extra else "")
        )
    if data["schema_intencoes_canonicas_parte_1"] != SCHEMA:
        raise CanonicalIntentError("schema Task39 inválido")
    if data["natureza"] != "reservado" or data["arco"] != ARC:
        raise CanonicalIntentError("autoridade Task39 inválida")
    if data["fonte_eventos"] != eventos_canonicos.CATALOG.as_posix():
        raise CanonicalIntentError("fonte_eventos deve apontar para o catálogo da Task36")
    if data["raiz_intencoes"] != INTENTS_DIR.as_posix():
        raise CanonicalIntentError("raiz_intencoes divergente")
    _parse_instant(data["fronteira_de_instalacao"], "fronteira_de_instalacao")

    frozen = _map(data["passado_congelado"], "passado_congelado")
    for event_id, digest in frozen.items():
        _event_id(event_id, "passado_congelado.evento")
        digest = _text(digest, f"passado_congelado.{event_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CanonicalIntentError(f"digest inválido para {event_id}")

    modes = _list(data["modos_rewrite_permitidos"], "modos_rewrite_permitidos")
    if len(modes) != len(set(modes)) or set(modes) != ALLOWED_REWRITE_MODES:
        raise CanonicalIntentError("modos_rewrite_permitidos deve declarar exatamente os quatro modos Task39")
    if data["regra_sem_rewrite"] != "realizacao_padrao":
        raise CanonicalIntentError("sem rewrite, a realização padrão deve permanecer autoritativa")
    if data["cancelamento_silencioso"] != "proibido":
        raise CanonicalIntentError("cancelamento silencioso de intenção é proibido")
    max_delay = _integer(
        data["atraso_maximo_global_horas"],
        "atraso_maximo_global_horas",
        1,
        MAX_GLOBAL_DELAY_HOURS,
    )
    data["_fronteira"] = _parse_instant(
        data["fronteira_de_instalacao"], "fronteira_de_instalacao"
    )
    data["_max_delay"] = max_delay
    return data


def _validate_intent(raw: Any, event_id: str) -> dict[str, Any]:
    data = _map(raw, f"{event_id}.intencao_canonica")
    if set(data) != {"id", "funcao", "criterios_satisfacao"}:
        raise CanonicalIntentError(
            f"{event_id}.intencao_canonica exige somente id, funcao e criterios_satisfacao"
        )
    intent_id = _text(data["id"], f"{event_id}.intencao_canonica.id")
    if not INTENT_ID_RE.fullmatch(intent_id):
        raise CanonicalIntentError(f"{event_id}: id de intenção inválido")
    function = _text(data["funcao"], f"{event_id}.intencao_canonica.funcao")
    criteria = _list(data["criterios_satisfacao"], f"{event_id}.criterios_satisfacao")
    if not 1 <= len(criteria) <= MAX_CRITERIA:
        raise CanonicalIntentError(
            f"{event_id}: critérios de satisfação devem ter entre 1 e {MAX_CRITERIA} itens"
        )
    normalized = [
        _text(item, f"{event_id}.criterios_satisfacao[{pos}]")
        for pos, item in enumerate(criteria)
    ]
    return {"id": intent_id, "funcao": function, "criterios_satisfacao": normalized}


def _validate_default_realization(raw: Any, event_id: str) -> dict[str, Any]:
    data = _map(raw, f"{event_id}.realizacao_padrao")
    expected = {
        "fonte": "evento_canonico_task36",
        "nucleo": "nucleo_obrigatorio",
        "forma": "forma_preferencial",
    }
    if data != expected:
        raise CanonicalIntentError(
            f"{event_id}.realizacao_padrao deve apontar exatamente para núcleo/forma da Task36"
        )
    return dict(data)


def _validate_default_target(event_id: str, event: dict[str, Any]) -> None:
    nucleus = event.get("nucleo_obrigatorio")
    preferred = event.get("forma_preferencial")
    if not isinstance(nucleus, list) or not nucleus:
        raise CanonicalIntentError(f"{event_id}: realização padrão sem núcleo")
    if not isinstance(preferred, list) or not preferred:
        raise CanonicalIntentError(f"{event_id}: realização padrão sem forma preferencial")


def _validate_rewrite(
    raw: Any,
    event_id: str,
    *,
    global_modes: set[str] | None = None,
    global_max_delay: int = MAX_GLOBAL_DELAY_HOURS,
) -> dict[str, Any]:
    data = _map(raw, f"{event_id}.contrato_rewrite")
    expected_keys = {
        "preserva_intencao",
        "sem_rewrite",
        "modos_permitidos",
        "atraso_maximo_horas",
        "integracao_sidequest",
        "satisfacao_antecipada",
        "reancoragem_local",
        "troca_de_atores",
    }
    if set(data) != expected_keys:
        raise CanonicalIntentError(f"{event_id}.contrato_rewrite possui estrutura inválida")
    if data["preserva_intencao"] is not True:
        raise CanonicalIntentError(f"{event_id}: rewrite precisa preservar a intenção")
    if data["sem_rewrite"] != "realizacao_padrao":
        raise CanonicalIntentError(f"{event_id}: fallback sem rewrite precisa ser realização padrão")

    modes = _list(data["modos_permitidos"], f"{event_id}.modos_permitidos")
    if not modes or len(modes) != len(set(modes)):
        raise CanonicalIntentError(f"{event_id}: modos de rewrite vazios ou duplicados")
    mode_set = {_text(mode, f"{event_id}.modos_permitidos") for mode in modes}
    allowed = global_modes or ALLOWED_REWRITE_MODES
    if mode_set - allowed:
        raise CanonicalIntentError(
            f"{event_id}: modo de rewrite proibido: {', '.join(sorted(mode_set - allowed))}"
        )
    if "cancelar" in mode_set:
        raise CanonicalIntentError(f"{event_id}: intenção canônica nunca aceita cancelar")

    delay = _integer(
        data["atraso_maximo_horas"],
        f"{event_id}.atraso_maximo_horas",
        0,
        global_max_delay,
    )
    if ("adiar" in mode_set) != (delay > 0):
        raise CanonicalIntentError(
            f"{event_id}: adiar exige atraso_maximo_horas > 0 e vice-versa"
        )

    integrate = _bool(data["integracao_sidequest"], f"{event_id}.integracao_sidequest")
    early = _bool(data["satisfacao_antecipada"], f"{event_id}.satisfacao_antecipada")
    reanchor = _bool(data["reancoragem_local"], f"{event_id}.reancoragem_local")
    swap = _bool(data["troca_de_atores"], f"{event_id}.troca_de_atores")
    if early and "satisfazer" not in mode_set:
        raise CanonicalIntentError(f"{event_id}: satisfação antecipada exige modo satisfazer")
    if reanchor and "reancorar" not in mode_set:
        raise CanonicalIntentError(f"{event_id}: reancoragem local exige modo reancorar")
    if swap and "transformar" not in mode_set:
        raise CanonicalIntentError(f"{event_id}: troca de atores exige modo transformar")

    return {
        "preserva_intencao": True,
        "sem_rewrite": "realizacao_padrao",
        "modos_permitidos": list(modes),
        "atraso_maximo_horas": delay,
        "integracao_sidequest": integrate,
        "satisfacao_antecipada": early,
        "reancoragem_local": reanchor,
        "troca_de_atores": swap,
    }


def load_intent(
    repo: Path,
    event_id: str,
    *,
    index: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = _event_id(event_id)
    index = index or load_index(repo)
    catalog = catalog or eventos_canonicos.load_catalog(repo)
    if event_id not in catalog["eventos"]:
        raise CanonicalIntentError(f"evento canônico inexistente: {event_id}")
    if event_id in index["passado_congelado"]:
        raise CanonicalIntentError(f"{event_id}: passado materializado é imutável e não possui rewrite Task39")

    event_meta = catalog["eventos"][event_id]
    instant = mundo.parse_instant(
        event_meta["ativacao"]["data"], event_meta["ativacao"]["hora"]
    )
    if instant.minute <= index["_fronteira"].minute:
        raise CanonicalIntentError(f"{event_id}: evento anterior à fronteira Task39 sem congelamento")

    rel = _intent_path(event_id)
    data = _map(_load(repo / rel), rel.as_posix())
    expected_keys = {
        "schema_intencao_canonica_parte_1",
        "natureza",
        "arco",
        "evento_id",
        "intencao_canonica",
        "realizacao_padrao",
        "contrato_rewrite",
    }
    if set(data) != expected_keys:
        raise CanonicalIntentError(f"{event_id}: fragmento de intenção possui campos inesperados")
    if data["schema_intencao_canonica_parte_1"] != INTENT_SCHEMA:
        raise CanonicalIntentError(f"{event_id}: schema de intenção inválido")
    if data["natureza"] != "reservado" or data["arco"] != ARC:
        raise CanonicalIntentError(f"{event_id}: autoridade do fragmento inválida")
    if data["evento_id"] != event_id:
        raise CanonicalIntentError(f"{event_id}: fragmento roteado para outro evento")

    return {
        "schema_intencao_canonica_parte_1": INTENT_SCHEMA,
        "natureza": "reservado",
        "arco": ARC,
        "evento_id": event_id,
        "intencao_canonica": _validate_intent(data["intencao_canonica"], event_id),
        "realizacao_padrao": _validate_default_realization(
            data["realizacao_padrao"], event_id
        ),
        "contrato_rewrite": _validate_rewrite(
            data["contrato_rewrite"],
            event_id,
            global_modes=set(index["modos_rewrite_permitidos"]),
            global_max_delay=index["_max_delay"],
        ),
        "_fonte": rel.as_posix(),
    }


def projection(repo: Path, event_id: str) -> dict[str, Any]:
    """Consulta dirigida sem abrir o fragmento narrativo da Task36."""
    index = load_index(repo)
    catalog = eventos_canonicos.load_catalog(repo)
    intent = load_intent(repo, event_id, index=index, catalog=catalog)
    event_meta = catalog["eventos"][event_id]
    return {
        "ok": True,
        "evento": event_id,
        "intencao_canonica": intent["intencao_canonica"],
        "realizacao_padrao": {
            **intent["realizacao_padrao"],
            "fragmento_evento": event_meta["fragmento"],
        },
        "contrato_rewrite": intent["contrato_rewrite"],
        "regra": (
            "Task39 não executa rewrite: sem uma futura transação autorizada, "
            "a Task36 materializa a realização padrão; a intenção nunca pode ser cancelada silenciosamente."
        ),
        "fontes_lidas": [
            INDEX.as_posix(),
            eventos_canonicos.CATALOG.as_posix(),
            intent["_fonte"],
        ],
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        catalog = eventos_canonicos.load_catalog(repo)
    except (CanonicalIntentError, eventos_canonicos.CanonicalEventError) as exc:
        return {"ok": False, "erros": [str(exc)]}

    frozen = index["passado_congelado"]
    seen_intents: set[str] = set()
    future_count = 0

    for event_id in catalog["eventos"]:
        try:
            event = eventos_canonicos.load_event(repo, event_id, catalog=catalog)
            instant = mundo.parse_instant(event["ativacao"]["data"], event["ativacao"]["hora"])
            if event_id in frozen:
                if instant.minute > index["_fronteira"].minute:
                    raise CanonicalIntentError(f"{event_id}: passado congelado após fronteira Task39")
                digest = eventos_canonicos.event_digest(event)
                if digest != frozen[event_id]:
                    raise CanonicalIntentError(f"{event_id}: passado materializado alterado após Task39")
                if (repo / _intent_path(event_id)).exists():
                    raise CanonicalIntentError(f"{event_id}: passado congelado não pode receber fragmento de intenção")
                continue

            future_count += 1
            if instant.minute <= index["_fronteira"].minute:
                raise CanonicalIntentError(
                    f"{event_id}: evento anterior à fronteira Task39 não foi congelado"
                )
            intent = load_intent(repo, event_id, index=index, catalog=catalog)
            _validate_default_target(event_id, event)
            intent_id = intent["intencao_canonica"]["id"]
            if intent_id in seen_intents:
                raise CanonicalIntentError(f"id de intenção duplicado: {intent_id}")
            seen_intents.add(intent_id)
        except (
            CanonicalIntentError,
            eventos_canonicos.CanonicalEventError,
            mundo.WorldEngineError,
        ) as exc:
            errors.append(str(exc))

    return {
        "ok": not errors,
        "erros": errors,
        "eventos": len(catalog["eventos"]),
        "passado_congelado": len(frozen),
        "futuros_com_intencao": future_count,
        "intencoes_unicas": len(seen_intents),
        "schedulers_novos": 0,
        "estados_novos": 0,
        "rng_novo": 0,
        "scans_globais_hot_path": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p_event = sub.add_parser("evento")
    p_event.add_argument("id")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    try:
        result = check(repo) if args.cmd == "check" else projection(repo, args.id)
    except (
        CanonicalIntentError,
        eventos_canonicos.CanonicalEventError,
        mundo.WorldEngineError,
    ) as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True, sort_keys=False))
        return 2

    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
