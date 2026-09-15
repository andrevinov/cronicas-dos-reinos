#!/usr/bin/env python3
"""Catálogo offline e reservas não canônicas de nomes, sob a fachada de NPCs."""
from __future__ import annotations

import csv
import fcntl
import os
import random
import re
import tempfile
import unicodedata
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

CATALOG = Path("nomes_npcs_forgotten_realms.csv")
RESERVATIONS = Path("runtime/reservas-nomes-npcs.yaml")
LOCK = Path("runtime/.reservas-nomes-npcs.lock")
SCHEMA = 1
MODULE_ID = "npc_continuity_and_social_behavior"
SURNAME_TYPES = ("sobrenome", "clã", "tribo", "dinástico", "alcunha")
EXTERNAL_ORIGINS = ("fonte_autorizada", "escolha_jogador", "parentesco_canonico")
FIELDS = (
    "id", "nome", "tipo_nome", "genero", "raca", "cultura_subraca",
    "regiao_primaria", "regioes_compativeis", "status", "fonte_base",
    "fonte_url", "observacao",
)


class NpcNameError(ValueError):
    pass


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not normalize(value):
        raise NpcNameError(f"{field} exige texto não vazio")
    return value.strip()


def load_catalog(repo: Path) -> list[dict[str, str]]:
    try:
        with (repo / CATALOG).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(FIELDS):
                raise NpcNameError(f"cabeçalho inválido em {CATALOG}")
            rows = []
            ids = set()
            for number, raw in enumerate(reader, 2):
                if None in raw or any(value is None for value in raw.values()):
                    raise NpcNameError(f"linha {number} do catálogo tem colunas inválidas")
                row = {key: value.strip() for key, value in raw.items()}
                for key in FIELDS[:7] + ("status",):
                    _text(row[key], f"linha {number}.{key}")
                if row["id"] in ids:
                    raise NpcNameError(f"ID duplicado no catálogo: {row['id']}")
                ids.add(row["id"])
                if row["genero"] not in {"masculino", "feminino", "neutro"}:
                    raise NpcNameError(f"gênero inválido na linha {number}")
                if row["tipo_nome"] not in {"nome", "virtude", *SURNAME_TYPES}:
                    raise NpcNameError(f"tipo de nome inválido na linha {number}")
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise NpcNameError(f"não foi possível ler {CATALOG}: {exc}") from exc
    if not rows:
        raise NpcNameError("catálogo de nomes vazio")
    return rows


