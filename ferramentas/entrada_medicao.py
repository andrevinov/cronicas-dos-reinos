"""Contrato de entrada pós-hoc: fontes congeladas, unidades e diagnósticos.

Esta porta prepara/valida entradas. Não executa comandos do rollout, não mede
desempenho e não consulta o estado vivo ou pacotes anteriores implicitamente.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "evaluation/contrato-medicao.json"
DEFAULT_MODULES = ROOT / "evaluation/contratos-modulos"
INPUT_SCHEMA = 1
SOURCES = (
    "catalogo", "metas", "baseline", "guardrails", "series", "releases",
    "interacoes", "adjudicacoes", "validade",
)
REQUIRED_SOURCES = frozenset({"catalogo", "metas", "baseline"})
DEFAULT_SOURCES = {
    "catalogo": ROOT / "evaluation/catalogo-modulos-v2.json",
    "metas": ROOT / "evaluation/metas-avaliacao-v2.json",
    "baseline": ROOT / "baseline/rollout-2026-08-15.json",
    "guardrails": ROOT / "evaluation/catalogo-guardrails-v2.json",
    "series": ROOT / "evaluation/series-avaliacao.json",
    "releases": ROOT / "evaluation/module-releases.json",
}
RATIO_MEASURES = frozenset({"proporcao", "percentual", "proporcao_adjudicada", "razao", "nota"})
MEASURES = RATIO_MEASURES | {"contagem", "tokens", "segundos", "palavras", "contagem_tipificada", "contagem_separada"}
ORIGINS = frozenset({"nativa", "observacao", "adjudicacao_ou_recibo_objetivo", "agregacao", "atribuicao_contabil"})


class InputContractError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"constante JSON inválida: {value}")

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"chave JSON duplicada: {key}")
            result[key] = value
        return result

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"número JSON não finito: {value}")
        return parsed

    return json.loads(text, parse_constant=reject_constant, parse_float=finite_float, object_pairs_hook=unique_keys)


def _load_json(path: Path) -> Any:
    return _json(path.read_text(encoding="utf-8"))


def diagnostic(code: str, scope: str, message: str, *, blocking: bool = True, line: int | None = None) -> dict[str, Any]:
    result = {"codigo": code, "escopo": scope, "gravidade": "bloqueio" if blocking else "limitacao", "mensagem": message}
    if line is not None:
        result["linha"] = line
    return result


def _field_errors(value: Mapping[str, Any], fields: set[str], scope: str) -> list[dict[str, Any]]:
    missing, extra = fields - set(value), set(value) - fields
    if missing or extra:
        return [diagnostic("campos_divergentes", scope, f"Campos ausentes: {sorted(missing)}; extras: {sorted(extra)}.")]
    return []


def _indicator_errors(definitions: Any, units: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    errors = []
    if not isinstance(definitions, dict) or not definitions:
        return [diagnostic("indicadores_ausentes", scope, "Declare os indicadores e suas unidades.")]
    for name, definition in sorted(definitions.items()):
        where = f"{scope}.{name}"
        if not isinstance(definition, dict):
            errors.append(diagnostic("indicador_invalido", where, "O indicador precisa ser um objeto."))
            continue
        errors.extend(_field_errors(definition, {"unidade_avaliativa", "medida", "fonte", "denominador", "ausencia_de_evidencia"}, where))
        if not isinstance(definition.get("unidade_avaliativa"), str) or definition["unidade_avaliativa"] not in units:
            errors.append(diagnostic("unidade_desconhecida", where, "Unidade avaliativa não declarada no contrato comum."))
        if not isinstance(definition.get("medida"), str) or definition["medida"] not in MEASURES or not isinstance(definition.get("fonte"), str) or definition["fonte"] not in ORIGINS:
            errors.append(diagnostic("indicador_invalido", where, "Medida ou origem desconhecida."))
        denominator = definition.get("denominador")
        if "denominador" not in definition or (denominator is not None and not isinstance(denominator, str)) or (isinstance(definition.get("medida"), str) and definition["medida"] in RATIO_MEASURES and not denominator):
            errors.append(diagnostic("denominador_ausente", where, "Razões, proporções e notas exigem denominador explícito."))
        if not isinstance(definition.get("ausencia_de_evidencia"), str) or not definition["ausencia_de_evidencia"]:
            errors.append(diagnostic("ausencia_nao_declarada", where, "Declare o tratamento da ausência de evidência."))
    return errors


def validate_contract(contract: Any) -> list[dict[str, Any]]:
    if not isinstance(contract, dict) or type(contract.get("schema_contrato_medicao")) is not int or contract["schema_contrato_medicao"] != 1:
        return [diagnostic("contrato_desconhecido", "contrato", "Schema de contrato de medição não suportado.")]
    errors = _field_errors(contract, {"schema_contrato_medicao", "versao_contrato", "escopo", "formatos", "unidades", "indicadores_globais", "indicadores_comuns_modulares", "politicas"}, "contrato")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(contract.get("versao_contrato", ""))):
        errors.append(diagnostic("versao_invalida", "contrato", "Declare uma versão SemVer."))
    units = contract.get("unidades")
    if not isinstance(units, dict) or not units:
        return errors + [diagnostic("unidades_ausentes", "contrato", "As unidades precisam ser declaradas.")]
    for name, unit in sorted(units.items()):
        if not isinstance(unit, dict) or not isinstance(unit.get("definicao"), str) or not unit["definicao"] or not isinstance(unit.get("identidade"), list) or not unit["identidade"] or any(not isinstance(field, str) or not field for field in unit["identidade"]):
            errors.append(diagnostic("unidade_invalida", f"unidades.{name}", "Declare definição e campos de identidade."))
        elif len(set(unit["identidade"])) != len(unit["identidade"]):
            errors.append(diagnostic("unidade_invalida", f"unidades.{name}", "Campos de identidade precisam ser únicos."))
        if isinstance(unit, dict):
            errors.extend(_field_errors(unit, {"definicao", "identidade"}, f"unidades.{name}"))
    profiles = contract.get("formatos")
    profile = profiles.get("codex_jsonl_v1") if isinstance(profiles, dict) else None
    if not isinstance(profile, dict) or any(not isinstance(profile.get(field), list) or not profile[field] or any(not isinstance(item, str) or not item for item in profile[field]) for field in ("tipos_registro", "tipos_response_item")) or profile.get("representacoes_output") != ["texto", "blocos"]:
        errors.append(diagnostic("perfil_invalido", "contrato.formatos", "Declare o perfil de envelope JSONL e suas saídas suportadas."))
    if isinstance(profiles, dict):
        errors.extend(_field_errors(profiles, {"codex_jsonl_v1"}, "contrato.formatos"))
    if isinstance(profile, dict):
        errors.extend(_field_errors(profile, {"tipos_registro", "tipos_response_item", "representacoes_output", "validacao", "correlacao_agrupada"}, "contrato.formatos.codex_jsonl_v1"))
        for name in ("validacao", "correlacao_agrupada"):
            if not isinstance(profile.get(name), str) or not profile[name]:
                errors.append(diagnostic("perfil_invalido", "contrato.formatos", "Declare o alcance da validação e da correlação."))
    for group in ("indicadores_globais", "indicadores_comuns_modulares"):
        errors.extend(_indicator_errors(contract.get(group), units, group))
    if not isinstance(contract.get("politicas"), dict) or not contract["politicas"] or any(not isinstance(value, str) or not value for value in contract["politicas"].values()) or not isinstance(contract.get("escopo"), str) or not contract["escopo"]:
        errors.append(diagnostic("politicas_ausentes", "contrato", "Declare escopo e políticas da entrada."))
    return errors


def validate_module_contract(local: Any, catalog_module: Mapping[str, Any], contract: Any) -> list[dict[str, Any]]:
    module_id = str(catalog_module.get("id", ""))
    if not isinstance(local, dict) or type(local.get("schema_contrato_modulo")) is not int or local["schema_contrato_modulo"] != 1 or local.get("module_id") != module_id:
        return [diagnostic("contrato_modulo_invalido", module_id, "Schema ou identidade do contrato local diverge do catálogo.")]
    units = contract.get("unidades", {}) if isinstance(contract, dict) else {}
    errors = _indicator_errors(local.get("indicadores"), units if isinstance(units, dict) else {}, module_id)
    errors.extend(_field_errors(local, {"schema_contrato_modulo", "versao_contrato", "module_id", "unidade_contexto_legada", "indicadores"}, module_id))
    if local.get("unidade_contexto_legada") not in ("turno", "cena", "fronteira", "sessao", "evento"):
        errors.append(diagnostic("unidade_legada_invalida", module_id, "Declare a unidade de contexto do catálogo anterior."))
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(local.get("versao_contrato", ""))):
        errors.append(diagnostic("versao_invalida", module_id, "Declare uma versão SemVer local."))
    specialized = catalog_module.get("indicadores_especializados")
    if not isinstance(specialized, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in specialized):
        return errors + [diagnostic("indicadores_catalogo_invalidos", module_id, "O catálogo precisa declarar os indicadores especializados.")]
    expected = {item["id"] for item in specialized}
    actual = set(local["indicadores"]) if isinstance(local.get("indicadores"), dict) else set()
    if expected != actual:
        errors.append(diagnostic("indicadores_divergentes", module_id, f"Indicadores ausentes: {sorted(expected - actual)}; extras: {sorted(actual - expected)}."))
    for item in specialized:
        definition = (local.get("indicadores") or {}).get(item["id"]) if isinstance(local.get("indicadores"), dict) else None
        if isinstance(definition, dict) and definition.get("medida") != item.get("unidade"):
            errors.append(diagnostic("medida_divergente", f"{module_id}.{item['id']}", "A medida do indicador diverge do catálogo selecionado."))
    return errors


def _blob(value: Any, format_name: str = "json") -> dict[str, Any]:
    return {"estado": "presente", "sha256": digest(value), "conteudo": value, "formato": format_name}


def _snapshot(path: Path | None, name: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    if path is None:
        errors.append(diagnostic("fonte_ausente", name, "Fonte não selecionada; a ausência fica explícita.", blocking=name in REQUIRED_SOURCES))
        return {"estado": "ausente", "sha256": None, "conteudo": None, "formato": None}
    try:
        if path.suffix == ".jsonl":
            value = [_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            value = _load_json(path)
        if not isinstance(value, (dict, list)):
            raise ValueError("a fonte selecionada precisa conter objeto JSON ou ledger JSONL")
        return _blob(value, "jsonl" if path.suffix == ".jsonl" else "json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(diagnostic("fonte_invalida", name, f"Não foi possível congelar a fonte: {exc}"))
        return {"estado": "invalida", "sha256": None, "conteudo": None, "formato": None}


def _read_prefix(path: Path, cutoff: int | None) -> bytes:
    with path.open("rb") as handle:
        limit = os.fstat(handle.fileno()).st_size if cutoff is None else cutoff
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise InputContractError("O corte precisa ser um número inteiro positivo de bytes.")
        data = handle.read(limit)
    if len(data) != limit:
        raise InputContractError("O corte ultrapassa o tamanho disponível da fonte.")
    return data


def _inspect_source(data: bytes, contract: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors = []
    profiles = contract.get("formatos") if isinstance(contract, dict) else None
    profile = profiles.get("codex_jsonl_v1") if isinstance(profiles, dict) else None
    profile = profile if isinstance(profile, dict) else {}
    record_types = profile.get("tipos_registro") if isinstance(profile.get("tipos_registro"), list) else []
    item_types = profile.get("tipos_response_item") if isinstance(profile.get("tipos_response_item"), list) else []
    records = 0
    last_timestamp = None
    native_id = None
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError:
        return {"registros": 0, "ultima_timestamp": None, "codex_session_id": None}, [diagnostic("utf8_invalido", "fonte", "O corte não contém UTF-8 válido.")]
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = _json(line)
        except ValueError as exc:
            errors.append(diagnostic("registro_json_invalido", "fonte", f"Registro incompleto ou inválido: {exc}", line=number))
            continue
        records += 1
        if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
            errors.append(diagnostic("envelope_invalido", "fonte", "Registro precisa conter type e payload objeto.", line=number))
            continue
        kind = record.get("type")
        payload = record["payload"]
        if kind not in record_types:
            errors.append(diagnostic("formato_nao_suportado", "fonte", f"Tipo de registro não suportado: {kind!r}.", line=number))
        elif kind == "response_item":
            item = payload.get("type")
            if item not in item_types:
                errors.append(diagnostic("item_nao_suportado", "fonte", f"Tipo de response_item não suportado: {item!r}.", line=number))
            if isinstance(item, str) and item in {"function_call_output", "custom_tool_call_output"}:
                output = payload.get("output")
                if not isinstance(output, (str, list)):
                    errors.append(diagnostic("saida_nao_suportada", "fonte", "Output precisa ser texto ou lista de blocos.", line=number))
                elif isinstance(output, list) and any(not isinstance(block, dict) for block in output):
                    errors.append(diagnostic("bloco_invalido", "fonte", "Blocos de saída precisam ser objetos.", line=number))
            if isinstance(item, str) and item in {"function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"} and (not isinstance(payload.get("call_id"), str) or not payload["call_id"]):
                errors.append(diagnostic("identidade_chamada_ausente", "chamada_ferramenta", "A chamada sem call_id exige correlação explicitamente indeterminada.", blocking=False, line=number))
        if kind == "session_meta" and payload.get("id") is not None:
            if not isinstance(payload["id"], str):
                errors.append(diagnostic("metadado_invalido", "fonte", "A identidade nativa precisa ser texto.", line=number))
            elif native_id is not None and native_id != payload["id"]:
                errors.append(diagnostic("sessoes_nativas_multiplas", "fonte", "O corte contém identidades nativas divergentes.", line=number))
            else:
                native_id = payload["id"]
        timestamp = record.get("timestamp")
        if timestamp is not None and not isinstance(timestamp, str):
            errors.append(diagnostic("metadado_invalido", "fonte", "O timestamp precisa ser texto.", line=number))
        elif timestamp:
            last_timestamp = timestamp
    if not records:
        errors.append(diagnostic("fonte_vazia", "fonte", "Não há registros JSON no corte."))
    return {"registros": records, "ultima_timestamp": last_timestamp, "codex_session_id": native_id}, errors


def prepare_input(
    rollout: Path, *, session_id: str, source_paths: Mapping[str, Path | None] | None = None,
    cutoff_bytes: int | None = None, expected_sha256: str | None = None,
    contract_path: Path = DEFAULT_CONTRACT, modules_directory: Path = DEFAULT_MODULES,
    code_paths: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9]{3,}", session_id) or int(session_id) == 0:
        raise InputContractError("sessao_id precisa conter ao menos três dígitos, por exemplo 023.")
    contract = _load_json(contract_path)
    errors = validate_contract(contract)
    data = _read_prefix(rollout, cutoff_bytes)
    source_hash = hashlib.sha256(data).hexdigest()
    inspected, source_errors = _inspect_source(data, contract)
    errors.extend(source_errors)
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        errors.append(diagnostic("hash_esperado_invalido", "fonte", "O hash esperado precisa ser SHA-256 hexadecimal minúsculo."))
    elif expected_sha256 is not None and source_hash != expected_sha256:
        errors.append(diagnostic("hash_fonte_divergente", "fonte", "O prefixo diverge do hash esperado."))
    selected = DEFAULT_SOURCES if source_paths is None else source_paths
    unknown = set(selected) - set(SOURCES)
    if unknown:
        raise InputContractError(f"Fontes não declaradas: {sorted(unknown)}")
    snapshots = {name: _snapshot(selected.get(name), name, errors) for name in SOURCES}
    catalog = snapshots["catalogo"]["conteudo"]
    modules = {}
    entries = catalog.get("modulos", []) if isinstance(catalog, dict) else []
    if not isinstance(entries, list) or not entries:
        errors.append(diagnostic("catalogo_invalido", "catalogo", "Declare uma lista não vazia de módulos."))
        entries = []
    for entry in entries:
        module_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(module_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", module_id) or module_id in modules:
            errors.append(diagnostic("modulo_invalido", "catalogo", "ID de módulo inválido ou duplicado."))
            continue
        local = _snapshot(modules_directory / f"{module_id}.json", module_id, errors)
        modules[module_id] = local
        if local["estado"] == "presente":
            errors.extend(validate_module_contract(local["conteudo"], entry, contract))
    code = {}
    default_code = {str(path.relative_to(ROOT)): path for path in (ROOT / "ferramentas").rglob("*.py")} if code_paths is None else code_paths
    if code_paths is None:
        default_code.update({name: ROOT / name for name in ("pyproject.toml", "poetry.lock")})
    for name, path in sorted(default_code.items()):
        try:
            code[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(diagnostic("codigo_ausente", f"codigo.{name}", str(exc)))
    if not code:
        errors.append(diagnostic("codigo_ausente", "codigo", "Declare os arquivos do avaliador selecionado."))
    result = {
        "schema_entrada_medicao": INPUT_SCHEMA, "sessao_id": session_id,
        "escopo_validacao": "entrada_e_unidades; não comprova extração nem desempenho",
        "fonte": {"perfil": "codex_jsonl_v1", "corte_bytes": len(data), "sha256": source_hash, "sha256_esperado": expected_sha256,
                  "recorte": "prefixo_integral_declarado; seleção de interações ainda não avaliada", **inspected},
        "contrato": _blob(contract), "snapshots": snapshots, "contratos_modulos": modules,
        "codigo_sha256": code, "ambiente": {"python": platform.python_version(), "PyYAML": importlib.metadata.version("PyYAML")},
        "diagnosticos": errors,
        "status": "bloqueada" if any(item["gravidade"] == "bloqueio" for item in errors) else "limitada" if errors else "valida",
    }
    result["entrada_id"] = digest(result)
    additional = [item for item in validate_input(result) if item not in errors]
    if additional:
        errors.extend(additional)
        result["status"] = "bloqueada" if any(item["gravidade"] == "bloqueio" for item in errors) else "limitada"
        result["entrada_id"] = digest({key: value for key, value in result.items() if key != "entrada_id"})
    return result


def validate_input(bundle: Any) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict) or type(bundle.get("schema_entrada_medicao")) is not int or bundle["schema_entrada_medicao"] != INPUT_SCHEMA:
        return [diagnostic("entrada_desconhecida", "entrada", "Schema de entrada não suportado.")]
    errors = []
    required = {"sessao_id", "escopo_validacao", "fonte", "contrato", "snapshots", "contratos_modulos", "codigo_sha256", "ambiente", "diagnosticos", "status", "entrada_id"}
    if required - set(bundle):
        return [diagnostic("entrada_incompleta", "entrada", f"Campos ausentes: {sorted(required - set(bundle))}")]
    unknown = set(bundle) - required - {"schema_entrada_medicao"}
    if unknown:
        errors.append(diagnostic("campos_desconhecidos", "entrada", f"Campos não declarados: {sorted(unknown)}"))
    for name in ("fonte", "contrato", "snapshots", "contratos_modulos", "codigo_sha256", "ambiente"):
        if not isinstance(bundle[name], dict):
            errors.append(diagnostic("estrutura_invalida", name, "O campo precisa ser um objeto."))
    if not isinstance(bundle["diagnosticos"], list) or any(
        not isinstance(item, dict) or item.get("gravidade") not in ("bloqueio", "limitacao")
        or not all(isinstance(item.get(key), str) and item[key] for key in ("codigo", "escopo", "mensagem"))
        for item in bundle["diagnosticos"]
    ):
        errors.append(diagnostic("diagnosticos_invalidos", "diagnosticos", "Declare diagnósticos tipados."))
    if errors and any(item["codigo"] in {"estrutura_invalida", "diagnosticos_invalidos"} for item in errors):
        return errors
    body = {key: value for key, value in bundle.items() if key != "entrada_id"}
    try:
        actual_id = digest(body)
    except (ValueError, TypeError):
        return errors + [diagnostic("json_invalido", "entrada", "A entrada precisa ser JSON finito e serializável.")]
    if bundle["entrada_id"] != actual_id:
        errors.append(diagnostic("entrada_alterada", "entrada", "O conteúdo diverge da identidade congelada."))
    if not isinstance(bundle["sessao_id"], str) or not re.fullmatch(r"[0-9]{3,}", bundle["sessao_id"]) or int(bundle["sessao_id"]) == 0:
        errors.append(diagnostic("sessao_invalida", "sessao_id", "Declare a identidade canônica da sessão selecionada."))
    if bundle["status"] not in ("valida", "limitada", "bloqueada"):
        errors.append(diagnostic("status_desconhecido", "status", "Estado de validação não suportado."))
    if not isinstance(bundle["escopo_validacao"], str) or not bundle["escopo_validacao"]:
        errors.append(diagnostic("escopo_ausente", "escopo_validacao", "Declare o alcance da validação."))
    source = bundle["fonte"]
    errors.extend(_field_errors(source, {"perfil", "corte_bytes", "sha256", "sha256_esperado", "recorte", "registros", "ultima_timestamp", "codex_session_id"}, "fonte"))
    if source.get("perfil") != "codex_jsonl_v1" or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        errors.append(diagnostic("fonte_invalida", "fonte", "Perfil ou hash da fonte inválido."))
    for name, minimum in (("corte_bytes", 1), ("registros", 0)):
        if isinstance(source.get(name), bool) or not isinstance(source.get(name), int) or source[name] < minimum:
            errors.append(diagnostic("corte_invalido", f"fonte.{name}", "Declare um inteiro dentro do intervalo permitido."))
    if not isinstance(source.get("recorte"), str) or not source["recorte"]:
        errors.append(diagnostic("recorte_ausente", "fonte", "Declare o recorte selecionado."))
    for name in ("ultima_timestamp", "codex_session_id"):
        if name not in source or (source[name] is not None and not isinstance(source[name], str)):
            errors.append(diagnostic("metadado_invalido", f"fonte.{name}", "Declare texto ou ausência explícita."))
    expected_hash = source.get("sha256_esperado")
    if "sha256_esperado" not in source or (expected_hash is not None and (not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash))):
        errors.append(diagnostic("hash_esperado_invalido", "fonte", "Declare SHA-256 esperado ou ausência explícita."))
    elif expected_hash is not None and expected_hash != source.get("sha256"):
        errors.append(diagnostic("hash_fonte_divergente", "fonte", "O prefixo diverge do hash esperado."))
    if not bundle["codigo_sha256"] or any(not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", str(value)) for key, value in bundle["codigo_sha256"].items()):
        errors.append(diagnostic("codigo_invalido", "codigo_sha256", "Declare hashes dos arquivos do avaliador."))
    if not all(isinstance(bundle["ambiente"].get(name), str) and bundle["ambiente"][name] for name in ("python", "PyYAML")):
        errors.append(diagnostic("ambiente_incompleto", "ambiente", "Declare versões do Python e PyYAML."))
    errors.extend(_field_errors(bundle["ambiente"], {"python", "PyYAML"}, "ambiente"))
    if set(bundle["snapshots"]) != set(SOURCES):
        errors.append(diagnostic("fontes_divergentes", "snapshots", "Todas as fontes precisam declarar presença ou ausência."))
    blobs = [("contrato", bundle["contrato"], True)]
    blobs.extend((name, blob, name in REQUIRED_SOURCES) for name, blob in bundle["snapshots"].items())
    blobs.extend((name, blob, True) for name, blob in bundle["contratos_modulos"].items())
    for name, blob, required_source in blobs:
        if isinstance(blob, dict):
            errors.extend(_field_errors(blob, {"estado", "sha256", "conteudo", "formato"}, name))
        if not isinstance(blob, dict) or blob.get("estado") not in ("presente", "ausente", "invalida"):
            errors.append(diagnostic("snapshot_invalido", name, "Estado de snapshot desconhecido."))
        elif blob["estado"] == "presente" and (blob.get("formato") not in ("json", "jsonl") or not isinstance(blob.get("conteudo"), (dict, list))):
            errors.append(diagnostic("snapshot_invalido", name, "Declare o formato e o conteúdo estruturado da fonte presente."))
        elif blob["estado"] == "presente" and blob.get("sha256") != digest(blob.get("conteudo")):
            errors.append(diagnostic("snapshot_alterado", name, "O snapshot diverge do seu hash."))
        elif blob["estado"] != "presente" and (blob.get("conteudo") is not None or blob.get("sha256") is not None or blob.get("formato") is not None):
            errors.append(diagnostic("snapshot_invalido", name, "Fonte ausente/inválida não pode carregar conteúdo ou hash."))
        if isinstance(blob, dict) and blob.get("estado") != "presente":
            blocking = required_source or blob.get("estado") == "invalida"
            if not any(item["escopo"] == name and item["gravidade"] == ("bloqueio" if blocking else "limitacao") for item in bundle["diagnosticos"]):
                errors.append(diagnostic("ausencia_nao_diagnosticada", name, "A ausência/invalidez precisa ter diagnóstico explícito.", blocking=blocking))
    if any(not isinstance(blob, dict) or blob.get("estado") not in ("presente", "ausente", "invalida") for _, blob, _ in blobs):
        return errors + bundle["diagnosticos"]
    contract = bundle["contrato"].get("conteudo")
    errors.extend(validate_contract(contract))
    if not isinstance(contract, dict):
        return errors + bundle["diagnosticos"]
    catalog = (bundle["snapshots"].get("catalogo") or {}).get("conteudo") or {}
    entries = catalog.get("modulos") if isinstance(catalog, dict) else None
    if not isinstance(entries, list) or not entries:
        errors.append(diagnostic("catalogo_invalido", "catalogo", "Declare uma lista não vazia de módulos."))
    else:
        expected_modules = set()
        for entry in entries:
            module_id = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(module_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", module_id) or module_id in expected_modules:
                errors.append(diagnostic("modulo_invalido", "catalogo", "ID de módulo inválido ou duplicado."))
                continue
            expected_modules.add(module_id)
            for name in ("versao_implementacao", "versao_avaliacao"):
                if not re.fullmatch(r"\d+\.\d+\.\d+", str(entry.get(name, ""))):
                    errors.append(diagnostic("versao_modulo_ausente", f"{module_id}.{name}", "Declare a versão da régua selecionada; não inferir a execução histórica."))
            local = bundle["contratos_modulos"].get(module_id)
            if local is None:
                errors.append(diagnostic("contrato_modulo_ausente", module_id, "Módulo sem contrato local."))
            elif not isinstance(local, dict):
                continue
            elif local.get("estado") == "presente":
                errors.extend(validate_module_contract(local["conteudo"], entry, contract))
        if set(bundle["contratos_modulos"]) != expected_modules:
            errors.append(diagnostic("registro_modulos_divergente", "contratos_modulos", "Contratos locais precisam corresponder exatamente ao catálogo selecionado."))
    stated_status = "bloqueada" if any(item["gravidade"] == "bloqueio" for item in bundle["diagnosticos"]) else "limitada" if bundle["diagnosticos"] else "valida"
    if bundle["status"] != stated_status:
        errors.append(diagnostic("status_divergente", "status", "O estado diverge dos diagnósticos registrados."))
    errors.extend(bundle["diagnosticos"])
    return errors


def read_frozen_source(bundle: dict[str, Any], path: Path) -> bytes:
    errors = validate_input(bundle)
    if any(item["gravidade"] == "bloqueio" for item in errors):
        raise InputContractError("A entrada tem bloqueios; consulte os diagnósticos.")
    data = _read_prefix(path, bundle["fonte"]["corte_bytes"])
    if hashlib.sha256(data).hexdigest() != bundle["fonte"]["sha256"]:
        raise InputContractError("O prefixo do rollout diverge da fonte congelada.")
    return data


def module_contract_id(bundle: dict[str, Any], module_id: str) -> str:
    """Assinatura do contrato local; não é hash de resultados ou custo causal."""
    catalog = bundle["snapshots"]["catalogo"]["conteudo"]
    entry = next((item for item in catalog["modulos"] if item["id"] == module_id), None)
    if entry is None or module_id not in bundle["contratos_modulos"]:
        raise InputContractError(f"Módulo não declarado: {module_id}")
    return digest({"comum": bundle["contrato"]["conteudo"], "catalogo_modulo": entry,
                   "local": bundle["contratos_modulos"][module_id]["conteudo"]})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    prepare = sub.add_parser("preparar", help="Congela a entrada sem copiar o rollout bruto.")
    prepare.add_argument("rollout", type=Path)
    prepare.add_argument("--sessao-id", required=True)
    prepare.add_argument("--saida", required=True, type=Path)
    prepare.add_argument("--corte-bytes", type=int)
    prepare.add_argument("--sha256-esperado")
    prepare.add_argument("--contrato", type=Path, default=DEFAULT_CONTRACT)
    prepare.add_argument("--contratos-modulos", type=Path, default=DEFAULT_MODULES)
    for name in SOURCES:
        prepare.add_argument(f"--{name}", type=Path, default=DEFAULT_SOURCES.get(name))
    check = sub.add_parser("validar", help="Valida hashes, unidades e fontes da entrada.")
    check.add_argument("entrada", type=Path)
    check.add_argument("--rollout", type=Path, help="Verifica também o prefixo do bruto disponível.")
    args = parser.parse_args()
    try:
        if args.cmd == "preparar":
            bundle = prepare_input(args.rollout, session_id=args.sessao_id,
                                   source_paths={name: getattr(args, name) for name in SOURCES},
                                   cutoff_bytes=args.corte_bytes, expected_sha256=args.sha256_esperado,
                                   contract_path=args.contrato, modules_directory=args.contratos_modulos)
            args.saida.parent.mkdir(parents=True, exist_ok=True)
            serialized = canonical_bytes(bundle) + b"\n"
            if args.saida.exists():
                if args.saida.read_bytes() != serialized:
                    raise InputContractError("A saída já contém outra entrada; use outro arquivo para preservar a anterior.")
            else:
                with args.saida.open("xb") as handle:
                    handle.write(serialized)
            print(json.dumps({"entrada_id": bundle["entrada_id"], "status": bundle["status"],
                              "saida": str(args.saida), "diagnosticos": bundle["diagnosticos"]}, ensure_ascii=False, indent=2))
            return 1 if bundle["status"] == "bloqueada" else 0
        bundle = _load_json(args.entrada)
        errors = validate_input(bundle)
        if args.rollout:
            read_frozen_source(bundle, args.rollout)
        print(json.dumps({"diagnosticos": errors, "escopo": "entrada_e_unidades"}, ensure_ascii=False, indent=2))
        return int(any(item["gravidade"] == "bloqueio" for item in errors))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"diagnosticos": [diagnostic("entrada_invalida", "entrada", str(exc))]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
