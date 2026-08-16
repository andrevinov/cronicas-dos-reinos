#!/usr/bin/env python3
"""Auditoria final da refatoração de economia de contexto.

Este comando é de manutenção/aceitação. Ele NÃO pertence ao loop narrativo.

Objetivos:
- executar a suíte acumulada de integridade e regressão;
- confrontar o estado atual com a baseline lógica pré-refatoração;
- provar que a retomada funciona somente com a camada quente/compacta;
- provar que deltas pendentes continuam visíveis numa retomada limpa;
- garantir que a própria auditoria não modifica a campanha;
- emitir um único veredito: PRONTO PARA RETOMAR ou BLOQUEADO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import contexto_core
import transacoes

BASELINE = Path("baseline/estado-logico-2026-08-15.yaml")
EXPECTED_ENGINEERING_PATHS = (
    "ferramentas/auditoria-final.py",
    "ferramentas/contexto.py",
    "ferramentas/turno.py",
    "ferramentas/checkpoint.py",
    "ferramentas/consolidar.py",
    "ferramentas/sessoes.py",
    "ferramentas/politica_acesso.py",
    "ferramentas/texturas.py",
    "ferramentas/analisar-rollout.py",
    "ferramentas/comparar-rollouts.py",
    "baseline/rollout-2026-08-15.json",
    "baseline/metas-rollout-pos-refatoracao.json",
    "docs/agente/escada-de-acesso.md",
    "docs/agente/memoria-de-sessoes.md",
    "docs/agente/telemetria-rollouts.md",
    "docs/agente/densidade-narrativa.md",
    "cenario/texturas/index.yaml",
)

# Áreas cuja mutação seria um efeito colateral intolerável da auditoria.
PROTECTED_ROOTS = (
    "campanha.yaml",
    "estado",
    "personagens/jogador",
    "sessoes",
    "narrador",
    "regras",
    "cenario",
    "runtime",
)

PROTECTED_EXCLUDES = {
    "runtime/consultas-contexto.jsonl",  # diagnóstico local opt-in, não cânone
    "runtime/consolidacao-em-andamento.json",
}


class AuditError(RuntimeError):
    pass


@dataclass
class GateResult:
    nome: str
    ok: bool
    detalhe: Any


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_path(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise AuditError(f"caminho ausente: {dotted}")
        current = current[part]
    return current


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_digest(repo: Path) -> tuple[str, int]:
    """Hash de árvore estável das áreas de campanha que a auditoria não pode alterar."""
    entries: list[tuple[str, str]] = []
    for root_name in PROTECTED_ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            rel = path.relative_to(repo).as_posix()
            if rel in PROTECTED_EXCLUDES or rel.startswith("runtime/.consolidacao-stage/"):
                continue
            entries.append((rel, _sha256(path)))
    digest = hashlib.sha256()
    for rel, sha in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), len(entries)


def run_command(repo: Path, args: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        tail = "\n".join(output.splitlines()[-30:])
        raise AuditError(f"comando falhou ({proc.returncode}): {' '.join(args)}\n{tail}")
    return {
        "comando": " ".join(args),
        "saida_final": "\n".join(output.splitlines()[-5:]),
    }


def _copy_hot_layer(repo: Path, target: Path) -> int:
    context = load_yaml(repo / "runtime/contexto.yaml") or {}
    session = ((context.get("sessao") or {}).get("numero"))
    if not isinstance(session, int):
        raise AuditError("runtime/contexto.yaml não informa sessão válida")

    rels = [
        Path("runtime/contexto.yaml"),
        Path("runtime/cena.yaml"),
        Path("runtime/eventos-pendentes.jsonl"),
        Path("sessoes/index.yaml"),
        Path("sessoes") / f"{session:03d}" / "handoff.yaml",
    ]
    for rel in rels:
        src = repo / rel
        if not src.is_file():
            raise AuditError(f"camada quente necessária ausente: {rel}")
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return session


def invoke_resume(repo: Path, sandbox: Path) -> tuple[dict[str, Any], int]:
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / "ferramentas/contexto.py"),
            "--repo",
            str(sandbox),
            "--json",
            "--sem-log",
            "retomada",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AuditError(f"retomada em sandbox falhou: {proc.stderr.strip()}\n{proc.stdout.strip()}")
    raw = proc.stdout
    if len(raw.encode("utf-8")) > 8192:
        raise AuditError("retomada ultrapassou o teto L2 de 8 KiB")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuditError(f"retomada não devolveu JSON válido: {exc}") from exc
    return data, len(raw.encode("utf-8"))


def _resume_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("resultado") or {}
    context = result.get("contexto") or {}
    scene = result.get("cena") or {}
    return {
        "sessao": ((context.get("sessao") or {}).get("numero")),
        "status": ((context.get("sessao") or {}).get("status")),
        "modo": ((context.get("sessao") or {}).get("modo_de_cena")),
        "personagem": ((context.get("personagem") or {}).get("nome")),
        "nivel": ((context.get("personagem") or {}).get("nivel")),
        "pv": ((context.get("recursos") or {}).get("pv")),
        "ki": ((context.get("recursos") or {}).get("ki")),
        "ca": ((context.get("recursos") or {}).get("ca")),
        "data": ((context.get("tempo") or {}).get("data")),
        "hora": ((context.get("tempo") or {}).get("hora_aproximada")),
        "area": ((context.get("localizacao") or {}).get("area")),
        "ponto_exato": ((context.get("localizacao") or {}).get("ponto_exato")),
        "resumo_imediato": scene.get("resumo_imediato"),
        "pendentes_recentes": result.get("eventos_pendentes_recentes") or [],
    }


def _effective_runtime(repo: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Estado operacional verdadeiro: último checkpoint + buffer ainda não consolidado."""
    base_context = load_yaml(repo / "runtime/contexto.yaml") or {}
    base_scene = load_yaml(repo / "runtime/cena.yaml") or {}
    records = transacoes.load_pending(repo)
    effective_context, effective_scene, _ = transacoes.overlay_runtime(
        base_context,
        base_scene,
        records,
    )
    return effective_context, effective_scene or {}, records


