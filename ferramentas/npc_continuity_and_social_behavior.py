#!/usr/bin/env python3
"""Fachada pública v2 de continuidade e comportamento social de NPCs.

Elenco, memória, medidores relacionais, identidade, reputação, personalidade e
iniciativa continuam com suas fontes canônicas próprias. Esta fachada compõe os
motores existentes no mesmo preparo/concluir e publica uma única identidade de
módulo. Nomeação explícita usa catálogo offline e reservas não canônicas; não
adiciona scan, sorteio ou chamada ao turno comum.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

import yaml

from _module_facade import attach_coverage, combine_checks
import dialogo_relacional as _dialogue
import estado_relacional as _relationships
import identidades as _identities
import iniciativa_elenco as _initiative
import iniciativa_elenco_conclusao as _initiative_conclusion
import iniciativa_elenco_estado as _initiative_receipts
import memoria_cena as _scene_memory
import memoria_cena_iniciativa as _scene_social
import memoria_duravel as _durable
import nomes_npcs as _names
import personalidade_decisoria as _personality
import reputacao_publica as _reputation

FACADE_SCHEMA = 2
IMPLEMENTATION_VERSION = "1.1.0"
MODULE_ID = "npc_continuity_and_social_behavior"
CAPABILITIES = (
    "social_initiative",
    "presence_and_identity",
    "relationship_memory_reputation",
)
LEGACY_ALIASES = ("npc_social_initiative",)
LEGACY_COMPONENTS = (
    "memoria_cena",
    "memoria_duravel",
    "estado_relacional",
    "dialogo_relacional",
    "personalidade_decisoria",
    "identidades",
    "reputacao_publica",
    "iniciativa_social",
    "iniciativa_elenco",
)

# A composição referencia as fontes; nunca replica seu conteúdo em outro estado.
SOURCE_OWNERSHIP = {
    "scene_cast": "estado/estado-atual.yaml:estado_narrativo.elenco_cena",
    "npc_state": "estado/npcs/index.yaml + fragmento dirigido",
    "relationship_and_memory": "estado/relacoes/index.yaml + fragmento dirigido",
    "identity": _identities.REGISTRY.as_posix(),
    "reputation": _reputation.STATE_FILE.as_posix(),
    "initiative_receipts": _initiative_receipts.STATE.as_posix(),
    "name_catalog": _names.CATALOG.as_posix(),
    "name_reservations": _names.RESERVATIONS.as_posix(),
}

# Compatibilidade com os nomes usados pela composição histórica da crônica.
VERSION = _scene_memory.VERSION
KEY = _scene_memory.KEY
TICKET_KEY = _scene_memory.TICKET_KEY
TRANSACTION_KEY = _durable.TRANSACTION_KEY
CAST_PATH = _scene_memory.CAST_PATH
SceneMemoryError = _scene_memory.SceneMemoryError
DurableMemoryError = _durable.DurableMemoryError
CastInitiativeError = _initiative.CastInitiativeError
InitiativeStateError = _initiative_receipts.InitiativeStateError

INITIATIVE_SCHEMA = _initiative.SCHEMA
INITIATIVE_PUBLIC_KEY = _initiative.PUBLIC_KEY
INITIATIVE_TICKET_KEY = _initiative.TICKET_KEY
INITIATIVE_TRANSACTION_KEY = _initiative.TRANSACTION_KEY
SOCIAL_PERSISTENCE_KEY = "continuidade_npc"


def generate_name(repo: Path, **conditions: Any) -> dict[str, Any]:
    """Reserva nome do catálogo sem criar NPC, parentesco ou presença."""
    return attach_coverage(
        _names.reserve(repo, **conditions),
        module_id=MODULE_ID,
        phase="gerar_nome",
        applicability="aplicavel",
    )


def register_authoritative_name(repo: Path, **source: Any) -> dict[str, Any]:
    """Documenta nome imposto por fonte/jogador/parentesco, nunca por estética."""
    return attach_coverage(
        _names.reserve_external(repo, **source),
        module_id=MODULE_ID,
        phase="registrar_nome",
        applicability="aplicavel",
    )


def interlocutors(value: list[str] | None):
    """Seleciona o subconjunto que recebe decisão no mesmo carregamento."""

    return _scene_social.interlocutors(value)


def attach(
    repo: Path,
    prepared: dict[str, Any],
    *,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
    participants: list[str] | None = None,
    base_in_context: Any = None,
    prospective_participants: list[str] | None = None,
    max_output_bytes: int = 8192,
) -> dict[str, Any]:
    """Compõe elenco, memória e iniciativa no envelope de preparo existente."""

    result = _scene_social.attach(
        repo,
        prepared,
        decode_ticket=decode_ticket,
        encode_ticket=encode_ticket,
        participants=participants,
        base_in_context=base_in_context,
        prospective_participants=prospective_participants,
        max_output_bytes=max_output_bytes,
    )
    applicability = "aplicavel" if (
        participants or prospective_participants or base_in_context
    ) else "nao_aplicavel"
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar",
        applicability=applicability,
    )


def compile_cast(
    payload: dict[str, Any],
    transaction: dict[str, Any],
    *,
    repo: Path | None = None,
) -> dict[str, Any]:
    """Revalida o elenco pela fonte de cena existente, sem writer próprio."""

    return _scene_memory.compile_cast(payload, transaction, repo=repo)


def resume(
    repo: Path,
    result: dict[str, Any],
    *,
    max_output_bytes: int = 8192,
    records: list[dict[str, Any]] | None = None,
    measure: Callable[[Any], int] = _scene_memory.size,
) -> dict[str, Any]:
    """Recompõe elenco e memória dirigida em retomada fria."""

    return _scene_memory.resume(
        repo,
        result,
        max_output_bytes=max_output_bytes,
        records=records,
        measure=measure,
    )


def _require_durable_relationship_facts(transaction: dict[str, Any]) -> None:
    """Impede incremento relacional novo sem o fato social transacional.

    A inicialização de um NPC recém-criado continua sendo responsabilidade do
    contrato de bootstrap. Mudanças posteriores devem entrar como
    ``memoria.fatos[tipo=relacao]``; o compilador durável então produz o único
    delta de medidor e a memória correspondente com a mesma evidência.
    """

    deltas = transaction.get("deltas", []) if isinstance(transaction, dict) else []
    loose = [
        delta
        for delta in deltas
        if _relationships.is_relationship_delta(delta)
        and not (delta.get("op") == "set" and delta.get("inicializacao") is True)
    ]
    if loose:
        raise DurableMemoryError(
            "mudança relacional incremental exige memoria.fatos tipo relacao "
            "com participantes e evidencia literal no mesmo concluir; não envie "
            "delta manual de afinidade/confianca"
        )


def prepare_transaction(repo: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    """Compila fatos sociais no writer existente e rejeita delta solto."""

    _require_durable_relationship_facts(transaction)
    return _durable.prepare_transaction(repo, transaction)


def social_persistence_observation(
    transaction: dict[str, Any],
) -> dict[str, Any] | None:
    """Resume fatos já validados para publicação após o writer concluir.

    Esta projeção não é estado e não substitui a memória durável. O chamador só
    deve anexá-la ao resultado depois do sucesso transacional, razão pela qual
    ela pode afirmar ``persistidos`` sem abrir ou consultar qualquer fonte.
    """

    block = transaction.get(TRANSACTION_KEY) if isinstance(transaction, dict) else None
    facts = block.get("fatos") if isinstance(block, dict) else None
    if not isinstance(facts, list) or not facts:
        return None
    by_type = {
        kind: sum(
            isinstance(fact, dict) and fact.get("tipo") == kind for fact in facts
        )
        for kind in ("informacao", "relacao", "promessa", "marco")
    }
    with_evidence = sum(
        isinstance(fact, dict)
        and isinstance(fact.get("evidencia"), dict)
        and bool(fact["evidencia"].get("trecho"))
        for fact in facts
    )
    return {
        "schema_npc_continuity": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "fatos_sociais_persistidos": len(facts),
        "fatos_sociais_com_evidencia": with_evidence,
        "por_tipo": by_type,
    }


def publish_social_persistence(
    result: dict[str, Any], observation: dict[str, Any] | None
) -> dict[str, Any]:
    """Publica telemetria somente no envelope de uma conclusão bem-sucedida."""

    if observation is not None:
        result[SOCIAL_PERSISTENCE_KEY] = observation
        systems = result.setdefault("sistemas_narrativos", [])
        if MODULE_ID not in systems:
            systems.append(MODULE_ID)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel" if observation is not None else "nao_aplicavel",
    )


def classify_actor_context(
    npc_id: str,
    *,
    present: list[str] | None = None,
    contactable: list[str] | None = None,
    mentioned: list[str] | None = None,
    known: bool = False,
) -> str:
    """Classifica contexto sem converter seleção, menção ou cadastro em presença."""

    return _initiative.classify_actor_context(
        npc_id,
        present=present,
        contactable=contactable,
        mentioned=mentioned,
        known=known,
    )


def project_voice(npc_id: str, role: Any) -> dict[str, Any] | None:
    """Projeta o perfil estável da textura, sem interpretar humor como valor."""

    return _personality.project(npc_id, role)


def evaluate_autonomous_options(
    profile: dict[str, Any], options: list[dict[str, Any]]
) -> dict[str, Any]:
    """Avalia afinidades declaradas; gates continuam sem executar a ação."""

    return _personality.evaluate_options(profile, options)


def project_dialogue(
    npc_payload: Any, *, role: str | None = None
) -> dict[str, Any] | None:
    return _dialogue.project(npc_payload, role=role)


def prepare_initiative(*args: Any, **kwargs: Any):
    return _initiative.attach_loaded(*args, **kwargs)


def initiative_ticket_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _initiative_conclusion.ticket_meta(payload)


def strip_initiative_ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _initiative_conclusion.strip_ticket_payload(payload)


def initiative_writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    return _initiative_conclusion.writer_transaction(transaction)


def prepare_initiative_conclusion(
    repo: Path, meta: Any, transaction: dict[str, Any]
) -> dict[str, Any]:
    return _initiative_conclusion.prepare(repo, meta, transaction)


def install_initiative_conclusion(
    repo: Path,
    meta: Any,
    plan: dict[str, Any],
    *,
    ticket_id: str,
    transaction_id: str,
) -> dict[str, Any]:
    result = _initiative_conclusion.install(
        repo,
        meta,
        plan,
        ticket_id=ticket_id,
        transaction_id=transaction_id,
    )
    outcomes = list(result.get("resultados") or [])
    result.update(
        schema_npc_continuity=FACADE_SCHEMA,
        module_id=MODULE_ID,
        metricas={
            "decisoes_persistidas": sum(not row.get("reutilizado") for row in outcomes),
            "aberturas_apresentadas": sum(
                row.get("resultado") == "apresentada" for row in outcomes
            ),
            "silencios_explicitos": sum(
                row.get("resultado") in {"silencio_justificado", "nao_elegivel"}
                for row in outcomes
            ),
            "repeticoes_reutilizadas": sum(bool(row.get("reutilizado")) for row in outcomes),
        },
    )
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir_iniciativa",
        applicability="aplicavel",
    )


def _list_check(check: Callable[[Path], list[str]]) -> Callable[[Path], dict[str, Any]]:
    def run(repo: Path) -> dict[str, Any]:
        errors = check(repo)
        return {"ok": not errors, "erros": errors}

    return run


def _behavior_check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        receipts = _initiative_receipts.load(repo)
    except _initiative_receipts.InitiativeStateError as exc:
        errors.append(str(exc))
        receipts = _initiative_receipts.empty_state()

    contexts = {
        state: classify_actor_context(
            "npc_fixture",
            present=["npc_fixture"] if state == "presente" else [],
            contactable=["npc_fixture"] if state == "contactavel" else [],
            mentioned=["npc_fixture"] if state == "mencionado" else [],
            known=state in {"apenas_conhecido", "mencionado"},
        )
        for state in ("presente", "contactavel", "mencionado", "apenas_conhecido")
    }
    if set(contexts.values()) != set(contexts):
        errors.append("presença, contato, menção e cadastro não permanecem distintos")
    return {
        "ok": not errors,
        "erros": errors,
        "contextos": contexts,
        "recibos_iniciativa": len(receipts["decisoes"]),
    }


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("social_initiative", _behavior_check),
            ("relationship_state", _list_check(_relationships.check)),
            ("identity_separation", _list_check(_identities.check)),
            ("reputation_by_persona", _list_check(_reputation.check)),
            ("name_catalog_and_reservations", _names.check),
        ),
        contract={
            "source_ownership": SOURCE_OWNERSHIP,
            "interlocutor_creates_presence": False,
            "initiative_creates_encounter_secret_sidequest_or_ren_action": False,
            "suspicion_confirms_identity": False,
            "personas_share_reputation_automatically": False,
            "narrator_memory_is_npc_knowledge": False,
            "relationship_change_without_durable_fact": False,
            "additional_orchestration_calls": 0,
            "new_scheduler": False,
            "new_rng": True,
            "naming_rng_only_on_explicit_request": True,
            "name_reservation_creates_npc_or_kinship": False,
            "full_name_duplicates_allowed": False,
            "component_reuse_requires_explicit_permission": True,
            "parallel_state": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("check")
    commands.add_parser("catalogo-nomes")
    generate = commands.add_parser("gerar-nome", help="reserva nome sem criar NPC")
    generate.add_argument("--reserva", required=True)
    generate.add_argument("--genero", required=True, choices=["masculino", "feminino", "neutro"])
    generate.add_argument("--raca", required=True)
    generate.add_argument("--regiao", required=True, help="região de origem, não residência")
    generate.add_argument("--cultura")
    surname = generate.add_mutually_exclusive_group()
    surname.add_argument("--sem-sobrenome", action="store_true")
    surname.add_argument("--tipo-sobrenome", choices=_names.SURNAME_TYPES, default="sobrenome")
    generate.add_argument("--permitir-reuso", action="store_true")
    register = commands.add_parser("registrar-nome", help="exceção nominal com autoridade explícita")
    register.add_argument("--reserva", required=True)
    register.add_argument("--nome", required=True)
    register.add_argument("--origem", required=True, choices=_names.EXTERNAL_ORIGINS)
    register.add_argument("--evidencia", required=True)
    cancel = commands.add_parser("cancelar-nome", help="libera somente proposta não materializada")
    cancel.add_argument("--reserva", required=True)
    # A porta anterior aceitava --repo também depois de check; preservar CLI.
    for command in commands.choices.values():
        command.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
        elif args.cmd == "gerar-nome":
            result = generate_name(
                repo, reservation=args.reserva, gender=args.genero, race=args.raca,
                region=args.regiao, culture=args.cultura,
                surname_type=None if args.sem_sobrenome else args.tipo_sobrenome,
                allow_reuse=args.permitir_reuso,
            )
        elif args.cmd == "registrar-nome":
            result = register_authoritative_name(
                repo, reservation=args.reserva, name=args.nome,
                origin=args.origem, evidence=args.evidencia,
            )
        else:
            result = (
                _names.catalog_summary(repo) if args.cmd == "catalogo-nomes"
                else _names.cancel(repo, args.reserva)
            )
            attach_coverage(result, module_id=MODULE_ID, phase=args.cmd.replace("-", "_"), applicability="nao_aplicavel")
    except (_names.NpcNameError, OSError) as exc:
        result = {"ok": False, "module_id": MODULE_ID, "erros": [str(exc)]}
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
