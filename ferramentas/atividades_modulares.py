"""Contrato compartilhado de passagens modulares; não comprova efeito narrativo.

Rotas e subfases são as portas já existentes. A unidade é uma passagem por
operação/fase/objeto, nunca o número de NPCs, linhas do resultado ou efeitos.
"""
from __future__ import annotations

import hashlib
import base64
import json
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.0.0"

# Fases públicas, alvo e escopo de uma negativa operacional. O motivo descreve
# somente o hook examinado; não afirma ausência de oportunidade no mundo.
PHASES = {
    "turn_and_session_orchestration": {
        **{phase: ("cena" if phase == "preparar" else "ticket", "controle_transacional")
           for phase in ("preparar", "concluir", "confirmar", "registrar")},
        **{f"sessao_{phase}": ("sessao_operacional", "lifecycle_sessao")
           for phase in ("status", "checkpoint", "encerrar", "iniciar", "recuperar")},
    },
    "context_and_memory": {
        "consulta": ("consulta_contexto", "consulta_dirigida"),
        "preparar": ("cena", "memoria_de_cena_solicitada"),
        "concluir": ("ticket", "memoria_duravel_do_lote"),
    },
    "npc_continuity_and_social_behavior": {
        "preparar": ("cena", "elenco_selecionado_e_memoria_disponivel"),
        "concluir": ("ticket", "fatos_sociais_do_lote"),
        "concluir_iniciativa": ("ticket", "decisoes_de_iniciativa_autorizadas_no_ticket"),
        **{phase: ("reserva", "reserva_nominal") for phase in
           ("gerar_nome", "registrar_nome", "cancelar_nome", "catalogo_nomes")},
    },
    "scene_world_projection": {
        **{phase: ("cena", "gatilho_espacial_solicitado") for phase in
           ("preparar", "confirmar", "abrir")},
        "permanencia": ("cena", "janela_de_permanencia_no_local"),
    },
    "world_boundary_resolution": {
        "fronteira": ("fronteira", "janela_temporal_solicitada"),
        "preparar_lote": ("lote", "pendencias_do_lote"),
        "aplicar_lote": ("lote", "lote_e_recibos_de_retry"),
    },
    "sidequest_authoring": {
        "preparar": ("cena", "oportunidade_declarada_no_preparo"),
        "preparar_autoria": ("cena", "ancora_autoral_do_preparo"),
        "concluir": ("ticket", "oferta_declarada_no_lote"),
        "instalar": ("ticket", "oferta_preparada_para_instalacao"),
    },
    "sidequest_lifecycle": {
        "projetar": ("missao", "missoes_aceitas"),
        "status": ("missao", "missao_consultada"),
        "preparar": ("cena", "missoes_aceitas_no_preparo"),
        "concluir": ("ticket", "fatos_de_progresso_autorizados_no_ticket"),
    },
    "causal_narrative_routing": {
        "preparar": ("cena", "materia_causal_disponivel_no_preparo"),
        "concluir": ("ticket", "materia_causal_do_lote"),
        "rotear": ("materia", "candidatas_causais_autorizadas"),
    },
    "adversarial_operations": {
        phase: ("operacao_adversarial", "operacoes_autorizadas_e_recibos_de_retry")
        for phase in ("consulta", "compromisso", "efeito_material")
    },
    "rules_and_character_state": {
        "rolagem": ("rolagem", "rolagem_solicitada"),
        "concluir": ("ticket", "obrigacoes_mecanicas_do_ticket"),
    },
    "narrative_delivery": {"concluir": ("ticket", "entrega_transacional")},
}

PREPARE_MODULES = (
    "scene_world_projection", "sidequest_authoring", "sidequest_lifecycle",
    "causal_narrative_routing", "npc_continuity_and_social_behavior", "context_and_memory",
)
CONCLUDE_MODULES = (
    "turn_and_session_orchestration", "context_and_memory",
    "npc_continuity_and_social_behavior", "rules_and_character_state", "narrative_delivery",
)