def gate_structure(repo: Path) -> dict[str, Any]:
    missing = [path for path in EXPECTED_ENGINEERING_PATHS if not (repo / path).is_file()]
    if missing:
        raise AuditError(f"infraestrutura acumulada ausente: {missing}")
    journal = repo / transacoes.CONSOLIDATION_JOURNAL
    if journal.exists():
        raise AuditError(
            "há consolidação em andamento; execute ferramentas/checkpoint.py recuperar antes de retomar"
        )
    return {"arquivos_criticos": len(EXPECTED_ENGINEERING_PATHS), "journal": "ausente"}


def gate_baseline_and_regressions(repo: Path) -> dict[str, Any]:
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "ferramentas/migrar-estado-atual.py", "--check"],
        [sys.executable, "ferramentas/migrar-memorias-fragmentadas.py", "--check"],
        [sys.executable, "ferramentas/reindexar-conhecimento.py", "--check"],
        [sys.executable, "ferramentas/turno.py", "check"],
        [sys.executable, "ferramentas/consolidar.py", "check"],
        [sys.executable, "ferramentas/sessoes.py", "check"],
        [sys.executable, "ferramentas/checkpoint.py", "check"],
        [sys.executable, "ferramentas/gerar-runtime.py", "--check"],
        [
            sys.executable,
            "ferramentas/verificar-integridade.py",
            "--baseline",
            BASELINE.as_posix(),
        ],
    ]
    results = [run_command(repo, command) for command in commands]
    return {"comandos": len(results), "ultimo": results[-1]["saida_final"]}


