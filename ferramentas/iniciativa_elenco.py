#!/usr/bin/env python3
"""NV-16 — iniciativa explicitamente decidida para o elenco presente.

Recebe interlocutores explícitos e reutiliza memória/relação já carregadas. Não
cria presença, encontro, side quest, scheduler, RNG ou consulta por NPC.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

import iniciativa_elenco_estado as receipts
import iniciativa_social
import pressao_narrativa

SCHEMA = 1
PUBLIC_KEY = "iniciativa_elenco"
TICKET_KEY = "iniciativa_elenco_nv16"
TRANSACTION_KEY = "iniciativa_elenco"
MAX_INTERLOCUTORS = 6
MAX_OPENINGS_PER_WINDOW = 1
MAX_PUBLIC_BYTES = 3072
MAX_TICKET_BYTES = 4096
ID = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
SILENCE_REASONS = {
    "sem_motivo_concreto", "repeticao_sem_causa_nova", "janela_ocupada",
    "risco", "indisponibilidade",
}
INELIGIBLE_REASONS = {"ausencia", "falta_conhecimento", "risco", "indisponibilidade"}


class CastInitiativeError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _text(value: Any, label: str, minimum: int = 1, maximum: int = 320) -> str:
    if not isinstance(value, str):
        raise CastInitiativeError(f"{label} deve ser texto")
    value = " ".join(value.strip().split())
    if not minimum <= len(value) <= maximum:
        raise CastInitiativeError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return value


def _npc(value: Any, label: str = "interlocutor") -> str:
    value = _text(value, label, maximum=80)
    if value == "ren" or not ID.fullmatch(value):
        raise CastInitiativeError(f"{label} deve usar ID canônico de NPC")
    return value


def normalize_interlocutors(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_INTERLOCUTORS:
        raise CastInitiativeError("--interlocutor exige 1..6 IDs canônicos")
    result = [_npc(item, f"interlocutor[{pos}]") for pos, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise CastInitiativeError("--interlocutor não aceita duplicatas")
    return result


def _window(payload: dict[str, Any]) -> tuple[str, str, str]:
    scene = payload.get("cena") or {}
    scene_id = _text(scene.get("scene_id"), "ticket.cena.scene_id", maximum=160)
    stay = payload.get("permanencia_espacial")
    if isinstance(stay, dict):
        identity = {key: stay.get(key) for key in ("local_id", "data", "periodo")}
        if all(isinstance(value, str) and value.strip() for value in identity.values()):
            return "conv-" + _digest(identity)[:20], "permanencia", scene_id
    return "cena-" + _digest(scene_id)[:20], "cena", scene_id


def _known(npc_id: str, indexes: list[dict[str, Any]]) -> bool:
    # Apenas membership nos índices compactos; não itera o cadastro inteiro.
    return any(isinstance(index, dict) and npc_id in index for index in indexes)


def _social(doc: Any) -> dict[str, Any] | None:
    result = doc.get("resultado") if isinstance(doc, dict) else None
    dialogue = result.get("dialogo_relacional") if isinstance(result, dict) else None
    social = dialogue.get("iniciativa_social") if isinstance(dialogue, dict) else None
    if not isinstance(social, dict):
        return None
    try:
        return iniciativa_social.validate_projection(copy.deepcopy(social))
    except ValueError as exc:
        raise CastInitiativeError(str(exc)) from exc


def _motive(docs: dict[str, Any], npc_id: str) -> tuple[str | None, bool]:
    rows = docs.get("@compromissos")
    if not isinstance(rows, dict):
        return None, False
    priority = {"janela_encerrada": 0, "em_janela": 1, "devido": 2, "ate_limite": 3,
                "sem_instante_exato": 4, "sem_data": 5}
    candidates = [
        (priority[row["situacao_temporal"]], str(cid))
        for cid, row in rows.items()
        if isinstance(row, dict) and npc_id in (row.get("envolvidos") or [])
        and row.get("situacao_temporal") in priority
    ]
    if not candidates:
        return None, False
    return "compromisso:" + min(candidates)[1], True


def _blockers(prepared: dict[str, Any], payload: dict[str, Any], scene_mode: str | None) -> list[str]:
    weighted: list[tuple[int, str]] = []
    for item in (prepared.get("pressao_narrativa") or {}).get("itens", []):
        if not isinstance(item, dict):
            continue
        priority = pressao_narrativa.PRIORITIES.get(item.get("tipo"), 99)
        if priority < pressao_narrativa.PRIORITIES["iniciativa_social"]:
            weighted.append((priority, str(item.get("id") or item.get("tipo"))))
    contact = prepared.get("contato_social")
    if isinstance(contact, dict) and contact.get("plano_id"):
        weighted.append((5, "contato_social:" + str(contact["plano_id"])))
    stay = prepared.get("permanencia_espacial")
    if isinstance(stay, dict) and stay.get("pressao_primaria"):
        weighted.append((6, "permanencia_espacial:" + str(stay["pressao_primaria"])))
    if (payload.get("cena") or {}).get("npcs"):
        weighted.append((5, "acao_social_solicitada"))
    if scene_mode in {"combate", "perigo_imediato"}:
        weighted.append((2, "modo_de_cena:" + scene_mode))
    return [item for _, item in sorted(set(weighted))]


def _proposal(social: dict[str, Any], cause: str | None) -> dict[str, Any]:
    return {"modo": social["modo"], "pode_iniciar": social["pode_iniciar"],
            "exige_motivo": social["exige_motivo"], "risco_alto": social["risco_alto"],
            "escopo": list(social["escopo"]), "causa_id": cause}


def _row(decision_id: str, npc_id: str, presence: str, proposal_digest: str, *,
         required: bool = False, automatic: str | None = None, reason: str | None = None,
         blocker: str | None = None, requires_motive: bool = False, reused: bool = False) -> dict[str, Any]:
    return {"decisao_id": decision_id, "npc_id": npc_id, "presenca": presence,
            "proposta_digest": proposal_digest, "requer_decisao": required,
            "resultado_automatico": automatic, "motivo_automatico": reason,
            "pressao_superior": blocker, "exige_motivo": requires_motive, "reutilizado": reused}


def _decision(window: str, npc: str, proposal: str) -> str:
    return "ini-" + _digest([window, npc, proposal])[:20]


def _from_receipt(raw: dict[str, Any]) -> dict[str, Any]:
    # Uma abertura já apresentada vira silêncio estrutural na projeção seguinte;
    # o recibo original permanece terminal e não é reescrito.
    if raw["resultado"] == "apresentada":
        automatic, reason = "silencio_justificado", "repeticao_sem_causa_nova"
    else:
        automatic, reason = raw["resultado"], raw.get("motivo_codigo")
    return _row(raw["id"], raw["npc_id"], raw["presenca"], raw["proposta_digest"],
                automatic=automatic, reason=reason,
                blocker=raw.get("pressao_superior"), reused=True)


def attach_loaded(repo: Path, prepared: dict[str, Any], payload: dict[str, Any], *,
                  interlocutors: list[str] | None, physical: list[str] | None,
                  contactable: list[str] | None, docs: dict[str, Any],
                  indexes: list[dict[str, Any]], scene_mode: str | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if interlocutors is None:
        return prepared, None
    people = normalize_interlocutors(interlocutors)
    physical_set, contactable_set = set(physical or []), set(contactable or [])
    window, window_type, scene_id = _window(payload)
    blockers = _blockers(prepared, payload, scene_mode)
    higher = blockers[0] if blockers else None
    try:
        state = receipts.load(repo)
    except receipts.InitiativeStateError as exc:
        raise CastInitiativeError(str(exc)) from exc
    presented = any(r.get("janela_id") == window and r.get("resultado") == "apresentada" for r in state["decisoes"].values())
    rows, proposals, pressures, candidates = [], {}, {}, []

    for npc_id in people:
        if not _known(npc_id, indexes):
            raise CastInitiativeError(f"interlocutor desconhecido: {npc_id}; use ID canônico")
        presence = "canal_contato" if npc_id in contactable_set else "elenco_cena" if npc_id in physical_set else "ausente"
        if presence == "ausente":
            digest = _digest([npc_id, presence]); did = _decision(window, npc_id, digest)
            existing = state["decisoes"].get(did)
            rows.append(_from_receipt(existing) if isinstance(existing, dict) else _row(did, npc_id, presence, digest, automatic="nao_elegivel", reason="ausencia"))
            continue
        social = _social(docs.get(npc_id))
        if social is None or social.get("identidade_relacional") != "ren":
            digest = _digest([npc_id, presence, None]); did = _decision(window, npc_id, digest)
            existing = state["decisoes"].get(did)
            rows.append(_from_receipt(existing) if isinstance(existing, dict) else _row(did, npc_id, presence, digest, automatic="nao_elegivel", reason="indisponibilidade"))
            continue
        cause, known = _motive(docs, npc_id)
        proposal = _proposal(social, cause); digest = _digest(proposal); did = _decision(window, npc_id, digest)
        existing = state["decisoes"].get(did)
        if isinstance(existing, dict) and existing.get("resultado") in receipts.TERMINAL_RESULTS:
            rows.append(_from_receipt(existing)); continue
        try:
            pressure = pressao_narrativa.project_social_pressure(social, npc_id=npc_id,
                presence_authorized=True, cause_id=cause, cause_known=known)
        except pressao_narrativa.NarrativePressureError as exc:
            raise CastInitiativeError(str(exc)) from exc
        if pressure is None:
            rows.append(_row(did, npc_id, presence, digest, automatic="silencio_justificado", reason="sem_motivo_concreto")); continue
        proposals[did], pressures[did] = proposal, pressure
        if higher is not None:
            if isinstance(existing, dict) and existing.get("resultado") == "adiada_por_pressao_superior" and existing.get("pressao_superior") == higher:
                rows.append(_from_receipt(existing))
            else:
                rows.append(_row(did, npc_id, presence, digest, automatic="adiada_por_pressao_superior", reason="pressao_superior", blocker=higher))
            continue
        if presented:
            rows.append(_row(did, npc_id, presence, digest, automatic="silencio_justificado", reason="janela_ocupada")); continue
        candidates.append((1 if social["exige_motivo"] else 0, 1 if social["risco_alto"] else 0, npc_id, did))
        rows.append(_row(did, npc_id, presence, digest, required=True, requires_motive=bool(social["exige_motivo"])))

    selected = min(candidates)[3] if candidates else None
    for row in rows:
        if row["requer_decisao"] and row["decisao_id"] != selected:
            row.update(requer_decisao=False, resultado_automatico="silencio_justificado", motivo_automatico="janela_ocupada")
    public_rows = []
    for row in rows:
        view = {key: copy.deepcopy(row[key]) for key in ("decisao_id", "npc_id", "presenca", "requer_decisao", "resultado_automatico", "motivo_automatico", "pressao_superior", "reutilizado")}
        if row["decisao_id"] == selected:
            view["proposta"] = proposals[selected]
        public_rows.append(view)
    public = {"schema_iniciativa_elenco": SCHEMA, "sistema": "iniciativa_social",
              "janela_id": window, "janela_tipo": window_type,
              "interlocutores": people, "selecionada": selected, "itens": public_rows,
              "regra": "participante, presença/contactabilidade e interlocutor são distintos; no máximo uma abertura por janela; Ren conserva sua resposta",
              "metricas": {"interlocutores": len(people), "aberturas": 1 if selected else 0,
                           "consultas_adicionais_por_npc": 0, "chamadas_ia": 0, "rng_novo": 0, "scheduler_novo": 0, "scan_global": 0}}
    if _size(public) > MAX_PUBLIC_BYTES:
        raise CastInitiativeError("projeção de iniciativa excede orçamento")
    out = copy.deepcopy(prepared); out[PUBLIC_KEY] = public
    out.setdefault("contrato_conclusao", {})[PUBLIC_KEY] = (
        "Se selecionada != null, iniciativa_elenco deve decidir a decisão selecionada; apresentada exige evidencia_literal; "
        "silencio_justificado/nao_elegivel exigem motivo_codigo+motivo. Sem selecionada, omitir o bloco."
    )
    if selected is not None:
        current = out.get("pressao_narrativa")
        if isinstance(current, dict):
            view = copy.deepcopy(current); view["itens"] = pressao_narrativa.sort_items([*(view.get("itens") or []), pressures[selected]])
        else:
            view = {"schema_pressao_narrativa": pressao_narrativa.SCHEMA, "itens": [pressures[selected]],
                    "regra_ordem": "prioridade organiza atenção e nunca escolhe resposta de Ren",
                    "metricas": {"rng_novo": 0, "scheduler_novo": 0, "scan_global": 0}}
        out["pressao_narrativa"] = view
    meta = {"schema": SCHEMA, "janela_id": window, "janela_tipo": window_type, "cena_id": scene_id,
            "selecionada": selected, "itens": copy.deepcopy(rows)}
    if _size(meta) > MAX_TICKET_BYTES:
        raise CastInitiativeError("ticket de iniciativa excede orçamento")
    out["fontes_lidas"] = list(dict.fromkeys([*(out.get("fontes_lidas") or []), receipts.STATE.as_posix()]))
    return out, meta
