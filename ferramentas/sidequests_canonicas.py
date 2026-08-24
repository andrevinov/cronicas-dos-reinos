#!/usr/bin/env python3
"""Engine determinístico de side quests canônicas e secretas.

A Task 31 aposentou o gate procedural. Esta camada é a única origem operacional
para novas side quests: o índice já quente contém somente referências opacas por
NPC; cada referência aponta para um gate mecânico compacto. O detalhe reservado
só é aberto depois de todos os gates passarem.

Sem RNG, scheduler, scan global ou auto-oferta. Disponibilidade não é fala,
oferta não é aceite e Ren sempre pode aceitar, adiar ou recusar.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import contexto_core
import estado_relacional
import identidades
import locais
import mundo
import oportunidades
import transacoes

ROUTER_KEY = "sidequests_canonicas"
ENGINE_ID = "canonical_secret_quest_engine_task32"
GATES_DIR = Path("narrador/sidequests-canonicas/gates")
DETAILS_DIR = Path("narrador/sidequests-canonicas/segredos")
QUEST_ID_RE = re.compile(r"^qsc-[0-9a-f]{12}$")
MAX_REFS_PER_NPC = 4
MAX_GATE_FRAGMENTS_PER_SCENE = 6
MAX_DETAIL_FRAGMENTS_PER_SCENE = 1
MAX_KNOWLEDGE_CONDITIONS = 3
MAX_WORLD_CONDITIONS = 4
MAX_IDENTITY_CONDITIONS = 2
MAX_DETAIL_BYTES = 10 * 1024
WORLD_ROOTS = {"estado", "runtime", "narrador", "cenario"}
WORLD_OPERATORS = {
    "igual",
    "diferente",
    "maior_igual",
    "menor_igual",
    "contem",
    "em",
    "existe",
    "verdadeiro",
    "falso",
}
FORBIDDEN_AGENCY_KEYS = {
    "fala_ren",
    "decisao_ren",
    "acao_ren",
    "intencao_ren",
    "emocao_ren",
    "crenca_ren",
}
_MISSING = object()


class CanonicalSidequestError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise CanonicalSidequestError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalSidequestError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CanonicalSidequestError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanonicalSidequestError(f"{label} deve ser texto não vazio")
    return value.strip()


def _integer(
    value: Any,
    label: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CanonicalSidequestError(f"{label} deve ser inteiro >= {minimum}")
    if maximum is not None and value > maximum:
        raise CanonicalSidequestError(f"{label} deve ser inteiro <= {maximum}")
    return value


def _quest_id(value: Any, label: str = "sidequest.id") -> str:
    value = _text(value, label)
    if not QUEST_ID_RE.fullmatch(value):
        raise CanonicalSidequestError(
            f"{label} deve usar id opaco qsc- + 12 hexadecimais"
        )
    return value


def _repo_path(repo: Path, raw: Any, root: Path) -> Path:
    rel = Path(_text(raw, "arquivo"))
    if rel.is_absolute() or ".." in rel.parts:
        raise CanonicalSidequestError(f"caminho fora do repo: {rel}")
    try:
        rel.relative_to(root)
    except ValueError as exc:
        raise CanonicalSidequestError(f"arquivo {rel} deve ficar sob {root}") from exc
    return repo / rel


def _world_path(raw: Any, label: str) -> str:
    rel = Path(_text(raw, label))
    if (
        rel.is_absolute()
        or ".." in rel.parts
        or not rel.parts
        or rel.parts[0] not in WORLD_ROOTS
    ):
        raise CanonicalSidequestError(f"{label} fora dos roots permitidos")
    return rel.as_posix()


def _router(index: dict[str, Any]) -> dict[str, Any]:
    raw = index.get(ROUTER_KEY)
    if not isinstance(raw, dict):
        raise CanonicalSidequestError(
            "índice de oportunidades não declara sidequests_canonicas"
        )
    if (
        raw.get("schema_sidequests_canonicas") != 1
        or raw.get("engine") != ENGINE_ID
        or raw.get("detalhes_somente_apos_gate") is not True
        or raw.get("scheduler") != "proibido"
        or raw.get("rng") != "proibido"
    ):
        raise CanonicalSidequestError("roteador de sidequests canônicas inválido")
    mapping = raw.get("por_npc")
    if not isinstance(mapping, dict):
        raise CanonicalSidequestError("sidequests_canonicas.por_npc deve ser mapa")

    seen: set[str] = set()
    for npc_id, refs in mapping.items():
        _text(npc_id, "sidequests_canonicas.por_npc.npc_id")
        refs = _list(refs, f"sidequests_canonicas.por_npc.{npc_id}")
        if len(refs) > MAX_REFS_PER_NPC:
            raise CanonicalSidequestError(
                f"{npc_id}: máximo de {MAX_REFS_PER_NPC} referências"
            )
        for pos, raw_ref in enumerate(refs):
            ref = _map(raw_ref, f"{npc_id}[{pos}]")
            extra = set(ref) - {"id", "gate", "prioridade"}
            if extra:
                raise CanonicalSidequestError(
                    f"{npc_id}[{pos}] expõe campos proibidos: {', '.join(sorted(extra))}"
                )
            qid = _quest_id(ref.get("id"), f"{npc_id}[{pos}].id")
            if qid in seen:
                raise CanonicalSidequestError(f"sidequest roteada duas vezes: {qid}")
            seen.add(qid)
            _repo_path(Path("/repo"), ref.get("gate"), GATES_DIR)
            _integer(ref.get("prioridade"), f"{qid}.prioridade", 0, 100)
    return raw


def route_for_npc(index: dict[str, Any], npc_id: str) -> list[dict[str, Any]]:
    """Resolve somente ponteiros opacos; não abre gate, detalhe ou estado."""
    refs = _router(index)["por_npc"].get(npc_id) or []
    return sorted(
        [
            {
                "id": item["id"],
                "gate": item["gate"],
                "prioridade": item["prioridade"],
                "npc_id": npc_id,
            }
            for item in refs
        ],
        key=lambda item: (-int(item["prioridade"]), str(item["id"])),
    )


def quest_giver_ids(index: dict[str, Any]) -> set[str]:
    return set(_router(index)["por_npc"])


def mission_id(quest_id: str) -> str:
    qid = _quest_id(quest_id)
    digest = hashlib.sha256(f"canonical-sidequest|{qid}".encode("utf-8")).hexdigest()
    return "sqc-" + digest[:16]


def _absolute_instant(value: Any, label: str) -> mundo.WorldInstant:
    raw = _map(value, label)
    if set(raw) != {"data", "hora"}:
        raise CanonicalSidequestError(f"{label} deve conter exatamente data e hora")
    try:
        return mundo.parse_instant(
            _text(raw["data"], label + ".data"),
            _text(raw["hora"], label + ".hora"),
        )
    except mundo.WorldEngineError as exc:
        raise CanonicalSidequestError(str(exc)) from exc


def _window_spec(value: Any, label: str) -> dict[str, Any]:
    raw = _map(value, label)
    kind = _text(raw.get("tipo"), label + ".tipo")
    if kind not in oportunidades.VALID_WINDOWS:
        raise CanonicalSidequestError(f"{label}.tipo inválido: {kind}")
    if kind == "temporal":
        _integer(raw.get("duracao_horas"), label + ".duracao_horas", 1)
        allowed = {"tipo", "duracao_horas"}
    elif kind == "enquanto_condicao":
        _text(raw.get("condicao"), label + ".condicao")
        allowed = {"tipo", "condicao"}
    else:
        allowed = {"tipo"}
    extra = set(raw) - allowed
    if extra:
        raise CanonicalSidequestError(
            f"{label} possui campos desconhecidos: {', '.join(sorted(extra))}"
        )
    return raw


def _validate_gate_conditions(raw: Any, qid: str) -> dict[str, Any]:
    conditions = _map(raw or {}, f"{qid}.condicoes")
    allowed = {
        "locais",
        "janela",
        "relacao",
        "conhecimento",
        "mundo",
        "identidade",
    }
    extra = set(conditions) - allowed
    if extra:
        raise CanonicalSidequestError(
            f"{qid}.condicoes possui campos desconhecidos: {', '.join(sorted(extra))}"
        )

    places = conditions.get("locais", [])
    if not isinstance(places, list) or len(places) > 6:
        raise CanonicalSidequestError(f"{qid}.locais deve ser lista de até 6 ids")
    for place in places:
        _text(place, f"{qid}.locais")

    window = conditions.get("janela")
    if window is not None:
        window = _map(window, f"{qid}.janela")
        if set(window) - {"inicio", "fim"}:
            raise CanonicalSidequestError(f"{qid}.janela aceita somente inicio/fim")
        start = (
            _absolute_instant(window["inicio"], f"{qid}.janela.inicio")
            if "inicio" in window
            else None
        )
        end = (
            _absolute_instant(window["fim"], f"{qid}.janela.fim")
            if "fim" in window
            else None
        )
        if start is not None and end is not None and end.minute < start.minute:
            raise CanonicalSidequestError(f"{qid}: janela canônica invertida")

    relation = conditions.get("relacao")
    if relation is not None:
        relation = _map(relation, f"{qid}.relacao")
        relational_keys = {
            "afinidade_min",
            "afinidade_max",
            "confianca_min",
            "confianca_max",
            "risco_min",
            "risco_max",
        }
        if set(relation) - relational_keys:
            raise CanonicalSidequestError(f"{qid}.relacao possui campo desconhecido")
        for key, value in relation.items():
            _integer(value, f"{qid}.relacao.{key}", 0, 10)

    knowledge = conditions.get("conhecimento", [])
    if (
        not isinstance(knowledge, list)
        or len(knowledge) > MAX_KNOWLEDGE_CONDITIONS
    ):
        raise CanonicalSidequestError(
            f"{qid}.conhecimento aceita até {MAX_KNOWLEDGE_CONDITIONS} condições"
        )
    for pos, item in enumerate(knowledge):
        item = _map(item, f"{qid}.conhecimento[{pos}]")
        if set(item) != {"arquivo", "termo", "presente"}:
            raise CanonicalSidequestError(
                f"{qid}.conhecimento[{pos}] exige arquivo, termo e presente"
            )
        _repo_path(Path("/repo"), item["arquivo"], contexto_core.KNOW_ROOT)
        _text(item["termo"], f"{qid}.conhecimento[{pos}].termo")
        if not isinstance(item["presente"], bool):
            raise CanonicalSidequestError(
                f"{qid}.conhecimento[{pos}].presente deve ser booleano"
            )

    world = conditions.get("mundo", [])
    if not isinstance(world, list) or len(world) > MAX_WORLD_CONDITIONS:
        raise CanonicalSidequestError(
            f"{qid}.mundo aceita até {MAX_WORLD_CONDITIONS} condições"
        )
    for pos, item in enumerate(world):
        item = _map(item, f"{qid}.mundo[{pos}]")
        if set(item) - {"arquivo", "caminho", "operador", "valor"}:
            raise CanonicalSidequestError(f"{qid}.mundo[{pos}] possui campo desconhecido")
        _world_path(item.get("arquivo"), f"{qid}.mundo[{pos}].arquivo")
        _text(item.get("caminho"), f"{qid}.mundo[{pos}].caminho")
        operator = _text(item.get("operador"), f"{qid}.mundo[{pos}].operador")
        if operator not in WORLD_OPERATORS:
            raise CanonicalSidequestError(
                f"{qid}.mundo[{pos}].operador inválido: {operator}"
            )
        if operator not in {"existe", "verdadeiro", "falso"} and "valor" not in item:
            raise CanonicalSidequestError(
                f"{qid}.mundo[{pos}] exige valor para {operator}"
            )
        expected = item.get("valor")
        if operator in {"maior_igual", "menor_igual"} and (
            isinstance(expected, bool) or not isinstance(expected, (int, float))
        ):
            raise CanonicalSidequestError(
                f"{qid}.mundo[{pos}].valor deve ser numérico para {operator}"
            )
        if operator == "em" and not isinstance(expected, list):
            raise CanonicalSidequestError(
                f"{qid}.mundo[{pos}].valor deve ser lista para operador em"
            )

    identity = conditions.get("identidade")
    if identity is not None:
        identity = _map(identity, f"{qid}.identidade")
        if set(identity) - {"persona_relacional", "suspeitas", "confirmacoes"}:
            raise CanonicalSidequestError(f"{qid}.identidade possui campo desconhecido")
        personas = identity.get("persona_relacional", [])
        if not isinstance(personas, list) or len(personas) > 3:
            raise CanonicalSidequestError(
                f"{qid}.identidade.persona_relacional deve ser lista de até 3 ids"
            )
        for item in personas:
            _text(item, f"{qid}.identidade.persona_relacional")
        suspicions = identity.get("suspeitas", [])
        confirmations = identity.get("confirmacoes", [])
        if (
            not isinstance(suspicions, list)
            or len(suspicions) > MAX_IDENTITY_CONDITIONS
            or not isinstance(confirmations, list)
            or len(confirmations) > MAX_IDENTITY_CONDITIONS
        ):
            raise CanonicalSidequestError(f"{qid}.identidade excede orçamento")
        for pos, item in enumerate(suspicions):
            item = _map(item, f"{qid}.identidade.suspeitas[{pos}]")
            if set(item) != {"observada", "possivel", "min_evidencias"}:
                raise CanonicalSidequestError(
                    f"{qid}.identidade.suspeitas[{pos}] inválida"
                )
            _text(item["observada"], "observada")
            _text(item["possivel"], "possivel")
            _integer(
                item["min_evidencias"],
                "min_evidencias",
                1,
                identidades.MAX_EVIDENCE,
            )
        for pos, item in enumerate(confirmations):
            item = _map(item, f"{qid}.identidade.confirmacoes[{pos}]")
            if set(item) != {"observada", "identidade", "presente"}:
                raise CanonicalSidequestError(
                    f"{qid}.identidade.confirmacoes[{pos}] inválida"
                )
            _text(item["observada"], "observada")
            _text(item["identidade"], "identidade")
            if not isinstance(item["presente"], bool):
                raise CanonicalSidequestError(
                    f"{qid}.identidade.confirmacoes[{pos}].presente deve ser booleano"
                )
    return conditions


def _load_gate(repo: Path, ref: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = _repo_path(repo, ref.get("gate"), GATES_DIR)
    source = path.relative_to(repo).as_posix()
    data = _map(_load(path), source)
    qid = _quest_id(data.get("id"))
    if (
        data.get("schema_gate_sidequest_canonica") != 1
        or data.get("natureza") != "reservado"
        or qid != ref.get("id")
        or data.get("npc_id") != ref.get("npc_id")
    ):
        raise CanonicalSidequestError(f"{qid}: gate diverge do roteador opaco")
    _repo_path(repo, data.get("detalhe"), DETAILS_DIR)
    _validate_gate_conditions(data.get("condicoes") or {}, qid)
    allowed = {
        "schema_gate_sidequest_canonica",
        "natureza",
        "id",
        "npc_id",
        "detalhe",
        "condicoes",
    }
    extra = set(data) - allowed
    if extra:
        raise CanonicalSidequestError(
            f"{qid}: gate contém conteúdo narrativo/extra proibido"
        )
    return data, source


def _agency_scan(value: Any, path: str = "conteudo") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = contexto_core.normalize(key).replace(" ", "_")
            if normalized in FORBIDDEN_AGENCY_KEYS:
                raise CanonicalSidequestError(
                    f"{path}.{key}: detalhe não pode controlar Ren"
                )
            _agency_scan(item, f"{path}.{key}")
    elif isinstance(value, list):
        for pos, item in enumerate(value):
            _agency_scan(item, f"{path}[{pos}]")


def _load_detail(repo: Path, gate: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = _repo_path(repo, gate.get("detalhe"), DETAILS_DIR)
    if path.stat().st_size > MAX_DETAIL_BYTES:
        raise CanonicalSidequestError(
            f"{gate['id']}: detalhe excede {MAX_DETAIL_BYTES} bytes"
        )
    source = path.relative_to(repo).as_posix()
    data = _map(_load(path), source)
    qid = _quest_id(data.get("id"))
    if (
        data.get("schema_sidequest_canonica") != 1
        or data.get("natureza") != "reservado"
        or qid != gate["id"]
        or data.get("npc_id") != gate["npc_id"]
    ):
        raise CanonicalSidequestError(f"{qid}: detalhe diverge do gate")
    kind = _text(data.get("tipo"), f"{qid}.tipo")
    if kind not in oportunidades.VALID_TYPES:
        raise CanonicalSidequestError(f"{qid}: tipo inválido: {kind}")
    _text(data.get("titulo"), f"{qid}.titulo")
    _text(data.get("objetivo"), f"{qid}.objetivo")
    _window_spec(data.get("janela"), f"{qid}.janela")
    if not isinstance(data.get("pode_reabrir"), bool):
        raise CanonicalSidequestError(f"{qid}.pode_reabrir deve ser booleano")
    _text(data.get("consequencia_sem_ren"), f"{qid}.consequencia_sem_ren")
    offer = _map(data.get("oferta"), f"{qid}.oferta")
    if offer.get("recusa_permitida") is not True:
        raise CanonicalSidequestError(
            f"{qid}: toda sidequest canônica precisa permitir recusa"
        )
    _text(offer.get("premissa"), f"{qid}.oferta.premissa")
    _text(offer.get("pedido"), f"{qid}.oferta.pedido")
    guardrails = offer.get("guardrails", [])
    if not isinstance(guardrails, list) or len(guardrails) > 4:
        raise CanonicalSidequestError(f"{qid}.oferta.guardrails deve ter até 4 itens")
    for item in guardrails:
        _text(item, f"{qid}.oferta.guardrails")
    effects = data.get("efeitos", [])
    if not isinstance(effects, list) or len(effects) > 6:
        raise CanonicalSidequestError(f"{qid}.efeitos deve ter até 6 itens")
    _agency_scan(data)
    return copy.deepcopy(data), source


def _offer_projection(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": detail["id"],
        "npc_id": detail["npc_id"],
        "tipo": detail["tipo"],
        "titulo": detail["titulo"],
        "objetivo": detail["objetivo"],
        "janela": copy.deepcopy(detail["janela"]),
        "pode_reabrir": detail["pode_reabrir"],
        "consequencia_sem_ren": detail["consequencia_sem_ren"],
        "oferta": copy.deepcopy(detail["oferta"]),
    }


class _Context:
    def __init__(self, repo: Path, now: mundo.WorldInstant | None):
        self.repo = repo
        self._now = now
        self._pending: list[dict[str, Any]] | None = None
        self._state: dict[str, Any] | None = None
        self._npc_index: dict[str, Any] | None = None
        self._npc_payloads: dict[str, dict[str, Any]] = {}
        self._world_docs: dict[str, Any] = {}
        self.sources: list[str] = []

    def add(self, *sources: str) -> None:
        self.sources = list(
            dict.fromkeys([*self.sources, *[item for item in sources if item]])
        )

    def now(self) -> mundo.WorldInstant:
        if self._now is None:
            try:
                self._now, _ = mundo.load_canonical_time(self.repo)
            except mundo.WorldEngineError as exc:
                raise CanonicalSidequestError(str(exc)) from exc
            self.add(mundo.TIME_PATH.as_posix())
        return self._now

    def pending(self) -> list[dict[str, Any]]:
        if self._pending is None:
            try:
                self._pending = transacoes.load_pending(self.repo)
            except (OSError, ValueError) as exc:
                raise CanonicalSidequestError(
                    f"overlay pendente inválido: {exc}"
                ) from exc
            if (self.repo / transacoes.PENDING_PATH).is_file():
                self.add(transacoes.PENDING_PATH.as_posix())
        return self._pending

    def state(self, index: dict[str, Any]) -> dict[str, Any]:
        if self._state is None:
            try:
                self._state = oportunidades.load_state(self.repo, index)
            except oportunidades.OpportunityError as exc:
                raise CanonicalSidequestError(str(exc)) from exc
            self.add(oportunidades.STATE.as_posix())
        return self._state

    def npc_payload(self, npc_id: str) -> dict[str, Any]:
        cached = self._npc_payloads.get(npc_id)
        if cached is not None:
            return cached
        if self._npc_index is None:
            self._npc_index = _map(
                _load(self.repo / estado_relacional.NPC_INDEX),
                str(estado_relacional.NPC_INDEX),
            )
            if not isinstance(self._npc_index.get("npcs"), dict):
                raise CanonicalSidequestError(
                    "índice de NPCs inválido para sidequest canônica"
                )
            self.add(estado_relacional.NPC_INDEX.as_posix())
        entry = self._npc_index["npcs"].get(npc_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
            raise CanonicalSidequestError(
                f"{npc_id}: NPC sem fragmento operacional"
            )
        rel = entry["arquivo"]
        doc = _map(_load(self.repo / rel), rel)
        payload = doc.get("npc")
        if not isinstance(payload, dict):
            raise CanonicalSidequestError(f"{npc_id}: fragmento NPC inválido")
        try:
            effective, _ = transacoes.overlay_target(
                payload,
                self.pending(),
                f"npc:{npc_id}",
            )
        except (OSError, ValueError) as exc:
            raise CanonicalSidequestError(
                f"{npc_id}: overlay relacional inválido: {exc}"
            ) from exc
        self.add(rel)
        self._npc_payloads[npc_id] = effective
        return effective

    def world_doc(self, rel: str) -> Any:
        if rel in self._world_docs:
            return self._world_docs[rel]
        rel = _world_path(rel, "fonte de mundo")
        data = _load(self.repo / rel)
        if rel == "runtime/contexto.yaml" and isinstance(data, dict):
            data, _, _ = transacoes.overlay_runtime(data, None, self.pending())
        elif rel == "runtime/cena.yaml" and isinstance(data, dict):
            _, scene, _ = transacoes.overlay_runtime({}, data, self.pending())
            data = scene
        self.add(rel)
        self._world_docs[rel] = data
        return data


def _lifecycle_allows(
    ctx: _Context,
    index: dict[str, Any],
    quest_id: str,
) -> tuple[bool, str]:
    state = ctx.state(index)
    mid = mission_id(quest_id)
    existing = state["missoes"].get(mid)
    if isinstance(existing, dict):
        if (
            existing.get("quest_id") != quest_id
            or existing.get("origem") != "sidequest_canonica"
        ):
            raise CanonicalSidequestError(f"colisão de mission_id: {mid}")
        if (
            existing.get("estado") == "recusada"
            and existing.get("pode_reabrir") is True
        ):
            mode = "reabertura"
        else:
            return False, "ja_materializada"
    else:
        mode = "nova"
    active, opened = oportunidades._mission_counts(state)
    budget = index["orcamento"]
    if active >= budget["max_ativas"]:
        return False, "limite_ativas"
    if opened >= budget["max_em_aberto"]:
        return False, "limite_abertas"
    return True, mode


def _relation_allows(ctx: _Context, npc_id: str, raw: Any) -> bool:
    if raw is None:
        return True
    relation = _map(raw, "condicoes.relacao")
    payload = ctx.npc_payload(npc_id)
    try:
        projection = estado_relacional.project(payload.get("medidores"))
    except estado_relacional.RelationshipStateError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    checks = {
        "afinidade_min": (
            projection["afinidade"],
            lambda a, b: a is not None and a >= b,
        ),
        "afinidade_max": (
            projection["afinidade"],
            lambda a, b: a is not None and a <= b,
        ),
        "confianca_min": (
            projection["confianca"],
            lambda a, b: a is not None and a >= b,
        ),
        "confianca_max": (
            projection["confianca"],
            lambda a, b: a is not None and a <= b,
        ),
        "risco_min": (
            projection["risco_percebido"],
            lambda a, b: a is not None and a >= b,
        ),
        "risco_max": (
            projection["risco_percebido"],
            lambda a, b: a is not None and a <= b,
        ),
    }
    return all(
        checks[key][1](checks[key][0], value)
        for key, value in relation.items()
    )


def _pending_knows(records: list[dict[str, Any]], term: str) -> bool:
    needle = contexto_core.normalize(term)
    for record in records:
        for delta in record.get("deltas") or []:
            if not isinstance(delta, dict):
                continue
            target = delta.get("alvo")
            if not isinstance(target, str) or not target.startswith("conhecimento"):
                continue
            body = yaml.safe_dump(delta.get("valor"), allow_unicode=True)
            if needle in contexto_core.normalize(body):
                return True
    return False


def _knowledge_allows(ctx: _Context, raw: Any) -> bool:
    for item in raw or []:
        path = _repo_path(ctx.repo, item["arquivo"], contexto_core.KNOW_ROOT)
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CanonicalSidequestError(str(exc)) from exc
        rel = path.relative_to(ctx.repo).as_posix()
        ctx.add(rel)
        found = (
            contexto_core.normalize(item["termo"])
            in contexto_core.normalize(body)
        )
        if not found:
            found = _pending_knows(ctx.pending(), item["termo"])
        if found != bool(item["presente"]):
            return False
    return True


def _get_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _compare(actual: Any, operator: str, expected: Any = _MISSING) -> bool:
    if operator == "existe":
        wanted = True if expected is _MISSING else bool(expected)
        return (actual is not _MISSING) == wanted
    if actual is _MISSING:
        return False
    if operator == "igual":
        return actual == expected
    if operator == "diferente":
        return actual != expected
    if operator == "maior_igual":
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and actual >= expected
        )
    if operator == "menor_igual":
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and actual <= expected
        )
    if operator == "contem":
        try:
            return expected in actual
        except TypeError:
            return False
    if operator == "em":
        try:
            return actual in expected
        except TypeError:
            return False
    if operator == "verdadeiro":
        return actual is True
    if operator == "falso":
        return actual is False
    raise CanonicalSidequestError(f"operador desconhecido: {operator}")


def _world_allows(ctx: _Context, raw: Any) -> bool:
    for item in raw or []:
        actual = _get_path(
            ctx.world_doc(str(item["arquivo"])),
            str(item["caminho"]),
        )
        expected = item.get("valor", _MISSING)
        if not _compare(actual, str(item["operador"]), expected):
            return False
    return True


def _identity_allows(ctx: _Context, npc_id: str, raw: Any) -> bool:
    if raw is None:
        return True
    identity = _map(raw, "condicoes.identidade")
    payload = ctx.npc_payload(npc_id)
    personas = list(identity.get("persona_relacional") or [])
    if personas and payload.get("identidade_relacional", "ren") not in personas:
        return False
    if not identity.get("suspeitas") and not identity.get("confirmacoes"):
        return True
    try:
        registry = identidades.load_registry(ctx.repo)
        state = identidades.validate_state(
            payload.get(identidades.STATE_FIELD),
            registry,
        )
    except identidades.IdentitySuspicionError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    ctx.add(identidades.REGISTRY.as_posix())
    suspicions = {
        (item["observada"], item["possivel"]): len(item["evidencias"])
        for item in state["suspeitas"]
    }
    confirmations = {
        (item["observada"], item["identidade"])
        for item in state["confirmacoes"]
    }
    for item in identity.get("suspeitas") or []:
        if (
            suspicions.get((item["observada"], item["possivel"]), 0)
            < item["min_evidencias"]
        ):
            return False
    for item in identity.get("confirmacoes") or []:
        found = (item["observada"], item["identidade"]) in confirmations
        if found != bool(item["presente"]):
            return False
    return True


def _evaluate_gate(
    ctx: _Context,
    index: dict[str, Any],
    ref: dict[str, Any],
    local_id: str | None,
) -> tuple[bool, str, dict[str, Any], str]:
    gate, gate_source = _load_gate(ctx.repo, ref)
    ctx.add(gate_source)
    conditions = gate.get("condicoes") or {}

    places = list(conditions.get("locais") or [])
    if places and local_id not in places:
        return False, "local", gate, gate_source

    window = conditions.get("janela")
    if isinstance(window, dict):
        current = ctx.now()
        if (
            "inicio" in window
            and current.minute
            < _absolute_instant(window["inicio"], "janela.inicio").minute
        ):
            return False, "data", gate, gate_source
        if (
            "fim" in window
            and current.minute
            > _absolute_instant(window["fim"], "janela.fim").minute
        ):
            return False, "data", gate, gate_source

    lifecycle_ok, mode = _lifecycle_allows(ctx, index, gate["id"])
    if not lifecycle_ok:
        return False, mode, gate, gate_source
    if not _relation_allows(ctx, gate["npc_id"], conditions.get("relacao")):
        return False, "relacao", gate, gate_source
    if not _knowledge_allows(ctx, conditions.get("conhecimento")):
        return False, "conhecimento", gate, gate_source
    if not _world_allows(ctx, conditions.get("mundo")):
        return False, "mundo", gate, gate_source
    if not _identity_allows(ctx, gate["npc_id"], conditions.get("identidade")):
        return False, "identidade", gate, gate_source
    return True, mode, gate, gate_source


def select_from_refs(
    repo: Path,
    refs: list[dict[str, Any]],
    *,
    local_id: str | None = None,
    now: mundo.WorldInstant | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    """Avalia refs roteadas e abre, no máximo, um detalhe reservado."""
    unique: dict[str, dict[str, Any]] = {}
    for raw in refs:
        if not isinstance(raw, dict):
            raise CanonicalSidequestError("referência canônica deve ser mapa")
        qid = _quest_id(raw.get("id"))
        unique.setdefault(qid, raw)
    ordered = sorted(
        unique.values(),
        key=lambda item: (-int(item.get("prioridade", 0)), str(item["id"])),
    )
    omitted = max(0, len(ordered) - MAX_GATE_FRAGMENTS_PER_SCENE)
    ordered = ordered[:MAX_GATE_FRAGMENTS_PER_SCENE]

    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    _router(index)

    ctx = _Context(repo, now)
    blockers: list[dict[str, str]] = []
    for position, ref in enumerate(ordered, start=1):
        eligible, mode, gate, gate_source = _evaluate_gate(
            ctx,
            index,
            ref,
            local_id,
        )
        if not eligible:
            if diagnostics:
                blockers.append({"id": str(ref["id"]), "bloqueio": mode})
            continue
        detail, detail_source = _load_detail(repo, gate)
        ctx.add(detail_source)
        return {
            "ok": True,
            "resultado": "sidequest_canonica_disponivel",
            "sidequest": {
                "id": gate["id"],
                "npc_id": gate["npc_id"],
                "prioridade": int(ref["prioridade"]),
                "modo": mode,
                "oferta": _offer_projection(detail),
                "fonte_gate": gate_source,
                "fonte_detalhe": detail_source,
                "recusa_permitida": True,
                "regra": (
                    "disponibilidade não é fala nem aceite; o NPC pode oferecer, "
                    "mas Ren decide aceitar, adiar ou recusar"
                ),
            },
            "gates_avaliados": position,
            "gates_omitidos_por_orcamento": omitted,
            "detalhes_lidos": 1,
            "fontes_lidas": ctx.sources,
        }

    result: dict[str, Any] = {
        "ok": True,
        "resultado": "nenhuma_sidequest_canonica",
        "gates_avaliados": len(ordered),
        "gates_omitidos_por_orcamento": omitted,
        "detalhes_lidos": 0,
        "fontes_lidas": ctx.sources,
    }
    if diagnostics:
        result["diagnostico"] = blockers
    return result


def evaluate_for_npc(
    repo: Path,
    npc_id: str,
    *,
    local: str | None = None,
    now: mundo.WorldInstant | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    refs = route_for_npc(index, npc_id)
    sources = [oportunidades.INDEX.as_posix()]
    local_id = None
    if local is not None:
        try:
            resolved = locais.resolve(repo, local)
        except locais.LocationError as exc:
            raise CanonicalSidequestError(str(exc)) from exc
        local_id = resolved["local_id"]
        sources.extend(resolved.get("fontes_lidas") or [])
    if not refs:
        return {
            "ok": True,
            "resultado": "nenhuma_sidequest_canonica_roteada",
            "npc_id": npc_id,
            "gates_avaliados": 0,
            "detalhes_lidos": 0,
            "fontes_lidas": list(dict.fromkeys(sources)),
        }
    result = select_from_refs(
        repo,
        refs,
        local_id=local_id,
        now=now,
        diagnostics=diagnostics,
    )
    result["fontes_lidas"] = list(
        dict.fromkeys([*sources, *(result.get("fontes_lidas") or [])])
    )
    return result


def _find_ref(
    index: dict[str, Any],
    npc_id: str,
    quest_id: str,
) -> dict[str, Any]:
    qid = _quest_id(quest_id)
    for ref in route_for_npc(index, npc_id):
        if ref["id"] == qid:
            return ref
    raise CanonicalSidequestError(f"{qid}: não roteada para {npc_id}")


def _same_canonical_mission(
    existing: dict[str, Any],
    quest_id: str,
    mid: str,
) -> None:
    if (
        existing.get("id") != mid
        or existing.get("quest_id") != quest_id
        or existing.get("origem") != "sidequest_canonica"
    ):
        raise CanonicalSidequestError(f"colisão de mission_id canônico: {mid}")


def _mission_window(
    detail: dict[str, Any],
    current: mundo.WorldInstant,
) -> dict[str, Any]:
    try:
        return oportunidades._window_at(
            {"janela": detail["janela"]},
            current,
        )
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc


def offer(
    repo: Path,
    quest_id: str,
    *,
    npc_id: str,
    local: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Revalida o gate e materializa uma oferta; retry é idempotente."""
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    ref = _find_ref(index, npc_id, quest_id)
    mid = mission_id(quest_id)
    sources = [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()]

    existing = state["missoes"].get(mid)
    if isinstance(existing, dict):
        _same_canonical_mission(existing, quest_id, mid)
        reopen = (
            existing.get("estado") == "recusada"
            and existing.get("pode_reabrir") is True
        )
        if not reopen:
            return {
                "ok": True,
                "resultado": "ja_registrada",
                "missao": copy.deepcopy(existing),
                "recusa_permitida": True,
                "fontes_lidas": sources,
            }

    local_id = None
    if local is not None:
        try:
            resolved = locais.resolve(repo, local)
        except locais.LocationError as exc:
            raise CanonicalSidequestError(str(exc)) from exc
        local_id = resolved["local_id"]
        sources.extend(resolved.get("fontes_lidas") or [])

    selected = select_from_refs(
        repo,
        [ref],
        local_id=local_id,
        now=now,
    )
    if selected.get("resultado") != "sidequest_canonica_disponivel":
        raise CanonicalSidequestError(
            "sidequest não está canonicamente elegível para oferta"
        )
    sidequest = selected["sidequest"]
    if sidequest["id"] != quest_id:
        raise CanonicalSidequestError("seleção canônica divergiu da oferta solicitada")
    sources.extend(selected.get("fontes_lidas") or [])
    projection = sidequest["oferta"]

    current = now
    if current is None:
        try:
            current, _ = mundo.load_canonical_time(repo)
        except mundo.WorldEngineError as exc:
            raise CanonicalSidequestError(str(exc)) from exc
        sources.append(mundo.TIME_PATH.as_posix())

    # Releitura curta antes da primeira escrita protege contra estado alterado
    # entre a avaliação e a materialização.
    try:
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    existing = state["missoes"].get(mid)
    if isinstance(existing, dict):
        _same_canonical_mission(existing, quest_id, mid)
        if (
            existing.get("estado") == "recusada"
            and existing.get("pode_reabrir") is True
        ):
            existing["estado"] = "oferecida"
            existing["reaberta_em"] = mundo.instant_parts(current)
            oportunidades._history(
                state,
                {
                    "tipo": "missao_canonica_reaberta",
                    "id": mid,
                    "de": "recusada",
                    "para": "oferecida",
                    "em": mundo.instant_parts(current),
                },
            )
            oportunidades.atomic(repo / oportunidades.STATE, state)
            return {
                "ok": True,
                "resultado": "oferecida",
                "reabertura": True,
                "missao": copy.deepcopy(existing),
                "oferta": projection["oferta"],
                "recusa_permitida": True,
                "fontes_lidas": list(dict.fromkeys(sources)),
            }
        return {
            "ok": True,
            "resultado": "ja_registrada",
            "missao": copy.deepcopy(existing),
            "recusa_permitida": True,
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    active, opened = oportunidades._mission_counts(state)
    budget = index["orcamento"]
    if (
        active >= budget["max_ativas"]
        or opened >= budget["max_em_aberto"]
    ):
        raise CanonicalSidequestError(
            "orçamento de sidequests não permite nova oferta"
        )

    npc_meta = index.get("perfis", {}).get(npc_id) or {}
    mission = {
        "id": mid,
        "estado": "oferecida",
        "origem": "sidequest_canonica",
        "quest_id": quest_id,
        "npc_id": npc_id,
        "npc_nome": npc_meta.get("nome") or npc_id,
        "necessidade_id": f"canonica:{quest_id}",
        "tipo": projection["tipo"],
        "titulo": projection["titulo"],
        "objetivo": projection["objetivo"],
        "janela": _mission_window(projection, current),
        "pode_reabrir": projection["pode_reabrir"],
        "consequencia_sem_ren": projection["consequencia_sem_ren"],
        "fonte_canonica": ref["gate"],
        "fonte_detalhe": sidequest["fonte_detalhe"],
        "oferecida_em": mundo.instant_parts(current),
    }
    state["missoes"][mid] = mission
    oportunidades._history(
        state,
        {
            "tipo": "missao_canonica_oferecida",
            "id": mid,
            "npc_id": npc_id,
            "em": mundo.instant_parts(current),
        },
    )
    oportunidades.atomic(repo / oportunidades.STATE, state)
    return {
        "ok": True,
        "resultado": "oferecida",
        "reabertura": False,
        "missao": copy.deepcopy(mission),
        "oferta": projection["oferta"],
        "recusa_permitida": True,
        "proximo_passo": (
            f"oportunidades.py responder {mid} aceitar|adiar|recusar"
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def effects_for_mission(
    repo: Path,
    mission_id_value: str,
) -> dict[str, Any]:
    """Abre efeitos reservados apenas para missão canônica aceita."""
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonicalSidequestError(str(exc)) from exc
    mission = state["missoes"].get(mission_id_value)
    if not isinstance(mission, dict):
        raise CanonicalSidequestError(
            f"sidequest inexistente: {mission_id_value}"
        )
    if (
        mission.get("origem") != "sidequest_canonica"
        or not isinstance(mission.get("quest_id"), str)
    ):
        raise CanonicalSidequestError("sidequest não é canônica da Task 32")
    if mission.get("estado") != "aceita":
        raise CanonicalSidequestError(
            f"efeitos exigem missão aceita; atual={mission.get('estado')}"
        )
    ref = _find_ref(index, mission["npc_id"], mission["quest_id"])
    gate, gate_source = _load_gate(repo, ref)
    detail, detail_source = _load_detail(repo, gate)
    return {
        "ok": True,
        "sidequest": mission_id_value,
        "quest_id": mission["quest_id"],
        "efeitos": copy.deepcopy(detail.get("efeitos") or []),
        "fontes_lidas": [
            oportunidades.INDEX.as_posix(),
            oportunidades.STATE.as_posix(),
            gate_source,
            detail_source,
        ],
    }


def check(repo: Path) -> dict[str, Any]:
    """Validação fria; pode abrir detalhes, mas nunca os inclui na saída."""
    errors: list[str] = []
    quest_count = 0
    giver_count = 0
    try:
        index = oportunidades.load_index(repo)
        router = _router(index)
        mapping = router["por_npc"]
        giver_count = len(mapping)
        npc_index = _map(
            _load(repo / estado_relacional.NPC_INDEX),
            str(estado_relacional.NPC_INDEX),
        )
        known_npcs = set(
            _map(
                npc_index.get("npcs"),
                "estado/npcs/index.yaml.npcs",
            )
        )
        registry = identidades.load_registry(repo)
        valid_identities = set(registry["identidades"])

        for npc_id, raw_refs in mapping.items():
            if npc_id not in known_npcs:
                errors.append(f"quest giver não canônico: {npc_id}")
                continue
            for raw_ref in raw_refs:
                ref = {**raw_ref, "npc_id": npc_id}
                quest_count += 1
                try:
                    gate, _ = _load_gate(repo, ref)
                    conditions = gate.get("condicoes") or {}
                    for local_id in conditions.get("locais") or []:
                        resolved = locais.resolve(repo, local_id)
                        if resolved["local_id"] != local_id:
                            raise CanonicalSidequestError(
                                f"{gate['id']}: local deve usar id canônico"
                            )
                    for item in conditions.get("conhecimento") or []:
                        if not _repo_path(
                            repo,
                            item["arquivo"],
                            contexto_core.KNOW_ROOT,
                        ).is_file():
                            raise CanonicalSidequestError(
                                f"{gate['id']}: fonte de conhecimento ausente"
                            )
                    for item in conditions.get("mundo") or []:
                        if not (
                            repo / _world_path(
                                item["arquivo"],
                                "fonte de mundo",
                            )
                        ).is_file():
                            raise CanonicalSidequestError(
                                f"{gate['id']}: fonte de mundo ausente"
                            )
                    identity = conditions.get("identidade") or {}
                    for persona in identity.get("persona_relacional") or []:
                        if persona not in valid_identities:
                            raise CanonicalSidequestError(
                                f"{gate['id']}: persona desconhecida: {persona}"
                            )
                    for item in identity.get("suspeitas") or []:
                        if (
                            item["observada"] not in valid_identities
                            or item["possivel"] not in valid_identities
                        ):
                            raise CanonicalSidequestError(
                                f"{gate['id']}: identidade de suspeita desconhecida"
                            )
                    for item in identity.get("confirmacoes") or []:
                        if (
                            item["observada"] not in valid_identities
                            or item["identidade"] not in valid_identities
                        ):
                            raise CanonicalSidequestError(
                                f"{gate['id']}: confirmação usa identidade desconhecida"
                            )
                    _load_detail(repo, gate)
                except (
                    CanonicalSidequestError,
                    locais.LocationError,
                ) as exc:
                    errors.append(str(exc))
    except (
        CanonicalSidequestError,
        oportunidades.OpportunityError,
        identidades.IdentitySuspicionError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "engine": ENGINE_ID,
        "quest_givers": giver_count,
        "quests_roteadas": quest_count,
        "detalhes_expostos": 0,
    }


def _instant_arg(
    date: str | None,
    hour: str | None,
) -> mundo.WorldInstant | None:
    if date is None and hour is None:
        return None
    if not date or not hour:
        raise CanonicalSidequestError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(date, hour)
    except mundo.WorldEngineError as exc:
        raise CanonicalSidequestError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    evaluate = sub.add_parser(
        "avaliar",
        help="avalia disponibilidade para um NPC sem escrever",
    )
    evaluate.add_argument("npc")
    evaluate.add_argument("--local")
    evaluate.add_argument("--data")
    evaluate.add_argument("--hora")
    evaluate.add_argument("--diagnostico", action="store_true")

    offer_parser = sub.add_parser(
        "oferecer",
        help="revalida e registra oferta canônica",
    )
    offer_parser.add_argument("id")
    offer_parser.add_argument("--npc", required=True)
    offer_parser.add_argument("--local")
    offer_parser.add_argument("--data")
    offer_parser.add_argument("--hora")

    effects = sub.add_parser(
        "efeitos",
        help="carrega efeitos somente de missão canônica aceita",
    )
    effects.add_argument("id")

    sub.add_parser(
        "check",
        help="valida roteador, gates e detalhes sem expor segredos",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "avaliar":
            result = evaluate_for_npc(
                repo,
                args.npc,
                local=args.local,
                now=_instant_arg(args.data, args.hora),
                diagnostics=args.diagnostico,
            )
        elif args.cmd == "oferecer":
            result = offer(
                repo,
                args.id,
                npc_id=args.npc,
                local=args.local,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "efeitos":
            result = effects_for_mission(repo, args.id)
        else:
            result = check(repo)
            print(
                yaml.safe_dump(
                    result,
                    allow_unicode=True,
                    sort_keys=False,
                ),
                end="",
            )
            return 0 if result["ok"] else 1
        print(
            yaml.safe_dump(
                result,
                allow_unicode=True,
                sort_keys=False,
            ),
            end="",
        )
        return 0
    except (
        CanonicalSidequestError,
        oportunidades.OpportunityError,
        mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(f"ERRO SIDEQUEST CANONICA — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
