#!/usr/bin/env python3
"""Patch temporário e determinístico da integração estrutural da Etapa 9."""
from pathlib import Path


def edit(path: str, edits: list[tuple[str, str]]) -> None:
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in edits:
        if old not in s:
            raise SystemExit(f"Padrão não encontrado em {path}: {old[:120]!r}")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")


edit("ferramentas/contexto_core.py", [
    ("\n\nDEFAULT_MAX_BYTES = 8 * 1024", "\n\nimport sessoes as memoria_sessoes\n\nDEFAULT_MAX_BYTES = 8 * 1024"),
    (
        "def iter_search_files(repo: Path, *, reserved: bool, historical: bool) -> Iterable[Path]:",
        "def iter_search_files(\n    repo: Path, *, reserved: bool, historical: bool, transcripts: bool = False\n) -> Iterable[Path]:",
    ),
    (
        '            for name in ("resumo.md", "alteracoes-de-estado.yaml", "consequencias.md", "experiencia.md"): ',
        '            for name in ("handoff.yaml", "resumo.md", "alteracoes-de-estado.yaml", "alteracoes-transacionais.yaml", "consequencias.md", "experiencia.md"): ',
    ),
    (
        '            if historical:\n                trans = session_dir / "transcricao.md"',
        '            if transcripts:\n                trans = session_dir / "transcricao.md"',
    ),
    (
        "    historical: bool,\n    limit: int = 8,",
        "    historical: bool,\n    transcripts: bool = False,\n    limit: int = 8,",
    ),
    (
        "    for path in iter_search_files(repo, reserved=reserved, historical=historical):",
        "    for path in iter_search_files(\n        repo, reserved=reserved, historical=historical, transcripts=transcripts\n    ):",
    ),
    (
        'def command_search(\n    repo: Path,\n    term: str,\n    *,\n    reserved: bool,\n    historical: bool,\n) -> dict[str, Any]:\n    matches = generic_search(repo, term, reserved=reserved, historical=historical, limit=8)\n    level = "L4" if historical else "L3"\n',
        'def command_search(\n    repo: Path,\n    term: str,\n    *,\n    reserved: bool,\n    historical: bool,\n    transcripts: bool = False,\n) -> dict[str, Any]:\n    matches = generic_search(\n        repo, term, reserved=reserved, historical=historical, transcripts=transcripts, limit=8\n    )\n    level = "L4T" if transcripts else ("L4" if historical else "L3")\n',
    ),
    (
        '    scope = {\n        "reservado": reserved,\n        "historico_com_transcricoes_e_arquivos_frios": historical,\n    }',
        '    scope = {\n        "reservado": reserved,\n        "historico_estruturado": historical,\n        "transcricoes_frias": transcripts,\n    }',
    ),
    (
        "def command_rule(repo: Path, term: str) -> dict[str, Any]:",
        '''def command_resume(repo: Path) -> dict[str, Any]:
    result, sources = memoria_sessoes.resume_view(repo)
    return envelope("retomada", None, "L1-L2", sources, result)


def command_session(repo: Path, term: str) -> dict[str, Any]:
    normalized = normalize(term)
    if normalized in {"atual", "current"}:
        session = memoria_sessoes.current_session(repo)
    else:
        try:
            session = int(term)
        except ValueError as exc:
            raise ValueError("sessao precisa ser número inteiro ou 'atual'") from exc
    result, sources = memoria_sessoes.session_snapshot(repo, session)
    return envelope("sessao", term, "L2-L3", sources, result)


def command_rule(repo: Path, term: str) -> dict[str, Any]:''',
    ),
    (
        '    sub.add_parser("cena", help="contexto quente + recorte imediato da cena")\n    sub.add_parser("status", help="somente o contexto quente operacional")\n',
        '    sub.add_parser("cena", help="contexto quente + recorte imediato da cena")\n    sub.add_parser("status", help="somente o contexto quente operacional")\n    sub.add_parser("retomada", help="retoma a cena sem abrir transcrições")\n    session = sub.add_parser("sessao", help="memória compacta de uma sessão, sem transcrição")\n    session.add_argument("termo", help="número da sessão ou atual")\n',
    ),
    (
        '    search.add_argument(\n        "--historico",\n        action="store_true",\n        help="inclui transcrições e histórico frio; usar somente após fontes correntes não bastarem",\n    )',
        '    search.add_argument(\n        "--historico",\n        action="store_true",\n        help="inclui histórico estruturado/frio, mas ainda exclui transcrições",\n    )\n    search.add_argument(\n        "--transcricoes",\n        action="store_true",\n        help="inclui transcrições brutas; exige --historico e deve ser a última escalada local",\n    )',
    ),
    (
        '        elif args.command == "status":\n            data = command_status(repo)\n        elif args.command == "npc":',
        '        elif args.command == "status":\n            data = command_status(repo)\n        elif args.command == "retomada":\n            data = command_resume(repo)\n        elif args.command == "sessao":\n            data = command_session(repo, args.termo)\n        elif args.command == "npc":',
    ),
    (
        '        elif args.command == "buscar":\n            data = command_search(\n                repo,\n                args.termo,\n                reserved=args.reservado,\n                historical=args.historico,\n            )',
        '        elif args.command == "buscar":\n            if args.transcricoes and not args.historico:\n                raise ValueError("--transcricoes exige --historico")\n            data = command_search(\n                repo,\n                args.termo,\n                reserved=args.reservado,\n                historical=args.historico,\n                transcripts=args.transcricoes,\n            )',
    ),
])