# Condição independente dos recibos: ticket autorizado ou resultado do hook.
SUBPHASES = {
    ("preparar", "scene_world_projection", "permanencia"):
        (None, "permanencia_espacial"),
    ("preparar", "sidequest_authoring", "preparar_autoria"):
        (None, "sidequest_emergente"),
    ("concluir", "npc_continuity_and_social_behavior", "concluir_iniciativa"):
        ("iniciativa_elenco_nv16", "iniciativa_elenco"),
    ("concluir", "sidequest_authoring", "instalar"):
        ("sidequest_emergente_task46", "sidequest_emergente"),
    ("concluir", "sidequest_lifecycle", "concluir"):
        ("sidequests_ativas_task48", "progresso_sidequests"),
}

DIRECT_ROUTES = {
    ("world_boundary_resolution.py", "fronteira"): ("world_boundary_resolution", "fronteira"),
    ("world_boundary_resolution.py", "preparar"): ("world_boundary_resolution", "preparar_lote"),
    ("world_boundary_resolution.py", "aplicar"): ("world_boundary_resolution", "aplicar_lote"),
    ("sidequest_lifecycle.py", "projetar"): ("sidequest_lifecycle", "projetar"),
    ("sidequest_lifecycle.py", "status"): ("sidequest_lifecycle", "status"),
    ("causal_narrative_routing.py", "rotear"): ("causal_narrative_routing", "rotear"),
    **{("npc_continuity_and_social_behavior.py", phase.replace("_", "-")):
       ("npc_continuity_and_social_behavior", phase)
       for phase in ("gerar_nome", "registrar_nome", "cancelar_nome", "catalogo_nomes")},
}

DYNAMIC_ROUTES = {
    ("adversarial_operations.py", operation): ("adversarial_operations", phases)
    for operation, phases in {
        "status": ("consulta",),  # compatibilidade da porta histórica
        "preparar": ("consulta",), "materializar": ("consulta", "compromisso"),
        "comprometer": ("consulta", "compromisso"),
        "registrar-rolagem": ("consulta", "compromisso"),
        "resolver": ("consulta", "efeito_material"),
        "entregar-informacao": ("consulta", "efeito_material"),
        "percepcao-ren": ("consulta",), "agente": ("consulta",),
        "reconciliar": ("consulta",),
    }.items()
}


def phase_contract(module_id: str, phase: str) -> dict[str, Any]:
    try:
        target, scope = PHASES[module_id][phase]
    except KeyError as exc:
        raise ValueError(f"fase modular fora do contrato: {module_id}/{phase}") from exc
    cause = {
        "fatos_sociais_do_lote": "sem_fatos_sociais_no_lote",
        "memoria_duravel_do_lote": "sem_memoria_nova_no_lote",
        "obrigacoes_mecanicas_do_ticket": "sem_obrigacoes_mecanicas_no_ticket",
        "elenco_selecionado_e_memoria_disponivel": "sem_elenco_solicitado",
        "gatilho_espacial_solicitado": "sem_gatilho_espacial_solicitado",
        "oportunidade_declarada_no_preparo": "sem_ancora_de_oportunidade_declarada",
        "missoes_aceitas_no_preparo": "sem_missao_aceita_projetada",
        "materia_causal_disponivel_no_preparo": "sem_materia_causal_no_preparo",
    }.get(scope, f"sem_materia_no_hook:{scope}")
    return {"versao": CONTRACT_VERSION, "module_id": module_id, "fase": phase,
            "unidades": 1, "objeto": target, "escopo_negativa": scope, "causa_negativa": cause}


def operation_phases(program: str, args: list[str], *, blocked: bool = False
                     ) -> list[tuple[str, str | None]]:
    """Expectativa pela invocação, inclusive quando todo recibo foi removido."""
    operation = args[0] if args else ""
    if operation == "check" or "--help" in args or "-h" in args:
        return []
    if program in {"cronica", "cronica.py"}:
        if operation == "preparar":
            return [("turn_and_session_orchestration", "preparar"), *(
                [(module, "preparar") for module in PREPARE_MODULES] if not blocked else []
            )]
        if operation == "concluir":
            return [(module, "concluir") for module in CONCLUDE_MODULES]
        if operation == "sessao" and len(args) > 1 and f"sessao_{args[1]}" in PHASES["turn_and_session_orchestration"]:
            return [("turn_and_session_orchestration", f"sessao_{args[1]}")]
    if program == "contexto.py":
        return [("context_and_memory", "consulta")]
    if program in {"dados", "dados-lote", "dados.py", "dados-lote.py"}:
        return [("rules_and_character_state", "rolagem")]
    if program == "endpoints.py" and operation == "fronteira":
        return [("world_boundary_resolution", "fronteira")]
    if (program, operation) in DIRECT_ROUTES:
        return [DIRECT_ROUTES[program, operation]]
    if (program, operation) in DYNAMIC_ROUTES:
        module, phases = DYNAMIC_ROUTES[program, operation]
        return [(module, phases[0] if len(phases) == 1 else None)]
    # Algumas APIs de reparo históricas delegam a fase de saída. A associação
    # exige uma fase PUBLICADA pelo contrato, nunca uma string arbitrária.
    module_id = program.removesuffix(".py")
    if module_id in PHASES and operation:
        return [(module_id, operation.replace("-", "_"))] if operation.replace("-", "_") in PHASES[module_id] else []
    return []


