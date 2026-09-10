#!/usr/bin/env python3
"""NV-17 — side quests vivas orientadas por causa.

A camada não cria sidequests. Descobre apenas causas NV-11 já declaradas em
planos dirigidos, prova se a causa vencida consegue alcançar Ren e reserva no
máximo um encaminhamento por janela. Autoria/materialização continuam nas
Tasks 40–46 e exigem oferta efetivamente narrada.

O catálogo Task32/33 é histórico. Sua migração é one-shot e fica registrada em
``narrador/sidequests-vivas/migracao-legado.yaml``; o runtime nunca o varre.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

import mundo

SCHEMA = 1
STATE = Path("narrador/sidequests-vivas/estado.yaml")
LOCK = Path("narrador/sidequests-vivas/.estado.lock")
MIGRATION = Path("narrador/sidequests-vivas/migracao-legado.yaml")
MIGRATION_EVIDENCE = Path("narrador/sidequests-vivas/evidencias-migracao.yaml")
LEGACY_SECRETS = Path("narrador/sidequests-canonicas/segredos")
LEGACY_GATES = Path("narrador/sidequests-canonicas/gates")
PLAN_SCHEDULE_PREFIX = "nv08."
PLAN_PENDING_TYPE = "avaliar_plano_personagem"
MAX_ACTIVE = 2
MAX_WINDOW_RECORDS = 32
MAX_CANDIDATES = 8
MAX_STATE_BYTES = 32 * 1024
MAX_OUTPUT_BYTES = 10 * 1024
PLAN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
QSC_RE = re.compile(r"^qsc-[0-9a-f]{12}$")


class LiveSidequestError(ValueError):
    """Falha de contrato causal; nunca completar lacunas por invenção."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiveSidequestError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LiveSidequestError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, maximum: int = 320) -> str:
    if not isinstance(value, str):
        raise LiveSidequestError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise LiveSidequestError(f"{label} deve ser texto não vazio de até {maximum} caracteres")
    return result


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _yaml_size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _atomic_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(value, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


@contextmanager
def _state_lock(repo: Path) -> Iterator[None]:
    path = repo / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise LiveSidequestError(f"{label}: {exc}") from exc
    return _map(value, label)


def _now(repo: Path, now: mundo.WorldInstant | None) -> tuple[mundo.WorldInstant, list[str]]:
    if now is not None:
        return now, []
    try:
        value, _ = mundo.load_canonical_time(repo)
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc
    return value, [mundo.TIME_PATH.as_posix()]


def _window(repo: Path, now: mundo.WorldInstant) -> tuple[dict[str, Any], list[str]]:
    import fronteira_vivacidade

    try:
        agenda = mundo.load_agenda(repo)
        dawn = mundo._dawn_minute(agenda)
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc
    parts = mundo.instant_parts(now)
    period = fronteira_vivacidade.period_at(now, dawn)
    data = _text(parts.get("data"), "janela.data", 80)
    return {"id": f"{data}|{period}", "data": data, "periodo": period}, [mundo.AGENDA_PATH.as_posix()]


def _parse_when(raw: Any, label: str) -> mundo.WorldInstant:
    if not isinstance(raw, dict) or set(raw) != {"data", "hora"}:
        raise LiveSidequestError(f"{label} exige data e hora")
    try:
        return mundo.parse_instant(str(raw["data"]), str(raw["hora"]))
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc


def _schedule_plan_id(schedule: dict[str, Any]) -> str | None:
    sid = schedule.get("id")
    if schedule.get("tipo") != PLAN_PENDING_TYPE or not isinstance(sid, str):
        return None
    if not sid.startswith(PLAN_SCHEDULE_PREFIX):
        return None
    rest = sid[len(PLAN_SCHEDULE_PREFIX):]
    plan_id, sep, revision = rest.rpartition(".")
    if not sep or not revision.isdigit() or not PLAN_ID_RE.fullmatch(plan_id):
        raise LiveSidequestError(f"agendamento NV-08 possui id inválido: {sid}")
    return plan_id


def due_plan_ids(repo: Path, now: mundo.WorldInstant) -> tuple[list[str], list[str]]:
    """Abre somente o índice temporal NV-08; nunca procura perfis/NPCs."""
    try:
        agenda = mundo.load_agenda(repo)
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc
    due: list[tuple[int, str]] = []
    for raw in agenda.get("agendamentos") or []:
        if not isinstance(raw, dict):
            continue
        pid = _schedule_plan_id(raw)
        if pid is None:
            continue
        when = _parse_when(raw.get("em"), f"agenda.{raw.get('id')}.em")
        if when <= now:
            due.append((when.minute, pid))
    ordered: list[str] = []
    for _, pid in sorted(due):
        if pid not in ordered:
            ordered.append(pid)
    return ordered, [mundo.AGENDA_PATH.as_posix()]


def _scene(repo: Path) -> tuple[Any, dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    import memoria_cena

    try:
        reader, state, records, saved = memoria_cena.load_scene(repo)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        raise LiveSidequestError(f"estado efetivo da cena indisponível: {exc}") from exc
    if not isinstance(state, dict):
        raise LiveSidequestError("estado efetivo da cena deve ser mapa")
    return reader, state, records, saved


def _canonical_local(repo: Path, raw: Any) -> tuple[str | None, list[str]]:
    if not isinstance(raw, str) or not raw.strip():
        return None, []
    import locais

    try:
        resolved = locais.resolve(repo, raw.strip())
    except locais.LocationError:
        return None, []
    return resolved["local_id"], list(resolved.get("fontes_lidas") or [])


def _scene_local(repo: Path, state: dict[str, Any], supplied: str | None) -> tuple[str | None, list[str]]:
    if supplied:
        local, sources = _canonical_local(repo, supplied)
        if local is not None:
            return local, sources
    location = state.get("localizacao") or {}
    if not isinstance(location, dict):
        return None, ["estado/estado-atual.yaml"]
    raw = location.get("local_id") or location.get("area")
    local, sources = _canonical_local(repo, raw)
    return local, ["estado/estado-atual.yaml", *sources]


def _participants(_saved: dict[str, Any] | None, explicit: Iterable[str] | None) -> set[str]:
    # ``--participante``/memória prospectiva não prova presença física (NV-16).
    # Apenas NPCs entregues como gatilho real da cena podem provar alcance aqui.
    return {str(value) for value in (explicit or []) if isinstance(value, str) and value}


def _opportunity_state(repo: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    import oportunidades

    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise LiveSidequestError(str(exc)) from exc
    return index, state, [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()]


def _mission_budget(index: dict[str, Any], state: dict[str, Any]) -> tuple[int, int, int]:
    import oportunidades

    active, opened = oportunidades._mission_counts(state)
    configured = int(index["orcamento"]["max_ativas"])
    if configured != MAX_ACTIVE:
        raise LiveSidequestError(f"NV-17 exige teto de {MAX_ACTIVE} sidequests ativas; configurado={configured}")
    return active, opened, configured


def _plan(repo: Path, world: dict[str, Any], plan_id: str) -> dict[str, Any]:
    import planos_personagens

    if not PLAN_ID_RE.fullmatch(plan_id):
        raise LiveSidequestError(f"plan_id inválido: {plan_id}")
    control = world.get(planos_personagens.KEY) or {}
    if not isinstance(control, dict):
        raise LiveSidequestError("controle de planos NV-08 deve ser mapa")
    raw = control.get(plan_id)
    if not isinstance(raw, dict):
        raise LiveSidequestError(f"agendamento dirigido aponta plano inexistente: {plan_id}")
    return raw


def _reach(
    repo: Path,
    *,
    view: Any,
    plan: dict[str, Any],
    present: set[str],
    local_id: str | None,
) -> tuple[dict[str, Any], list[str]]:
    import planos_personagens

    owner = str((plan.get("agente") or {}).get("id") or "")
    if owner in present:
        return {
            "alcança_ren": True,
            "tipo": "elenco_presente",
            "fundamento": "dono da necessidade integra um gatilho real da cena; presença só transporta causa NV-11 já validada",
        }, []

    step = plan.get("passo") or {}
    step_local, sources = _canonical_local(repo, step.get("local"))
    if local_id is not None and step_local == local_id:
        local_hint = {
            "alcança_ren": False,
            "tipo": "mesmo_local_sem_presenca_confirmada",
            "fundamento": "o passo aponta o local de Ren, mas isso não prova que o dono da necessidade esteja presente",
        }
    else:
        local_hint = {
            "alcança_ren": False,
            "tipo": "sem_rota_confirmada",
            "fundamento": "causa vencida não possui presença ou canal causal confirmado até Ren",
        }

    resolution = step.get("resolucao") or {}
    if resolution.get("tipo") == "contato":
        import contatos_sociais
        try:
            contatos_sociais.delivery(view, plan)
        except planos_personagens.PlanError as exc:
            return {**local_hint, "contato_bloqueado": str(exc)[:180]}, sources
        return {
            "alcança_ren": True,
            "tipo": "contato_causal",
            "fundamento": "o plano possui entrega de contato revalidada pelo motor social existente",
        }, sources
    return local_hint, sources


def _live_need(
    repo: Path,
    *,
    view: Any,
    plan: dict[str, Any],
    contract: dict[str, Any],
    present: set[str],
    local_id: str | None,
    active_count: int,
) -> tuple[dict[str, Any], list[str]]:
    import sidequests_personagens

    cause = sidequests_personagens._cause_projection(plan, contract)
    reach, sources = _reach(repo, view=view, plan=plan, present=present, local_id=local_id)
    step = plan["passo"]
    due = _parse_when(step["em"], f"plano.{plan['id']}.passo.em")
    blockers = [copy.deepcopy(item) for item in (step.get("condicoes") or [])]
    return {
        "id": cause["id"],
        "plano_id": plan["id"],
        "causa": {
            "tipo": contract["tipo"],
            "referencia": copy.deepcopy(contract["causa"]),
            "situacao": contract["situacao"],
        },
        "dono": copy.deepcopy(plan["agente"]),
        "bloqueio": {"estado_plano": plan.get("estado"), "condicoes": blockers},
        "conhecimento": list(step.get("conhecimento") or []),
        "alcance": reach,
        "reavaliacao": {"em": copy.deepcopy(step["em"]), "condicoes": blockers},
        "stakes": copy.deepcopy(contract.get("consequencias") or {}),
        "protecoes": {
            "oferta_nao_e_aceite": True,
            "sem_terminal_inventado": True,
            "sem_recompensa_inventada": True,
            "sem_reacao_inventada": True,
            "agencia_de_ren_preservada": True,
        },
        "motivo_envolver_ren": contract["motivo_envolver_ren"],
        "vencida": True,
        "vencida_em_minuto": due.minute,
        "prioridade_elevada_por_zero_ativas": active_count == 0,
    }, sources


def collect_due(
    repo: Path,
    *,
    now: mundo.WorldInstant | None = None,
    participants: Iterable[str] | None = None,
    local_id: str | None = None,
    explicit_plan_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Projeta causas vencidas por índices dirigidos, sem catálogo legado ou IA."""
    import planos_personagens
    import sidequests_personagens

    now, sources = _now(repo, now)
    due, agenda_sources = due_plan_ids(repo, now)
    sources.extend(agenda_sources)
    for raw in explicit_plan_ids or []:
        pid = _text(raw, "explicit_plan_id", 64)
        if not PLAN_ID_RE.fullmatch(pid):
            raise LiveSidequestError(f"explicit_plan_id inválido: {pid}")
        if pid not in due:
            due.append(pid)
    if len(due) > MAX_CANDIDATES:
        due = due[:MAX_CANDIDATES]

    index, opportunity_state, budget_sources = _opportunity_state(repo)
    sources.extend(budget_sources)
    active, opened, limit = _mission_budget(index, opportunity_state)
    if not due:
        return {
            "schema_sidequests_vivas": SCHEMA,
            "resultado": "sem_causa_dirigida_vencida",
            "causas": [],
            "selecionada": None,
            "orcamento": {"ativas": active, "abertas": opened, "max_ativas": limit},
            "fontes_lidas": list(dict.fromkeys(sources)),
            "metricas": {"planos_dirigidos": 0, "catalogo_legado_lido": 0, "scans_npc": 0, "chamadas_ia": 0},
        }

    try:
        world = mundo.load_world_state(repo)
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc
    sources.append(mundo.WORLD_STATE_PATH.as_posix())
    _, scene_state, records, saved = _scene(repo)
    view = planos_personagens.View(repo, records)
    current_local, local_sources = _scene_local(repo, scene_state, local_id)
    sources.extend(local_sources)
    present = _participants(saved, participants)

    candidates: list[dict[str, Any]] = []
    for pid in due:
        plan = _plan(repo, world, pid)
        if plan.get("estado") in planos_personagens.TERMINAL:
            continue
        step = plan.get("passo") or {}
        when = _parse_when(step.get("em"), f"plano.{pid}.passo.em")
        if when > now:
            continue
        try:
            contract = sidequests_personagens.validate_definition(view, plan)
        except (planos_personagens.PlanError, sidequests_personagens.CharacterSidequestError) as exc:
            raise LiveSidequestError(str(exc)) from exc
        if contract is None:
            continue
        cause = sidequests_personagens._cause_projection(plan, contract)
        if sidequests_personagens._existing_for_cause(opportunity_state, cause["id"]) is not None:
            continue
        need, extra_sources = _live_need(
            repo, view=view, plan=plan, contract=contract, present=present,
            local_id=current_local, active_count=active,
        )
        sources.extend(extra_sources)
        candidates.append(need)

    eligible = [item for item in candidates if item["alcance"]["alcança_ren"]]
    if active >= limit:
        eligible = []
        result_name = "limite_ativas"
    elif eligible:
        result_name = "causa_viva_alcancavel"
    elif candidates:
        result_name = "causas_sem_alcance"
    else:
        result_name = "sem_causa_nv11_vencida"
    selected = min(
        eligible,
        key=lambda item: (
            0 if item["prioridade_elevada_por_zero_ativas"] else 1,
            item["vencida_em_minuto"],
            item["id"],
        ),
        default=None,
    )
    public_candidates = [
        {k: copy.deepcopy(v) for k, v in item.items() if k != "vencida_em_minuto"}
        for item in sorted(candidates, key=lambda row: (row["vencida_em_minuto"], row["id"]))
    ]
    public_selected = (
        {k: copy.deepcopy(v) for k, v in selected.items() if k != "vencida_em_minuto"}
        if selected is not None else None
    )
    result = {
        "schema_sidequests_vivas": SCHEMA,
        "resultado": result_name,
        "causas": public_candidates,
        "selecionada": public_selected,
        "orcamento": {"ativas": active, "abertas": opened, "max_ativas": limit},
        "local_id": current_local,
        "fontes_lidas": list(dict.fromkeys([*sources, *sorted(view.signatures)])),
        "metricas": {
            "planos_dirigidos": len(due), "causas_nv11": len(candidates),
            "alcancaveis": len(eligible), "catalogo_legado_lido": 0,
            "scans_npc": 0, "chamadas_ia": 0,
        },
    }
    if _yaml_size(result) > MAX_OUTPUT_BYTES:
        raise LiveSidequestError("projeção NV-17 excede orçamento; reduza fontes dirigidas")
    return result


def _empty_state() -> dict[str, Any]:
    return {"schema_sidequests_vivas": SCHEMA, "natureza": "controle_reservado", "janelas": {}, "ordem_recente": []}


def load_state(repo: Path) -> dict[str, Any]:
    path = repo / STATE
    if not path.is_file():
        return _empty_state()
    state = _load_yaml(path, STATE.as_posix())
    if state.get("schema_sidequests_vivas") != SCHEMA or state.get("natureza") != "controle_reservado":
        raise LiveSidequestError("estado NV-17 inválido")
    windows = _map(state.get("janelas"), "sidequests-vivas.janelas")
    order = _list(state.get("ordem_recente"), "sidequests-vivas.ordem_recente")
    if len(windows) > MAX_WINDOW_RECORDS or len(order) > MAX_WINDOW_RECORDS or len(order) != len(set(order)):
        raise LiveSidequestError("estado NV-17 excede orçamento de janelas")
    if set(order) != set(windows):
        raise LiveSidequestError("ordem de janelas NV-17 diverge do estado")
    for key, raw in windows.items():
        row = _map(raw, f"janelas.{key}")
        if row.get("janela_id") != key or row.get("estado") != "reservada":
            raise LiveSidequestError(f"reserva NV-17 inválida: {key}")
        signal = row.get("sinal_efetivo")
        if signal is not None and not isinstance(signal, dict):
            raise LiveSidequestError(f"reserva NV-17 sem sinal válido: {key}")
        base = {k: copy.deepcopy(v) for k, v in row.items() if k != "digest"}
        if row.get("digest") != _digest(base)[:24]:
            raise LiveSidequestError(f"reserva NV-17 perdeu integridade: {key}")
    if _yaml_size(state) > MAX_STATE_BYTES:
        raise LiveSidequestError("estado NV-17 excede orçamento")
    return state


def _reserve(repo: Path, window: dict[str, Any], *, source: str, signal: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    with _state_lock(repo):
        state = load_state(repo)
        key = window["id"]
        existing = state["janelas"].get(key)
        if isinstance(existing, dict):
            return copy.deepcopy(existing), True
        base = {
            "janela_id": key, "data": window["data"], "periodo": window["periodo"],
            "estado": "reservada", "origem": source, "sinal_efetivo": copy.deepcopy(signal),
        }
        row = {**base, "digest": _digest(base)[:24]}
        state["janelas"][key] = row
        state["ordem_recente"].append(key)
        while len(state["ordem_recente"]) > MAX_WINDOW_RECORDS:
            old = state["ordem_recente"].pop(0)
            state["janelas"].pop(old, None)
        if _yaml_size(state) > MAX_STATE_BYTES:
            raise LiveSidequestError("reserva NV-17 excede orçamento de controle")
        _atomic_yaml(repo / STATE, state)
        return copy.deepcopy(row), False


def _automatic_signal(selected: dict[str, Any], *, local_id: str | None, danger: str, tier: int | None) -> dict[str, Any]:
    return {"plano_id": selected["plano_id"], "local_id": local_id, "periculosidade": danger, "tier": tier}


def route_prepare(
    repo: Path,
    *,
    manual_signal: dict[str, Any] | None,
    participants: Iterable[str] | None = None,
    local_id: str | None = None,
    danger: str = "media",
    tier: int | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Escolhe o único sinal Task40 da janela sem permitir veto de causa vencida."""
    now, sources = _now(repo, now)
    window, window_sources = _window(repo, now)
    sources.extend(window_sources)

    current = load_state(repo)["janelas"].get(window["id"])
    if isinstance(current, dict):
        return {
            "schema_sidequests_vivas": SCHEMA,
            "janela": window,
            "resultado": "reserva_reutilizada",
            "sinal_efetivo": copy.deepcopy(current["sinal_efetivo"]),
            "origem": current["origem"],
            "reutilizada": True,
            "causa_viva": None,
            "ancora_manual_adiada": bool(manual_signal) and current["origem"] != "ancora_cena",
            "projecao": {"causas": [], "selecionada": None, "orcamento": None, "metricas": {"reavaliacoes": 0}},
            "fontes_lidas": list(dict.fromkeys([*sources, STATE.as_posix()])),
        }

    referenced: list[str] = []
    scene_anchor = manual_signal
    if isinstance(manual_signal, dict) and set(manual_signal) == {"plano_id", "local_id", "periculosidade", "tier"}:
        referenced = [str(manual_signal["plano_id"])]
        scene_anchor = None

    live = collect_due(
        repo, now=now, participants=participants, local_id=local_id,
        explicit_plan_ids=referenced,
    )
    selected = live.get("selecionada")
    automatic = (
        _automatic_signal(selected, local_id=live.get("local_id") or local_id, danger=danger, tier=tier)
        if isinstance(selected, dict) else None
    )

    if automatic is not None:
        row, reused = _reserve(repo, window, source="causa_nv11_vencida", signal=automatic)
        return {
            "schema_sidequests_vivas": SCHEMA, "janela": window,
            "resultado": "reserva_reutilizada" if reused else "causa_viva_projetada",
            "sinal_efetivo": copy.deepcopy(row["sinal_efetivo"]), "origem": row["origem"],
            "reutilizada": reused, "causa_viva": selected,
            "ancora_manual_adiada": bool(scene_anchor), "projecao": live,
            "fontes_lidas": list(dict.fromkeys([*sources, STATE.as_posix(), *(live.get("fontes_lidas") or [])])),
        }
    if scene_anchor is not None:
        if not isinstance(scene_anchor, dict):
            raise LiveSidequestError("sinal manual de oportunidade deve ser mapa ou null")
        row, reused = _reserve(repo, window, source="ancora_cena", signal=scene_anchor)
        return {
            "schema_sidequests_vivas": SCHEMA, "janela": window,
            "resultado": "reserva_reutilizada" if reused else "ancora_cena_encaminhada",
            "sinal_efetivo": copy.deepcopy(row["sinal_efetivo"]), "origem": row["origem"],
            "reutilizada": reused, "causa_viva": None, "ancora_manual_adiada": False,
            "projecao": live,
            "fontes_lidas": list(dict.fromkeys([*sources, STATE.as_posix(), *(live.get("fontes_lidas") or [])])),
        }
    return {
        "schema_sidequests_vivas": SCHEMA, "janela": window,
        "resultado": "sem_nova_oportunidade", "sinal_efetivo": None,
        "origem": None, "reutilizada": False, "causa_viva": None,
        "ancora_manual_adiada": False, "projecao": live,
        "fontes_lidas": list(dict.fromkeys([*sources, *(live.get("fontes_lidas") or [])])),
    }


def _load_migration_evidence(repo: Path) -> dict[str, str]:
    data = _load_yaml(repo / MIGRATION_EVIDENCE, MIGRATION_EVIDENCE.as_posix())
    if data.get("schema_evidencias_migracao_nv17") != SCHEMA or data.get("natureza") != "declaracao_reservada":
        raise LiveSidequestError("declaração de evidências de migração inválida")
    mappings = _map(data.get("mapeamentos"), "evidencias.mapeamentos")
    result: dict[str, str] = {}
    for qid, plan_id in mappings.items():
        if not isinstance(qid, str) or not QSC_RE.fullmatch(qid):
            raise LiveSidequestError(f"quest legada inválida em evidências: {qid}")
        pid = _text(plan_id, f"mapeamentos.{qid}", 64)
        if not PLAN_ID_RE.fullmatch(pid):
            raise LiveSidequestError(f"plano inválido em evidências: {pid}")
        result[qid] = pid
    return result


def _legacy_entries(repo: Path) -> list[tuple[str, str]]:
    """Única varredura autorizada: somente dentro da migração ainda não executada."""
    result: list[tuple[str, str]] = []
    for path in sorted((repo / LEGACY_SECRETS).glob("qsc-*.yaml")):
        qid = path.stem
        if not QSC_RE.fullmatch(qid):
            raise LiveSidequestError(f"arquivo legado possui id inválido: {path.name}")
        data = _load_yaml(path, path.relative_to(repo).as_posix())
        if data.get("id") != qid:
            raise LiveSidequestError(f"id interno legado diverge: {qid}")
        npc_id = _text(data.get("npc_id"), f"{qid}.npc_id", 96)
        gate_path = repo / LEGACY_GATES / f"{qid}.yaml"
        gate = _load_yaml(gate_path, gate_path.relative_to(repo).as_posix())
        if gate.get("id") != qid or gate.get("npc_id") != npc_id:
            raise LiveSidequestError(f"gate legado diverge do detalhe: {qid}")
        result.append((qid, npc_id))
    return result


def _migration_conversion(repo: Path, qid: str, npc_id: str, plan_id: str) -> dict[str, Any]:
    import planos_personagens
    import sidequests_personagens

    try:
        world = mundo.load_world_state(repo)
    except mundo.WorldEngineError as exc:
        raise LiveSidequestError(str(exc)) from exc
    plan = _plan(repo, world, plan_id)
    _, _, records, _ = _scene(repo)
    view = planos_personagens.View(repo, records)
    try:
        contract = sidequests_personagens.validate_definition(view, plan)
    except (planos_personagens.PlanError, sidequests_personagens.CharacterSidequestError) as exc:
        raise LiveSidequestError(f"{qid}: evidência NV-11 inválida: {exc}") from exc
    if contract is None:
        raise LiveSidequestError(f"{qid}: plano mapeado não contém causa NV-11")
    owner = str((plan.get("agente") or {}).get("id") or "")
    if owner != npc_id:
        raise LiveSidequestError(f"{qid}: dono da causa {owner} diverge do NPC legado {npc_id}")
    cause = sidequests_personagens._cause_projection(plan, contract)
    return {
        "id": qid, "estado": "convertida_em_causa_nv11", "npc_id": npc_id,
        "plano_id": plan_id, "causa_id": cause["id"],
        "fonte_causa": copy.deepcopy(contract["causa"]),
        "regra": "somente a causa NV-11 sobrevive; título, terminal, reação, recompensa e necessidade do catálogo não são copiados",
    }


def load_migration(repo: Path) -> dict[str, Any] | None:
    path = repo / MIGRATION
    if not path.is_file():
        return None
    data = _load_yaml(path, MIGRATION.as_posix())
    if data.get("schema_migracao_nv17") != SCHEMA or data.get("natureza") != "recibo_reservado":
        raise LiveSidequestError("recibo de migração NV-17 inválido")
    if data.get("executada") is not True:
        raise LiveSidequestError("recibo de migração existe mas não está concluído")
    converted = _list(data.get("convertidas"), "migracao.convertidas")
    archived = _list(data.get("arquivadas"), "migracao.arquivadas")
    seen: set[str] = set()
    for row in [*converted, *archived]:
        item = _map(row, "migracao.item")
        qid = _text(item.get("id"), "migracao.item.id", 32)
        if qid in seen:
            raise LiveSidequestError(f"migração decide duas vezes {qid}")
        seen.add(qid)
        if item.get("estado") == "arquivada" and not item.get("motivo"):
            raise LiveSidequestError(f"arquivo {qid} sem razão explícita")
    return data


def migrate_legacy(repo: Path) -> dict[str, Any]:
    """Migração one-shot; se o recibo existe, retorna sem abrir o catálogo."""
    existing = load_migration(repo)
    if existing is not None:
        return existing
    evidence = _load_migration_evidence(repo)
    entries = _legacy_entries(repo)
    known = {qid for qid, _ in entries}
    unknown = set(evidence) - known
    if unknown:
        raise LiveSidequestError("evidência aponta sidequest legada inexistente: " + ", ".join(sorted(unknown)))
    converted: list[dict[str, Any]] = []
    archived: list[dict[str, Any]] = []
    for qid, npc_id in entries:
        if qid in evidence:
            converted.append(_migration_conversion(repo, qid, npc_id, evidence[qid]))
        else:
            archived.append({
                "id": qid, "estado": "arquivada", "npc_id": npc_id,
                "motivo": "sem_evidencia_canonica_explicita_de_causa_viva_nv11",
            })
    receipt = {
        "schema_migracao_nv17": SCHEMA, "natureza": "recibo_reservado", "executada": True,
        "politica": {
            "catalogo_legado_nao_e_runtime": True,
            "afinidade_ou_presenca_nao_sao_evidencia": True,
            "zero_ativas_nao_cria_causa": True,
            "nao_copiar_terminal_reacao_recompensa_necessidade": True,
        },
        "convertidas": converted, "arquivadas": archived,
        "metricas": {"itens": len(entries), "convertidas": len(converted), "arquivadas": len(archived), "varreduras_catalogo": 1},
    }
    _atomic_yaml(repo / MIGRATION, receipt)
    return receipt


def migration_status(repo: Path, qid: str) -> dict[str, Any] | None:
    receipt = load_migration(repo)
    if receipt is None:
        return None
    for row in [*receipt["convertidas"], *receipt["arquivadas"]]:
        if row.get("id") == qid:
            return copy.deepcopy(row)
    return None


def check(repo: Path) -> dict[str, Any]:
    state = load_state(repo)
    migration = load_migration(repo)
    if migration is None:
        raise LiveSidequestError("migração NV-17 ainda não possui recibo one-shot")
    evidence = _load_migration_evidence(repo)
    index, opportunities_state, _ = _opportunity_state(repo)
    active, opened, limit = _mission_budget(index, opportunities_state)
    if any(meta.get("estado") != "inativo" for meta in (index.get("perfis") or {}).values() if isinstance(meta, dict)):
        raise LiveSidequestError("perfil procedural legado não pode ser reativado após a migração NV-17")
    decided = len(migration["convertidas"]) + len(migration["arquivadas"])
    metrics = migration.get("metricas") or {}
    if metrics.get("itens") != decided or metrics.get("varreduras_catalogo") != 1:
        raise LiveSidequestError("recibo de migração possui contagem/varredura divergente")
    if set(evidence) != {row["id"] for row in migration["convertidas"]}:
        raise LiveSidequestError("evidências explícitas e conversões do recibo divergem")
    return {
        "ok": True, "schema_sidequests_vivas": SCHEMA,
        "janelas_reservadas": len(state["janelas"]), "migracao_executada": True,
        "legado_convertido": len(migration["convertidas"]),
        "legado_arquivado": len(migration["arquivadas"]),
        "ativas": active, "abertas": opened, "max_ativas": limit,
        "catalogo_legado_lido": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("migrar-legado")
    status = sub.add_parser("status")
    status.add_argument("--plano", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.command == "check":
            print(yaml.safe_dump(check(repo), allow_unicode=True, sort_keys=False), end="")
        elif args.command == "migrar-legado":
            print(yaml.safe_dump(migrate_legacy(repo), allow_unicode=True, sort_keys=False), end="")
        else:
            print(yaml.safe_dump(collect_due(repo, explicit_plan_ids=args.plano), allow_unicode=True, sort_keys=False), end="")
    except LiveSidequestError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
