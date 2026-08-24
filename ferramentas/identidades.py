#!/usr/bin/env python3
"""Suspeita e reconhecimento de identidades de Ren, sem onisciência automática.

A Task 28 usa o próprio fragmento ``estado/npcs/<id>.yaml`` como armazenamento.
O campo opcional ``reconhecimento_identidade`` só existe quando há algo a guardar;
portanto o hot path comum não ganha estado paralelo, scheduler ou leitura adicional.

Suspeita é uma crença do NPC, não verdade objetiva. Evidências acumulam até uma
suspeita forte, mas nunca promovem sozinhas para confirmação. Confirmação exige
fato canônico explícito. Actor pode neutralizar evidência de *performance* quando
uma rolagem pertinente teve sucesso; não apaga semelhança física, conhecimento,
rotina, testemunho ou contradições observáveis.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

import contexto_core

REGISTRY = Path("personagens/jogador/identidades.yaml")
NPC_INDEX = Path("estado/npcs/index.yaml")
STATE_FIELD = "reconhecimento_identidade"
SCHEMA = 1
MAX_EDGES = 4
MAX_EVIDENCE = 3
MAX_STATE_BYTES = 1800
EVIDENCE_TYPES = {"atuacao", "fisica", "contextual", "contradicao", "testemunho"}
ACTOR_RESULTS = {"sucesso", "falha", "nao_aplicavel"}
ACTOR_MASKABLE = {"atuacao"}


class IdentitySuspicionError(ValueError):
    """Estado de suspeita/identidade incoerente ou transição inválida."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IdentitySuspicionError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise IdentitySuspicionError(f"YAML inválido em {path}: {exc}") from exc


def load_registry(repo: Path) -> dict[str, Any]:
    data = _load(repo / REGISTRY)
    if not isinstance(data, dict) or data.get("schema_identidades_ren") != 1:
        raise IdentitySuspicionError("registro de identidades de Ren inválido")
    identities = data.get("identidades")
    if not isinstance(identities, dict) or data.get("principal") not in identities:
        raise IdentitySuspicionError("registro de identidades sem mapa/principal válido")
    for identity_id, entry in identities.items():
        if not isinstance(identity_id, str) or not identity_id:
            raise IdentitySuspicionError("id de identidade inválido")
        if not isinstance(entry, dict) or not isinstance(entry.get("nome"), str):
            raise IdentitySuspicionError(f"identidade inválida: {identity_id}")
    return data


def _norm(value: Any) -> str:
    return contexto_core.normalize(value)


def resolve_identity(registry: dict[str, Any], term: str) -> str:
    query = _norm(term)
    matches: list[str] = []
    for identity_id, entry in registry["identidades"].items():
        candidates = [identity_id, entry.get("nome"), *(entry.get("aliases") or [])]
        if any(_norm(candidate) == query for candidate in candidates if candidate):
            matches.append(identity_id)
    if len(matches) != 1:
        raise IdentitySuspicionError(
            f"identidade ambígua/desconhecida {term!r}; use um id do registro: "
            + ", ".join(sorted(registry["identidades"]))
        )
    return matches[0]


def empty_state() -> dict[str, Any]:
    return {"schema_reconhecimento_identidade": SCHEMA, "suspeitas": [], "confirmacoes": []}


def _edge_key(item: dict[str, Any], *, confirmed: bool = False) -> tuple[str, str]:
    return (
        str(item.get("observada") or ""),
        str(item.get("identidade" if confirmed else "possivel") or ""),
    )


