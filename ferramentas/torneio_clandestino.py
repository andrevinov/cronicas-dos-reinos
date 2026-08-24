#!/usr/bin/env python3
"""Task 37 — mini-arco secreto de torneio clandestino, sem scheduler.

O convite só aparece em encontro explícito com o NPC roteado. Aceite ancora cinco
noites relativas ao instante canônico; ``fronteira_mundo`` usa esse estado somente
quando há compressão temporal. Cada rodada abre exatamente um fragmento reservado.
Nenhuma função decide fala, identidade, vitória ou ação de Ren.
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

import agentes
import arco_mundo
import entradas
import estado_relacional
import mundo
import progressao_juppongatana
import transacoes

ROOT = Path("narrador/arcos/parte_1/torneio-clandestino")
INDEX = ROOT / "index.yaml"
STATE = ROOT / "estado.yaml"
ROUNDS = ROOT / "rodadas"
SCHEMA = 1
STATE_SCHEMA = 1
MAX_STATE_BYTES = 12 * 1024
MAX_HISTORY = 24
MAX_ROUNDS = 5
MAX_SOURCE_CHARS = 120
MAX_EVIDENCE_CHARS = 420
SOURCE_PREFIXES = ("sessoes/", "historico/", "estado/")
VALID_STATES = {"latente", "convidado", "ativo", "recusado", "eliminado", "abandonado", "encerrado"}
VALID_OUTCOMES = {"vitoria", "derrota", "abandono", "ausencia"}
LOSS_OUTCOMES = {"derrota", "ausencia"}
VALID_PERSONAS = {"ren", "kage", "shinta", "outra"}
VALID_PRIZES = {
    "indisponivel",
    "parcial_disponivel",
    "integral_disponivel",
    "parcial_entregue",
    "integral_entregue",
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


class TournamentError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TournamentError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise TournamentError(f"YAML invalido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TournamentError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TournamentError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TournamentError(f"{label} deve ser texto nao vazio")
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise TournamentError(f"{label} excede {maximum} caracteres")
    return result


def _atomic(path: Path, data: dict[str, Any]) -> None:
    rendered = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    size = len(rendered.encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise TournamentError(f"estado do torneio excederia {MAX_STATE_BYTES} bytes: {size}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _safe_fragment(value: Any, label: str) -> str:
    raw = _text(value, label)
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or ROOT not in path.parents:
        raise TournamentError(f"{label} precisa ficar sob {ROOT.as_posix()}")
    return raw


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_torneio_clandestino") != SCHEMA or data.get("natureza") != "reservado":
        raise TournamentError("indice do torneio clandestino invalido")
    if data.get("estatuto") != "mini_arco_opcional_multinoite":
        raise TournamentError("estatuto do torneio inesperado")
    _text(data.get("id"), "torneio.id")
    invite = _map(data.get("convite"), "convite")
    if invite.get("npc") != "luath" or invite.get("exige_encontro_explicito") is not True:
        raise TournamentError("convite deve permanecer dirigido a encontro explicito com Luath")
    if not isinstance(invite.get("nivel_minimo"), int) or invite["nivel_minimo"] < 1:
        raise TournamentError("convite.nivel_minimo invalido")
    if not isinstance(invite.get("confianca_minima"), int) or not 0 <= invite["confianca_minima"] <= 10:
        raise TournamentError("convite.confianca_minima invalida")
    mundo.parse_instant(_text(invite.get("data_minima"), "convite.data_minima"), "00:00")
    _safe_fragment(invite.get("fragmento"), "convite.fragmento")
    if invite.get("recusa_permitida") is not True:
        raise TournamentError("convite precisa permitir recusa")

    schedule = _list(data.get("agenda_relativa"), "agenda_relativa")
    if len(schedule) != MAX_ROUNDS:
        raise TournamentError(f"torneio precisa de exatamente {MAX_ROUNDS} rodadas")
    seen: set[str] = set()
    previous = 0
    final_count = 0
    for pos, item in enumerate(schedule, start=1):
        item = _map(item, f"agenda_relativa[{pos - 1}]")
        rid = _text(item.get("id"), "rodada.id")
        if not ID_RE.fullmatch(rid) or rid in seen:
            raise TournamentError(f"id de rodada invalido/duplicado: {rid}")
        seen.add(rid)
        offset = item.get("offset_dias")
        if not isinstance(offset, int) or offset <= previous:
            raise TournamentError("offsets das rodadas precisam crescer estritamente")
        previous = offset
        mundo._parse_clock(_text(item.get("hora"), f"{rid}.hora"))
        _safe_fragment(item.get("fragmento"), f"{rid}.fragmento")
        final_count += int(item.get("final") is True)
    if final_count != 1 or schedule[-1].get("final") is not True:
        raise TournamentError("somente a ultima rodada pode ser final")
    if schedule[-1]["offset_dias"] not in {13, 14, 15}:
        raise TournamentError("mini-arco deve ocupar aproximadamente duas semanas")

    final = _map(data.get("final"), "final")
    candidates = _list(final.get("candidatos_prioridade"), "final.candidatos_prioridade")
    if len(candidates) < 2 or any(not isinstance(item, str) or not item for item in candidates):
        raise TournamentError("final precisa de candidatos kozakurianos de fallback")
    prize = _map(data.get("premio"), "premio")
    _safe_fragment(prize.get("fragmento"), "premio.fragmento")
    rules = _map(data.get("regras"), "regras")
    required_true = {
        "derrota_nao_e_reescrita",
        "duas_derrotas_nas_tres_primeiras_eliminam",
        "semifinal_exige_vitoria_para_final",
        "retirada_sempre_permitida",
        "ausencia_conta_como_derrota",
        "combate_nao_e_letal_por_padrao",
        "morte_intencional_nao_e_objetivo_do_torneio",
        "identidade_de_inscricao_e_escolha_do_jogador",
        "actor_nao_apaga_evidencia_fisica_ou_marcial",
        "task28_permanece_autoridade_de_identidade",
        "task54_permanece_autoridade_de_neutralizacao",
        "premio_nao_vira_conhecimento_automatico",
        "nenhum_oponente_automaticamente_vira_sidequest",
        "rodada_so_abre_um_fragmento",
    }
    if any(rules.get(key) is not True for key in required_true):
        raise TournamentError("guardrails obrigatorios do torneio precisam permanecer verdadeiros")
    if rules.get("scheduler") != "proibido" or rules.get("rng_de_progressao") != "proibido":
        raise TournamentError("torneio nao pode criar scheduler ou RNG de progressao")
    return data


def _validate_when(value: Any, label: str) -> dict[str, str] | None:
    if value is None:
        return None
    value = _map(value, label)
    instant = mundo.parse_instant(_text(value.get("data"), label + ".data"), _text(value.get("hora"), label + ".hora"))
    return mundo.instant_parts(instant)


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_torneio_clandestino") != STATE_SCHEMA:
        raise TournamentError("estado do torneio deve usar schema 1")
    if data.get("natureza") != "estado_reservado" or data.get("id") != index["id"]:
        raise TournamentError("metadados do estado do torneio invalidos")
    if data.get("estado") not in VALID_STATES:
        raise TournamentError("estado do mini-arco invalido")
    invite = _map(data.get("convite"), "estado.convite")
    _validate_when(invite.get("oferecido_em"), "convite.oferecido_em")
    _validate_when(invite.get("respondido_em"), "convite.respondido_em")
    if invite.get("resposta") not in {None, "aceitar", "recusar"}:
        raise TournamentError("convite.resposta invalida")
    reg = _map(data.get("inscricao"), "inscricao")
    _validate_when(reg.get("aceita_em"), "inscricao.aceita_em")
    if reg.get("identidade") not in {None, *VALID_PERSONAS}:
        raise TournamentError("identidade de inscricao invalida")
    if reg.get("identidade") == "outra" and not isinstance(reg.get("nome"), str):
        raise TournamentError("inscricao em outra persona exige nome")

    schedule = _list(data.get("agenda"), "estado.agenda")
    if data["estado"] in {"ativo", "eliminado", "abandonado", "encerrado"} and len(schedule) != MAX_ROUNDS:
        raise TournamentError("estado iniciado precisa preservar cinco instantes de rodada")
    if data["estado"] in {"latente", "convidado", "recusado"} and schedule:
        raise TournamentError("estado nao iniciado nao pode possuir agenda de lutas")
    expected_ids = [item["id"] for item in index["agenda_relativa"]]
    for pos, item in enumerate(schedule):
        item = _map(item, f"agenda[{pos}]")
        if item.get("id") != expected_ids[pos]:
            raise TournamentError("agenda materializada diverge da ordem secreta")
        _validate_when(item.get("em"), f"agenda[{pos}].em")

    completed = _list(data.get("rodadas_concluidas"), "rodadas_concluidas")
    if len(completed) > MAX_ROUNDS:
        raise TournamentError("mais rodadas concluidas que o quadro")
    seen: set[str] = set()
    losses = 0
    for pos, item in enumerate(completed):
        item = _map(item, f"rodadas_concluidas[{pos}]")
        rid = _text(item.get("id"), "rodada concluida.id")
        if rid in seen or rid not in expected_ids:
            raise TournamentError("rodada concluida invalida/duplicada")
        seen.add(rid)
        if expected_ids.index(rid) != pos:
            raise TournamentError("rodadas concluidas precisam preservar ordem")
        outcome = item.get("resultado")
        if outcome not in VALID_OUTCOMES:
            raise TournamentError("resultado de rodada invalido")
        _validate_when(item.get("concluida_em"), "rodada.concluida_em")
        if pos < 3 and outcome in LOSS_OUTCOMES:
            losses += 1
    if data.get("derrotas_classificatorias") != losses:
        raise TournamentError("contador de derrotas classificatorias diverge do historico")
    if not isinstance(data.get("qualificado_final"), bool):
        raise TournamentError("qualificado_final precisa ser booleano")
    prize = _map(data.get("premio"), "estado.premio")
    if prize.get("estado") not in VALID_PRIZES:
        raise TournamentError("estado de premio invalido")
    _validate_when(prize.get("entregue_em"), "premio.entregue_em")
    history = _list(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise TournamentError("historico do torneio excede teto")
    return data


def _source_evidence(repo: Path, source: Any, evidence: Any) -> tuple[str, str]:
    source = _text(source, "fonte", MAX_SOURCE_CHARS)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or not source.startswith(SOURCE_PREFIXES):
        raise TournamentError("fonte precisa ficar sob sessoes/, historico/ ou estado/")
    evidence = _text(evidence, "evidencia", MAX_EVIDENCE_CHARS)
    path = repo / rel
    if not path.is_file():
        raise TournamentError(f"fonte canonica inexistente: {source}")
    body = " ".join(path.read_text(encoding="utf-8").split())
    if " ".join(evidence.split()) not in body:
        raise TournamentError("evidencia literal nao encontrada na fonte")
    return source, evidence


def _history(state: dict[str, Any], action: str, now: mundo.WorldInstant, note: str) -> None:
    state["historico_recente"].append({"acao": action, "em": mundo.instant_parts(now), "nota": note})
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]


def _effective_luath(repo: Path) -> tuple[dict[str, Any], list[str]]:
    npc_index = _map(_load(repo / estado_relacional.NPC_INDEX), estado_relacional.NPC_INDEX.as_posix())
    entry = _map((npc_index.get("npcs") or {}).get("luath"), "npcs.luath")
    rel = _text(entry.get("arquivo"), "npcs.luath.arquivo")
    doc = _map(_load(repo / rel), rel)
    payload = _map(doc.get("npc"), rel + ".npc")
    pending = transacoes.load_pending(repo)
    effective, applied = transacoes.overlay_target(payload, pending, "npc:luath")
    meters = estado_relacional.validate_meters(effective.get("medidores"), entity_id="luath")
    sources = [estado_relacional.NPC_INDEX.as_posix(), rel]
    if applied:
        sources.append(transacoes.PENDING_PATH.as_posix())
    return meters, sources


def invitation_candidate(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    sources = [INDEX.as_posix(), STATE.as_posix()]
    if state["estado"] != "latente":
        return {"disponivel": False, "motivo": "mini_arco_ja_decidido", "fontes_lidas": sources}
    now = now or mundo.load_canonical_time(repo)[0]
    minimum = mundo.parse_instant(index["convite"]["data_minima"], "00:00")
    if now < minimum:
        return {"disponivel": False, "motivo": "janela_temporal_fechada", "fontes_lidas": sources}
    level = entradas.level(repo)
    sources.append(entradas.RUNTIME.as_posix())
    if level < index["convite"]["nivel_minimo"]:
        return {"disponivel": False, "motivo": "nivel_insuficiente", "nivel": level, "fontes_lidas": sources}
    meters, rel_sources = _effective_luath(repo)
    sources.extend(rel_sources)
    trust = meters["confianca"]
    if trust is None or trust < index["convite"]["confianca_minima"]:
        return {"disponivel": False, "motivo": "confianca_luath_insuficiente", "confianca": trust, "fontes_lidas": list(dict.fromkeys(sources))}
    fragment = index["convite"]["fragmento"]
    invite = _map(_load(repo / fragment), fragment)
    if invite.get("schema_convite_torneio_clandestino") != 1 or invite.get("npc") != "luath":
        raise TournamentError("fragmento de convite invalido")
    sources.append(fragment)
    return {
        "disponivel": True,
        "torneio": index["id"],
        "npc": "luath",
        "convite": copy.deepcopy(invite),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def offer(repo: Path, *, source: str, evidence: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    source, evidence = _source_evidence(repo, source, evidence)
    if state["estado"] == "convidado":
        if state["convite"].get("fonte") == source and state["convite"].get("evidencia") == evidence:
            return {"ok": True, "alterou": False, "resultado": "ja_oferecido"}
        raise TournamentError("convite ja foi oferecido com outra evidencia")
    if state["estado"] != "latente":
        raise TournamentError("torneio nao esta em estado latente para oferta")
    gate = invitation_candidate(repo)
    if not gate["disponivel"]:
        raise TournamentError(f"convite nao esta elegivel: {gate.get('motivo')}")
    now = mundo.load_canonical_time(repo)[0]
    state["estado"] = "convidado"
    state["convite"].update({"oferecido_em": mundo.instant_parts(now), "fonte": source, "evidencia": evidence})
    _history(state, "convite_oferecido", now, "Luath apresentou o circuito; nenhuma resposta de Ren foi presumida.")
    _atomic(repo / STATE, state)
    return {"ok": True, "alterou": True, "resultado": "convidado"}


def _scheduled_instant(base: mundo.WorldInstant, offset_days: int, clock: str) -> mundo.WorldInstant:
    day_index = base.minute // 1440 + offset_days
    return mundo.WorldInstant(day_index * 1440 + mundo._parse_clock(clock))


def respond(
    repo: Path,
    response: str,
    *,
    source: str,
    evidence: str,
    persona: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    if response not in {"aceitar", "recusar"}:
        raise TournamentError("resposta deve ser aceitar ou recusar")
    index = load_index(repo)
    state = load_state(repo, index)
    source, evidence = _source_evidence(repo, source, evidence)
    if state["estado"] in {"recusado", "ativo", "eliminado", "abandonado", "encerrado"}:
        expected = "aceitar" if state["estado"] in {"ativo", "eliminado", "abandonado", "encerrado"} else "recusar"
        if state["convite"].get("resposta") == response == expected:
            return {"ok": True, "alterou": False, "resultado": "resposta_ja_registrada"}
        raise TournamentError("convite ja possui resposta terminal")
    if state["estado"] != "convidado":
        raise TournamentError("convite ainda nao foi oferecido")
    now = mundo.load_canonical_time(repo)[0]
    state["convite"].update({"resposta": response, "respondido_em": mundo.instant_parts(now)})
    if response == "recusar":
        state["estado"] = "recusado"
        _history(state, "convite_recusado", now, "Ren recusou o circuito; nenhuma penalidade relacional automatica foi criada.")
        _atomic(repo / STATE, state)
        return {"ok": True, "alterou": True, "resultado": "recusado"}

    if persona not in VALID_PERSONAS:
        raise TournamentError("aceite exige --persona ren|kage|shinta|outra")
    if persona == "outra":
        name = _text(name, "nome de inscricao", 80)
    elif name is not None:
        name = _text(name, "nome de inscricao", 80)
    else:
        name = persona
    state["estado"] = "ativo"
    state["inscricao"] = {"aceita_em": mundo.instant_parts(now), "identidade": persona, "nome": name}
    state["agenda"] = [
        {"id": item["id"], "em": mundo.instant_parts(_scheduled_instant(now, item["offset_dias"], item["hora"]))}
        for item in index["agenda_relativa"]
    ]
    _history(state, "inscricao_aceita", now, f"Ren aceitou participar sob a inscricao escolhida ({persona}); resultados permanecem abertos.")
    _atomic(repo / STATE, state)
    return {"ok": True, "alterou": True, "resultado": "ativo", "proxima_rodada": state["agenda"][0]}


def _completed_ids(state: dict[str, Any]) -> set[str]:
    return {item["id"] for item in state["rodadas_concluidas"]}


def _next_schedule(state: dict[str, Any]) -> dict[str, Any] | None:
    done = _completed_ids(state)
    return next((item for item in state["agenda"] if item["id"] not in done), None)


def next_boundary(
    repo: Path,
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
) -> dict[str, Any]:
    if not (repo / STATE).is_file():
        return {"quando": None, "rodada": None, "fontes_lidas": []}
    raw = _map(_load(repo / STATE), STATE.as_posix())
    if raw.get("estado") != "ativo":
        return {"quando": None, "rodada": None, "fontes_lidas": [STATE.as_posix()]}
    index = load_index(repo)
    state = load_state(repo, index)
    nxt = _next_schedule(state)
    if nxt is None:
        return {"quando": None, "rodada": None, "fontes_lidas": [STATE.as_posix(), INDEX.as_posix()]}
    due = mundo.parse_instant(nxt["em"]["data"], nxt["em"]["hora"])
    if due <= start:
        return {"quando": start, "rodada": nxt["id"], "atrasada": True, "fontes_lidas": [STATE.as_posix(), INDEX.as_posix()]}
    if due <= target:
        return {"quando": due, "rodada": nxt["id"], "atrasada": False, "fontes_lidas": [STATE.as_posix(), INDEX.as_posix()]}
    return {"quando": None, "rodada": nxt["id"], "fontes_lidas": [STATE.as_posix(), INDEX.as_posix()]}


def _final_candidate(repo: Path, index: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    sources: list[str] = []
    level = entradas.level(repo)
    sources.append(entradas.RUNTIME.as_posix())
    entry_index = entradas.load_index(repo)
    entry_state = entradas.load_state(repo, entry_index)
    sources.extend([entradas.INDEX.as_posix(), entradas.STATE.as_posix()])
    neutralized = {
        item["membro"]
        for item in progressao_juppongatana.load_state(repo).get("neutralizacoes") or []
        if isinstance(item, dict) and item.get("membro")
    }
    sources.append(progressao_juppongatana.STATE.as_posix())
    for candidate in index["final"]["candidatos_prioridade"]:
        if candidate in entry_index["candidatos"]:
            meta = entry_index["candidatos"][candidate]
            state = entry_state["candidatos"][candidate]
            if state["estado"] == "inviavel" or level < meta["nivel_minimo_normal"]:
                continue
            try:
                gate = arco_mundo.entry_gate(repo, candidate)
            except arco_mundo.ArcWorldError as exc:
                raise TournamentError(str(exc)) from exc
            sources.extend(gate.get("fontes_lidas") or [])
            if not gate["permitido"]:
                continue
            return {
                "id": candidate,
                "nome": meta["nome"],
                "origem": "Kozakura",
                "estado_entrada": state["estado"],
                "confirmar_entrada_se_aparecer": state["estado"] == "latente",
            }, list(dict.fromkeys(sources))
        if candidate == "kurobane_jinzaburo":
            if candidate in neutralized:
                continue
            try:
                loaded = agentes.load_agent(repo, candidate)
            except agentes.AgentValidationError as exc:
                raise TournamentError(str(exc)) from exc
            sources.extend(loaded.get("fontes_lidas") or [])
            payload = loaded.get("resultado") or {}
            presence = payload.get("presenca") or {}
            if payload.get("estado") == "ativo" and presence.get("estado") == "presente":
                return {
                    "id": candidate,
                    "nome": "Kurobane Jinzaburo",
                    "origem": "Kozakura",
                    "estado_entrada": "ja_presente",
                    "confirmar_entrada_se_aparecer": False,
                }, list(dict.fromkeys(sources))
    return None, list(dict.fromkeys(sources))


def round_view(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    sources = [INDEX.as_posix(), STATE.as_posix()]
    if state["estado"] != "ativo":
        return {"resultado": "sem_rodada_ativa", "estado": state["estado"], "fontes_lidas": sources}
    nxt = _next_schedule(state)
    if nxt is None:
        return {"resultado": "quadro_concluido", "fontes_lidas": sources}
    now = now or mundo.load_canonical_time(repo)[0]
    due = mundo.parse_instant(nxt["em"]["data"], nxt["em"]["hora"])
    if now < due:
        return {"resultado": "aguardando", "proxima_rodada": copy.deepcopy(nxt), "fontes_lidas": sources}
    meta = next(item for item in index["agenda_relativa"] if item["id"] == nxt["id"])
    fragment = meta["fragmento"]
    detail = _map(_load(repo / fragment), fragment)
    if detail.get("schema_rodada_torneio_clandestino") != 1 or detail.get("id") != nxt["id"]:
        raise TournamentError(f"fragmento de rodada invalido: {nxt['id']}")
    sources.append(fragment)
    result = {
        "resultado": "rodada_devida",
        "rodada": nxt["id"],
        "em": copy.deepcopy(nxt["em"]),
        "atrasada": now > due,
        "inscricao": copy.deepcopy(state["inscricao"]),
        "detalhe": copy.deepcopy(detail),
        "fontes_lidas": sources,
    }
    if meta.get("final") is True:
        candidate, candidate_sources = _final_candidate(repo, index)
        sources.extend(candidate_sources)
        if candidate is None:
            result["resultado"] = "final_temporariamente_impossivel"
            result["detalhe"] = {"id": "final", "regra": "nenhum kozakuriano conhecido esta causalmente disponivel; adaptar antes de avancar"}
        else:
            result["oponente_final"] = candidate
        result["fontes_lidas"] = list(dict.fromkeys(sources))
    return result


def conclude_round(repo: Path, outcome: str, *, source: str, evidence: str) -> dict[str, Any]:
    if outcome not in VALID_OUTCOMES:
        raise TournamentError("resultado deve ser vitoria|derrota|abandono|ausencia")
    index = load_index(repo)
    state = load_state(repo, index)
    if state["estado"] != "ativo":
        raise TournamentError("nao ha rodada ativa para concluir")
    source, evidence = _source_evidence(repo, source, evidence)
    view = round_view(repo)
    if view["resultado"] == "final_temporariamente_impossivel":
        raise TournamentError("final esta causalmente impossivel; nao conclua com substituto arbitrario")
    if view["resultado"] != "rodada_devida":
        raise TournamentError("nenhuma rodada esta devida no instante canonico")
    rid = view["rodada"]
    now = mundo.load_canonical_time(repo)[0]
    state["rodadas_concluidas"].append(
        {"id": rid, "resultado": outcome, "concluida_em": mundo.instant_parts(now), "fonte": source, "evidencia": evidence}
    )
    position = [item["id"] for item in index["agenda_relativa"]].index(rid)
    if position < 3 and outcome in LOSS_OUTCOMES:
        state["derrotas_classificatorias"] += 1
    if outcome == "abandono":
        state["estado"] = "abandonado"
    elif position < 3:
        if state["derrotas_classificatorias"] >= 2:
            state["estado"] = "eliminado"
        elif position == 2:
            state["estado"] = "ativo"
    elif rid == "semifinal":
        if outcome == "vitoria":
            state["qualificado_final"] = True
            state["premio"]["estado"] = "parcial_disponivel"
        elif outcome == "derrota":
            state["estado"] = "eliminado"
            state["premio"]["estado"] = "parcial_disponivel"
        else:
            state["estado"] = "abandonado" if outcome == "abandono" else "eliminado"
    elif rid == "final":
        if not state["qualificado_final"]:
            raise TournamentError("estado incoerente: final sem qualificacao")
        if outcome == "vitoria":
            state["estado"] = "encerrado"
            state["premio"]["estado"] = "integral_disponivel"
        elif outcome == "derrota":
            state["estado"] = "encerrado"
            if state["premio"]["estado"] == "indisponivel":
                state["premio"]["estado"] = "parcial_disponivel"
        else:
            state["estado"] = "abandonado" if outcome == "abandono" else "eliminado"
    _history(state, "rodada_concluida", now, f"{rid}: {outcome}; nenhum resultado adicional foi inferido.")
    _atomic(repo / STATE, state)
    return {
        "ok": True,
        "rodada": rid,
        "resultado": outcome,
        "estado_torneio": state["estado"],
        "premio": state["premio"]["estado"],
        "proxima_rodada": _next_schedule(state),
    }


def prize_view(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    status = state["premio"]["estado"]
    if status == "indisponivel":
        return {"resultado": "indisponivel", "fontes_lidas": [STATE.as_posix()]}
    if status in {"parcial_entregue", "integral_entregue"}:
        return {"resultado": "ja_entregue", "grau": status.split("_")[0], "fontes_lidas": [STATE.as_posix()]}
    fragment = index["premio"]["fragmento"]
    data = _map(_load(repo / fragment), fragment)
    if data.get("schema_premio_torneio_clandestino") != 1:
        raise TournamentError("fragmento de premio invalido")
    tier = "integral" if status == "integral_disponivel" else "parcial"
    return {
        "resultado": "disponivel",
        "grau": tier,
        "premio": copy.deepcopy(_map(data.get(tier), tier)),
        "guardrails": list(data.get("guardrails") or []),
        "fontes_lidas": [STATE.as_posix(), fragment],
    }


def deliver_prize(repo: Path, *, source: str, evidence: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    status = state["premio"]["estado"]
    if status in {"parcial_entregue", "integral_entregue"}:
        return {"ok": True, "alterou": False, "resultado": "ja_entregue"}
    if status not in {"parcial_disponivel", "integral_disponivel"}:
        raise TournamentError("premio ainda nao esta disponivel")
    source, evidence = _source_evidence(repo, source, evidence)
    now = mundo.load_canonical_time(repo)[0]
    tier = "integral" if status == "integral_disponivel" else "parcial"
    state["premio"] = {"estado": f"{tier}_entregue", "entregue_em": mundo.instant_parts(now)}
    _history(state, "premio_entregue", now, f"Premio {tier} foi efetivamente entregue; conhecimento ainda segue pipeline normal.")
    _atomic(repo / STATE, state)
    return {"ok": True, "alterou": True, "resultado": f"{tier}_entregue", "fonte": source, "evidencia": evidence}


def status(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    return {
        "ok": True,
        "estado": state["estado"],
        "convite": {"resposta": state["convite"]["resposta"], "oferecido_em": state["convite"]["oferecido_em"]},
        "inscricao": copy.deepcopy(state["inscricao"]),
        "rodadas_concluidas": [{"id": item["id"], "resultado": item["resultado"]} for item in state["rodadas_concluidas"]],
        "proxima_rodada": _next_schedule(state),
        "premio": state["premio"]["estado"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
    }


def _validate_round(repo: Path, raw: dict[str, Any], position: int) -> tuple[str, str]:
    fragment = raw["fragmento"]
    data = _map(_load(repo / fragment), fragment)
    if data.get("schema_rodada_torneio_clandestino") != 1 or data.get("natureza") != "reservado":
        raise TournamentError(f"fragmento de rodada invalido: {raw['id']}")
    if data.get("id") != raw["id"] or data.get("ordem") != position + 1:
        raise TournamentError(f"fragmento diverge do indice: {raw['id']}")
    if raw.get("final") is True:
        if data.get("oponente_slot", {}).get("tipo") != "kozakuriano_conhecido":
            raise TournamentError("final precisa manter slot kozakuriano conhecido")
        return "kara_tur", fragment
    opponent = _map(data.get("oponente"), f"{raw['id']}.oponente")
    region = _text(opponent.get("regiao_macro"), f"{raw['id']}.regiao_macro")
    if region not in {"faerun", "kara_tur"}:
        raise TournamentError("oponente precisa pertencer a Faerun ou Kara-Tur")
    _text(opponent.get("tradicao"), f"{raw['id']}.tradicao")
    return region, fragment


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    regions: list[str] = []
    try:
        index = load_index(repo)
        load_state(repo, index)
        for position, item in enumerate(index["agenda_relativa"]):
            region, _ = _validate_round(repo, item, position)
            regions.append(region)
        if "faerun" not in regions or "kara_tur" not in regions:
            raise TournamentError("quadro precisa misturar tradicoes de Faerun e Kara-Tur")
        invite = _map(_load(repo / index["convite"]["fragmento"]), "convite")
        if invite.get("schema_convite_torneio_clandestino") != 1:
            raise TournamentError("convite secreto invalido")
        prize = _map(_load(repo / index["premio"]["fragmento"]), "premio")
        if prize.get("schema_premio_torneio_clandestino") != 1:
            raise TournamentError("premio secreto invalido")
        entry_index = entradas.load_index(repo)
        agent_index = agentes.load_index(repo)
        known = set(entry_index["candidatos"]) | set(agent_index["agentes"])
        missing = [item for item in index["final"]["candidatos_prioridade"] if item not in known]
        if missing:
            raise TournamentError("candidatos finais inexistentes: " + ", ".join(missing))
        if (repo / INDEX).stat().st_size > 12 * 1024:
            raise TournamentError("indice do torneio excede 12 KiB")
        for item in index["agenda_relativa"]:
            if (repo / item["fragmento"]).stat().st_size > 6 * 1024:
                raise TournamentError(f"fragmento de rodada excede 6 KiB: {item['id']}")
    except (TournamentError, entradas.EntryError, agentes.AgentValidationError, OSError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors, "regioes": sorted(set(regions))}


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("convite")
    offer_cmd = sub.add_parser("oferecer")
    offer_cmd.add_argument("--fonte", required=True)
    offer_cmd.add_argument("--evidencia", required=True)
    response = sub.add_parser("responder")
    response.add_argument("resposta", choices=["aceitar", "recusar"])
    response.add_argument("--fonte", required=True)
    response.add_argument("--evidencia", required=True)
    response.add_argument("--persona", choices=sorted(VALID_PERSONAS))
    response.add_argument("--nome")
    sub.add_parser("rodada")
    done = sub.add_parser("concluir")
    done.add_argument("resultado", choices=sorted(VALID_OUTCOMES))
    done.add_argument("--fonte", required=True)
    done.add_argument("--evidencia", required=True)
    sub.add_parser("premio")
    deliver = sub.add_parser("entregar-premio")
    deliver.add_argument("--fonte", required=True)
    deliver.add_argument("--evidencia", required=True)
    sub.add_parser("check")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "convite":
            result = invitation_candidate(repo)
        elif args.cmd == "oferecer":
            result = offer(repo, source=args.fonte, evidence=args.evidencia)
        elif args.cmd == "responder":
            result = respond(repo, args.resposta, source=args.fonte, evidence=args.evidencia, persona=args.persona, name=args.nome)
        elif args.cmd == "rodada":
            result = round_view(repo)
        elif args.cmd == "concluir":
            result = conclude_round(repo, args.resultado, source=args.fonte, evidence=args.evidencia)
        elif args.cmd == "premio":
            result = prize_view(repo)
        elif args.cmd == "entregar-premio":
            result = deliver_prize(repo, source=args.fonte, evidence=args.evidencia)
        else:
            result = check(repo)
        print(_dump(result), end="")
        return 0 if args.cmd != "check" or result["ok"] else 1
    except (TournamentError, mundo.WorldEngineError, entradas.EntryError, estado_relacional.RelationshipStateError, transacoes.TransactionError, OSError, yaml.YAMLError) as exc:
        print(f"erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
