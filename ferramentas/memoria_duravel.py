"""Fatos declarados no concluir -> deltas existentes; nenhuma escrita paralela.

Não extrai significado da prosa. Evidência literal, participantes e precondições
são verificáveis; a completude/adequação da anotação continua sendo avaliada na
narração. Sem o bloco ``memoria``, não há leitura nem mudança de payload.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

TRANSACTION_KEY = "memoria"
MAX_FACTS = 8
MAX_BLOCK_BYTES = 8192
MAX_FRAGMENT_BYTES = 12 * 1024
MAX_PARTICIPANTS = 6
ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
COLLECTIONS = {"informacoes_recebidas", "memorias_importantes"}
COMMON = {"id", "tipo", "participantes", "evidencia"}
FIELDS = {
    "promessa": {"operacao", "compromisso", "compromisso_id", "anterior"},
    "informacao": {"emissor", "destinatario", "canal", "estatuto", "texto"},
    "relacao": {"npc", "eixo", "anterior", "variacao"},
    "marco": {"texto"},
}


class DurableMemoryError(ValueError):
    """Contrato de memória inválido ou diferente do estado efetivo."""


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DurableMemoryError("memória exige valores JSON finitos") from exc


def _text(value: Any, label: str, limit: int, minimum: int = 1) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= limit:
        raise DurableMemoryError(f"{label}: texto de {minimum} a {limit} caracteres")
    return value.strip()


def _id(value: Any) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise DurableMemoryError("ID de memória/participante exige snake_case, até 64 caracteres")
    return value


def event_id(transaction_id: str, fact_id: str) -> str:
    """ID estável também utilizado pelo compromisso novo; não depende do save."""
    digest = hashlib.sha256(_json([transaction_id, fact_id]).encode()).hexdigest()[:24]
    return "mem_" + digest


def _facts(transaction: dict) -> list[dict]:
    block = transaction.get(TRANSACTION_KEY)
    if not isinstance(block, dict) or set(block) != {"versao", "fatos"}:
        raise DurableMemoryError("memoria exige somente versao=1 e fatos=[...]")
    if type(block["versao"]) is not int or block["versao"] != 1:
        raise DurableMemoryError("versão de memória não suportada")
    if len(_json(block).encode("utf-8")) > MAX_BLOCK_BYTES:
        raise DurableMemoryError("bloco de memória excede 8 KiB; divida os acontecimentos")
    facts = block["fatos"]
    if not isinstance(facts, list) or not 1 <= len(facts) <= MAX_FACTS:
        raise DurableMemoryError("memoria.fatos exige 1 a 8 fatos; sem fato novo, omita memoria")
    seen: set[str] = set()
    result = []
    for raw in facts:
        if not isinstance(raw, dict) or not isinstance(raw.get("tipo"), str) or raw["tipo"] not in FIELDS:
            raise DurableMemoryError("tipo de memória deve ser promessa, informacao, relacao ou marco")
        if set(raw) - COMMON - FIELDS[raw["tipo"]]:
            raise DurableMemoryError("campo desconhecido no fato de memória")
        fact = deepcopy(raw)
        fid = _id(fact.get("id"))
        if fid in seen:
            raise DurableMemoryError("id de fato duplicado no mesmo concluir")
        seen.add(fid)
        people = fact.get("participantes")
        if not isinstance(people, list) or not 2 <= len(people) <= MAX_PARTICIPANTS:
            raise DurableMemoryError("participantes exige 2 a 6 IDs, incluindo ren")
        for person in people:
            _id(person)
        if len(set(people)) != len(people) or "ren" not in people:
            raise DurableMemoryError("participantes não pode duplicar IDs e deve incluir ren")
        fact["participantes"] = sorted(people)
        proof = fact.get("evidencia")
        if not isinstance(proof, dict) or set(proof) != {"campo", "trecho"}:
            raise DurableMemoryError("evidencia exige campo e trecho literal")
        if proof["campo"] not in ("jogador", "narracao"):
            raise DurableMemoryError("evidência vem do jogador ON ou da narração, nunca do resumo/segredo")
        quote = _text(proof["trecho"], "evidencia.trecho", 600, 20)
        source = transaction.get(proof["campo"])
        if not isinstance(source, str) or quote not in source:
            raise DurableMemoryError("evidência de memória não é literal no campo indicado")
        fact["evidencia"] = {"campo": proof["campo"], "trecho": quote}
        result.append(fact)
    return result


def compile_transaction(transaction: dict, transaction_id: str, session: int) -> tuple[dict, list[dict]]:
    """Compila sem ler o save; só o schema de compromisso é delegado ao domínio."""
    facts = _facts(transaction)
    raw_deltas = transaction.get("deltas", [])
    if not isinstance(raw_deltas, list) or any(not isinstance(d, dict) for d in raw_deltas):
        raise DurableMemoryError("deltas deve ser lista de objetos")
    signed = deepcopy(transaction)
    signed.update(id=transaction_id, sessao=session)
    digest = hashlib.sha256(_json(signed).encode("utf-8")).hexdigest()
    generated: list[dict] = []
    changes: set[tuple[str, str]] = set()
    for fact in facts:
        kind = fact["tipo"]
        people = fact["participantes"]
        eid = event_id(transaction_id, fact["id"])
        memory = {"id": eid, "tipo": kind, "fonte": f"transacao:{transaction_id}",
                  "participantes": people, "evidencia": fact["evidencia"], "registro_sha256": digest}
        anchors = [person for person in people if person != "ren"]
        collection = "memorias_importantes"
        if kind == "promessa":
            import compromissos
            operation = fact.get("operacao")
            if operation not in ("registrar", "cumprir", "cancelar", "substituir"):
                raise DurableMemoryError("promessa exige registrar, cumprir, cancelar ou substituir")
            old = None
            if operation != "registrar":
                old = _id(fact.get("compromisso_id"))
                previous = compromissos.validate_record(fact.get("anterior"))
                if sorted(previous.get("envolvidos", [])) != people:
                    raise DurableMemoryError("participantes divergem dos envolvidos no compromisso anterior")
                fact["anterior"] = previous
                generated.append(compromissos.close_delta(old))
            elif "anterior" in fact or "compromisso_id" in fact:
                raise DurableMemoryError("registrar gera ID; não aceita compromisso_id/anterior")
            if operation in ("registrar", "substituir"):
                value = fact.get("compromisso")
                if not isinstance(value, dict) or "envolvidos" in value:
                    raise DurableMemoryError("compromisso exige tipo/resumo/janela; envolvidos vêm dos participantes")
                record = compromissos.validate_record({**value, "envolvidos": people})
                generated.append(compromissos.create_delta(eid, record))
                fact["compromisso"] = record
                memory["compromisso_id"] = eid
                if old is not None:
                    if old == eid:
                        raise DurableMemoryError("substituição exige um compromisso novo")
                    memory["substitui"] = old
            elif "compromisso" in fact:
                raise DurableMemoryError("cumprir/cancelar não aceita compromisso novo")
            else:
                memory["compromisso_id"] = old
            memory["operacao"] = operation
        elif kind == "relacao":
            npc = fact.get("npc")
            axis = fact.get("eixo")
            previous, change = fact.get("anterior"), fact.get("variacao")
            if npc not in people or npc == "ren" or axis not in ("afinidade", "confianca"):
                raise DurableMemoryError("relação exige NPC participante e eixo afinidade/confianca")
            if type(previous) is not int or type(change) is not int or change not in (-1, 1):
                raise DurableMemoryError("relação exige anterior inteiro conhecido e variacao +1/-1")
            if not 0 <= previous <= 10 or not 0 <= previous + change <= 10:
                raise DurableMemoryError("mudança relacional fora da escala 0..10")
            stored = "vinculo" if axis == "afinidade" else "confianca"
            generated.append({"alvo": f"npc:{npc}", "op": "inc", "caminho": f"medidores.{stored}",
                              "valor": change, "fonte": memory["fonte"],
                              "fato_canonico": fact["evidencia"]["trecho"]})
            memory.update(eixo=axis, anterior=previous, variacao=change)
            anchors = [npc]
        else:
            text = _text(fact.get("texto"), "texto", 220)
            if text not in fact["evidencia"]["trecho"]:
                raise DurableMemoryError("texto da informação/marco deve estar na evidência literal")
            memory["texto"] = text
            if kind == "informacao":
                sender, recipient = fact.get("emissor"), fact.get("destinatario")
                if sender not in people or recipient not in people or sender == recipient:
                    raise DurableMemoryError("informação exige emissor e destinatario participantes distintos")
                if "ren" not in (sender, recipient):
                    raise DurableMemoryError("troca reservada entre NPCs não é memória operacional de Ren")
                if fact.get("canal") not in ("presencial", "mensagem_entregue"):
                    raise DurableMemoryError("informação exige canal presencial ou mensagem_entregue, não intenção de enviar")
                if fact.get("estatuto") not in ("relato", "rumor"):
                    raise DurableMemoryError("informação transmitida é relato/rumor, não confirmação automática")
                memory.update(emissor=sender, destinatario=recipient, canal=fact["canal"], estatuto=fact["estatuto"])
                anchors = [recipient if recipient != "ren" else sender]
                if recipient == "ren":
                    generated.append({"alvo": "conhecimento", "op": "registrar", "valor": {
                        **memory, "texto": f"{fact['estatuto']} recebido de {sender} por {fact['canal']}: {text}"}})
                else:
                    collection = "informacoes_recebidas"
        for npc in anchors:
            generated.append({"alvo": f"relacao:{npc}", "op": "append", "caminho": collection,
                              "valor": deepcopy(memory)})
    for delta in generated:
        if delta["op"] in ("set", "remove", "inc"):
            key = (delta["alvo"], delta["caminho"])
            if key in changes:
                raise DurableMemoryError("dois fatos disputam o mesmo compromisso/eixo no concluir")
            changes.add(key)
    for raw in raw_deltas:
        for delta in generated:
            if raw.get("alvo") != delta["alvo"]:
                continue
            left, right = raw.get("caminho"), delta.get("caminho")
            if left is None or right is None or (isinstance(left, str) and
                    (left == right or left.startswith(right + ".") or right.startswith(left + "."))):
                raise DurableMemoryError("delta manual concorre com memória compilada; registre o fato uma vez")
    writer = deepcopy(transaction)
    writer.pop(TRANSACTION_KEY)
    writer.update(id=transaction_id, sessao=session, deltas=deepcopy(raw_deltas) + generated)
    return writer, facts


def _path(repo: Path, relative: str, prefix: str) -> Path:
    if not isinstance(relative, str) or not relative.startswith(prefix + "/"):
        raise DurableMemoryError("ponteiro de memória fora do domínio esperado")
    path = repo / relative
    try:
        path.resolve().relative_to(repo.resolve())
        path.resolve().relative_to((repo / prefix).resolve())
    except ValueError as exc:
        raise DurableMemoryError("ponteiro de memória escapa do domínio") from exc
    if path.suffix != ".yaml" or ".." in Path(relative).parts:
        raise DurableMemoryError("ponteiro de memória inválido")
    return path


def _load(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DurableMemoryError(f"documento de memória inválido: {path.name}")
    return value


class _State:
    """Cache restrito à conclusão atual: índices e fragmentos dirigidos, nunca global."""
    def __init__(self, repo: Path, pending: list[dict]):
        self.repo, self.pending = repo, pending
        self.indices: dict[str, dict] = {}
        self.documents: dict[str, tuple[dict, str]] = {}
        self.entries: dict[str, dict] = {}

    def entity(self, target: str) -> dict:
        import transacoes
        if target not in self.documents:
            kind, npc = target.split(":")
            plural = "relacoes" if kind == "relacao" else "npcs"
            if plural not in self.indices:
                mapping = _load(self.repo / f"estado/{plural}/index.yaml").get(plural)
                if not isinstance(mapping, dict):
                    raise DurableMemoryError(f"índice de {plural} inválido")
                self.indices[plural] = mapping
            entry = self.indices[plural].get(npc)
            if not isinstance(entry, dict):
                raise DurableMemoryError(f"{target}: ID canônico não indexado; não criar identidade por aproximação")
            path = _path(self.repo, entry.get("arquivo"), f"estado/{plural}")
            doc = _load(path)
            if doc.get("id", npc) != npc or not isinstance(doc.get(kind), dict):
                raise DurableMemoryError(f"fragmento incompatível com {target}")
            doc[kind], _ = transacoes.overlay_target(doc[kind], self.pending, target)
            self.documents[target] = (doc, kind)
            self.entries[target] = entry
        doc, kind = self.documents[target]
        return doc[kind]

    def check_sizes(self) -> None:
        for target, (doc, _) in self.documents.items():
            size = len(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=110).encode("utf-8"))
            if size > MAX_FRAGMENT_BYTES:
                raise DurableMemoryError(f"{target}: fragmento excederia 12 KiB; arquive por manutenção antes de concluir")


def _already_consolidated(repo: Path, session: int, txid: str) -> bool:
    path = repo / f"sessoes/{session:03d}/consolidacoes.jsonl"
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DurableMemoryError("ledger de consolidação inválido") from exc
        if not isinstance(row, dict) or not isinstance(row.get("transacoes"), list):
            raise DurableMemoryError("ledger de consolidação inválido")
        if txid in row["transacoes"]:
            return True
    return False


def _verify_consolidated(state: _State, writer: dict) -> None:
    """Retry frio só consulta históricos dos alvos conhecidos, sem transcrição."""
    histories: dict[str, dict] = {}
    for delta in writer["deltas"]:
        value = delta.get("valor")
        if delta.get("caminho") not in COLLECTIONS or not isinstance(value, dict) or "registro_sha256" not in value:
            continue
        target = delta["alvo"]
        current = state.entity(target).get(delta["caminho"], [])
        if isinstance(current, list) and value in current:
            continue
        if target not in histories:
            npc = target.split(":")[1]
            relative = state.entries[target].get("historico", f"historico/relacoes/{npc}.yaml")
            path = _path(state.repo, relative, "historico/relacoes")
            histories[target] = _load(path) if path.exists() else {}
        history = histories[target]
        found = any(
            old.get("valor") == value and old.get("caminho") == delta["caminho"]
            for event in history.get("eventos_pos_migracao", [])
            if event.get("transacao") == writer["id"]
            for old in event.get("deltas", [])
        )
        if not found:
            raise DurableMemoryError("retry consolidado diverge do acontecimento original; não reescrever memória")


def prepare_transaction(repo: Path, transaction: dict) -> dict:
    """Valida tudo antes do writer/journals; devolve apenas deltas já suportados."""
    if not isinstance(transaction, dict):
        raise DurableMemoryError("transação de memória precisa ser objeto")
    if TRANSACTION_KEY not in transaction:
        return transaction
    # Falhas de forma/evidência não precisam sequer abrir a campanha.
    _facts(transaction)
    import compromissos
    import estado_relacional
    import transacoes
    import turno

    session, status = turno.current_session_info(repo)
    requested_session = transaction.get("sessao", session)
    if type(requested_session) is not int or requested_session != session or status not in (None, "em_sessao"):
        raise DurableMemoryError("memória só pode ser registrada na sessão ativa")
    txid = transacoes.stable_transaction_id(transaction, session)
    try:
        writer, facts = compile_transaction(transaction, txid, session)
        record = transacoes.build_pending_record(writer, session)
        pending = transacoes.load_pending(repo)
        for old in pending:
            if old["id"] == txid:
                if transacoes.record_fingerprint(old) != transacoes.record_fingerprint(record):
                    raise DurableMemoryError("retry pendente diverge do acontecimento original")
                return writer
        state = _State(repo, pending)
        if _already_consolidated(repo, session, txid):
            _verify_consolidated(state, writer)
            return writer
        for fact in facts:
            for npc in fact["participantes"]:
                if npc != "ren":
                    state.entity(f"relacao:{npc}")
        active = None
        if any(fact["tipo"] == "promessa" for fact in facts):
            base = _load(repo / "estado/estado-atual.yaml")
            effective, _ = transacoes.overlay_target(base, pending, "estado")
            active = effective.get("compromissos", {})
            if not isinstance(active, dict):
                raise DurableMemoryError("estado.compromissos não é mapa")
        for fact in facts:
            if fact["tipo"] == "promessa":
                eid = event_id(txid, fact["id"])
                old = fact.get("compromisso_id")
                if fact["operacao"] != "registrar":
                    if active.get(old) != fact["anterior"]:
                        raise DurableMemoryError("compromisso anterior ausente/obsoleto; não cumprir/cancelar/substituir outro fato")
                    active.pop(old)
                if fact["operacao"] in ("registrar", "substituir"):
                    if eid in active:
                        raise DurableMemoryError("ID de compromisso já existe")
                    active[eid] = fact["compromisso"]
            elif fact["tipo"] == "relacao":
                npc = fact["npc"]
                payload = state.entity(f"npc:{npc}")
                meters = estado_relacional.validate_meters(payload.get("medidores"), entity_id=npc)
                stored = "vinculo" if fact["eixo"] == "afinidade" else "confianca"
                if meters[stored] != fact["anterior"]:
                    raise DurableMemoryError("medidor anterior obsoleto/desconhecido; use o estado efetivo")
        for delta in writer["deltas"]:
            target = delta["alvo"]
            if target.startswith(("relacao:", "npc:")):
                payload = state.entity(target)
                if estado_relacional.is_relationship_delta(delta):
                    estado_relacional.validate_relationship_delta(delta)
                if delta.get("visibilidade", "operacional") != "narrador" and delta["op"] != "registrar":
                    transacoes.apply_delta(payload, delta)
        state.check_sizes()
        return writer
    except (compromissos.CommitmentError, estado_relacional.RelationshipStateError,
            transacoes.TransactionError) as exc:
        raise DurableMemoryError(str(exc)) from exc
