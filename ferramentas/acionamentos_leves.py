"""Acionamento causal dos agentes leves na fila e no journal existentes.

Não executa ações, não concede conhecimento e não agenda um segundo mundo.
Dependências: fontes_causais declaradas, npc:<id> e envolvidos de compromissos.
Somente um lote canônico alterado ou uma janela alcançada produz um acionamento.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

KEY = "acionamentos_leves"
PENDING_KEY = "acionamento_causal"
STATE = Path("estado/estado-atual.yaml")
INDEX = Path("narrador/agentes-leves/index.yaml")
LIGHT_STATE = Path("narrador/agentes-leves/estado.yaml")
WORLD = Path("narrador/mundo/estado.yaml")
TIME = Path("estado/tempo.yaml")
BARRIER = Path("runtime/mundo-pendencias.yaml")
MAX_CONTROL_BYTES = 16384
MAX_SIGNALS = 32
MAX_CAUSES_PER_AGENT = 8
MAX_CONTEXT_BYTES = 2560


class ActivationError(ValueError):
    """Contrato causal inválido; nunca descartar trabalho para caber no teto."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:24]


def _size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def configured(repo: Path) -> bool:
    return all((repo / path).is_file() for path in (INDEX, LIGHT_STATE, WORLD, TIME, STATE))


def _read(repo: Path, path: Path, outputs: dict | None = None) -> dict:
    raw = (outputs or {}).get(path.as_posix())
    if raw is None:
        raw = (repo / path).read_bytes()
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise ActivationError(f"fonte causal não é mapa: {path}")
    return value


def _minute(when: dict) -> int:
    import mundo
    if not isinstance(when, dict) or set(when) != {"data", "hora"}:
        raise ActivationError("instante causal exige data e hora")
    return mundo.parse_instant(when["data"], when["hora"]).minute


def _instant(time: dict) -> dict:
    import mundo
    return mundo.instant_parts(mundo.parse_instant(
        time.get("data_atual") or time.get("data"), time["hora_aproximada"]))


def _active(index: dict) -> dict:
    return {aid: meta for aid, meta in index["agentes"].items() if meta["estado"] == "ativo"}


def require_stable_canon(repo: Path) -> None:
    import _consolidar_core
    if (repo / _consolidar_core.JOURNAL_PATH).exists():
        raise ActivationError("consolidação interrompida; recuperar o journal antes de avaliar acionamentos")


def _entity_path(repo: Path, kind: str, aid: str, cache: dict) -> str:
    prefix = "estado/relacoes" if kind == "relacao" else "estado/npcs"
    index_path = prefix + "/index.yaml"
    if index_path not in cache:
        cache[index_path] = _read(repo, Path(index_path)) if (repo / index_path).is_file() else {}
    key = "relacoes" if kind == "relacao" else "npcs"
    entry = cache[index_path].get(key, {}).get(aid) or {}
    path = entry.get("arquivo") or f"{prefix}/{aid}.yaml"
    if (not isinstance(path, str) or not path.startswith(prefix + "/")
            or not (repo / path).resolve().is_relative_to((repo / prefix).resolve())
            or not (repo / path).resolve().is_relative_to(repo.resolve())
            or Path(path).suffix != ".yaml"):
        raise ActivationError("fragmento causal fora do domínio autorizado")
    return path


def _dependencies(index: dict, repo: Path | None = None, cache: dict | None = None) -> dict[str, set[str]]:
    cache = {} if cache is None else cache
    result: dict[str, set[str]] = {}
    for aid, meta in _active(index).items():
        meter = _entity_path(repo, "npc", aid, cache) if repo is not None else f"estado/npcs/{aid}.yaml"
        for source in [*(meta.get("fontes_causais") or []), meter]:
            result.setdefault(source, set()).add(aid)
    return result


def _source(delta: dict, repo: Path | None = None, cache: dict | None = None) -> str | None:
    if delta.get("visibilidade", "operacional") != "operacional":
        return None
    target = delta.get("alvo", "")
    if isinstance(target, str) and target.startswith(("relacao:", "npc:")):
        kind, aid = target.split(":", 1)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", aid):
            raise ActivationError("alvo de acionamento exige ID canônico")
        if repo is not None:
            return _entity_path(repo, kind, aid, {} if cache is None else cache)
        return f"estado/{'relacoes' if kind == 'relacao' else 'npcs'}/{aid}.yaml"
    return None