def _validate_source(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IdentitySuspicionError(f"{label} exige fonte canônica rastreável")
    return value.strip()


def validate_state(value: Any, registry: dict[str, Any]) -> dict[str, Any]:
    if value is None:
        return empty_state()
    if not isinstance(value, dict) or value.get("schema_reconhecimento_identidade") != SCHEMA:
        raise IdentitySuspicionError("reconhecimento_identidade precisa usar schema 1")
    allowed = {"schema_reconhecimento_identidade", "suspeitas", "confirmacoes"}
    extra = set(value) - allowed
    if extra:
        raise IdentitySuspicionError(
            "reconhecimento_identidade possui campos desconhecidos: " + ", ".join(sorted(extra))
        )
    identities = set(registry["identidades"])
    suspicions = value.get("suspeitas")
    confirmations = value.get("confirmacoes")
    if not isinstance(suspicions, list) or len(suspicions) > MAX_EDGES:
        raise IdentitySuspicionError(f"suspeitas deve ser lista com no máximo {MAX_EDGES} arestas")
    if not isinstance(confirmations, list) or len(confirmations) > MAX_EDGES:
        raise IdentitySuspicionError(f"confirmacoes deve ser lista com no máximo {MAX_EDGES} arestas")

    suspicion_keys: set[tuple[str, str]] = set()
    evidence_ids: set[str] = set()
    normalized_suspicions: list[dict[str, Any]] = []
    for item in suspicions:
        if not isinstance(item, dict) or set(item) != {"observada", "possivel", "evidencias"}:
            raise IdentitySuspicionError("suspeita deve conter observada, possivel e evidencias")
        observed, possible = _edge_key(item)
        if observed not in identities or possible not in identities or observed == possible:
            raise IdentitySuspicionError(f"aresta de suspeita inválida: {observed!r} -> {possible!r}")
        key = (observed, possible)
        if key in suspicion_keys:
            raise IdentitySuspicionError(f"suspeita duplicada: {observed}->{possible}")
        suspicion_keys.add(key)
        evidences = item.get("evidencias")
        if not isinstance(evidences, list) or not 1 <= len(evidences) <= MAX_EVIDENCE:
            raise IdentitySuspicionError(
                f"{observed}->{possible}: evidencias deve ter 1..{MAX_EVIDENCE} itens"
            )
        clean_evidences: list[dict[str, Any]] = []
        for evidence in evidences:
            if not isinstance(evidence, dict) or set(evidence) != {"id", "tipo", "fonte"}:
                raise IdentitySuspicionError("evidência precisa conter somente id, tipo e fonte")
            evidence_id = evidence.get("id")
            evidence_type = evidence.get("tipo")
            if not isinstance(evidence_id, str) or not re.fullmatch(r"ids-[0-9a-f]{16}", evidence_id):
                raise IdentitySuspicionError(f"id de evidência inválido: {evidence_id!r}")
            if evidence_id in evidence_ids:
                raise IdentitySuspicionError(f"evidência duplicada: {evidence_id}")
            evidence_ids.add(evidence_id)
            if evidence_type not in EVIDENCE_TYPES:
                raise IdentitySuspicionError(f"tipo de evidência inválido: {evidence_type!r}")
            clean_evidences.append(
                {"id": evidence_id, "tipo": evidence_type, "fonte": _validate_source(evidence.get("fonte"), "evidência")}
            )
        normalized_suspicions.append(
            {"observada": observed, "possivel": possible, "evidencias": clean_evidences}
        )

    confirmation_keys: set[tuple[str, str]] = set()
    normalized_confirmations: list[dict[str, Any]] = []
    for item in confirmations:
        if not isinstance(item, dict) or set(item) != {"observada", "identidade", "fonte"}:
            raise IdentitySuspicionError("confirmação deve conter observada, identidade e fonte")
        observed, identity = _edge_key(item, confirmed=True)
        if observed not in identities or identity not in identities or observed == identity:
            raise IdentitySuspicionError(f"confirmação inválida: {observed!r} -> {identity!r}")
        key = (observed, identity)
        if key in confirmation_keys:
            raise IdentitySuspicionError(f"confirmação duplicada: {observed}->{identity}")
        if key in suspicion_keys:
            raise IdentitySuspicionError(
                f"{observed}->{identity} não pode permanecer simultaneamente como suspeita e confirmação"
            )
        confirmation_keys.add(key)
        normalized_confirmations.append(
            {"observada": observed, "identidade": identity, "fonte": _validate_source(item.get("fonte"), "confirmação")}
        )

    result = {
        "schema_reconhecimento_identidade": SCHEMA,
        "suspeitas": normalized_suspicions,
        "confirmacoes": normalized_confirmations,
    }
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise IdentitySuspicionError(
            f"reconhecimento_identidade excede orçamento: {size} > {MAX_STATE_BYTES} bytes"
        )
    return result


def band(count: int) -> str:
    return {1: "possibilidade", 2: "suspeita", 3: "suspeita_forte"}.get(count, "nenhuma")


def project(value: Any, registry: dict[str, Any]) -> dict[str, Any] | None:
    state = validate_state(value, registry)
    if not state["suspeitas"] and not state["confirmacoes"]:
        return None
    return {
        "schema_reconhecimento_identidade": SCHEMA,
        "suspeitas": [
            {
                "observada": item["observada"],
                "possivel": item["possivel"],
                "grau": band(len(item["evidencias"])),
                "evidencias": len(item["evidencias"]),
            }
            for item in state["suspeitas"]
        ],
        "confirmacoes": [
            {"observada": item["observada"], "identidade": item["identidade"]}
            for item in state["confirmacoes"]
        ],
        "regra": "suspeita nunca equivale a conhecimento confirmado",
    }


def evidence_id(
    entity_id: str,
    observed: str,
    possible: str,
    evidence_type: str,
    source: str,
    fact: str,
) -> str:
    raw = "\x1f".join([entity_id, observed, possible, evidence_type, source.strip(), fact.strip()])
    return "ids-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def is_identity_delta(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and isinstance(delta.get("alvo"), str)
        and str(delta["alvo"]).startswith("npc:")
        and delta.get("caminho") == STATE_FIELD
    )


