"""Retry espacial na porta pública; recibo operacional, nunca fato do mundo.

Uma falha conserva a operação até conclusão com ticket espacial compatível.
Não sorteia, agenda, escreve cânone nem replica reservas dos produtores.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

import locais

PENDING = Path("runtime/preparo-espacial-pendente.json")
CANCELLATIONS = Path("runtime/preparos-espaciais-abandonados.jsonl")


def intent(kwargs):
    if kwargs.get("permanence_local"):
        return "permanencia"
    if kwargs.get("urban_transit"):
        return "transito"
    if any(kwargs.get(key) is not None for key in ("place", "action", "tier", "danger")):
        return "entrada"
    return None


def ticket_intent(payload):
    if payload.get("permanencia_espacial"):
        return "permanencia"
    if payload.get("transito_urbano"):
        return "transito"
    scene = payload.get("cena") or {}
    return "entrada" if scene.get("place") and scene.get("action") else None


def load(repo):
    path = Path(repo) / PENDING
    if not path.exists():
        return None
    if path.stat().st_size > 1024:
        raise ValueError("recibo de retry espacial excede orçamento")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict) or set(doc) != {"schema", "natureza", "cena_id", "tipo"}
            or doc["schema"] != 1 or doc["natureza"] != "retry_operacional"
            or doc["tipo"] not in {"permanencia", "transito", "entrada"}
            or not isinstance(doc["cena_id"], str) or not 1 <= len(doc["cena_id"]) <= 160):
        raise ValueError("recibo de retry espacial inválido")
    return doc


def save(repo, scene_id, kind):
    if not isinstance(scene_id, str) or not 1 <= len(scene_id) <= 160:
        return
    doc = {"schema": 1, "natureza": "retry_operacional", "cena_id": scene_id, "tipo": kind}
    path = Path(repo) / PENDING
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = stream.name
        json.dump(doc, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def require(pending, scene_id, kind):
    if pending and (scene_id != pending["cena_id"] or kind != pending["tipo"]):
        raise ValueError(
            f"preparo espacial pendente: {pending['tipo']} na cena {pending['cena_id']}. "
            "Corrija a causa e repita essa operação com o gatilho original; "
            "ticket neutro ou novo cena-id não substitui o retry."
        )


def abandon(repo, reason):
    """Desistência explícita da operação; não encerra causas nem suas reservas."""
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 320:
        raise ValueError("abandono espacial exige motivo factual de até 320 caracteres")
    pending = load(repo)
    if pending is None:
        return  # Retry da desistência não duplica o recibo.
    path = Path(repo) / CANCELLATIONS
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**pending, "motivo_desistencia": reason.strip()}, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    (Path(repo) / PENDING).unlink()


def bind_location(repo, payload, transaction):
    """Compila vínculo explícito de entrada e invalida vínculo antigo na saída.

    Só localização narrada com delta materializa ID; preparo sozinho não move.
    Fixtures sem registro mantêm os contratos anteriores.
    """
    if not locais.declared(Path(repo)) or not isinstance(transaction, dict):
        return transaction
    deltas = transaction.get("deltas")
    if not isinstance(deltas, list):
        return transaction  # O writer mantém o diagnóstico do schema.
    area_deltas = [d for d in deltas if isinstance(d, dict) and d.get("alvo") == "estado"
                   and d.get("op") == "set" and d.get("caminho") in {"localizacao", "localizacao.area"}]
    explicit = [d for d in deltas if isinstance(d, dict) and d.get("alvo") == "estado"
                and d.get("caminho") == "localizacao.local_id"]
    if not area_deltas:
        if explicit:
            current_id = locais.current(Path(repo))["local_id"]
            if any(d.get("op") != "set" or d.get("valor") != current_id for d in explicit):
                raise ValueError("local_id isolado não autoriza movimento; registre área e entrada correspondente")
        return transaction
    local_id = None
    if ticket_intent(payload) == "entrada":
        local_id = locais.resolve(Path(repo), payload["cena"]["place"])["local_id"]
        for delta in area_deltas:
            area = delta.get("valor")
            if isinstance(area, dict):
                area = area.get("area")
            try:
                resolved = locais.resolve(Path(repo), area)
            except locais.LocationError:
                continue  # Prosa vinculada ao ID explicitamente preparado.
            if resolved["local_id"] != local_id:
                raise ValueError("local narrado no delta diverge do ticket de entrada")
    if ticket_intent(payload) == "permanencia":
        # Permanecer não autoriza trocar a área no mesmo ticket.
        expected = payload["permanencia_espacial"]["local_id"]
        for delta in area_deltas:
            area = delta.get("valor")
            if isinstance(area, dict):
                area = area.get("local_id") or area.get("area")
            if locais.resolve(Path(repo), area)["local_id"] != expected:
                raise ValueError("ticket de permanência não autoriza saída para outro local")
        local_id = expected
    if any(d.get("op") != "set" or d.get("valor") != local_id for d in explicit):
        raise ValueError("vínculo local_id diverge da operação espacial; prepare a entrada correspondente")
    result = deepcopy(transaction)
    for delta in result["deltas"]:
        if delta in area_deltas and delta.get("caminho") == "localizacao" and isinstance(delta.get("valor"), dict):
            supplied = delta["valor"].get("local_id")
            if supplied is not None and supplied != local_id:
                raise ValueError("local_id do delta completo diverge do ticket espacial")
            delta["valor"]["local_id"] = local_id
    if not explicit and not any(d.get("caminho") == "localizacao" for d in area_deltas):
        result["deltas"].append({"alvo": "estado", "op": "set", "caminho": "localizacao.local_id", "valor": local_id})
    return result


def install(base):
    if getattr(base, "_spatial_retry_installed", False):
        return
    original_prepare, original_conclude, original_register = base.prepare, base.conclude, base.register
    original_parser, original_run_turn = base.build_parser, base._run_turn

    def prepare(repo, **kwargs):
        kind, scene = intent(kwargs), kwargs.get("scene_id")
        try:
            require(load(repo), scene, kind)
        except (ValueError, OSError) as exc:
            raise base.CronicaError(str(exc)) from exc
        try:
            return original_prepare(repo, **kwargs)
        except ValueError as exc:
            if kind:
                save(repo, scene, kind)
                raise base.CronicaError(
                    f"{exc} Retry espacial obrigatório: mantenha cena-id e gatilho {kind}; "
                    "corrija fonte/envelope, sem substituir por preparo neutro."
                ) from exc
            raise

    def conclude(repo, token, transaction):
        payload = base.decode_ticket(token)
        kind, scene = ticket_intent(payload), payload["cena"]["scene_id"]
        try:
            require(load(repo), scene, kind)
        except (ValueError, OSError) as exc:
            raise base.CronicaError(str(exc)) from exc
        try:
            transaction = bind_location(repo, payload, transaction)
        except (ValueError, OSError) as exc:
            if kind:
                save(repo, scene, kind)
            raise base.CronicaError(str(exc)) from exc
        try:
            result = original_conclude(repo, token, transaction)
        except ValueError:
            if kind:
                save(repo, scene, kind)
            raise  # Preserva PartialConclusionError e seu contrato de recuperação.
        if result.get("fase") == "concluida":
            (Path(repo) / PENDING).unlink(missing_ok=True)
        return result

    def register(repo, token, transaction, *, revalidate=True):
        payload = base.decode_ticket(token)
        try:
            require(load(repo), payload["cena"]["scene_id"], ticket_intent(payload))
            transaction = bind_location(repo, payload, transaction)
        except (ValueError, OSError) as exc:
            raise base.CronicaError(str(exc)) from exc
        return original_register(repo, token, transaction, revalidate=revalidate)

    def build_parser():
        parser = original_parser()
        base._subparsers(parser).choices["preparar"].add_argument(
            "--abandonar-preparo-espacial", metavar="MOTIVO",
            help="somente se o jogador desistiu da operação: registra o motivo e libera outro preparo; não resolve causas do mundo",
        )
        return parser

    def run_turn(repo, args):
        reason = getattr(args, "abandonar_preparo_espacial", None)
        if args.cmd == "preparar" and reason is not None:
            try:
                abandon(repo, reason)
            except (ValueError, OSError) as exc:
                raise base.CronicaError(str(exc)) from exc
        return original_run_turn(repo, args)

    base.prepare, base.conclude, base.register = prepare, conclude, register
    base.build_parser, base._run_turn = build_parser, run_turn
    base._spatial_retry_installed = True