def gate_hot_only_resume(repo: Path) -> dict[str, Any]:
    expected_context, expected_scene, pending = _effective_runtime(repo)
    with tempfile.TemporaryDirectory(prefix="cronicas-retomada-quente-") as tmp:
        sandbox = Path(tmp)
        session = _copy_hot_layer(repo, sandbox)
        # Prova negativa: nenhuma transcrição, estado completo, ficha ou histórico é copiado.
        forbidden = [
            sandbox / "sessoes" / f"{session:03d}" / "transcricao.md",
            sandbox / "estado/estado-atual.yaml",
            sandbox / "personagens/jogador/ficha.yaml",
            sandbox / "historico",
        ]
        if any(path.exists() for path in forbidden):
            raise AuditError("sandbox quente contém material frio/canônico que não deveria estar presente")

        data, output_bytes = invoke_resume(repo, sandbox)
        snapshot = _resume_snapshot(data)
        sources = data.get("fontes") or []
        cold_sources = [source for source in sources if "transcricao" in str(source) or str(source).startswith("historico/")]
        if cold_sources:
            raise AuditError(f"retomada declarou fonte fria: {cold_sources}")

        expected_summary = contexto_core.truncate_text(expected_scene.get("resumo_imediato", ""), 1400)
        checks = {
            "sessao": (((expected_context.get("sessao") or {}).get("numero")), snapshot["sessao"]),
            "modo": (((expected_context.get("sessao") or {}).get("modo_de_cena")), snapshot["modo"]),
            "personagem": (((expected_context.get("personagem") or {}).get("nome")), snapshot["personagem"]),
            "nivel": (((expected_context.get("personagem") or {}).get("nivel")), snapshot["nivel"]),
            "pv": (((expected_context.get("recursos") or {}).get("pv")), snapshot["pv"]),
            "ki": (((expected_context.get("recursos") or {}).get("ki")), snapshot["ki"]),
            "ca": (((expected_context.get("recursos") or {}).get("ca")), snapshot["ca"]),
            "data": (((expected_context.get("tempo") or {}).get("data")), snapshot["data"]),
            "hora": (((expected_context.get("tempo") or {}).get("hora_aproximada")), snapshot["hora"]),
            "area": (((expected_context.get("localizacao") or {}).get("area")), snapshot["area"]),
            "ponto": (((expected_context.get("localizacao") or {}).get("ponto_exato")), snapshot["ponto_exato"]),
            "resumo": (expected_summary, snapshot["resumo_imediato"]),
        }
        mismatches = {
            name: {"esperado": expected, "obtido": actual}
            for name, (expected, actual) in checks.items()
            if expected != actual
        }
        if mismatches:
            raise AuditError(f"retomada quente divergiu do estado efetivo: {mismatches}")
        return {
            "sessao": session,
            "bytes_saida": output_bytes,
            "fontes": sources,
            "eventos_pendentes": len(pending),
            "transcricao_lida": False,
            "snapshot": snapshot,
        }


def gate_pending_overlay_resume(repo: Path) -> dict[str, Any]:
    base = load_yaml(repo / "runtime/contexto.yaml") or {}
    session = ((base.get("sessao") or {}).get("numero"))
    base_ki = (((base.get("recursos") or {}).get("ki") or {}).get("atuais"))
    if not isinstance(session, int) or not isinstance(base_ki, int):
        raise AuditError("runtime atual não possui sessão/Ki adequados ao teste de overlay")

    with tempfile.TemporaryDirectory(prefix="cronicas-retomada-pendente-") as tmp:
        sandbox = Path(tmp)
        _copy_hot_layer(repo, sandbox)
        record = transacoes.build_pending_record(
            {
                "id": "auditoria-step12-overlay",
                "resumo": "Delta sintético da auditoria final; existe somente no sandbox temporário.",
                "modo": ((base.get("sessao") or {}).get("modo_de_cena")),
                "deltas": [
                    {
                        "alvo": "estado",
                        "op": "inc",
                        "caminho": "recursos.ki.atuais",
                        "valor": -1,
                    }
                ],
            },
            session,
        )
        (sandbox / transacoes.PENDING_PATH).write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        data, output_bytes = invoke_resume(repo, sandbox)
        snapshot = _resume_snapshot(data)
        effective_ki = ((snapshot.get("ki") or {}).get("atuais"))
        if effective_ki != base_ki - 1:
            raise AuditError(
                f"overlay pendente não apareceu na retomada: esperado Ki {base_ki - 1}, obtido {effective_ki}"
            )
        ids = [item.get("id") for item in snapshot.get("pendentes_recentes") or [] if isinstance(item, dict)]
        if record["id"] not in ids:
            raise AuditError("retomada não expôs resumo do evento pendente sintético")
        if (sandbox / f"sessoes/{session:03d}/transcricao.md").exists():
            raise AuditError("teste de overlay criou/leu transcrição inesperadamente")
        return {
            "bytes_saida": output_bytes,
            "ki_base": base_ki,
            "ki_efetivo": effective_ki,
            "evento": record["id"],
            "somente_sandbox": True,
        }


def gate_telemetry_contract(repo: Path) -> dict[str, Any]:
    fixture = "tests/fixtures/rollout-step11-mini.jsonl"
    analyzed = run_command(
        repo,
        [sys.executable, "ferramentas/analisar-rollout.py", fixture, "--json"],
    )
    compared = run_command(
        repo,
        [sys.executable, "ferramentas/comparar-rollouts.py", fixture, "--json"],
    )
    return {
        "analisador": analyzed["comando"],
        "comparador": compared["comando"],
        "observacao": "fixture de engenharia; números reais pós-refatoração exigem rollout de jogo futuro",
    }