def validate_identity_delta(delta: Any, registry: dict[str, Any]) -> dict[str, Any]:
    if not is_identity_delta(delta):
        raise IdentitySuspicionError("delta não aponta reconhecimento_identidade")
    if delta.get("op") != "set":
        raise IdentitySuspicionError("reconhecimento_identidade aceita somente set do estado compacto inteiro")
    if delta.get("visibilidade", "operacional") != "operacional":
        raise IdentitySuspicionError("reconhecimento de NPC usa visibilidade operacional")
    motive = delta.get("motivo_identidade")
    if motive not in {"evidencia", "confirmacao"}:
        raise IdentitySuspicionError("motivo_identidade deve ser evidencia ou confirmacao")
    fact = delta.get("fato_canonico")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise IdentitySuspicionError("mudança de identidade exige fato_canonico concreto")
    _validate_source(delta.get("fonte"), "mudança de identidade")
    actor = delta.get("actor_resultado", "nao_aplicavel")
    if actor not in ACTOR_RESULTS:
        raise IdentitySuspicionError("actor_resultado inválido")
    if motive == "confirmacao" and delta.get("confirmacao_canonica") is not True:
        raise IdentitySuspicionError("confirmação de identidade exige confirmacao_canonica=true")
    validate_state(delta.get("valor"), registry)
    return delta


