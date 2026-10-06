"""Decisão terminal única, compartilhada pelo ledger e adaptador histórico."""
from __future__ import annotations

import json
import re
from typing import Any

import yaml


EXIT_CODES = (
    re.compile(r"process exited with code\s+(-?\d+)", re.I),
    re.compile(r"exit(?:_|\s+)code[\"']?\s*[:=]\s*[\"']?(-?\d+)", re.I),
    re.compile(r"returncode[\"']?\s*[:=]\s*[\"']?(-?\d+)", re.I),
)


def terminal_result(
    payload: dict[str, Any], text: str, *, domain: bool = False,
    execution_prevented: bool = False,
) -> tuple[str, str, str]:
    """Falha explícita prevalece; envelope e saída truncada não provam sucesso.

    Retorna estado/fonte/marcador. Não interpreta vitória ficcional, registra
    commits ou transforma um trecho de documentação em resultado de domínio.
    """
    if execution_prevented:
        return "nao_executada", "envelope_host", "falha_antes_da_invocacao"
    positive: list[tuple[str, str]] = []
    negative: list[tuple[str, str]] = []
    for key in ("exit_code", "returncode"):
        value = payload.get(key)
        if type(value) is int:
            (positive if value == 0 else negative).append((f"resultado.{key}", f"{key}={value}"))
    if type(payload.get("success")) is bool:
        value = payload["success"]
        (positive if value else negative).append(("resultado.success", f"success={str(value).lower()}"))
    if payload.get("isError") is True or payload.get("is_error") is True:
        negative.append(("resultado", "is_error=true"))
    status = str(payload.get("status") or "").casefold()
    if status in {"success", "succeeded", "completed", "ok"}:
        positive.append(("resultado.status", f"status={status}"))
    elif status in {"failure", "failed", "error", "cancelled", "canceled"}:
        negative.append(("resultado.status", f"status={status}"))
    for pattern in EXIT_CODES:
        for match in pattern.finditer(text):
            value = int(match.group(1))
            (positive if value == 0 else negative).append(("saida_operacao", f"exit_code={value}"))
    terminal_values = []
    if domain:
        patterns = (
            ("erro_terminal", r"(?im)^\s*erro\b"),
            ("falha_terminal", r"(?im)^\s*falha\b"),
            ("recusa_terminal", r"(?im)^\s*(?:opera[cç][aã]o\s+)?recusad[ao]\b"),
            ("estado_falho", r"(?im)^(?:estado|status)\s*:\s*(?:erro|falha|falhou|recusad[ao])\s*$"),
        )
        for marker, pattern in patterns:
            if re.search(pattern, text):
                negative.append(("saida_operacao", marker))
                break
    if re.search(r"(?im)^\s*(?:script failed|error\b|failed\b|invalid patch|traceback \(most recent call last\)|(?:command|operation|process) timed out\b)", text):
        negative.append(("saida_operacao", "falha_terminal_execucao"))
    value = None
    if domain:
        body = re.split(r"(?m)^Final output:\s*", text, maxsplit=1)[-1].strip()
        body = re.sub(r"\A(?:(?:Process exited with code -?\d+|Wall time[^\n]*|Chunk ID[^\n]*|Script completed|Output:)\r?\n)+", "", body, flags=re.I)
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            if re.search(r"(?m)^(?:estado|status|schema_[a-z_]+)\s*:", body):
                try:
                    value = yaml.safe_load(body)
                except yaml.YAMLError:
                    pass
        if isinstance(value, dict):
            terminal_values.append(value)
            pending = list(value.values())
            seen = {id(value)}
            while pending:
                child = pending.pop()
                if isinstance(child, dict) and id(child) not in seen:
                    seen.add(id(child))
                    if "schema_turn_and_session_orchestration" in child:
                        terminal_values.append(child)
                    pending.extend(child.values())
            for terminal in terminal_values:
                state = str(terminal.get("estado") or terminal.get("status") or "").casefold()
                if state in {"erro", "falha", "falhou", "failed", "error", "recusado", "recusada"} or terminal.get("is_error") is True or terminal.get("isError") is True:
                    negative.append(("saida_operacao", "estado_falho"))
    if negative:
        source, marker = negative[0]
        # O erro de domínio prevalece sobre exit 0 do envelope/subprocesso.
        return "falha_operacional", source, marker
    if re.search(r"(?im)(?:warning: truncated output|output (?:was )?truncated|\[output truncated\])", text):
        return "evidencia_insuficiente", "saida_operacao", "saida_truncada"
    if positive:
        source, marker = positive[0]
        return "sucesso", source, marker
    if domain:
        # Só uma estrutura raiz válida é terminal: citações e exemplos aninhados
        # com a palavra 'concluido' não são recibos de execução.
        for terminal in terminal_values:
            state = str(terminal.get("estado") or terminal.get("status") or "").casefold()
            if state in {"preparado", "concluido", "iniciado", "aplicado", "registrado", "confirmado", "ok", "sucesso"}:
                return "sucesso", "saida_operacao", "estado_terminal_sucesso"
    if re.match(r"^(?:OK\b|Done!|Success\b|SUCCESS\b)", text.strip()) and domain:
        return "sucesso", "saida_operacao", "prefixo_sucesso"
    return "evidencia_insuficiente", "saida_operacao", "sem_sinal_terminal"


def legacy_success(payload: dict[str, Any], text: str, *, domain: bool = False) -> bool | None:
    state, _, _ = terminal_result(payload, text, domain=domain)
    return True if state == "sucesso" else False if state == "falha_operacional" else None
