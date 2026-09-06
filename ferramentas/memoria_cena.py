"""Memória dos participantes efetivos, na preparação e na retomada.

Projeção descartável, nunca fonte canônica. O elenco reside no estado existente
via deltas do concluir. Recibos só evitam retransmissão mediante declaração
explícita de base no contexto; nenhum cache de disco representa contexto da IA.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shlex
import unicodedata
from typing import Any, Callable

import yaml

VERSION = 1
MAX_PARTICIPANTS = 6
MAX_MEMORY_BYTES = 4096
MAX_RECEIPT_BYTES = 1400
STATE_PATH = "estado/estado-atual.yaml"
CAST_PATH = "estado_narrativo.elenco_cena"
TICKET_KEY = "memoria_cena_nv05"
KEY = "memoria_cena"
ID = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
INDEXES = (("estado/npcs/index.yaml", "npcs", "npc"),
           ("estado/relacoes/index.yaml", "relacoes", "relacao"),
           ("cenario/texturas/index.yaml", "npcs", "textura"))


class SceneMemoryError(ValueError):
    """Elenco, recibo ou orçamento de memória inválido."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:24]


def size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _normalize(value: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value.lower())
                            if not unicodedata.combining(c)).replace("_", " ").replace("-", " ").split())


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_PARTICIPANTS:
        raise SceneMemoryError("elenco exige lista de até seis IDs de NPCs; [] declara cena sem NPCs")
    if any(not isinstance(p, str) or not ID.fullmatch(p) or p == "ren" for p in value):
        raise SceneMemoryError("elenco exige IDs de NPCs, não nomes livres nem ren")
    return sorted(set(value))


def location(state: dict) -> dict:
    raw = state.get("localizacao") or {}
    return {k: deepcopy(raw[k]) for k in ("area", "ponto_exato") if k in raw}


def cast(value: Any) -> dict | None:
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"versao", "cena_id", "local", "participantes"}
            or type(value["versao"]) is not int or value["versao"] != VERSION):
        raise SceneMemoryError("elenco_cena exige versao, cena_id, local e participantes")
    scene = value["cena_id"]
    if not isinstance(scene, str) or not 1 <= len(scene) <= 160:
        raise SceneMemoryError("cena_id do elenco inválido")
    loc = value["local"]
    if (not isinstance(loc, dict) or set(loc) - {"area", "ponto_exato"}
            or any(not isinstance(v, str) for v in loc.values())):
        raise SceneMemoryError("local do elenco inválido")
    return {"versao": VERSION, "cena_id": scene, "local": deepcopy(loc),
            "participantes": _ids(value["participantes"])}