def _commitment_delta(delta: dict) -> bool:
    return (delta.get("alvo") == "estado"
            and delta.get("visibilidade", "operacional") == "operacional"
            and str(delta.get("caminho", "")).startswith("compromissos."))


def _control(world: dict) -> dict:
    value = world.get(KEY)
    if value is None:
        value = {"versao": 1, "aguardando": {}, "prazos": {}, "rotinas_suspensas": {}}
        world[KEY] = value
    if (not isinstance(value, dict) or set(value) != {"versao", "aguardando", "prazos", "rotinas_suspensas"}
            or type(value["versao"]) is not int or value["versao"] != 1
            or any(not isinstance(value[k], dict) for k in ("aguardando", "prazos", "rotinas_suspensas"))):
        raise ActivationError("controle de acionamentos leves inválido")
    for aid in value["aguardando"]:
        if not isinstance(aid, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", aid):
            raise ActivationError("agente da fila causal inválido")
    for key, signature in value["prazos"].items():
        if not isinstance(key, str) or not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{24}", signature):
            raise ActivationError("recibo de prazo inválido")
    for pid, pending in value["rotinas_suspensas"].items():
        if (not isinstance(pending, dict) or pending.get("id") != pid
                or pending.get("tipo") != "reavaliar_agente_leve"
                or PENDING_KEY in pending):
            raise ActivationError("rotina suspensa inválida")
        _minute(pending["disparado_em"])
    return value


def _validate_control(world: dict) -> None:
    control = _control(world)
    groups = list(control["aguardando"].values())
    groups += [p[PENDING_KEY] for p in world["pendencias"] if PENDING_KEY in p]
    count = 0
    for causes in groups:
        if not isinstance(causes, dict) or not causes or len(causes) > MAX_CAUSES_PER_AGENT:
            raise ActivationError("causas por agente excedem o teto; resolver o lote pendente")
        count += len(causes)
        for key, cause in causes.items():
            if (not isinstance(key, str) or not isinstance(cause, dict)
                    or cause.get("tipo") not in {"mudanca", "prazo"}
                    or not isinstance(cause.get("fonte"), str)
                    or not isinstance(cause.get("assinatura"), str)
                    or not re.fullmatch(r"[0-9a-f]{24}", cause["assinatura"])):
                raise ActivationError("causa de acionamento inválida")
            if cause["tipo"] == "prazo" and (cause.get("fase") not in {"inicio", "fim"}
                    or not isinstance(cause.get("compromisso"), str)
                    or not isinstance(cause.get("registro"), str)):
                raise ActivationError("causa de prazo inválida")
            _minute(cause["em"])
    if count > MAX_SIGNALS or _size({KEY: control, "ativos": groups}) > MAX_CONTROL_BYTES:
        raise ActivationError("fila causal excede orçamento; resolver pendências antes de acumular outras")


def _enqueue(world: dict, aid: str, key: str, signal: dict) -> None:
    _control(world)["aguardando"].setdefault(aid, {})[key] = deepcopy(signal)


def _commitments(state: dict) -> dict:
    import compromissos
    values = state.get("compromissos") or {}
    if not isinstance(values, dict):
        raise ActivationError("compromissos deve ser mapa")
    for cid, raw in values.items():
        compromissos.commitment_path(cid)
        compromissos.validate_record(raw)
    return values


def deadline_events(state: dict, index: dict, receipts: dict, now: dict) -> list[tuple[str, str, dict]]:
    """Instantes exatos declarados; descrição livre não vira prazo por inferência."""
    current = _minute(now)
    active = set(_active(index))
    events = []
    for cid, record in sorted(_commitments(state).items()):
        involved = sorted(active & set(record.get("envolvidos") or []))
        if not involved:
            continue
        version = _digest(record)
        for phase in ("inicio", "fim"):
            when = (record.get("janela") or {}).get(phase)
            if when is None or _minute(when) > current:
                continue
            key = f"{cid}:{phase}"
            signature = _digest([cid, version, phase])
            for aid in involved:
                if receipts.get(f"{aid}:{key}") == signature:
                    continue
                events.append((aid, key, {
                    "tipo": "prazo", "fonte": f"{STATE.as_posix()}:compromissos.{cid}",
                    "compromisso": cid, "fase": phase, "registro": version,
                    "em": deepcopy(when), "assinatura": signature,
                }))
    return events


def _refresh_deadlines(world: dict, state: dict, index: dict, now: dict) -> None:
    control = _control(world)
    records = _commitments(state)
    versions = {cid: _digest(value) for cid, value in records.items()}
    active = set(_active(index))
    valid_receipts = {}
    for aid in active:
        for cid, record in records.items():
            if aid not in (record.get("envolvidos") or []):
                continue
            for phase in ("inicio", "fim"):
                if (record.get("janela") or {}).get(phase) is not None:
                    key = f"{aid}:{cid}:{phase}"
                    signature = _digest([cid, versions[cid], phase])
                    if control["prazos"].get(key) == signature:
                        valid_receipts[key] = signature
    control["prazos"] = valid_receipts

    def valid(aid: str, cause: dict) -> bool:
        if aid not in active:
            return False
        if cause["tipo"] != "prazo":
            return True
        cid = cause.get("compromisso")
        return (cid in records and versions[cid] == cause.get("registro")
                and aid in (records[cid].get("envolvidos") or []))

    for aid, causes in list(control["aguardando"].items()):
        kept = {k: c for k, c in causes.items() if valid(aid, c)}
        if kept:
            control["aguardando"][aid] = kept
        else:
            del control["aguardando"][aid]
    for pending in list(world["pendencias"]):
        if PENDING_KEY not in pending:
            continue
        aid = pending.get("agente_leve")
        kept = {k: c for k, c in pending[PENDING_KEY].items() if valid(aid, c)}
        if kept:
            pending[PENDING_KEY] = kept
        elif aid not in active or str(pending.get("origem", "")).startswith("nv07:"):
            world["pendencias"].remove(pending)
            world["concluidas_recentes"].append({
                "id": pending["id"], "tipo": pending["tipo"],
                "disparado_em": pending["disparado_em"], "resultado": "gatilho_revogado",
            })
            import mundo
            world["concluidas_recentes"] = world["concluidas_recentes"][-mundo.MAX_RECENT_COMPLETED:]
        else:
            del pending[PENDING_KEY]
    for pid, pending in list(control["rotinas_suspensas"].items()):
        if pending.get("agente_leve") not in active:
            del control["rotinas_suspensas"][pid]
    for aid, key, signal in deadline_events(state, index, control["prazos"], now):
        _enqueue(world, aid, "prazo:" + key, signal)
        control["prazos"][f"{aid}:{key}"] = signal["assinatura"]


def _rank(causes: dict) -> tuple:
    return min((0 if c["tipo"] == "prazo" else 1, _minute(c["em"]), key)
               for key, c in causes.items())


def dispatch(world: dict, index: dict) -> None:
    """Mantém o teto global existente de pendências leves. Rotinas são suspensas."""
    control = _control(world)
    waiting = control["aguardando"]
    suspended = control["rotinas_suspensas"]
    active = _active(index)
    limit = int(index["orcamento"]["max_pendencias_abertas"])
    light = [p for p in world["pendencias"] if p.get("tipo") == "reavaliar_agente_leve"]
    for pending in light:
        aid = pending.get("agente_leve")
        if aid in waiting:
            pending.setdefault(PENDING_KEY, {}).update(waiting.pop(aid))
    for aid in sorted(list(waiting), key=lambda x: (_rank(waiting[x]), x)):
        if aid not in active:
            del waiting[aid]
            continue
        if len(light) >= limit:
            routines = [p for p in light if PENDING_KEY not in p]
            if not routines:
                break
            victim = max(routines, key=lambda p: (_minute(p["disparado_em"]), p["id"]))
            suspended[victim["id"]] = victim
            world["pendencias"].remove(victim)
            light.remove(victim)
        causes = waiting.pop(aid)
        previous = next((p for p in suspended.values() if p.get("agente_leve") == aid), None)
        if previous is not None:
            pending = suspended.pop(previous["id"])
            pending[PENDING_KEY] = causes
        else:
            when = min((c["em"] for c in causes.values()), key=_minute)
            pid = "mundo-" + hashlib.sha256(_json([aid, causes]).encode("utf-8")).hexdigest()[:16]
            pending = {"id": pid, "tipo": "reavaliar_agente_leve", "agente_leve": aid,
                       "agentes_afetados": [], "disparado_em": deepcopy(when),
                       "motivo": "Condição causal atingida; avaliar a resposta possível, não presumir sucesso ou presença.",
                       "origem": f"nv07:{aid}", PENDING_KEY: causes}
        world["pendencias"].append(pending)
        light.append(pending)
    for pid in sorted(list(suspended), key=lambda x: (_minute(suspended[x]["disparado_em"]), x)):
        if len(light) >= limit:
            break
        pending = suspended[pid]
        if any(p.get("agente_leve") == pending.get("agente_leve") for p in light):
            continue
        world["pendencias"].append(suspended.pop(pid))
        light.append(pending)
    _validate_control(world)


def _effective(repo: Path, records: list) -> tuple[dict, dict]:
    import transacoes
    import tempo_transacional
    state, _ = transacoes.overlay_target(_read(repo, STATE), records, "estado")
    time = _read(repo, TIME)
    for record in tempo_transacional.expand_records(records):
        for delta in record.get("deltas") or []:
            if delta.get("visibilidade", "operacional") != "operacional" or delta.get("op") != "set":
                continue
            if delta.get("alvo") == "tempo" and delta.get("caminho") in {"data_atual", "data", "hora_aproximada"}:
                time[delta["caminho"]] = delta.get("valor")
    return state, _instant(time)


def _changed_source(repo: Path, source: str, prior: list, current: dict) -> bool:
    import transacoes
    document = _read(repo, Path(source))
    kind = "relacao" if source.startswith("estado/relacoes/") else "npc"
    aid = document.get("id", Path(source).stem)
    before, _ = transacoes.overlay_target(document[kind], prior, f"{kind}:{aid}")
    after, _ = transacoes.overlay_target(before, [current], f"{kind}:{aid}")
    return before != after


def checkpoint_trigger(repo: Path, prior: list, record: dict) -> dict | None:
    """Zero leitura no turno sem relação, medidor, compromisso ou tempo alterados."""
    import tempo_transacional
    deltas = record.get("deltas") or []
    touched = {s for d in deltas if (s := _source(d)) is not None}
    commitments_changed = any(_commitment_delta(d) for d in deltas)
    time_changed = tempo_transacional.has_instant_change(deltas)
    if not (touched or commitments_changed or time_changed) or not configured(repo):
        return None
    if any(str(t).startswith("resolver-pendencia-mundo:") for t in record.get("tags") or []):
        return None
    import agentes_leves
    index = agentes_leves.load_index(repo)
    cache: dict = {}
    touched = {s for d in deltas if (s := _source(d, repo, cache)) is not None}
    dependencies = _dependencies(index, repo, cache)
    prior = [r for r in prior if r.get("sessao") == record.get("sessao")]
    if not (touched & dependencies.keys() or commitments_changed or time_changed):
        return None
    changed = any(_changed_source(repo, source, prior, record) for source in sorted(touched & dependencies.keys()))
    effective, now = _effective(repo, [*prior, record])
    if commitments_changed:
        previous, _ = _effective(repo, prior)
        before, after = _commitments(previous), _commitments(effective)
        changed |= any(before.get(cid) != after.get(cid) and
                       (set((before.get(cid) or {}).get("envolvidos") or []) |
                        set((after.get(cid) or {}).get("envolvidos") or [])) & set(_active(index))
                       for cid in before.keys() | after.keys())
    world = _read(repo, WORLD)
    receipts = (world.get(KEY) or {}).get("prazos") or {}
    due = deadline_events(effective, index, receipts, now) if time_changed or commitments_changed else []
    if not changed and not due:
        return None
    return {"motivo": "prazo_relevante" if due else "acontecimento_relevante",
            "minutos_desde_checkpoint": max(0, _minute(now) - _minute(world["processado_ate"])),
            "tempo_efetivo": now}


def stage(repo: Path, plan: dict | None, records: list) -> None:
    """Sinais e marcador entram no MESMO journal da mudança canônica: sem janela perdida."""
    if plan is None or not records or not configured(repo):
        return
    import agentes_leves
    import barreira_mundo
    import tempo_transacional
    cache: dict = {}
    touched = {s for r in records for d in r.get("deltas", []) if (s := _source(d, repo, cache)) is not None}
    commitment_change = any(_commitment_delta(d) for r in records for d in r.get("deltas", []))
    time_change = any(tempo_transacional.has_instant_change(r.get("deltas", [])) for r in records)
    if not (touched or commitment_change or time_change):
        return
    index = agentes_leves.load_index(repo)
    outputs = plan["outputs"]
    world = _read(repo, WORLD, outputs)
    original = deepcopy(world)
    dependencies = _dependencies(index, repo, cache)
    now = _instant(_read(repo, TIME, outputs))
    pending_agents = {p["id"]: p.get("agente_leve") for p in world["pendencias"]}
    for source in sorted(touched & dependencies.keys() & outputs.keys()):
        kind = "relacao" if source.startswith("estado/relacoes/") else "npc"
        if _read(repo, Path(source)).get(kind) == _read(repo, Path(source), outputs).get(kind):
            continue
        for aid in sorted(dependencies[source]):
            origins = []
            for record in records:
                if not any(_source(d, repo, cache) == source for d in record.get("deltas", [])):
                    continue
                resolving = {pending_agents.get(str(t).split(":", 1)[1]) for t in record.get("tags") or []
                             if str(t).startswith("resolver-pendencia-mundo:")}
                if aid not in resolving:
                    origins.append(record["id"])
            if origins:
                _enqueue(world, aid, source, {"tipo": "mudanca", "fonte": source, "em": now,
                         "assinatura": _digest([plan["batch"], source, origins]), "lote": plan["batch"]})
    if commitment_change:
        before = _commitments(_read(repo, STATE))
        after = _commitments(_read(repo, STATE, outputs))
        for cid in sorted(before.keys() | after.keys()):
            if before.get(cid) == after.get(cid):
                continue
            involved = (set((before.get(cid) or {}).get("envolvidos") or []) |
                        set((after.get(cid) or {}).get("envolvidos") or [])) & set(_active(index))
            for aid in sorted(involved):
                relevant = [r for r in records if any(
                    _commitment_delta(d) and d.get("caminho") == f"compromissos.{cid}"
                    for d in r.get("deltas", []))]
                if relevant and all(any(
                    pending_agents.get(str(t).split(":", 1)[1]) == aid
                    for t in r.get("tags") or [] if str(t).startswith("resolver-pendencia-mundo:"))
                    for r in relevant):
                    continue
                _enqueue(world, aid, f"compromisso:{cid}", {
                    "tipo": "mudanca", "fonte": f"{STATE.as_posix()}:compromissos.{cid}",
                    "em": now, "assinatura": _digest([plan["batch"], cid]), "lote": plan["batch"],
                })
    if commitment_change or time_change:
        _refresh_deadlines(world, _read(repo, STATE, outputs), index, now)
    empty = {"versao": 1, "aguardando": {}, "prazos": {}, "rotinas_suspensas": {}}
    if KEY not in original and world.get(KEY) == empty:
        world.pop(KEY, None)
    if world == original:
        return
    dispatch(world, index)
    outputs[WORLD.as_posix()] = yaml.safe_dump(world, allow_unicode=True, sort_keys=False).encode("utf-8")
    outputs[BARRIER.as_posix()] = yaml.safe_dump(barreira_mundo.payload_from_state(world), allow_unicode=True, sort_keys=False).encode("utf-8")
    session = plan["sessao"]
    ledger_path = f"sessoes/{session:03d}/consolidacoes.jsonl"
    if ledger_path in outputs:
        rows = [json.loads(line) for line in outputs[ledger_path].decode("utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("id") == plan["batch"]:
                row["arquivos_afetados"] = sorted(set(row.get("arquivos_afetados") or []) | {WORLD.as_posix(), BARRIER.as_posix()})
        outputs[ledger_path] = ("".join(_json(row) + "\n" for row in rows)).encode("utf-8")
        import _consolidar_core
        _consolidar_core._session_artifacts(repo, session, rows, plan["checkpoint_antes"],
                                           plan["checkpoint_depois"], plan["tipo"], outputs)


def reconcile(repo: Path, world: dict) -> dict:
    """Refaz prazos e repõe vagas após conclusão, inclusive no mesmo minuto/retry."""
    if not configured(repo):
        return world
    require_stable_canon(repo)
    import agentes_leves
    import mundo
    out = deepcopy(world)
    _validate_control(out)
    index = agentes_leves.load_index(repo)
    _refresh_deadlines(out, _read(repo, STATE), index, _instant(_read(repo, TIME)))
    dispatch(out, index)
    if KEY not in world and out.get(KEY) == {"versao": 1, "aguardando": {}, "prazos": {}, "rotinas_suspensas": {}}:
        out.pop(KEY, None)
    if out != world:
        mundo._atomic_write_yaml(repo / WORLD, out)
    return out


def boundary_candidates(repo: Path, start, target) -> tuple[list[tuple[int, str, str]], list[str]]:
    if not configured(repo):
        return [], []
    require_stable_canon(repo)
    import agentes_leves
    import transacoes
    index = agentes_leves.load_index(repo)
    state = _read(repo, STATE)
    session = (state.get("campanha") or {}).get("sessao_atual")
    records = transacoes.load_pending(repo)
    if type(session) is int:
        records = transacoes.pending_for_session(records, session)
    state, _ = transacoes.overlay_target(state, records, "estado")
    result = []
    for cid, record in sorted(_commitments(state).items()):
        if not set(record.get("envolvidos") or []) & set(_active(index)):
            continue
        for phase in ("inicio", "fim"):
            when = (record.get("janela") or {}).get(phase)
            if when is not None and start.minute < _minute(when) <= target.minute:
                result.append((_minute(when), "agentes_leves", f"compromisso:{cid}:{phase}"))
    sources = [INDEX.as_posix(), STATE.as_posix()]
    if (repo / transacoes.PENDING_PATH).is_file():
        sources.append(transacoes.PENDING_PATH.as_posix())
    return result, sources


def pending_context(repo: Path, pending: dict) -> dict:
    """Um fragmento dirigido por pendência, no lugar do perfil rotineiro estático.

    Outros domínios/perfil permanecem disponíveis por aprofundamento explícito.
    Os hashes integrais detectam staleness até quando a seleção omitir um campo.
    """
    require_stable_canon(repo)
    import memoria_cena as memory
    import transacoes
    import compromissos
    reader, state, records, _ = memory.load_scene(repo)
    aid = pending["agente_leve"]
    indexes = reader.indexes()
    choices = [("relacao", indexes[1].get(aid)), ("npc", indexes[0].get(aid))]
    changed = {c["fonte"] for c in pending[PENDING_KEY].values() if c["tipo"] == "mudanca"}
    choices.sort(key=lambda item: ((item[1] or {}).get("arquivo") not in changed, item[0] != "relacao"))
    result: dict[str, Any] = {"encontrado": any(entry for _, entry in choices)}
    full_source = None
    selected = None
    for kind, entry in choices:
        if not isinstance(entry, dict) or not entry.get("arquivo"):
            continue
        relative = _entity_path(reader.repo, kind, aid, reader.docs)
        document = reader.read(relative)
        if document.get("id", aid) != aid or not isinstance(document.get(kind), dict):
            raise ActivationError("fragmento causal não corresponde ao participante")
        effective, _ = transacoes.overlay_target(document[kind], records, f"{kind}:{aid}")
        result["relacao" if kind == "relacao" else "medidores"] = {"id": aid, "dados": effective}
        full_source, selected = effective, relative
        break
    role = (indexes[2].get(aid) or {}).get("papel_conversacional")
    if role is not None:
        result["textura_narrativa"] = {"papel_conversacional": deepcopy(role)}
    docs = {aid: {"consulta": {"comando": "npc", "termo": aid}, "fontes": reader.sources,
                  "resultado": result}}
    applicable = {cid: raw for cid, raw in _commitments(state).items()
                  if aid in (raw.get("envolvidos") or [])}
    commitments = compromissos.runtime_bundle(applicable, *memory._time(state, records),
                                              limit=max(1, len(applicable)))
    if commitments:
        docs["@compromissos"] = commitments["itens"]
    causes = [{k: c[k] for k in ("tipo", "fonte", "compromisso", "fase", "em") if k in c
               and not (k == "fonte" and c["tipo"] == "prazo")}
              for _, c in sorted(pending[PENDING_KEY].items())]
    context = {"causas": causes, "base_fonte": _digest([full_source, applicable]),
               "fragmento": selected,
               "fontes_lidas": sorted(set(reader.sources)),
               "consulta_perfil": f"poetry run python ferramentas/agentes_leves.py mostrar {aid}",
               "regra": "Avaliar em lote; prazo não depende de ação de Ren. Conhecimento, presença e sucesso não são concedidos. Aprofundar só lacuna necessária."}
    budget = MAX_CONTEXT_BYTES - _size(context) - 160
    while budget >= 200:
        pack = memory.project(docs, scope=_digest([aid, pending[PENDING_KEY]]), budget=budget)
        output = {**context, "memoria_atual": pack}
        if _size(output) <= MAX_CONTEXT_BYTES:
            return output
        budget -= 128
    raise ActivationError("contexto causal excede teto; aprofundamento dirigido necessário")
