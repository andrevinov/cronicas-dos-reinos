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


def _compact_spatial_envelope(out):
    """Instruções equivalentes; decisões, gates, fonte e reserva ficam completas."""
    projection = out.get("permanencia_espacial")
    if not isinstance(projection, dict):
        return
    # Proveniência agregada da mesma orquestração, compartilhada como alias
    # YAML. Não suprime caminhos nem implica consulta adicional.
    sources = list(dict.fromkeys([*(projection.get("fontes_lidas") or []), *(out.get("fontes_lidas") or [])]))
    projection["fontes_lidas"] = out["fontes_lidas"] = sources
    contract = out.get("contrato_conclusao") or {}
    if "comando" in contract:
        contract["comando"] = "cronica concluir --ticket <ticket>"
    fields = contract.get("campos") or {}
    if "jogador" in fields:
        fields["jogador"] = "<entrada ON>"
    if "resumo" in fields:
        fields["resumo"] = "<mudança relevante>"
    if "modo" in fields:
        fields["modo"] = "<modo coerente>"
    for key, text in {
        "mecanica": "Número explícito na prosa exige linha `MECÂNICA — ...`.",
        "disciplina": "Ticket completo; não ticket_id/redescoberta de sintaxe.",
        "retry_espacial": "Retry: mesma cena+gatilho+reserva; não usar ticket neutro.",
        "iniciativa_elenco": "selecionada != null: decidir; apresentada exige evidencia_literal; silencio_justificado/nao_elegivel exigem motivo_codigo+motivo. Senão omitir.",
    }.items():
        if key in contract:
            contract[key] = text
    card = (projection.get("microevento_local") or {}).get("carta") or {}
    equivalents = {
        "Usar somente papéis anônimos compatíveis com a ecologia, salvo NPC já estabelecido por outra fonte.": "Papéis anônimos compatíveis; NPC nomeado já estabelecido por fonte.",
        "Não transformar inconveniência cotidiana em combate, crime grave, pista secreta, missão ou recompensa automática.": "Não converter rotina em combate/crime grave/pista secreta/quest/recompensa automáticos.",
        "Estado canônico, arco, cena aceita e pendências prevalecem; incompatibilidade consome a carta sem rerrolar outra.": "Cânone/arco/cena aceita/pendências prevalecem; carta incompatível consome sem rerroll.",
    }
    if "guardrails" in card:
        card["guardrails"] = [equivalents.get(rule, rule) for rule in card["guardrails"]]
    projection["regra"] = "Janela local/data/período congelada; candidato não é fato; sem rerroll; ausência explícita."
    out["iniciativa_elenco"]["regra"] = "Memória não prova presença/canal; 1 abertura/janela; Ren decide resposta."
    if "entrada" in (out.get("proximo_passo") or {}):
        out["proximo_passo"]["entrada"] = "Contrato de conclusão; JSON por stdin, sem arquivo temporário."


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
    current = memory.continuing_cast(payload, saved, memory.location(state))
    physical_scene_id = current["cena_id"] if current is not None else scene_id
    canonical_present = list(current["participantes"]) if current is not None else []

    # Memória pode ser selecionada prospectivamente; isso é deliberadamente
    # distinto da presença física já persistida acima.
    people = list(current["participantes"]) if current is not None else None
    terms = participants if participants is not None else request.get("npcs") or None
    unresolved = []
    indexes = reader.indexes()
    if terms is not None:
        try:
            explicit = reader.resolve(terms, indexes) if terms else []
            people = explicit if participants is not None else sorted(set((people or []) + explicit))
        except memory.SceneMemoryError:
            if participants is not None:
                raise
            people, unresolved = None, terms
    if participants is not None:
        # Declaração completa: quem foi retirado não permanece interlocutor
        # físico. Novos IDs continuam apenas prospectivos neste preparo.
        canonical_present = [npc for npc in canonical_present if npc in (people or [])]
    selected = (
        memory.cast({"versao": memory.VERSION, "cena_id": physical_scene_id,
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
    prospective = reader.resolve(prospective_participants, indexes) if prospective_participants else []
    present_needed = set(requested) & set(canonical_present)
    memory_people = memory._ids(sorted(set((people or []) + prospective + list(present_needed))))
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
            mentioned=people,
            docs=docs,
            indexes=indexes,
            scene_mode=(state.get("campanha") or {}).get("modo_de_cena_atual"),
        )
    except iniciativa_elenco.CastInitiativeError as exc:
        raise memory.SceneMemoryError(f"NV16: {exc}") from exc
    if initiative_meta is not None:
        payload[iniciativa_elenco.TICKET_KEY] = initiative_meta
    if selected is not None or saved is not None or initiative_meta is not None:
        out["ticket"], out["ticket_id"] = encode_ticket(payload)

    _compact_spatial_envelope(out)

    if people is None and not prospective and not canonical_present:
        pack = {"versao": memory.VERSION, "modo": "completa", **annotations}
    else:
        scope = memory.digest([
            memory.VERSION, (state.get("campanha") or {}).get("sessao_atual"),
            physical_scene_id, memory.location(state),
        ])
        # Mantém o teto anterior: NV-16 consome parte do mesmo envelope e a
        # memória usa apenas o restante, inclusive sua própria anotação.
        compact_spatial = isinstance(out.get("permanencia_espacial"), dict) and type(out) is not dict
        measure = memory.size
        wrap = lambda value: value
        if compact_spatial:
            # Contabilizar o envelope realmente emitido, incluindo aliases de
            # proveniência. Somar dumps separados cobra a mesma lista duas
            # vezes; a margem antiga de 300 bytes também duplicava a reserva
            # de orquestração que o chamador já descontou.
            sources = list(dict.fromkeys([*(out.get("fontes_lidas") or []), *reader.sources]))
            out["fontes_lidas"] = out["permanencia_espacial"]["fontes_lidas"] = sources
            def wrap(value):
                result = type(out)(value)
                result["fontes"] = sources
                return result
            envelope_bytes = memory.size(out)
            def measure(value):
                packed = wrap(value)
                if memory.size(packed) > memory.MAX_MEMORY_BYTES:
                    return memory.MAX_MEMORY_BYTES + 1
                return memory.size(type(out)({**out, memory.KEY: packed})) - envelope_bytes
        budget = min(memory.MAX_MEMORY_BYTES, max_output_bytes - memory.size(out) - (0 if compact_spatial else 300))
        budget -= memory.size(annotations) if annotations else 0
        pack = wrap({**memory.project(docs, scope=scope, budget=max(0, budget), base=base, sources=reader.sources, measure=measure), **annotations})
        while budget >= 400 and memory.size(type(out)({**out, memory.KEY: pack})) > max_output_bytes:
            budget -= 128
            pack = wrap({**memory.project(docs, scope=scope, budget=budget, base=base, sources=reader.sources, measure=measure), **annotations})
    if unresolved:
        pack["participantes_sem_memoria"] = unresolved
    out[memory.KEY] = pack
    if memory.size(out) > max_output_bytes:
        raise memory.SceneMemoryError("NV16: preparo sem espaço para memória+decisão indispensáveis; refine a cena, sem elevar teto")
    return out


memory.attach = attach
