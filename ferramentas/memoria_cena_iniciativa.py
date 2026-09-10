#!/usr/bin/env python3
"""Composição NV-16 sobre ``memoria_cena.attach``.

O caminho sem interlocutores delega byte-logicamente ao NV-05. Com
``--interlocutor`` a mesma leitura já necessária para a memória produz também a
decisão social, sem reabrir um fragmento por NPC.

A lista solicitada por ``--participante`` seleciona memória/elenco prospectivo;
ela não prova presença física no mesmo preparo. Presença física vem do elenco já
persistido e ainda ancorado ao local atual. Contato previamente validado fornece
a alternativa de contactabilidade.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Iterator

import iniciativa_elenco
import memoria_cena as memory

_BASE_ATTACH = memory.attach
_CURRENT: ContextVar[list[str] | None] = ContextVar("nv16_interlocutores", default=None)


@contextmanager
def interlocutors(value: list[str] | None) -> Iterator[None]:
    token = _CURRENT.set(value)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def attach(repo, prepared: dict, *, decode_ticket, encode_ticket,
           participants: list[str] | None = None, base_in_context: Any = None,
           prospective_participants: list[str] | None = None,
           max_output_bytes: int = 8192) -> dict:
    requested = _CURRENT.get()
    if requested is None:
        return _BASE_ATTACH(
            repo, prepared, decode_ticket=decode_ticket, encode_ticket=encode_ticket,
            participants=participants, base_in_context=base_in_context,
            prospective_participants=prospective_participants,
            max_output_bytes=max_output_bytes,
        )
    try:
        requested = iniciativa_elenco.normalize_interlocutors(requested)
    except iniciativa_elenco.CastInitiativeError as exc:
        raise memory.SceneMemoryError(f"NV16: {exc}") from exc

    base = memory.receipt(base_in_context)
    reader, state, records, saved = memory.load_scene(repo)
    if not state:
        raise memory.SceneMemoryError("NV16: --interlocutor exige estado canônico e elenco/contactabilidade verificáveis")
    payload = decode_ticket(prepared["ticket"])
    request = payload["cena"]
    scene_id = request["scene_id"]
    stay_window = isinstance(payload.get("permanencia_espacial"), dict)
    same_scene = saved is not None and saved["cena_id"] == scene_id
    # Permanência NV-15 congela o mesmo local atual; seu ``place`` no ticket
    # não é movimento. Fora dela, um gatilho local/transporte invalida a
    # continuidade de presença como no NV-05.
    changed_place = bool(
        (request.get("place") and not stay_window)
        or payload.get("transito_urbano")
    )
    saved_is_current = saved is not None and not changed_place and (same_scene or stay_window)
    canonical_present = list(saved["participantes"]) if saved_is_current else []

    # Memória pode ser selecionada prospectivamente; isso é deliberadamente
    # distinto da presença física já persistida acima.
    people = list(saved["participantes"]) if saved_is_current else None
    terms = participants if participants is not None else request.get("npcs") or None
    unresolved = []
    if terms is not None:
        try:
            explicit = reader.resolve(terms, reader.indexes()) if terms else []
            people = explicit if participants is not None else sorted(set((people or []) + explicit))
        except memory.SceneMemoryError:
            if participants is not None:
                raise
            people, unresolved = None, terms
    selected = (
        memory.cast({"versao": memory.VERSION, "cena_id": scene_id,
                     "local": memory.location(state), "participantes": people})
        if people is not None else None
    )
    out = deepcopy(prepared)
    memory_meta = {"elenco": selected, "anterior": saved, "local": memory.location(state)}
    if selected is not None or saved is not None:
        payload[memory.TICKET_KEY] = memory_meta

    # ``prospective_participants`` é produzido apenas por contato cujo canal e
    # chegada já passaram pelos gates próprios; ainda assim ele não vira
    # presença física — apenas contactabilidade para a decisão social.
    prospective = reader.resolve(prospective_participants, reader.indexes()) if prospective_participants else []
    memory_people = memory._ids(sorted(set((people or []) + canonical_present + prospective)))
    annotations = {"participantes_previstos": prospective} if prospective else {}
    if people is None:
        annotations.update({
            "participantes": None,
            "aprofundamento_necessario": True,
            "aviso": "Elenco não registrado para esta cena; use --participante <id> ou --sem-participantes. Menção não prova presença.",
        })

    docs = memory.documents(reader, state, records, memory_people) if memory_people else {}
    try:
        out, initiative_meta = iniciativa_elenco.attach_loaded(
            repo, out, payload,
            interlocutors=requested,
            physical=canonical_present,
            contactable=prospective,
            docs=docs,
            indexes=reader.indexes(),
            scene_mode=(state.get("campanha") or {}).get("modo_de_cena_atual"),
        )
    except iniciativa_elenco.CastInitiativeError as exc:
        raise memory.SceneMemoryError(f"NV16: {exc}") from exc
    if initiative_meta is not None:
        payload[iniciativa_elenco.TICKET_KEY] = initiative_meta
    if selected is not None or saved is not None or initiative_meta is not None:
        out["ticket"], out["ticket_id"] = encode_ticket(payload)

    if people is None and not prospective and not canonical_present:
        pack = {"versao": memory.VERSION, "modo": "completa", **annotations}
    else:
        scope = memory.digest([
            memory.VERSION, (state.get("campanha") or {}).get("sessao_atual"),
            scene_id, memory.location(state),
        ])
        # Mantém o teto anterior: NV-16 consome parte do mesmo envelope e a
        # memória usa apenas o restante, inclusive sua própria anotação.
        budget = min(memory.MAX_MEMORY_BYTES, max_output_bytes - memory.size(out) - 300)
        budget -= memory.size(annotations) if annotations else 0
        pack = {**memory.project(docs, scope=scope, budget=max(0, budget), base=base, sources=reader.sources), **annotations}
        while budget >= 400 and memory.size({**out, memory.KEY: pack}) > max_output_bytes:
            budget -= 128
            pack = {**memory.project(docs, scope=scope, budget=budget, base=base, sources=reader.sources), **annotations}
    if unresolved:
        pack["participantes_sem_memoria"] = unresolved
    out[memory.KEY] = pack
    if memory.size(out) > max_output_bytes:
        raise memory.SceneMemoryError("NV16: preparo sem espaço para memória+decisão indispensáveis; refine a cena, sem elevar teto")
    return out


memory.attach = attach