def _yaml(repo: Path, path: Path, default: dict | None = None) -> dict:
    try:
        result = yaml.safe_load((repo / path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if default is not None:
            return default
        raise NpcNameError(f"arquivo obrigatório ausente: {path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise NpcNameError(f"não foi possível ler {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise NpcNameError(f"{path} deve conter mapa")
    return result


def _registry(repo: Path) -> dict:
    result = _yaml(repo, RESERVATIONS, {
        "schema_reservas_nomes_npcs": SCHEMA,
        "natureza": "reservas_operacionais_nao_canonicas; usos derivados dos índices de NPCs",
        "reservas": {},
    })
    if result.get("schema_reservas_nomes_npcs") != SCHEMA or not isinstance(result.get("reservas"), dict):
        raise NpcNameError("registro de reservas de nomes inválido")
    for key, entry in result["reservas"].items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise NpcNameError("reserva de nome inválida")
        _text(entry.get("nome_completo"), f"reserva {key}.nome_completo")
        if entry.get("estado") not in {"reservado", "cancelado"} or not isinstance(entry.get("parametros"), dict):
            raise NpcNameError(f"reserva {key} tem estado/parâmetros inválidos")
        if not isinstance(entry.get("selecoes"), list) or not entry["selecoes"]:
            raise NpcNameError(f"reserva {key} sem seleções")
        for row in entry["selecoes"]:
            if not isinstance(row, dict) or row.get("tipo_nome") not in {"nome", "virtude", *SURNAME_TYPES}:
                raise NpcNameError(f"reserva {key} com seleção inválida")
            _text(row.get("nome"), f"reserva {key}.selecao.nome")
            if entry["parametros"].get("origem") not in EXTERNAL_ORIGINS:
                _text(row.get("id"), f"reserva {key}.selecao.id")
        if normalize(entry["nome_completo"]) != normalize(" ".join(row["nome"] for row in entry["selecoes"])):
            raise NpcNameError(f"reserva {key} diverge das seleções nominais")
    return result


def _known(repo: Path) -> dict[str, set[str]]:
    """Somente índices compactos; aliases não contam como outra pessoa."""
    known: dict[str, set[str]] = {}
    for path, field, optional in (
        (Path("estado/npcs/index.yaml"), "npcs", False),
        (Path("estado/relacoes/index.yaml"), "relacoes", True),
    ):
        doc = _yaml(repo, path, {field: {}} if optional else None)
        mapping = doc.get(field)
        if not isinstance(mapping, dict):
            raise NpcNameError(f"{path}.{field} deve conter mapa")
        for npc_id, meta in mapping.items():
            if not isinstance(meta, dict):
                raise NpcNameError(f"identidade inválida no índice: {npc_id}")
            name = _text(meta.get("nome"), f"{npc_id}.nome")
            labels = {normalize(name), normalize(str(npc_id))}
            aliases = meta.get("aliases") or []
            if not isinstance(aliases, list):
                raise NpcNameError(f"{npc_id}.aliases deve ser lista")
            labels.update(normalize(alias) for alias in aliases if isinstance(alias, str))
            for label in list(labels):
                words = label.split(maxsplit=1)
                if len(words) == 2 and words[0] in {"velha", "velho", "sir", "lady", "senhor", "senhora", "dama"}:
                    labels.add(words[1])
            known.setdefault(str(npc_id), set()).update(labels)
    return known


def _region_matches(row: dict[str, str], region: str) -> bool:
    for value in (row["regiao_primaria"], row["regioes_compativeis"]):
        if normalize(value) == region:
            return True
        parts = re.split(r";|\s+/\s+", value)
        if any(normalize(re.sub(r"\([^)]*\)", "", part)) == region for part in parts):
            return True
    return False


def _candidates(rows: list[dict[str, str]], params: dict) -> list[dict[str, str]]:
    matched = []
    seen = set()
    for row in rows:
        if normalize(row["raca"]) != params["raca"]:
            continue
        if not _region_matches(row, params["regiao"]):
            continue
        if params["cultura"] and normalize(row["cultura_subraca"]) != params["cultura"]:
            continue
        if row["tipo_nome"] in {"nome", "virtude"} and row["genero"] not in {params["genero"], "neutro"}:
            continue
        key = tuple(normalize(row[field]) for field in ("nome", "tipo_nome", "cultura_subraca"))
        if key not in seen:
            seen.add(key)
            matched.append(row)
    return matched


def _uses(row: dict, known: dict[str, set[str]], registry: dict) -> dict[str, int]:
    part = normalize(row["nome"])
    given = row["tipo_nome"] in {"nome", "virtude"}

    def matches(label: str) -> bool:
        return label == part or (label.startswith(part + " ") if given else label.endswith(" " + part))

    canonical = sum(any(matches(label) for label in labels) for labels in known.values())
    canonical_labels = set().union(*known.values()) if known else set()
    pending = sum(
        entry["estado"] == "reservado"
        and normalize(entry["nome_completo"]) not in canonical_labels
        and any(
            normalize(selection["nome"]) == part
            and (selection["tipo_nome"] in {"nome", "virtude"}) == given
            for selection in entry["selecoes"]
        )
        for entry in registry["reservas"].values()
    )
    return {"canonicos": canonical, "reservas_pendentes": pending, "total": canonical + pending}


@contextmanager
def _locked(repo: Path):
    path = repo / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _save(repo: Path, registry: dict) -> None:
    path = repo / RESERVATIONS
    text = yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, width=110)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".nomes-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _blocked(known: dict[str, set[str]], registry: dict) -> set[str]:
    result = set().union(*known.values()) if known else set()
    result.update(normalize(entry["nome_completo"]) for entry in registry["reservas"].values() if entry["estado"] == "reservado")
    return result


def _existing(registry: dict, key: str, params: dict) -> dict | None:
    entry = registry["reservas"].get(key)
    if entry is not None:
        if entry["estado"] == "cancelado":
            raise NpcNameError("reserva cancelada não pode ser reutilizada; use outra chave")
        if entry["parametros"] != params:
            raise NpcNameError("a mesma reserva exige os mesmos filtros e política; retry não sorteia de novo")
    return entry


def _public(key: str, entry: dict, known: dict[str, set[str]], reused: bool) -> dict:
    result = {**entry, "ok": True, "reserva": key, "reutilizado": reused, "cria_npc": False}
    if normalize(entry["nome_completo"]) in (set().union(*known.values()) if known else set()):
        result["estado"] = "materializado"
    return result


def reserve(
    repo: Path, *, reservation: str, gender: str, race: str, region: str,
    culture: str | None = None, surname_type: str | None = "sobrenome",
    allow_reuse: bool = False, rng: Any = None,
) -> dict:
    """Reserva uma identidade nominal; não cria pessoa, parentesco ou presença."""
    key = _text(reservation, "reserva")
    if not isinstance(allow_reuse, bool):
        raise NpcNameError("permissão de reuso deve ser booleana explícita")
    params = {
        "genero": normalize(_text(gender, "gênero")),
        "raca": normalize(_text(race, "raça")),
        "regiao": normalize(_text(region, "região de origem")),
        "cultura": normalize(_text(culture, "cultura")) if culture is not None else None,
        "tipo_sobrenome": normalize(surname_type) if surname_type is not None else None,
        "permitir_reuso": bool(allow_reuse),
    }
    if params["genero"] not in {"masculino", "feminino", "neutro"}:
        raise NpcNameError("gênero deve ser masculino, feminino ou neutro")
    if surname_type is not None and params["tipo_sobrenome"] not in {normalize(item) for item in SURNAME_TYPES}:
        raise NpcNameError("tipo de sobrenome inválido")
    rows = load_catalog(repo)
    source = rng if rng is not None else random.SystemRandom()
    with _locked(repo):
        registry = _registry(repo)
        known = _known(repo)
        existing = _existing(registry, key, params)
        if existing is not None:
            return _public(key, existing, known, True)
        candidates = _candidates(rows, params)
        given = [row for row in candidates if row["tipo_nome"] in {"nome", "virtude"} and row["genero"] in {params["genero"], "neutro"}]
        family = [row for row in candidates if normalize(row["tipo_nome"]) == params["tipo_sobrenome"]]
        if not given or (surname_type is not None and not family):
            raise NpcNameError("sem candidatos para os filtros; não ampliar raça/gênero/região automaticamente; consulte catalogo-nomes ou declare --sem-sobrenome/--tipo-sobrenome")
        blocked = _blocked(known, registry)
        uses = {id(row): _uses(row, known, registry) for row in given + family}
        selected = None
        best = None
        ties = 0
        for first in given:
            for last in family if surname_type is not None else [None]:
                if last is not None and normalize(first["cultura_subraca"]) != normalize(last["cultura_subraca"]):
                    continue
                selections = [first] + ([last] if last is not None else [])
                full = " ".join(row["nome"] for row in selections)
                if normalize(full) in blocked:
                    continue
                counts = [uses[id(row)]["total"] for row in selections]
                if not allow_reuse and any(counts):
                    continue
                score = (sum(counts), max(counts))
                if best is None or score < best:
                    best, selected, ties = score, selections, 1
                elif score == best:
                    ties += 1
                    if source.randrange(ties) == 0:
                        selected = selections
        if selected is None:
            raise NpcNameError("pool sem combinação inédita: amplie filtros explicitamente ou use --permitir-reuso; nome completo duplicado nunca é permitido")
        entry = {
            "estado": "reservado", "parametros": params,
            "nome_completo": " ".join(row["nome"] for row in selected),
            "selecoes": selected,
            "usos_antes": [uses[id(row)] for row in selected],
            "reuso_componentes": any(uses[id(row)]["total"] for row in selected),
        }
        registry["reservas"][key] = entry
        _save(repo, registry)
        return _public(key, entry, known, False)


def reserve_external(repo: Path, *, reservation: str, name: str, origin: str, evidence: str) -> dict:
    """Exceção explícita para nome imposto por autoridade; nunca por estética."""
    load_catalog(repo)
    key, name = _text(reservation, "reserva"), _text(name, "nome")
    if origin not in EXTERNAL_ORIGINS:
        raise NpcNameError("origem da exceção de nome inválida")
    params = {"origem": origin, "evidencia": _text(evidence, "evidência"), "nome": name}
    parts = name.split(maxsplit=1)
    selections = [{"nome": part, "tipo_nome": "nome" if index == 0 else "sobrenome", "status": "excecao_documentada"} for index, part in enumerate(parts)]
    with _locked(repo):
        registry, known = _registry(repo), _known(repo)
        existing = _existing(registry, key, params)
        if existing is not None:
            return _public(key, existing, known, True)
        if normalize(name) in _blocked(known, registry):
            raise NpcNameError("nome completo já pertence a identidade ou reserva existente")
        entry = {"estado": "reservado", "parametros": params, "nome_completo": name, "selecoes": selections, "usos_antes": [_uses(row, known, registry) for row in selections]}
        registry["reservas"][key] = entry
        _save(repo, registry)
        return _public(key, entry, known, False)


def require_reservation(repo: Path, name: str) -> dict | None:
    """Trava de bootstrap quando o catálogo está instalado; fixtures legadas ficam isoladas."""
    if not (repo / CATALOG).exists() and not (repo / RESERVATIONS).exists():
        return None
    load_catalog(repo)
    registry = _registry(repo)
    matches = [(key, entry) for key, entry in registry["reservas"].items() if entry["estado"] == "reservado" and normalize(entry["nome_completo"]) == normalize(name)]
    if len(matches) != 1:
        raise NpcNameError("NPC novo exige uma reserva nominal única: npc_continuity_and_social_behavior.py gerar-nome; fonte autorizada/jogador/parentesco usa registrar-nome com evidência")
    key, entry = matches[0]
    provenance = {"reserva": key, "catalogo": CATALOG.as_posix()}
    if entry["parametros"].get("origem"):
        provenance.update(entry["parametros"])
    else:
        provenance["entradas"] = [row["id"] for row in entry["selecoes"]]
    return {"reserva": key, "nome_completo": entry["nome_completo"], "nomeacao": provenance}


def cancel(repo: Path, reservation: str) -> dict:
    with _locked(repo):
        registry, known = _registry(repo), _known(repo)
        entry = registry["reservas"].get(reservation)
        if entry is None:
            raise NpcNameError("reserva de nome inexistente")
        if normalize(entry["nome_completo"]) in (set().union(*known.values()) if known else set()):
            raise NpcNameError("nome materializado não pode ser liberado; cancelar não apaga cânone")
        if entry["estado"] != "cancelado":
            entry["estado"] = "cancelado"
            _save(repo, registry)
        return {"ok": True, "reserva": reservation, "estado": "cancelado", "cria_npc": False}


def catalog_summary(repo: Path) -> dict:
    rows = load_catalog(repo)
    return {
        "ok": True, "catalogo": CATALOG.as_posix(), "entradas": len(rows),
        "generos": sorted({row["genero"] for row in rows}),
        "racas": sorted({row["raca"] for row in rows}),
        "culturas": sorted({row["cultura_subraca"] for row in rows}),
        "regioes_primarias": sorted({row["regiao_primaria"] for row in rows}),
        "regioes_compativeis": sorted({row["regioes_compativeis"] for row in rows}),
        "tipos": dict(Counter(row["tipo_nome"] for row in rows)),
    }


def check(repo: Path) -> dict:
    try:
        rows, registry, known = load_catalog(repo), _registry(repo), _known(repo)
        pending = [entry for entry in registry["reservas"].values() if entry["estado"] == "reservado"]
        names = [normalize(entry["nome_completo"]) for entry in pending]
        if len(names) != len(set(names)):
            raise NpcNameError("reservas ativas possuem nomes completos duplicados")
        return {"ok": True, "erros": [], "entradas": len(rows), "identidades_indexadas": len(known), "reservas_ativas": len(pending)}
    except NpcNameError as exc:
        return {"ok": False, "erros": [str(exc)]}
