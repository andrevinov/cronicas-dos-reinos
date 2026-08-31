#!/usr/bin/env python3
"""Porta pública/recovery da integração Task46, endurecida pela Task48.

O estado de oportunidades é o commit point da instalação: os quatro fragmentos
reservados podem ser reparados idempotentemente, mas a missão só passa a existir
depois que todos eles estão presentes e íntegros.

Task48 corrige duas propriedades observadas em rollout real:

- Task40 integrada usa o instante efetivo do turno quando já há avanço temporal
  pendente, em vez de voltar silenciosamente ao relógio consolidado;
- a revalidação do ticket compara um snapshot semântico explícito. Telemetria,
  fontes lidas e contadores de orçamento podem variar sem invalidar uma decisão
  semanticamente idêntica; relação, quests, mundo, cânone, atores e recompensa
  continuam invalidando o ticket quando mudam.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

import sidequests_integracao as _base

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

SEMANTIC_DIGEST_VERSION = 1
SEMANTIC_DIGEST_EXCLUDED = frozenset({"fontes_lidas", "metricas", "orcamento_pacote"})
CLOCK_SOURCE_EXPLICIT = "explicita"
CLOCK_SOURCE_CANONICAL = "canonico"
CLOCK_SOURCE_PENDING = "overlay_transacional"
CLOCK_SOURCES = {CLOCK_SOURCE_EXPLICIT, CLOCK_SOURCE_CANONICAL, CLOCK_SOURCE_PENDING}


def _semantic_snapshot(package: dict[str, Any]) -> dict[str, Any]:
    """Projeta somente fatos que podem mudar a decisão autoral Task40.

    A whitelist é deliberada. Incluir o pacote bruto aqui recriaria o bug da
    Task46 em que ``fontes_lidas``/``metricas`` mudavam o hash sem o mundo mudar.
    """
    package = _base._map(package, "pacote Task40")
    horizon = _base._map(
        package.get("horizonte_intencoes_canonicas"),
        "pacote.horizonte_intencoes_canonicas",
    )
    return {
        "digest_semantico_schema": SEMANTIC_DIGEST_VERSION,
        "resultado": package.get("resultado"),
        "origem": copy.deepcopy(package.get("origem")),
        "relacao_efetiva": copy.deepcopy(package.get("relacao_efetiva")),
        "quests": copy.deepcopy(package.get("quests")),
        "prazo_mundo": copy.deepcopy(package.get("prazo_mundo")),
        "horizonte_intencoes_canonicas": {
            "janela_dias": horizon.get("janela_dias"),
            "compativeis": copy.deepcopy(horizon.get("compativeis") or []),
        },
        "atores_causalmente_disponiveis": copy.deepcopy(
            package.get("atores_causalmente_disponiveis") or []
        ),
        "juppongatana_possiveis": copy.deepcopy(package.get("juppongatana_possiveis") or []),
        "envelope_recompensa": copy.deepcopy(package.get("envelope_recompensa")),
        "autoridade": copy.deepcopy(package.get("autoridade")),
    }


def _semantic_digest(package: dict[str, Any]) -> str:
    return _base._digest(_semantic_snapshot(package))


def _pending_instant(repo: Path):
    """Retorna o último instante temporal pendente, sem ler tempo consolidado.

    O writer atual persiste ``tempo/instante`` atômico. A expansão em memória
    também cobre pares legados; só se existir hora legada sem data é necessário
    consultar a data canônica como fallback.
    """
    pending_path = repo / _base.opportunity.transacoes.PENDING_PATH
    if not pending_path.is_file() or pending_path.stat().st_size == 0:
        return None
    try:
        records = _base.opportunity.transacoes.load_pending(repo)
        expanded = _base.opportunity.transacoes.tempo_transacional.expand_records(records)
    except (OSError, ValueError, _base.opportunity.transacoes.TransactionError) as exc:
        raise _base.EmergentSidequestIntegrationError(str(exc)) from exc

    date: str | None = None
    hour: str | None = None
    for record in expanded:
        for delta in record.get("deltas") or []:
            if delta.get("visibilidade", "operacional") == "narrador" or delta.get("op") != "set":
                continue
            target = delta.get("alvo")
            path = delta.get("caminho")
            if target == "tempo" and path in {"data_atual", "data"}:
                date = str(delta.get("valor"))
            elif target == "tempo" and path == "hora_aproximada":
                hour = str(delta.get("valor"))
            elif target == "estado" and path == "tempo.data_exata":
                date = str(delta.get("valor"))
            elif target == "estado" and path == "tempo.hora_aproximada":
                hour = str(delta.get("valor"))

    if hour is None:
        return None
    if date is None:
        try:
            canonical, _ = _base.opportunity.mundo.load_canonical_time(repo)
        except _base.opportunity.mundo.WorldEngineError as exc:
            raise _base.EmergentSidequestIntegrationError(str(exc)) from exc
        date = _base.opportunity.mundo.instant_parts(canonical)["data"]
    try:
        return _base.opportunity.mundo.parse_instant(date, hour)
    except _base.opportunity.mundo.WorldEngineError as exc:
        raise _base.EmergentSidequestIntegrationError(str(exc)) from exc


def _prepare_clock(repo: Path, explicit_now):
    if explicit_now is not None:
        return explicit_now, CLOCK_SOURCE_EXPLICIT
    pending = _pending_instant(repo)
    if pending is not None:
        return pending, CLOCK_SOURCE_PENDING
    # ``None`` é intencional: preserva o fail-fast Task40. Se o orçamento de
    # sidequests estiver cheio, Task40 retorna antes de abrir estado/tempo.yaml.
    return None, CLOCK_SOURCE_CANONICAL


def _current_effective_now(repo: Path):
    """Relógio efetivo = consolidado + overlay transacional corrente."""
    try:
        canonical, raw = _base.opportunity.mundo.load_canonical_time(repo)
        records = _base.opportunity.transacoes.load_pending(repo)
        effective, _ = _base.opportunity.transacoes.overlay_target(raw, records, "tempo")
        date = effective.get("data_atual") or effective.get("data")
        hour = effective.get("hora_aproximada")
        if date is None or hour is None:
            return canonical
        return _base.opportunity.mundo.parse_instant(str(date), str(hour))
    except (
        OSError,
        ValueError,
        _base.opportunity.mundo.WorldEngineError,
        _base.opportunity.transacoes.TransactionError,
    ) as exc:
        raise _base.EmergentSidequestIntegrationError(str(exc)) from exc


def _mark_clock_source(package: dict[str, Any], source: str) -> dict[str, Any]:
    package = copy.deepcopy(package)
    if source == CLOCK_SOURCE_PENDING:
        sources = list(package.get("fontes_lidas") or [])
        pending = _base.opportunity.transacoes.PENDING_PATH.as_posix()
        if pending not in sources:
            sources.append(pending)
        package["fontes_lidas"] = sources
        if _base._yaml_size(package) > _base.MAX_AUTHOR_PACKET_BYTES:
            raise _base.EmergentSidequestIntegrationError(
                "pacote autoral Task40 excedeu 8 KiB após registrar relógio efetivo"
            )
    return package


def integrate_prepare(
    repo: Path,
    base_result: dict[str, Any],
    *,
    signal_raw: Any,
    decode_ticket,
    encode_ticket,
    now: Any | None = None,
) -> dict[str, Any]:
    """Task46 + Task48: relógio efetivo e digest semântico no mesmo ticket."""
    planned_now, clock_source = _prepare_clock(repo, now)
    result = _base.integrate_prepare(
        repo,
        base_result,
        signal_raw=signal_raw,
        decode_ticket=decode_ticket,
        encode_ticket=encode_ticket,
        now=planned_now,
    )
    package_raw = result.get("sidequest_emergente")
    if not isinstance(package_raw, dict):
        return result
    package = _mark_clock_source(package_raw, clock_source)
    result["sidequest_emergente"] = package

    marker = result.get("sidequest_emergente_task46")
    if not isinstance(marker, dict) or marker.get("integrada_ao_ticket") is not True:
        return result

    token = result.get("ticket")
    if not isinstance(token, str):
        raise _base.EmergentSidequestIntegrationError("preparação Task48 perdeu ticket Task46")
    payload = copy.deepcopy(decode_ticket(token))
    meta = _base._map(payload.get(_base.TICKET_KEY), _base.TICKET_KEY)
    signal = _base._map(meta.get("sinal"), "ticket.sinal")
    signal["agora_fonte"] = clock_source
    meta["pacote_digest"] = _semantic_digest(package)
    new_token, new_id = encode_ticket(payload)
    result["ticket"] = new_token
    result["ticket_id"] = new_id
    marker = copy.deepcopy(marker)
    marker["digest_pacote"] = "semantico_task48_v1"
    marker["relogio_efetivo"] = clock_source
    result["sidequest_emergente_task46"] = marker
    total = _base._yaml_size(result)
    if total > _base.MAX_COMBINED_PREP_BYTES:
        raise _base.EmergentSidequestIntegrationError(
            f"preparação rara Task48 excede {_base.MAX_COMBINED_PREP_BYTES} bytes: {total}"
        )
    return result


def _plan_from_ticket(repo: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Revalida Task40 sem confundir telemetria com mudança causal."""
    signal = _base._map(meta.get("sinal"), "ticket.sinal")
    now_raw = _base._map(signal.get("agora"), "ticket.sinal.agora")
    source = signal.get("agora_fonte")
    try:
        ticket_now = _base.opportunity.mundo.parse_instant(
            str(now_raw.get("data")), str(now_raw.get("hora"))
        )
        if source is None:
            # Compatibilidade transitória: ticket Task46 emitido antes da Task48
            # conserva o digest bruto e o instante congelado antigos.
            now = ticket_now
        else:
            if source not in CLOCK_SOURCES:
                raise _base.EmergentSidequestIntegrationError(
                    f"fonte de relógio Task48 inválida: {source!r}"
                )
            now = ticket_now if source == CLOCK_SOURCE_EXPLICIT else _current_effective_now(repo)
        package = _base.opportunity.plan(
            repo,
            signaled=True,
            origin_type=signal.get("origem_tipo"),
            origin_id=signal.get("origem_id"),
            anchor_type=signal.get("ancora_tipo"),
            anchor=signal.get("ancora"),
            npc_id=signal.get("npc_id"),
            local_id=signal.get("local_id"),
            danger=str(signal.get("periculosidade")),
            tier=signal.get("tier"),
            now=now,
        )
    except (
        _base.opportunity.EmergentSidequestOpportunityError,
        _base.opportunity.mundo.WorldEngineError,
    ) as exc:
        raise _base.EmergentSidequestIntegrationError(str(exc)) from exc
    if package.get("resultado") != "material_para_planejamento":
        raise _base.EmergentSidequestIntegrationError(
            f"pacote Task40 deixou de estar disponível: {package.get('resultado')}"
        )
    actual = _base._digest(package) if source is None else _semantic_digest(package)
    if actual != meta.get("pacote_digest"):
        raise _base.EmergentSidequestIntegrationError(
            "snapshot semântico Task40 mudou desde cronica preparar; descarte o ticket e prepare novamente"
        )
    return package


def writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Remove o envelope reservado Task46 antes do writer canônico do turno."""
    clean = copy.deepcopy(transaction)
    clean.pop(_base.TRANSACTION_KEY, None)
    return clean


def prepare_installation(
    repo: Path,
    *,
    package: dict[str, Any],
    block: dict[str, Any],
    offer_scene_id: str,
    offer_summary: str,
) -> dict[str, Any]:
    """Reusa Task41–45 e mantém ponteiros compactos na missão."""
    plan = _base.prepare_installation(
        repo,
        package=package,
        block=block,
        offer_scene_id=offer_scene_id,
        offer_summary=offer_summary,
    )
    plan = copy.deepcopy(plan)
    plan["mission"]["contrato_adversarial"] = plan["adversarial_path"]
    return plan


def install(repo: Path, journal: dict) -> dict:
    """Instala uma sidequest em uma única transação Task46 recuperável."""
    journal = _base._freeze_targets(repo, journal)
    changed: list[str] = []

    # Fragmentos reservados primeiro. Retry aceita somente bytes idênticos.
    for target in journal["targets"][:-1]:
        rel = Path(str(target["path"]))
        path = repo / rel
        content = str(target["content"])
        if path.is_file():
            if path.read_text(encoding="utf-8") != content:
                raise _base.EmergentSidequestIntegrationError(
                    f"alvo Task46 divergiu durante instalação: {rel.as_posix()}"
                )
            continue
        _base._atomic_text(path, content)
        changed.append(rel.as_posix())

    # O estado compacto é o commit point e entra por último.
    state_target = journal["targets"][-1]
    state_path = repo / Path(str(state_target["path"]))
    desired_state = str(state_target["content"])
    current_text = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    if current_text != desired_state:
        try:
            current = _base.oportunidades.load_state(
                repo, _base.oportunidades.load_index(repo)
            )
        except _base.oportunidades.OpportunityError as exc:
            raise _base.EmergentSidequestIntegrationError(str(exc)) from exc
        mid = journal["plan"]["mission_id"]
        existing = current["missoes"].get(mid)
        if isinstance(existing, dict):
            if existing != journal["plan"]["mission"]:
                raise _base.EmergentSidequestIntegrationError(
                    "missão Task46 já existe com conteúdo divergente"
                )
        else:
            frozen = yaml.safe_load(desired_state)
            without = copy.deepcopy(frozen)
            without["missoes"].pop(mid, None)
            without["historico_recente"] = [
                item
                for item in without.get("historico_recente") or []
                if not (
                    isinstance(item, dict)
                    and item.get("id") == mid
                    and item.get("tipo") == "sidequest_emergente_materializada_task46"
                )
            ]
            if current != without:
                raise _base.EmergentSidequestIntegrationError(
                    "estado de oportunidades mudou durante instalação Task46; repita após reconciliar"
                )
            _base._atomic_text(state_path, desired_state)
            changed.append(_base.oportunidades.STATE.as_posix())

    (repo / _base.JOURNAL).unlink(missing_ok=True)
    return {
        "ok": True,
        "resultado": "sidequest_materializada",
        "mission_id": journal["plan"]["mission_id"],
        "quest_id": journal["plan"]["quest_id"],
        "transacao_instalacao": journal["id"],
        "arquivos_alterados": changed,
        "instalacoes_logicas": 1,
        "idempotente": True,
    }


def check(repo: Path) -> dict[str, Any]:
    """Congela os mesmos tetos da Task40 e os invariantes semânticos Task48."""
    errors: list[str] = []
    try:
        if _base.MAX_AUTHOR_PACKET_BYTES != _base.opportunity.MAX_PAYLOAD_BYTES:
            errors.append("teto Task46 do pacote autoral diverge da Task40")
        if _base.MAX_CANON_INTENTS != _base.opportunity.MAX_INTENT_FRAGMENTS:
            errors.append("teto Task46 de intenções diverge da Task40")
        if SEMANTIC_DIGEST_VERSION != 1:
            errors.append("versão do digest semântico Task48 divergiu")
        if SEMANTIC_DIGEST_EXCLUDED != frozenset({"fontes_lidas", "metricas", "orcamento_pacote"}):
            errors.append("campos observacionais excluídos do digest Task48 divergiram")
        index = _base.oportunidades.load_index(repo)
        if index.get("nova_origem_sidequests") not in {
            "emergente_causal_task40",
            "canonica_explicita",
        }:
            errors.append("origem operacional de sidequests desconhecida")
        journal = _base._load_journal(repo)
        if journal is not None and journal.get("schema_task46_journal") != _base.SCHEMA:
            errors.append("journal Task46 possui schema inesperado")
    except (
        _base.EmergentSidequestIntegrationError,
        _base.oportunidades.OpportunityError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "turno_neutro_leituras_task40_45": 0,
            "turno_neutro_fragmentos_emergentes": 0,
            "turno_neutro_horizonte_canonico": 0,
            "chamadas_orquestracao": 2,
            "pacote_autoral_max_bytes": _base.MAX_AUTHOR_PACKET_BYTES,
            "intencoes_max": _base.MAX_CANON_INTENTS,
            "instalacoes_por_oferta": 1,
            "digest_task40": "semantico_task48_v1",
            "relogio_task40": "canonico_mais_overlay_transacional",
            "schedulers_novos": 0,
            "relogios_novos": 0,
        },
    }


# A porta pública usa os wrappers corrigidos sem duplicar os motores 40–45.
globals()["integrate_prepare"] = integrate_prepare
globals()["_plan_from_ticket"] = _plan_from_ticket
globals()["prepare_installation"] = prepare_installation
globals()["install"] = install
globals()["check"] = check