class Reader:
    """Memoização somente desta chamada; não varre diretórios nem abre segredos."""

    def __init__(self, repo: Path):
        self.repo = Path(repo).resolve()
        self.docs: dict[str, dict] = {}
        self.sources: list[str] = []

    def read(self, relative: str) -> dict:
        if relative in self.docs:
            return self.docs[relative]
        path = self.repo / relative
        if (not path.resolve().is_relative_to(self.repo)
                or not any(path.resolve().is_relative_to(self.repo / domain)
                           for domain in ("estado", "cenario/texturas"))
                or path.suffix != ".yaml"):
            raise SceneMemoryError("fonte de memória fora dos domínios autorizados")
        if not path.is_file():
            raise SceneMemoryError(f"fonte de memória ausente: {relative}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SceneMemoryError(f"fonte de memória não é mapa: {relative}")
        self.docs[relative] = data
        self.sources.append(relative)
        return data

    def indexes(self) -> list[dict]:
        result = []
        for path, key, _ in INDEXES:
            mapping = self.read(path).get(key, {}) if (self.repo / path).is_file() else {}
            if not isinstance(mapping, dict):
                raise SceneMemoryError(f"índice inválido: {path}:{key}")
            result.append(mapping)
        return result

    def resolve(self, terms: list[str], indexes: list[dict]) -> list[str]:
        if len(terms) > MAX_PARTICIPANTS:
            raise SceneMemoryError("elenco admite até seis participantes, sem multiplicar orçamento")
        resolved = []
        for term in terms:
            if not isinstance(term, str) or not term.strip():
                raise SceneMemoryError("participante precisa de ID ou alias explícito")
            # ID exato vence alias. Nunca usar correspondência aproximada.
            exact = {term for mapping in indexes if term in mapping}
            matches = exact or {key for mapping in indexes for key, entry in mapping.items()
                               if isinstance(entry, dict) and _normalize(term) in
                               {_normalize(str(v)) for v in [key, entry.get("nome", ""),
                                                            *(entry.get("aliases") or [])]}}
            if len(matches) != 1:
                raise SceneMemoryError(f"participante desconhecido ou ambíguo: {term}; use ID canônico")
            resolved.append(next(iter(matches)))
        return _ids(resolved)


def load_scene(repo: Path, records: list | None = None) -> tuple[Reader, dict, list, dict | None]:
    import transacoes
    reader = Reader(repo)
    if not (reader.repo / STATE_PATH).is_file():
        return reader, {}, [], None
    state = reader.read(STATE_PATH)
    records = transacoes.load_pending(reader.repo) if records is None else records
    session = (state.get("campanha") or {}).get("sessao_atual")
    records = transacoes.pending_for_session(records, session) if type(session) is int else records
    effective, _ = transacoes.overlay_target(state, records, "estado")
    if (reader.repo / transacoes.PENDING_PATH).is_file():
        reader.sources.append(transacoes.PENDING_PATH.as_posix())
    saved = cast((effective.get("estado_narrativo") or {}).get("elenco_cena"))
    if saved is not None and saved["local"] != location(effective):
        saved = None  # Nunca transportar presença antiga para outro lugar.
    return reader, effective, records, saved


def _time(state: dict, records: list) -> tuple[Any, Any]:
    raw = state.get("tempo") or {}
    date, hour = raw.get("data_exata"), raw.get("hora_aproximada")
    for record in records:
        for delta in record.get("deltas", []):
            if (delta.get("alvo") == "tempo" and delta.get("op") == "instante"
                    and delta.get("visibilidade", "operacional") == "operacional"):
                value = delta.get("valor") or {}
                date, hour = value.get("data"), value.get("hora")
    return date, hour


def _npc(reader: Reader, person: str, indexes: list[dict], records: list) -> dict:
    import transacoes
    import dialogo_relacional
    result: dict[str, Any] = {"encontrado": False}
    sources = []
    for (index_path, _, kind), mapping in zip(INDEXES, indexes):
        entry = mapping.get(person)
        if not isinstance(entry, dict):
            continue
        sources.append(index_path)
        rel = entry.get("arquivo")
        payload = None
        if rel is not None:
            parent = "cenario/texturas/npcs/" if kind == "textura" else str(Path(index_path).parent) + "/"
            if (not isinstance(rel, str) or not rel.startswith(parent)
                    or not (reader.repo / rel).resolve().is_relative_to(reader.repo / parent)):
                raise SceneMemoryError("fragmento de participante fora de seu domínio")
            document = reader.read(rel)
            if document.get("id", person) != person:
                raise SceneMemoryError("fragmento aponta para outro participante")
            payload = document.get(kind)
            if kind == "textura":
                payload = document
            elif not isinstance(payload, dict):
                raise SceneMemoryError(f"fragmento inválido: {rel}")
            sources.append(rel)
        if kind == "textura":
            texture = deepcopy(payload or {})
            if "papel_conversacional" in entry:
                texture["papel_conversacional"] = deepcopy(entry["papel_conversacional"])
            if texture:
                result["textura_narrativa"] = texture
        elif payload is not None:
            effective, _ = transacoes.overlay_target(payload, records, f"{kind}:{person}")
            result["medidores" if kind == "npc" else "relacao"] = {"id": person, "dados": effective}
        result["encontrado"] = True
    meter = (result.get("medidores") or {}).get("dados")
    role = ((result.get("textura_narrativa") or {}).get("papel_conversacional") or {}).get("papel")
    if isinstance(meter, dict):
        dialogue = dialogo_relacional.project(meter, role=role)
        if dialogue is not None:
            dialogo_relacional.validate_projection(dialogue)
            result["dialogo_relacional"] = dialogue
    return {"consulta": {"comando": "npc", "termo": person}, "fontes": sources, "resultado": result}


def documents(reader: Reader, state: dict, records: list, people: list[str]) -> dict[str, dict]:
    import compromissos
    indexes = reader.indexes() if people else []
    docs = {person: _npc(reader, person, indexes, records) for person in people}
    # Compromissos são compartilhados uma única vez, não repetidos por envolvido.
    commitments = state.get("compromissos") or {}
    if not isinstance(commitments, dict) or any(not isinstance(v, dict) for v in commitments.values()):
        raise SceneMemoryError("compromissos deve ser mapa de registros")
    applicable = {key: value for key, value in commitments.items()
                  if set(value.get("envolvidos") or []) & set(people)}
    bundle = compromissos.runtime_bundle(applicable, *_time(state, records), limit=max(1, len(applicable)))
    if bundle:
        docs["@compromissos"] = bundle["itens"]
    return docs


def receipt(raw: Any) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_RECEIPT_BYTES:
            raise SceneMemoryError("recibo de memória excede orçamento")
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SceneMemoryError("recibo de memória precisa ser JSON válido") from exc
    if (not isinstance(raw, dict) or set(raw) != {"versao", "escopo", "itens"}
            or type(raw["versao"]) is not int or raw["versao"] != VERSION
            or not isinstance(raw["escopo"], str) or not re.fullmatch(r"[0-9a-f]{24}", raw["escopo"])
            or not isinstance(raw["itens"], dict) or len(raw["itens"]) > MAX_PARTICIPANTS + 1
            or any(not isinstance(k, str) or not isinstance(v, str)
                   or not re.fullmatch(r"[0-9a-f]{24}", v) for k, v in raw["itens"].items())):
        raise SceneMemoryError("recibo de memória inválido; retomada fria não usa recibo")
    if len(canonical(raw).encode("utf-8")) > MAX_RECEIPT_BYTES:
        raise SceneMemoryError("recibo de memória excede orçamento")
    return deepcopy(raw)


def project(docs: dict, *, scope: str, budget: int, base: dict | None = None,
            sources: list[str] | None = None, measure: Callable[[Any], int] = size) -> dict:
    """Seleção conjunta de fatos NV03: nunca um teto de 8 KiB por personagem."""
    import memoria_relevante as relevant
    base = receipt(base)
    budget = min(MAX_MEMORY_BYTES, budget)
    sources = sorted(set(sources or []) | {src for person, doc in docs.items() if person != "@compromissos"
                                         for src in doc.get("fontes", [])})
    skeleton: dict[str, dict] = {}
    fields = []
    for person, doc in sorted(docs.items()):
        if person == "@compromissos":
            skeleton[person] = {}
            for key, value in doc.items():
                fields.append((person, (key,), value, 1))
            continue
        skeleton[person] = {"encontrado": bool(doc["resultado"].get("encontrado"))}
        absent = [key for key in ("relacao", "medidores", "textura_narrativa") if key not in doc["resultado"]]
        if absent:
            skeleton[person]["dominios_ausentes"] = absent
        _, selected_fields = relevant._fields(doc)
        for path, value, rank in selected_fields:
            if rank is not None:
                # O estado, os compromissos e as memórias vêm antes de instruções
                # interpretativas longas. Não remover orientação sem sinalizar.
                if path[0] in {"dialogo_relacional", "iniciativa_social"} or path[-1] == "papel_conversacional":
                    rank = 5
                fields.append((person, path, value, rank))
    candidates = []
    for f, (_, path, value, rank) in enumerate(fields):
        indices = list(reversed(range(len(value)))) if isinstance(value, list) and value else [0]
        for turn, index in enumerate(indices):
            candidates.append((turn, rank, path, fields[f][0], f, index))

    def render(chosen: dict[int, set[int]]) -> dict:
        items = deepcopy(skeleton)
        missing: dict[str, list] = {}
        origins: dict[str, dict] = {}
        for f, (person, path, value, _) in enumerate(fields):
            ids = chosen.get(f, set())
            count = len(value) if isinstance(value, list) and value else 1
            if ids:
                payload = [value[i] for i in sorted(ids)] if isinstance(value, list) and value else value
                relevant._put(items[person], path, payload)
                if isinstance(value, list) and value and len(ids) < count:
                    origins.setdefault(person, {})[relevant.pointer(path)] = sorted(ids)
            if len(ids) < count:
                missing.setdefault(person, []).append(relevant.pointer(path))
        for person in items:
            absent = missing.get(person, [])
            meta = {"aprofundamento_necessario": bool(absent), "campos_pendentes": len(absent)}
            if absent:
                meta["primeiro_campo"] = absent[0]
                meta["consulta"] = ("poetry run python ferramentas/contexto.py npc " + person + " --campo " + shlex.quote(absent[0]) if person != "@compromissos"
                                     else "consultar estado/estado-atual.yaml:compromissos com overlay transacional")
            if person in origins:
                meta["indices_origem"] = origins[person]
            items[person]["memoria_relevante"] = meta
        return {"versao": VERSION, "modo": "completa", "itens": items,
                "aprofundamento_necessario": bool(missing) or any(not v.get("encontrado", True) for v in items.values()), "fontes": sources,
                "recibo": {"versao": VERSION, "escopo": scope,
                           "itens": {k: digest(v) for k, v in items.items()}}}

    chosen: dict[int, set[int]] = {}
    out = render(chosen)
    if measure(out) > budget:
        return {"versao": VERSION, "modo": "completa", "participantes": sorted(docs),
                "aprofundamento_necessario": True,
                "aviso": "Sem espaço para memória conjunta; consulte participantes por ID. Não interpretar ausência como esquecimento."}
    for _, _, _, _, f, index in sorted(candidates):
        trial = {k: set(v) for k, v in chosen.items()}
        trial.setdefault(f, set()).add(index)
        candidate = render(trial)
        if measure(candidate) <= budget:
            chosen = trial
            out = candidate
    # Primeiro seleciona a mesma base completa. Depois envia apenas diferenças.
    # Nunca usa espaço poupado pelo delta para selecionar uma base incompatível.
    if base is not None and base["escopo"] == scope:
        delta = deepcopy(out)
        delta["modo"] = "delta"
        delta["base"] = digest(base)
        delta["removidos"] = sorted(set(base["itens"]) - set(out["itens"]))
        delta["itens"] = {k: v for k, v in out["itens"].items()
                          if base["itens"].get(k) != out["recibo"]["itens"][k]}
        if measure(delta) <= budget:
            out = delta
    return out


def attach(repo: Path, prepared: dict, *, decode_ticket, encode_ticket,
           participants: list[str] | None = None, base_in_context: Any = None,
           max_output_bytes: int = 8192) -> dict:
    base = receipt(base_in_context)
    reader, state, records, saved = load_scene(repo)
    if not state:
        if participants is not None or base is not None:
            raise SceneMemoryError("memória de cena exige estado canônico")
        return prepared
    payload = decode_ticket(prepared["ticket"])
    request = payload["cena"]
    scene_id = request["scene_id"]
    same_scene = saved is not None and saved["cena_id"] == scene_id
    changed_place = bool(request.get("place") or payload.get("transito_urbano"))
    people = saved["participantes"] if same_scene and not changed_place else None
    terms = participants if participants is not None else request.get("npcs") or None
    unresolved = []
    if terms is not None:
        try:
            explicit = reader.resolve(terms, reader.indexes()) if terms else []
            people = explicit if participants is not None else sorted(set((people or []) + explicit))
        except SceneMemoryError:
            if participants is not None:
                raise
            # O gate anterior pode estar preparando um stub ainda não canônico.
            # Memória não bloqueia seu nascimento nem o inventa antes de confirmar.
            people, unresolved = None, terms
    selected = (cast({"versao": VERSION, "cena_id": scene_id, "local": location(state),
                      "participantes": people}) if people is not None else None)
    out = deepcopy(prepared)
    # O ticket contém somente elenco/metadados, nunca biografias ou memórias.
    meta = {"elenco": selected, "anterior": saved, "local": location(state)}
    if selected is not None or saved is not None:
        payload[TICKET_KEY] = meta
        out["ticket"], out["ticket_id"] = encode_ticket(payload)
    if people is None:
        pack = {"versao": VERSION, "modo": "completa", "participantes": None,
                "aprofundamento_necessario": True,
                "aviso": "Elenco não registrado para esta cena; use --participante <id> ou --sem-participantes. Menção não prova presença."}
    else:
        docs = documents(reader, state, records, people)
        scope = digest([VERSION, (state.get("campanha") or {}).get("sessao_atual"), scene_id, location(state)])
        # Margem de indentação do envelope YAML. O teste final mede a saída real.
        budget = min(MAX_MEMORY_BYTES, max_output_bytes - size(out) - 300)
        pack = project(docs, scope=scope, budget=budget, base=base, sources=reader.sources)
        while budget >= 400 and size({**out, KEY: pack}) > max_output_bytes:
            budget -= 128
            pack = project(docs, scope=scope, budget=budget, base=base, sources=reader.sources)
    if unresolved:
        pack["participantes_sem_memoria"] = unresolved
    out[KEY] = pack
    if size(out) > max_output_bytes:
        raise SceneMemoryError("preparo sem espaço para memória indispensável; refine a cena, sem aumentar o teto")
    return out


def resume(repo: Path, result: dict, *, max_output_bytes: int = 8192,
           records: list | None = None, measure: Callable[[Any], int] = size) -> dict:
    reader, state, records, saved = load_scene(repo, records)
    if not state:
        return result
    if saved is None:
        pack = {"versao": VERSION, "modo": "completa", "participantes": None,
                "aprofundamento_necessario": True, "aviso": "Elenco legado ausente; não inferir presença pelo resumo."}
    else:
        docs = documents(reader, state, records, saved["participantes"])
        scope = digest([VERSION, (state.get("campanha") or {}).get("sessao_atual"), saved["cena_id"], location(state)])
        budget = min(MAX_MEMORY_BYTES, max_output_bytes - measure(result) - 300)
        pack = project(docs, scope=scope, budget=budget, sources=reader.sources, measure=measure)
        while budget >= 400 and measure({**result, KEY: pack}) > max_output_bytes:
            budget -= 128
            pack = project(docs, scope=scope, budget=budget, sources=reader.sources, measure=measure)
    out = {**result, KEY: pack}
    if measure(out) > max_output_bytes:
        raise SceneMemoryError("retomada excede teto conjunto; aprofundamento dirigido necessário")
    return out


def compile_cast(payload: dict, transaction: dict, *, repo: Path | None = None) -> dict:
    """Compila para os writers existentes; replay produz exatamente o mesmo delta."""
    meta = payload.get(TICKET_KEY)
    if meta is None:
        return transaction
    if not isinstance(meta, dict) or set(meta) != {"elenco", "anterior", "local"}:
        raise SceneMemoryError("metadados de elenco inválidos")
    selected, previous = cast(meta["elenco"]), cast(meta["anterior"])
    scene_id = payload["cena"]["scene_id"]
    initial_location = meta["local"]
    # Valida o local até quando o elenco é desconhecido.
    cast({"versao": VERSION, "cena_id": scene_id, "local": initial_location, "participantes": []})
    if selected is not None and (selected["cena_id"] != scene_id or selected["local"] != initial_location):
        raise SceneMemoryError("elenco pertence a outra cena/local")
    deltas = transaction.get("deltas", [])
    if not isinstance(deltas, list) or any(not isinstance(d, dict) for d in deltas):
        raise SceneMemoryError("deltas deve ser lista de objetos")
    final_location = deepcopy(initial_location)
    explicit = []
    for d in deltas:
        if d.get("alvo") != "estado":
            continue
        path = d.get("caminho", "")
        if not isinstance(path, str):
            raise SceneMemoryError("caminho de estado deve ser texto")
        if path == "estado_narrativo" or path.startswith(CAST_PATH + "."):
            raise SceneMemoryError("não sobrescrever parcialmente o elenco; use set do registro completo")
        if path == CAST_PATH:
            explicit.append(d)
        if d.get("visibilidade", "operacional") != "operacional":
            continue
        if path == "localizacao":
            if d.get("op") != "set" or not isinstance(d.get("valor"), dict):
                raise SceneMemoryError("mudança de local exige set do mapa ou dos campos")
            final_location = location({"localizacao": d["valor"]})
        elif path in {"localizacao.area", "localizacao.ponto_exato"}:
            key = path.split(".")[1]
            if d.get("op") == "remove":
                final_location.pop(key, None)
            elif d.get("op") == "set":
                final_location[key] = d.get("valor")
            else:
                raise SceneMemoryError("mudança de local exige set/remove")
    if len(explicit) > 1:
        raise SceneMemoryError("elenco deve ser substituído uma única vez por turno")
    if explicit:
        d = explicit[0]
        if d.get("op") != "set" or "valor" not in d or d.get("visibilidade", "operacional") != "operacional":
            raise SceneMemoryError("elenco exige set operacional do registro completo ou null")
        final_cast = cast(d["valor"])
        if final_cast is not None:
            if final_cast["cena_id"] != scene_id or final_cast["local"] != final_location:
                raise SceneMemoryError("elenco final precisa coincidir com a cena/local resultante")
            if repo is not None and final_cast["participantes"]:
                reader = Reader(repo)
                reader.resolve(final_cast["participantes"], reader.indexes())
        return transaction
    if final_location != initial_location:
        selected = None  # Deslocamento não transporta presença por inferência.
    if selected == previous:
        return transaction
    out = deepcopy(transaction)
    out["deltas"] = [*out.get("deltas", []),
                     {"alvo": "estado", "op": "set", "caminho": CAST_PATH, "valor": selected}]
    return out