edit("ferramentas/contexto.py", [
    (
        "_CORE_COMMAND_STATUS = core.command_status\n_CORE_COMMAND_SCENE = core.command_scene",
        "_CORE_COMMAND_STATUS = core.command_status\n_CORE_COMMAND_SCENE = core.command_scene\n_CORE_COMMAND_RESUME = core.command_resume",
    ),
    (
        "def command_relation(repo: Path, term: str) -> dict[str, Any]:",
        '''def command_resume(repo: Path) -> dict[str, Any]:
    data = _CORE_COMMAND_RESUME(repo)
    result = data.get("resultado") or {}
    if not isinstance(result, dict):
        return data
    context = result.get("contexto")
    scene = result.get("cena")
    records = _pending(repo)
    if isinstance(context, dict) and isinstance(scene, dict):
        effective_context, effective_scene, _ = transacoes.overlay_runtime(context, scene, records)
        result["contexto"] = effective_context
        result["cena"] = effective_scene
    session = result.get("sessao")
    if isinstance(session, int):
        recent = transacoes.pending_for_session(records, session)[-6:]
    else:
        recent = records[-6:]
    result["eventos_pendentes_recentes"] = [
        {
            "id": item.get("id"),
            "resumo": core.truncate_text(item.get("resumo", ""), 500),
            "modo": item.get("modo"),
        }
        for item in recent
    ]
    if recent:
        _add_pending_source(data)
    return data


def command_relation(repo: Path, term: str) -> dict[str, Any]:''',
    ),
    (
        '    historical: bool,\n) -> dict[str, Any]:\n    data = _CORE_COMMAND_SEARCH(\n        repo, term, reserved=reserved, historical=historical\n    )',
        '    historical: bool,\n    transcripts: bool = False,\n) -> dict[str, Any]:\n    data = _CORE_COMMAND_SEARCH(\n        repo, term, reserved=reserved, historical=historical, transcripts=transcripts\n    )',
    ),
    (
        "    core.command_status = command_status\n    core.command_scene = command_scene",
        "    core.command_status = command_status\n    core.command_scene = command_scene\n    core.command_resume = command_resume",
    ),
])

edit("ferramentas/gerar-runtime.py", [
    (
        '            "conhecimento_de_ren": "personagens/jogador/conhecimento.md",\n            "transcricao_atual": transcricao,\n            "narrador": "narrador/",',
        '            "conhecimento_de_ren": "personagens/jogador/conhecimento.md",\n            "indice_sessoes": "sessoes/index.yaml",\n            "retomada": "ferramentas/contexto.py retomada",\n            "transcricao_fria": transcricao,\n            "narrador": "narrador/",',
    ),
    (
        '            "estado": "estado/estado-atual.yaml",\n            "transcricao": transcricao,\n            "relacoes": "estado/relacoes.yaml",',
        '            "estado": "estado/estado-atual.yaml",\n            "handoff": f"sessoes/{sessao:03d}/handoff.yaml",\n            "indice_sessoes": "sessoes/index.yaml",\n            "transcricao_fria": transcricao,\n            "relacoes": "estado/relacoes.yaml",',
    ),
])

edit("ferramentas/consolidar.py", [
    ("import transacoes\nimport turno", "import transacoes\nimport turno\nimport sessoes as memoria_sessoes"),
    (
        '    outputs["runtime/contexto.yaml"] = runtime_mod.dump_yaml(new_context).encode("utf-8")\n    outputs["runtime/cena.yaml"] = runtime_mod.dump_yaml(new_scene).encode("utf-8")\n\n    processed_ids =',
        '''    outputs["runtime/contexto.yaml"] = runtime_mod.dump_yaml(new_context).encode("utf-8")
    outputs["runtime/cena.yaml"] = runtime_mod.dump_yaml(new_scene).encode("utf-8")

    handoff = memoria_sessoes.build_handoff(
        repo,
        session=session,
        kind=kind,
        context=new_context,
        scene=new_scene,
        ledger=combined_ledger,
    )
    outputs[memoria_sessoes.handoff_rel(session).as_posix()] = memoria_sessoes.dump_yaml_bytes(handoff)
    outputs[memoria_sessoes.INDEX_PATH.as_posix()] = memoria_sessoes.dump_yaml_bytes(
        memoria_sessoes.build_index(repo, active_session=session, virtual_files=outputs)
    )

    processed_ids =''',
    ),
    (
        "    return errors\n\n\ndef status(repo: Path)",
        "    errors.extend(memoria_sessoes.check(repo))\n    return errors\n\n\ndef status(repo: Path)",
    ),
])

p = Path("tests/test_consolidacao.py")
s = p.read_text(encoding="utf-8")
old = '        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")\n\n        ledger = mod.load_ledger(self.repo, 3)'
new = '        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")\n        self.assertTrue((self.repo / "sessoes/003/handoff.yaml").is_file())\n        self.assertTrue((self.repo / "sessoes/index.yaml").is_file())\n\n        ledger = mod.load_ledger(self.repo, 3)'
if old not in s:
    raise SystemExit("Padrão de teste de consolidação não encontrado")
p.write_text(s.replace(old, new, 1), encoding="utf-8")

print("OK — patch estrutural da Etapa 9 aplicado.")
