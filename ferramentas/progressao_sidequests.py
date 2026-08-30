#!/usr/bin/env python3
"""Task 45 — Sidequest Progression, Deadlines & Consequences.

A implementação base permanece isolada em ``_progressao_sidequests_task45_base``.
Esta porta aplica correções de autoridade/recovery descobertas pelo CI da Task45:

1. o lifecycle legado pode observar o mesmo prazo antes da Task45; nesse caso o
   mesmo desfecho terminal é reconciliado pela Task42, em vez de virar conflito;
2. uma resolução de consequência pode ser staged antes de o checkpoint automático
   falhar; a Task45 guarda o payload transacional completo antes do writer e o retry
   reapresenta exatamente esse payload até o checkpoint concluir, sem duplicar
   morte, recompensa, evento ou consequência.

A regra funcional continua a mesma: ``sidequests_emergentes``/Task41 define a quest;
``recompensas_sidequest``/Task43 governa recompensas e perdas;
``integridade_adversarial``/Task44 governa stakes e Protected Core;
``canon_bridge_runtime.finish``/Task42 governa o terminal canônico. Um desfecho
adversarial devido entra no Mundo Vivo como pendência ``resolver_sidequest`` e só
esta porta Task45 pode materializá-lo; ele nunca equivale a um no-op genérico. Não
há scheduler novo e a integração automática ao hot path continua reservada à Task46.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

import _progressao_sidequests_task45_base as _base


def _terminalize(
    repo: Path,
    mid: str,
    mission: dict[str, Any],
    doc: dict[str, Any],
    rel: Path,
    outcome: str,
    *,
    reason: str,
    current: Any,
    trigger: str,
) -> dict[str, Any]:
    """Fecha Task45 sem competir com o prune legado do mesmo prazo.

    ``oportunidades`` já conhecia expiração/falha temporal antes da Task45. Se
    esse prune observar primeiro exatamente o mesmo desfecho, não é erro nem um
    segundo motor: reconciliamos a Task42 sobre o lifecycle já terminalizado.
    Qualquer desfecho diferente continua falhando fechado.
    """
    terminal = doc["estado"].get("terminal")
    if isinstance(terminal, dict):
        if terminal.get("resultado") != outcome:
            raise _base.SidequestProgressionError(
                "Task45 já possui desfecho terminal divergente"
            )
        return terminal

    def reconcile_existing() -> dict[str, Any]:
        try:
            _base.canon_bridge_runtime.reconcile(repo, now=current)
        except _base.canon_bridge_runtime.CanonBridgeRuntimeError as exc:
            raise _base.SidequestProgressionError(str(exc)) from exc
        _, _, refreshed = _base._mission(repo, mid)
        if refreshed.get("estado") != outcome:
            raise _base.SidequestProgressionError(
                f"lifecycle terminalizou {mid} como {refreshed.get('estado')}, "
                f"mas Task45 esperava {outcome}"
            )
        return refreshed

    if mission.get("estado") == outcome:
        mission = reconcile_existing()
    else:
        try:
            result = _base.canon_bridge_runtime.finish(
                repo, mid, outcome, reason=reason, now=current
            )
            mission = result["missao"]
        except _base.canon_bridge_runtime.CanonBridgeRuntimeError as exc:
            # ``finish`` chama o lifecycle existente, que pode fazer prune pelo
            # próprio ``now`` antes de aplicar a transição explícita. Aceitamos
            # somente se ele chegou exatamente ao mesmo outcome pedido.
            _, _, refreshed = _base._mission(repo, mid)
            if refreshed.get("estado") != outcome:
                raise _base.SidequestProgressionError(str(exc)) from exc
            mission = reconcile_existing()

    terminal = {
        "resultado": outcome,
        "gatilho": trigger,
        "em": _base.mundo.instant_parts(current),
        "motivo": reason,
        "pendencia_id": None,
    }
    doc["estado"]["terminal"] = terminal
    _base._history(
        doc,
        {
            "tipo": "desfecho_terminal",
            "resultado": outcome,
            "gatilho": trigger,
            "em": _base.mundo.instant_parts(current),
        },
    )
    _base._atomic(repo / rel, doc)
    return terminal


def _transaction_state(
    repo: Path, txid: str
) -> tuple[str, dict[str, Any] | None]:
    """Retorna absent/pending/consolidated para uma transação Task45."""
    try:
        pending = _base.transacoes.load_pending(repo)
        existing = next((item for item in pending if item.get("id") == txid), None)
        if existing is not None:
            return "pending", copy.deepcopy(existing)
        session = _base.turno.current_session(repo)
    except (_base.transacoes.TransactionError, OSError, ValueError) as exc:
        raise _base.SidequestProgressionError(str(exc)) from exc

    ledger = repo / "sessoes" / f"{session:03d}" / _base.turno.LEDGER_NAME
    if not ledger.is_file():
        return "absent", None
    for pos, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _base.SidequestProgressionError(
                f"ledger inválido {ledger}:{pos}: {exc}"
            ) from exc
        if txid in (item.get("transacoes") or []):
            return "consolidated", None
    return "absent", None


def _recovery_transaction(
    repo: Path,
    doc: dict[str, Any],
    rel: Path,
    *,
    txid: str,
    mission: dict[str, Any],
    pending_id: str,
    chosen: str,
    narration: str,
    deltas: list[dict[str, Any]],
) -> dict[str, Any]:
    """Congela o payload completo antes do writer para reparar crash pós-stage."""
    stored = doc["estado"].get("transacao_pendente")
    if stored is not None:
        if not isinstance(stored, dict) or stored.get("id") != txid:
            raise _base.SidequestProgressionError(
                "Task45 possui transação de recuperação divergente"
            )
        return copy.deepcopy(stored)

    transaction = {
        "id": txid,
        "narracao": _base._text(narration, "narracao", 20, 2400),
        "resumo": _base._text(
            f"Sidequest {mission['quest_id']} materializa a consequência {chosen}.",
            "resumo",
            12,
            500,
        ),
        "modo": "mundo",
        "tags": [
            "task45-sidequest",
            f"missao:{mission['id']}",
            f"resolver-pendencia-mundo:{pending_id}",
        ],
        "deltas": copy.deepcopy(deltas),
    }
    doc["estado"]["transacao_pendente"] = copy.deepcopy(transaction)
    _base._atomic(repo / rel, doc)
    return transaction


def _assert_pending_matches_recovery(
    recovery: dict[str, Any], pending_record: dict[str, Any]
) -> None:
    """Garante que o buffer staged veio exatamente do payload Task45 congelado."""
    try:
        expected = _base.transacoes.build_pending_record(
            recovery, int(pending_record["sessao"])
        )
    except (
        _base.transacoes.TransactionError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise _base.SidequestProgressionError(str(exc)) from exc
    if expected != pending_record:
        raise _base.SidequestProgressionError(
            "transação staged diverge do payload de recuperação Task45"
        )


def resolve_pending(
    repo: Path,
    mission_ref: str,
    pending_id: str,
    *,
    chosen_escalation_id: str,
    proofs: Any,
    blocker: Any | None,
    narration: str,
    loss_evidences: Any | None = None,
    loss_narration: str | None = None,
) -> dict[str, Any]:
    """Materializa consequência terminal e repara retry parcial exactly-once."""
    _, mid, mission = _base._mission(repo, mission_ref)
    if mission.get("estado") not in {"falhada", "expirada"}:
        raise _base.SidequestProgressionError(
            "consequência terminal Task45 exige missão falhada/expirada"
        )
    doc, rel = _base._load_progress(repo, mission, mid)
    item, completed = _base._pending_record(repo, pending_id, mid)
    terminal = _base._map(doc["estado"].get("terminal"), "Task45.terminal")
    if terminal.get("pendencia_id") != pending_id:
        raise _base.SidequestProgressionError(
            "pendência não corresponde ao desfecho Task45"
        )

    allowed = _base._allowed_escalations(doc, str(terminal.get("gatilho")))
    chosen = _base._slug(chosen_escalation_id, "escalada_escolhida")
    if chosen not in allowed:
        raise _base.SidequestProgressionError(
            "escalada escolhida não pertence ao gatilho terminal da quest"
        )
    proof_map = _base._map(proofs, "provas_escaladas")
    if chosen not in proof_map:
        raise _base.SidequestProgressionError(
            "escalada escolhida exige prova causal literal"
        )

    activated = doc["estado"]["consequencias_ativadas"].get(chosen)
    writer: dict[str, Any]
    if activated is None:
        if item is None and not completed:
            raise _base.SidequestProgressionError(
                "pendência Task45 não está aberta nem concluída"
            )
        try:
            choice = _base.adversarial.resolve_escalation_choice(
                repo,
                mid,
                chosen_escalation_id=chosen,
                proofs=proof_map,
                blocker=blocker,
            )
            adv_doc, _ = _base.adversarial.load_contract(repo, mission)
            escalation = next(
                row
                for row in adv_doc["contrato"]["escaladas_possiveis"]
                if row["id"] == chosen
            )
            raw_consequence = {
                "titulo": f"Sidequest — {mission.get('titulo') or mission['quest_id']}",
                "descricao": escalation["consequencia"],
                "gravidade": escalation["gravidade"],
                "reversibilidade": escalation["reversibilidade"],
                "classe_impacto": escalation["classe_impacto"],
                "alvos_npc": list(escalation["alvos"]),
                "escalada_id": chosen,
            }
            authorized = _base.adversarial.authorize_sidequest_consequence(
                repo, mid, raw_consequence, proof=proof_map[chosen]
            )
        except _base.adversarial.AdversarialIntegrityError as exc:
            raise _base.SidequestProgressionError(str(exc)) from exc

        deltas = [
            {
                "alvo": "consequencia",
                "op": "registrar",
                "valor": authorized["valor"],
            }
        ]
        for effect in _base._effect_map(doc).get(chosen, []):
            deltas.append(
                {
                    "alvo": f"npc:{effect['npc_id']}",
                    "op": "set",
                    "caminho": "vida.estado",
                    "valor": effect["estado"],
                }
            )

        txid = _base._txid(mid, pending_id, chosen)
        transaction = _recovery_transaction(
            repo,
            doc,
            rel,
            txid=txid,
            mission=mission,
            pending_id=pending_id,
            chosen=chosen,
            narration=narration,
            deltas=deltas,
        )
        tx_state, pending_tx = _transaction_state(repo, txid)
        if tx_state == "pending":
            if pending_tx is None:
                raise _base.SidequestProgressionError(
                    "estado pending sem registro staged recuperável"
                )
            _assert_pending_matches_recovery(transaction, pending_tx)
        elif tx_state == "consolidated":
            transaction = None

        if transaction is not None:
            try:
                writer = _base.turno.register_transaction(repo, transaction)
            except (
                _base.transacoes.TransactionError,
                OSError,
                yaml.YAMLError,
                ValueError,
            ) as exc:
                # O payload completo já está congelado no fragmento Task45. Não
                # grave ``consequencias_ativadas`` nem feche a pendência; o retry
                # reapresentará exatamente esse payload, inclusive a narração.
                raise _base.SidequestProgressionError(str(exc)) from exc
        else:
            writer = {"ja_registrada": True, "consolidada": True}

        activated = {
            "escalada_id": chosen,
            "transacao": txid,
            "autoridade": authorized["autoridade"],
            "prova": authorized["valor"]["prova_causal"],
            "efeitos_npc": copy.deepcopy(_base._effect_map(doc).get(chosen, [])),
            "escolha_adversarial": {
                "obrigatorias_demonstradas": choice["obrigatorias_demonstradas"],
                "bloqueio_causal": choice["bloqueio_causal"],
            },
        }
        doc["estado"]["consequencias_ativadas"][chosen] = activated
        doc["estado"].pop("transacao_pendente", None)
        _base._history(
            doc,
            {
                "tipo": "consequencia_materializada",
                "escalada_id": chosen,
                "transacao": txid,
            },
        )
        _base._atomic(repo / rel, doc)
    else:
        writer = {"ja_registrada": True}

    # Crash após a transação/registro Task45 e antes de concluir a barreira é
    # reparável: a consequência já ativada apenas fecha a pendência restante.
    item, completed = _base._pending_record(repo, pending_id, mid)
    if item is not None:
        try:
            conclusion = _base.barreira_mundo.conclude(
                repo,
                pending_id,
                f"Task45 materializou {chosen} para {mid}",
            )
        except (
            _base.barreira_mundo.WorldPendingBarrierError,
            _base.mundo.WorldEngineError,
        ) as exc:
            raise _base.SidequestProgressionError(str(exc)) from exc
    else:
        conclusion = {"ja_concluida": completed}

    losses = None
    if loss_evidences is not None:
        try:
            losses = _base.quest_rewards.apply_losses(
                repo,
                mid,
                evidences=loss_evidences,
                narration=loss_narration or narration,
            )
        except _base.quest_rewards.QuestRewardError as exc:
            raise _base.SidequestProgressionError(str(exc)) from exc

    return {
        "ok": True,
        "resultado": "consequencia_materializada",
        "mission_id": mid,
        "escalada_id": chosen,
        "transacao_id": activated["transacao"],
        "writer": writer,
        "pendencia": conclusion,
        "perdas": losses,
    }


# Monkey-patch somente as fronteiras de autoridade/recovery. As demais regras
# continuam na implementação base, inclusive progresso factual, budgets e CLI.
_base._terminalize = _terminalize
_base.resolve_pending = resolve_pending

# Reexporta a superfície pública original após aplicar os patches.
for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)

# Garante que importadores recebam a versão corrigida, não a função original.
globals()["resolve_pending"] = resolve_pending


if __name__ == "__main__":
    raise SystemExit(_base.main())