def operation_args(args: list[str]) -> list[str]:
    """Remove somente a opção global de repositório, preservando a operação."""
    normalized = []
    index = 0
    while index < len(args):
        if args[index] == "--repo":
            index += 2
        elif args[index].startswith("--repo="):
            index += 1
        else:
            normalized.append(args[index])
            index += 1
    return normalized


def object_ref(kind: str, value: str) -> str:
    return f"{kind}:sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def observed_ticket(token: str | None) -> tuple[str | None, dict[str, Any]]:
    """Lê somente o ticket capturado, sem consultar estado posterior.

    Usa o wire format crn1 existente. Tokens ilegíveis não fornecem gatilhos nem
    identidade por checksum; a operação continua vinculada ao hash da chamada.
    """
    if not token or len(token) > 131072:
        return None, {}
    parts = token.split(".", 2)
    if len(parts) != 3 or parts[0] != "crn1" or len(parts[1]) != 20:
        return None, {}
    try:
        packed = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, 262144)
        if not decoder.eof or decoder.unconsumed_tail:
            return None, {}
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("schema_cronica_ticket") != 1:
            return None, {}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(canonical).hexdigest()[:20] != parts[1]:
            return None, {}
        return parts[1], payload
    except (ValueError, UnicodeError, zlib.error):
        return None, {}


@lru_cache(maxsize=1)
def producer_hash() -> str:
    """Fingerprint do pacote de emissão efetivamente carregado.

    Uma identidade compartilhada economiza repetir um SHA por hook. Identifica
    as fachadas e seu contrato de emissão, não o estado do mundo ou toda a árvore
    de dependências. A proveniência da medição conserva os hashes individuais.
    """
    files = sorted([*PHASES, "_module_facade", "atividades_modulares", "_cronica_nv14"])
    data = [(name, hashlib.sha256(Path(__file__).with_name(f"{name}.py").read_bytes()).hexdigest())
            for name in files]
    return hashlib.sha256(json.dumps(data, separators=(",", ":")).encode()).hexdigest()


def bind_output(result: dict[str, Any], *, operation: str | None = None) -> dict[str, Any]:
    """Correlaciona envelopes aninhados com o ticket externo já consolidado.

    Repetir apenas atualiza o vínculo prospectivo; não cria atividade, recibo ou
    efeito. O digest do ticket evita expor seu conteúdo na telemetria.
    """
    ids = result.get("ids") or {}
    scene = ids.get("cena") or result.get("cena_id") if isinstance(ids, dict) else None
    ticket = result.get("ticket_id")
    tx = result.get("transacao") or {}
    public_interaction = result.get("interacao") or {}
    interaction = public_interaction.get("interaction_ref") if isinstance(public_interaction, dict) else None
    if not interaction and isinstance(tx, dict):
        interaction = tx.get("interacao_ref") or tx.get("interaction_ref") or result.get("interacao_ref")
    binding = {}
    if ticket:
        binding["ticket_id"] = str(ticket)
    if scene:
        binding["cena_id"] = str(scene)
    if interaction:
        binding["interacao_ref"] = str(interaction)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            block = node.get("cobertura_avaliacao_modular")
            if isinstance(block, dict) and block.get("contrato_atividades") == CONTRACT_VERSION:
                if binding:
                    block["vinculo"] = dict(binding)
            for key, value in node.items():
                if key != "cobertura_avaliacao_modular":
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(result)
    return result