def _suspicion_map(state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {_edge_key(item): item for item in state["suspeitas"]}


def _confirmation_map(state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {_edge_key(item, confirmed=True): item for item in state["confirmacoes"]}


def validate_transition(
    entity_id: str,
    before: Any,
    delta: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    validate_identity_delta(delta, registry)
    old = validate_state(before, registry)
    new = validate_state(delta["valor"], registry)
    old_s = _suspicion_map(old)
    new_s = _suspicion_map(new)
    old_c = _confirmation_map(old)
    new_c = _confirmation_map(new)
    motive = delta["motivo_identidade"]

    if motive == "evidencia":
        if old_c != new_c:
            raise IdentitySuspicionError("evidência não pode alterar confirmações")
        changed = [key for key in set(old_s) | set(new_s) if old_s.get(key) != new_s.get(key)]
        if len(changed) != 1:
            raise IdentitySuspicionError("cada fato pode alterar exatamente uma suspeita")
        key = changed[0]
        before_item = old_s.get(key)
        after_item = new_s.get(key)
        if after_item is None:
            raise IdentitySuspicionError("evidência não pode remover suspeita")
        old_e = list((before_item or {}).get("evidencias") or [])
        new_e = list(after_item.get("evidencias") or [])
        if len(old_e) >= MAX_EVIDENCE:
            raise IdentitySuspicionError("suspeita já está forte; nova evidência não altera o estado")
        if new_e[:-1] != old_e or len(new_e) != len(old_e) + 1:
            raise IdentitySuspicionError("nova evidência deve apenas acrescentar um item à aresta existente")
        evidence = new_e[-1]
        if evidence["fonte"] != str(delta["fonte"]).strip():
            raise IdentitySuspicionError("fonte da evidência deve coincidir com a fonte do delta")
        expected = evidence_id(
            entity_id,
            key[0],
            key[1],
            evidence["tipo"],
            str(delta["fonte"]),
            str(delta["fato_canonico"]),
        )
        if evidence["id"] != expected:
            raise IdentitySuspicionError("id da evidência não corresponde ao fato/fonte declarados")
        if evidence["tipo"] in ACTOR_MASKABLE and delta.get("actor_resultado") == "sucesso":
            raise IdentitySuspicionError("Actor bem-sucedido impede evidência puramente performática")
        return new

    # Confirmação é um fato qualitativamente diferente; número de pistas nunca basta.
    if delta.get("confirmacao_canonica") is not True:
        raise IdentitySuspicionError("confirmação exige fato canônico explícito")
    added = [key for key in new_c if key not in old_c]
    if len(added) != 1 or any(key not in new_c for key in old_c):
        raise IdentitySuspicionError("cada confirmação deve acrescentar exatamente uma identidade")
    key = added[0]
    if new_c[key]["fonte"] != str(delta["fonte"]).strip():
        raise IdentitySuspicionError("fonte da confirmação deve coincidir com a fonte do delta")
    # A aresta equivalente pode desaparecer ao confirmar; outras suspeitas permanecem byte-lógicas.
    expected_s = copy.deepcopy(old_s)
    expected_s.pop(key, None)
    if new_s != expected_s:
        raise IdentitySuspicionError("confirmar só pode remover a suspeita equivalente; outras arestas permanecem")
    return new


def _npc_state(repo: Path, term: str) -> tuple[str, dict[str, Any], str]:
    index = _load(repo / NPC_INDEX)
    if not isinstance(index, dict) or not isinstance(index.get("npcs"), dict):
        raise IdentitySuspicionError("índice NPC inválido")
    entity_id, entry, candidates = contexto_core.resolve_entity(index["npcs"], term)
    if entity_id is None or not isinstance(entry, dict):
        raise IdentitySuspicionError(
            f"NPC não resolvido: {term!r}" + (f"; candidatos: {', '.join(candidates)}" if candidates else "")
        )
    rel = entry.get("arquivo")
    if not isinstance(rel, str):
        raise IdentitySuspicionError(f"{entity_id}: fragmento NPC não indexado")
    doc = _load(repo / rel)
    payload = doc.get("npc") if isinstance(doc, dict) else None
    if not isinstance(payload, dict):
        raise IdentitySuspicionError(f"{entity_id}: fragmento NPC inválido")
    return entity_id, payload, rel


def validate_batch(repo: Path, records: Iterable[dict[str, Any]]) -> int:
    registry = load_registry(repo)
    deltas: list[dict[str, Any]] = []
    for record in records:
        for delta in record.get("deltas") or []:
            if is_identity_delta(delta):
                validate_identity_delta(delta, registry)
                deltas.append(delta)
    if not deltas:
        return 0
    working: dict[str, dict[str, Any]] = {}
    for delta in deltas:
        entity_id = str(delta["alvo"]).split(":", 1)[1]
        if entity_id not in working:
            _, payload, _ = _npc_state(repo, entity_id)
            working[entity_id] = validate_state(payload.get(STATE_FIELD), registry)
        working[entity_id] = validate_transition(entity_id, working[entity_id], delta, registry)
    return len(deltas)


def propose_evidence(
    repo: Path,
    *,
    npc: str,
    observed: str,
    possible: str,
    evidence_type: str,
    fact: str,
    source: str,
    actor_result: str,
) -> dict[str, Any]:
    registry = load_registry(repo)
    entity_id, payload, rel = _npc_state(repo, npc)
    observed_id = resolve_identity(registry, observed)
    possible_id = resolve_identity(registry, possible)
    if observed_id == possible_id:
        raise IdentitySuspicionError("identidade observada e possível não podem ser iguais")
    if evidence_type not in EVIDENCE_TYPES:
        raise IdentitySuspicionError("tipo de evidência inválido")
    if actor_result not in ACTOR_RESULTS:
        raise IdentitySuspicionError("resultado de Actor inválido")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise IdentitySuspicionError("evidência exige fato concreto")
    source = _validate_source(source, "evidência")
    if evidence_type in ACTOR_MASKABLE and actor_result == "sucesso":
        return {
            "schema_reconhecimento_identidade": SCHEMA,
            "npc": entity_id,
            "resultado": "sem_delta",
            "motivo": "Actor bem-sucedido sustentou a performance; nenhuma pista performática nova é registrada",
            "fonte_npc": rel,
        }

    state = validate_state(payload.get(STATE_FIELD), registry)
    key = (observed_id, possible_id)
    if key in _confirmation_map(state):
        return {"schema_reconhecimento_identidade": SCHEMA, "npc": entity_id, "resultado": "sem_delta", "motivo": "identidade já confirmada"}
    current = _suspicion_map(state).get(key)
    old_e = list((current or {}).get("evidencias") or [])
    if len(old_e) >= MAX_EVIDENCE:
        return {"schema_reconhecimento_identidade": SCHEMA, "npc": entity_id, "resultado": "sem_delta", "motivo": "suspeita já está forte; novas pistas não promovem confirmação"}
    eid = evidence_id(entity_id, observed_id, possible_id, evidence_type, source, fact)
    if any(evidence["id"] == eid for item in state["suspeitas"] for evidence in item["evidencias"]):
        return {"schema_reconhecimento_identidade": SCHEMA, "npc": entity_id, "resultado": "sem_delta", "motivo": "mesma evidência já registrada"}
    new = copy.deepcopy(state)
    mapping = _suspicion_map(new)
    if key in mapping:
        mapping[key]["evidencias"].append({"id": eid, "tipo": evidence_type, "fonte": source})
    else:
        new["suspeitas"].append(
            {"observada": observed_id, "possivel": possible_id, "evidencias": [{"id": eid, "tipo": evidence_type, "fonte": source}]}
        )
    new = validate_state(new, registry)
    delta = {
        "alvo": f"npc:{entity_id}",
        "op": "set",
        "caminho": STATE_FIELD,
        "valor": new,
        "motivo_identidade": "evidencia",
        "fato_canonico": fact.strip(),
        "fonte": source,
        "actor_resultado": actor_result,
    }
    validate_transition(entity_id, state, delta, registry)
    return {
        "schema_reconhecimento_identidade": SCHEMA,
        "npc": entity_id,
        "resultado": "registrar_delta",
        "projecao_depois": project(new, registry),
        "delta": delta,
        "fonte_npc": rel,
    }


def propose_confirmation(
    repo: Path,
    *,
    npc: str,
    observed: str,
    identity: str,
    fact: str,
    source: str,
) -> dict[str, Any]:
    registry = load_registry(repo)
    entity_id, payload, rel = _npc_state(repo, npc)
    observed_id = resolve_identity(registry, observed)
    identity_id = resolve_identity(registry, identity)
    if observed_id == identity_id:
        raise IdentitySuspicionError("confirmação precisa ligar persona a identidade diferente")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise IdentitySuspicionError("confirmação exige fato concreto")
    source = _validate_source(source, "confirmação")
    state = validate_state(payload.get(STATE_FIELD), registry)
    key = (observed_id, identity_id)
    if key in _confirmation_map(state):
        return {"schema_reconhecimento_identidade": SCHEMA, "npc": entity_id, "resultado": "sem_delta", "motivo": "identidade já confirmada"}
    new = copy.deepcopy(state)
    new["suspeitas"] = [item for item in new["suspeitas"] if _edge_key(item) != key]
    new["confirmacoes"].append({"observada": observed_id, "identidade": identity_id, "fonte": source})
    new = validate_state(new, registry)
    delta = {
        "alvo": f"npc:{entity_id}",
        "op": "set",
        "caminho": STATE_FIELD,
        "valor": new,
        "motivo_identidade": "confirmacao",
        "fato_canonico": fact.strip(),
        "fonte": source,
        "actor_resultado": "nao_aplicavel",
        "confirmacao_canonica": True,
    }
    validate_transition(entity_id, state, delta, registry)
    return {
        "schema_reconhecimento_identidade": SCHEMA,
        "npc": entity_id,
        "resultado": "registrar_delta",
        "projecao_depois": project(new, registry),
        "delta": delta,
        "fonte_npc": rel,
    }


def check(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        registry = load_registry(repo)
        index = _load(repo / NPC_INDEX)
        if not isinstance(index, dict) or not isinstance(index.get("npcs"), dict):
            raise IdentitySuspicionError("índice NPC inválido")
        valid_ids = set(registry["identidades"])
        for entity_id, entry in index["npcs"].items():
            if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
                continue
            doc = _load(repo / entry["arquivo"])
            payload = doc.get("npc") if isinstance(doc, dict) else None
            if not isinstance(payload, dict):
                continue
            relational = payload.get("identidade_relacional", "ren")
            if relational not in valid_ids:
                errors.append(f"{entity_id}: identidade_relacional desconhecida: {relational!r}")
            if STATE_FIELD in payload:
                try:
                    validate_state(payload[STATE_FIELD], registry)
                except IdentitySuspicionError as exc:
                    errors.append(f"{entity_id}: {exc}")
    except IdentitySuspicionError as exc:
        errors.append(str(exc))
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    evidence = sub.add_parser("evidencia", help="prepara delta read-only de uma pista de identidade")
    evidence.add_argument("npc")
    evidence.add_argument("--observada", required=True)
    evidence.add_argument("--possivel", required=True)
    evidence.add_argument("--tipo", required=True, choices=sorted(EVIDENCE_TYPES))
    evidence.add_argument("--fato", required=True)
    evidence.add_argument("--fonte", required=True)
    evidence.add_argument("--actor", choices=sorted(ACTOR_RESULTS), default="nao_aplicavel")

    confirmation = sub.add_parser("confirmar", help="prepara confirmação explícita; suspeita forte não chama isto sozinha")
    confirmation.add_argument("npc")
    confirmation.add_argument("--observada", required=True)
    confirmation.add_argument("--identidade", required=True)
    confirmation.add_argument("--fato", required=True)
    confirmation.add_argument("--fonte", required=True)

    sub.add_parser("check", help="valida registro e estados atuais")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "evidencia":
            result = propose_evidence(
                repo,
                npc=args.npc,
                observed=args.observada,
                possible=args.possivel,
                evidence_type=args.tipo,
                fact=args.fato,
                source=args.fonte,
                actor_result=args.actor,
            )
        elif args.cmd == "confirmar":
            result = propose_confirmation(
                repo,
                npc=args.npc,
                observed=args.observada,
                identity=args.identidade,
                fact=args.fato,
                source=args.fonte,
            )
        else:
            errors = check(repo)
            result = {"ok": not errors, "erros": errors}
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0 if not errors else 1
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (IdentitySuspicionError, OSError, yaml.YAMLError) as exc:
        print(f"FALHA IDENTIDADES — {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