def gate_no_raw_rollout_tracked(repo: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise AuditError(f"git indisponível para auditoria de privacidade: {exc}") from exc
    if proc.returncode != 0:
        raise AuditError("git ls-files falhou durante auditoria de privacidade")
    tracked = [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]
    raw = [
        path
        for path in tracked
        if Path(path).name.startswith("rollout-")
        and path.endswith(".jsonl")
        and not path.startswith("tests/fixtures/")
    ]
    if raw:
        raise AuditError(f"rollout bruto foi versionado fora de fixture: {raw}")
    return {"rollouts_brutos_versionados": 0}


def baseline_snapshot(repo: Path) -> dict[str, Any]:
    context, scene, _ = _effective_runtime(repo)
    return {
        "sessao": ((context.get("sessao") or {}).get("numero")),
        "status": ((context.get("sessao") or {}).get("status")),
        "modo": ((context.get("sessao") or {}).get("modo_de_cena")),
        "personagem": ((context.get("personagem") or {}).get("nome")),
        "nivel": ((context.get("personagem") or {}).get("nivel")),
        "pv": ((context.get("recursos") or {}).get("pv")),
        "ki": ((context.get("recursos") or {}).get("ki")),
        "ca": ((context.get("recursos") or {}).get("ca")),
        "data": ((context.get("tempo") or {}).get("data")),
        "hora": ((context.get("tempo") or {}).get("hora_aproximada")),
        "area": ((context.get("localizacao") or {}).get("area")),
        "ponto_exato": ((context.get("localizacao") or {}).get("ponto_exato")),
        "resumo_imediato": scene.get("resumo_imediato"),
    }


def execute_gate(name: str, function: Callable[[Path], Any], repo: Path) -> GateResult:
    try:
        return GateResult(name, True, function(repo))
    except Exception as exc:  # relatório deve mostrar todos os gates possíveis
        return GateResult(name, False, str(exc))


def audit(repo: Path) -> dict[str, Any]:
    before_digest, protected_files = protected_digest(repo)
    gates: list[GateResult] = []
    for name, function in (
        ("estrutura_acumulada", gate_structure),
        ("regressoes_e_baseline", gate_baseline_and_regressions),
        ("retomada_somente_camada_quente", gate_hot_only_resume),
        ("retomada_com_delta_pendente", gate_pending_overlay_resume),
        ("telemetria_pos_hoc", gate_telemetry_contract),
        ("privacidade_rollouts", gate_no_raw_rollout_tracked),
    ):
        gates.append(execute_gate(name, function, repo))

    after_digest, protected_files_after = protected_digest(repo)
    immutable = before_digest == after_digest and protected_files == protected_files_after
    gates.append(
        GateResult(
            "auditoria_sem_mutacao",
            immutable,
            {
                "arquivos_protegidos": protected_files,
                "hash_antes": before_digest,
                "hash_depois": after_digest,
            }
            if immutable
            else "a auditoria alterou uma área protegida da campanha",
        )
    )

    ready = all(gate.ok for gate in gates)
    return {
        "schema_auditoria": 1,
        "veredito": "PRONTO PARA RETOMAR" if ready else "BLOQUEADO",
        "pronto_para_retomar": ready,
        "estado_de_retomada": baseline_snapshot(repo),
        "gates": [
            {"nome": gate.nome, "ok": gate.ok, "detalhe": gate.detalhe}
            for gate in gates
        ],
        "nota_telemetria": (
            "A infraestrutura de medição está pronta; economia real antes/depois só pode ser calculada "
            "depois de novos avanços narrativos produzirem rollout pós-refatoração."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emite relatório JSON completo")
    args = parser.parse_args()
    repo = args.repo.resolve()
    report = audit(repo)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"AUDITORIA FINAL — {report['veredito']}")
        for gate in report["gates"]:
            print(f"{'OK' if gate['ok'] else 'FALHA'} — {gate['nome']}")
            if not gate["ok"]:
                print(f"  {gate['detalhe']}")
        state = report["estado_de_retomada"]
        print(
            "Retomada: "
            f"sessão {state.get('sessao')} | {state.get('personagem')} nv. {state.get('nivel')} | "
            f"PV {((state.get('pv') or {}).get('atuais'))}/{((state.get('pv') or {}).get('maximos'))} | "
            f"Ki {((state.get('ki') or {}).get('atuais'))}/{((state.get('ki') or {}).get('maximos'))} | "
            f"{state.get('area')} | {state.get('hora')}"
        )
    return 0 if report["pronto_para_retomar"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
