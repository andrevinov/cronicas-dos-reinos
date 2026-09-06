"""Projeção de memória após o overlay; fatos atômicos, sem resumo inventado.

A classificação usa o papel dos campos existentes, não simula compreensão da cena.
Não lê arquivos, não muda o cânone e não atribui conhecimento novo a ninguém.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
from typing import Any, Callable

Serializer = Callable[[Any, bool], str]
Path = tuple[str, ...]
IDENTITY = {"nome", "tipo", "status", "identidade", "personalidade", "valores", "limites"}
BOND = {"confianca", "respeito", "afinidade", "divida", "visao_atual", "vinculo",
        "dialogo_relacional", "papel_conversacional", "iniciativa_social"}
MEMORIES = {"momentos_de_vinculo", "marcos_da_relacao", "memorias_importantes", "marcos"}
GUARDS = {"riscos", "notas_de_consistencia", "canal_confirmado", "canal_de_registro"}


def pointer(path: Path) -> str:
    return "/" + "/".join(key.replace("~", "~0").replace("/", "~1") for key in path)


def _priority(key: str, path: Path) -> int | None:
    if key in IDENTITY:
        return 0
    if key in BOND or key.startswith(("acordo", "compromisso", "promessa")):
        return 1
    if key in GUARDS or key.startswith(("conhecimento", "informacoes_recebidas")):
        return 2
    if key in MEMORIES:
        return 3
    # Os medidores inteiros alimentam a projeção de diálogo antes desta seleção.
    if path[:2] == ("medidores", "dados"):
        return 2
    if path == ("textura_narrativa",):
        return 4
    return None


def _get(value: Any, path: Path) -> Any:
    for key in path:
        value = value[key]
    return value


def _put(value: dict, path: Path, item: Any) -> None:
    for key in path[:-1]:
        value = value.setdefault(key, {})
    value[path[-1]] = deepcopy(item)


def _fields(data: dict) -> tuple[dict, list[tuple[Path, Any, int | None]]]:
    """Mantém wrappers/IDs; separa campos sem achatar seus fatos internos."""
    base = deepcopy(data)
    result = base.get("resultado") or {}
    if not isinstance(result, dict):
        raise ValueError("resultado de memória precisa ser mapa")
    base["resultado"] = result
    command = data.get("consulta", {}).get("comando")
    containers = [("relacao",)] if command == "relacao" else [
        ("relacao", "dados"), ("medidores", "dados"), ("textura_narrativa",)]
    fields = []
    for path in containers:
        try:
            payload = _get(result, path)
        except (KeyError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if not isinstance(key, str):
                raise ValueError("campo de memória precisa ter chave textual")
            fields.append((path + (key,), value, _priority(key, path)))
        _put(result, path, {})
    for key in ("dialogo_relacional", "iniciativa_social"):
        if key in result:
            fields.append(((key,), result.pop(key), 1))
    return base, sorted(fields, key=lambda row: row[0])


def add_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--campo", help="ponteiro JSON no resultado efetivo; não é caminho de arquivo")
    group.add_argument("--campos", action="store_true", help="lista campos disponíveis sem trazer seus valores")
    parser.add_argument("--inicio", type=int, default=0, help="índice inicial da página dirigida; padrão 0")


def request(data: dict, *, campo: str | None = None, campos: bool = False,
            inicio: int = 0) -> dict:
    if inicio < 0 or (inicio and campo is None and not campos):
        raise ValueError("--inicio exige consulta dirigida e índice não negativo")
    if campo is not None and campos:
        raise ValueError("use --campo ou --campos, não ambos")
    result = deepcopy(data)
    if campo is not None or campos:
        result["consulta"].update(campo=campo, campos=campos, inicio=inicio)
    return result


def _resolve(result: Any, text: str) -> Any:
    if text == "":
        return result
    if not text.startswith("/"):
        raise ValueError("--campo precisa ser ponteiro JSON iniciado por /")
    for raw in text[1:].split("/"):
        # Rejeita escapes inválidos, sem interpretar caminhos de arquivos.
        if "~" in raw.replace("~0", "").replace("~1", ""):
            raise ValueError("escape inválido em --campo")
        key = raw.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(result, list):
                if not key.isascii() or not key.isdecimal() or str(int(key)) != key:
                    raise ValueError("índice inválido em --campo")
                result = result[int(key)]
            elif isinstance(result, dict):
                result = result[key]
            else:
                raise ValueError("--campo atravessa um valor indivisível")
        except (KeyError, IndexError) as exc:
            raise ValueError("--campo não existe no estado efetivo") from exc
    return result


def _fallback() -> dict:
    return {"resultado": {"memoria_incompleta": True,
            "aprofundamento_necessario": True,
            "aviso": "Metadados excedem o orçamento; refine entidade/campo ou consulte a fonte dirigida."},
            "truncado_por_orcamento": True}


def _page(data: dict, fields: list, limit: int, as_json: bool, serialize: Serializer) -> tuple[str, bool]:
    query = data["consulta"]
    directory = query.get("campos", False)
    start = query.get("inicio", 0)
    path = query.get("campo")
    if not isinstance(start, int) or start < 0:
        raise ValueError("--inicio precisa ser índice não negativo")
    if directory:
        entries = [{"campo": pointer(p), "tipo": type(v).__name__,
                    "itens": len(v) if isinstance(v, (dict, list)) else 1,
                    "prioritario": rank is not None} for p, v, rank in fields]
    else:
        value = _resolve(data["resultado"], path)
        if isinstance(value, dict):
            entries = [{"chave": k, "valor": v} for k, v in value.items()]
        elif isinstance(value, list):
            entries = [{"indice": i, "valor": v} for i, v in enumerate(value)]
        else:
            entries = [{"valor": value}]
    if start > len(entries):
        raise ValueError("--inicio excede a quantidade de itens")
    out = {k: deepcopy(v) for k, v in data.items() if k != "resultado"}
    result = {"campo": path, "inicio": start, "total": len(entries),
              "itens": [], "proximo_inicio": start if start < len(entries) else None}
    out["resultado"] = result
    out["truncado_por_orcamento"] = start < len(entries)
    for index in range(start, len(entries)):
        trial = deepcopy(out)
        trial["resultado"]["itens"].append(entries[index])
        trial["resultado"]["proximo_inicio"] = index + 1 if index + 1 < len(entries) else None
        trial["truncado_por_orcamento"] = trial["resultado"]["proximo_inicio"] is not None
        if len(serialize(trial, as_json).encode("utf-8")) > limit:
            break
        out = trial
    if not out["resultado"]["itens"] and start < len(entries):
        # Nunca devolver o mesmo cursor como se fosse possível progredir.
        out["resultado"]["proximo_inicio"] = None
        out["resultado"]["item_nao_cabe"] = start
        entry = entries[start]
        if not directory and ("chave" in entry or "indice" in entry):
            child = str(entry.get("chave", entry.get("indice")))
            out["resultado"]["campo_nao_cabe"] = (path or "") + pointer((child,))
        out["resultado"]["aprofundamento_necessario"] = True
        out["resultado"]["aviso"] = "Fato indivisível: refine --campo ou consulte a fonte; não foi cortado."
    text = serialize(out, as_json)
    if len(text.encode("utf-8")) > limit:
        text = serialize(_fallback(), as_json)
        return text, True
    return text, out["truncado_por_orcamento"]


def fit(data: dict, limit: int, as_json: bool, serialize: Serializer) -> tuple[str, bool]:
    """Seleciona só na saída, depois de todos os deltas e do diálogo derivado."""
    limit = max(1024, min(limit, 16384))
    base, fields = _fields(data)
    query = data.get("consulta", {})
    if query.get("campo") is not None or query.get("campos"):
        return _page(data, fields, limit, as_json, serialize)
    selected: dict[Path, set[int]] = {}
    # Uma rodada por campo: biografia/lista longa não monopoliza o orçamento.
    candidates = []
    for path, value, rank in fields:
        if rank is None:
            continue
        indices = list(reversed(range(len(value)))) if isinstance(value, list) and value else [0]
        for round_number, index in enumerate(indices):
            candidates.append((round_number, rank, path, index))

    def render(selection: dict) -> dict:
        out = deepcopy(base)
        missing, secondary, origins = [], [], {}
        for path, value, rank in fields:
            indices = selection.get(path, set())
            count = len(value) if isinstance(value, list) and value else 1
            if indices:
                if isinstance(value, list) and value:
                    _put(out["resultado"], path, [value[i] for i in sorted(indices)])
                    if len(indices) < count:
                        origins[pointer(path)] = sorted(indices)
                else:
                    _put(out["resultado"], path, value)
            if rank is None:
                secondary.append(pointer(path))
            elif len(indices) < count:
                missing.append({"campo": pointer(path), "itens": count - len(indices)})
        meta = {"versao": 1, "aprofundamento_necessario": bool(missing),
                "campos_prioritarios_pendentes": len(missing),
                "pendentes": [m for m in missing if len(m["campo"]) <= 140][:4],
                "campos_secundarios": len(secondary)}
        if origins:
            meta["indices_origem"] = origins
        if missing or secondary:
            meta["consulta_dirigida"] = "--campos [--inicio N]; --campo <ponteiro> [--inicio N]"
        out["memoria_relevante"] = meta
        # Exclusão deliberada de detalhes não é perda por orçamento.
        out["truncado_por_orcamento"] = bool(missing)
        return out

    for _, _, path, index in sorted(candidates):
        trial = {p: set(items) for p, items in selected.items()}
        trial.setdefault(path, set()).add(index)
        if len(serialize(render(trial), as_json).encode("utf-8")) <= limit:
            selected = trial
    out = render(selected)
    text = serialize(out, as_json)
    if len(text.encode("utf-8")) > limit:
        return serialize(_fallback(), as_json), True
    return text, out["truncado_por_orcamento"]
