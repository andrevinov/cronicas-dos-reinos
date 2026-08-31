from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"marker not unique in {path}: count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


cronica = ROOT / "ferramentas/cronica.py"
replace_once(cronica, "import argparse\nimport sys\n", "import argparse\nimport json\nimport sys\n")
replace_once(
    cronica,
    "import cronica_pending_gate as _pending_gate\nimport progressao_juppongatana\n",
    "import cronica_pending_gate as _pending_gate\nimport mecanica_cronica as _mechanics\nimport progressao_juppongatana\n",
)
replace_once(
    cronica,
    '''    contract["sidequest_emergente_task46"] = (\n        "Somente em ticket preparado com --oportunidade-sidequest, a transação pode "\n        "conter sidequest_emergente com oferta+quest+contratos Task43/44/45. "\n        "Sem oferta literal narrada, omita o bloco inteiro."\n    )\n    return contract\n''',
    '''    contract["sidequest_emergente_task46"] = (\n        "Somente em ticket preparado com --oportunidade-sidequest, a transação pode "\n        "conter sidequest_emergente com oferta+quest+contratos Task43/44/45. "\n        "Sem oferta literal narrada, omita o bloco inteiro."\n    )\n    fields = contract.get("campos")\n    if isinstance(fields, dict):\n        fields["mecanica"] = {\n            "resolucoes": (\n                "somente quando a preparação devolver mecanica.obrigacoes; uma resolução "\n                "estruturada por obrigação, antes dos deltas mecânicos"\n            )\n        }\n    contract["causalidade_mecanica_task6"] = (\n        "Deltas de Ki/Focus e efeitos declarados no ticket exigem resolução compatível; "\n        "cronica valida pelo núcleo mecânico antes do writer."\n    )\n    return contract\n''',
)
replace_once(
    cronica,
    '''    signal = kwargs.pop("sidequest_signal", _SIDEQUEST_DECISION_UNSET)\n    if signal is _SIDEQUEST_DECISION_UNSET:\n''',
    '''    signal = kwargs.pop("sidequest_signal", _SIDEQUEST_DECISION_UNSET)\n    mechanical_spec = kwargs.pop("mechanical_spec", None)\n    if signal is _SIDEQUEST_DECISION_UNSET:\n''',
)
replace_once(
    cronica,
    '''    base = _hot.prepare(*args, **kwargs)\n    if signal is None:\n        return base\n    try:\n        return _sidequests46.integrate_prepare(\n            Path(repo),\n            base,\n            signal_raw=signal,\n            decode_ticket=decode_ticket,\n            encode_ticket=_core.encode_ticket,\n            now=kwargs.get("now"),\n        )\n    except _sidequests46.EmergentSidequestIntegrationError as exc:\n        raise _core.CronicaError(str(exc)) from exc\n''',
    '''    base = _hot.prepare(*args, **kwargs)\n    if signal is None:\n        prepared = base\n    else:\n        try:\n            prepared = _sidequests46.integrate_prepare(\n                Path(repo),\n                base,\n                signal_raw=signal,\n                decode_ticket=decode_ticket,\n                encode_ticket=_core.encode_ticket,\n                now=kwargs.get("now"),\n            )\n        except _sidequests46.EmergentSidequestIntegrationError as exc:\n            raise _core.CronicaError(str(exc)) from exc\n    try:\n        output_budget = (\n            _sidequests46.MAX_COMBINED_PREP_BYTES\n            if "sidequest_emergente" in prepared\n            else _core.MAX_PREP_OUTPUT_BYTES\n        )\n        return _mechanics.attach_to_prepare(\n            Path(repo),\n            prepared,\n            mechanical_spec,\n            decode_ticket=decode_ticket,\n            encode_ticket=_core.encode_ticket,\n            max_ticket_chars=_core.MAX_TICKET_CHARS,\n            max_output_bytes=output_budget,\n        )\n    except _mechanics.MechanicalContractError as exc:\n        raise _core.CronicaError(str(exc)) from exc\n''',
)
replace_once(
    cronica,
    '''def conclude(repo: Path, token: str, transaction: dict):\n    payload, meta = _task46_meta(token)\n    if meta is None:\n        return _conclude_base(repo, token, transaction)\n\n    ticket_id_original = _core.ticket_id(token)\n    base_token = _base_token(payload)\n    writer_tx = _sidequests46.writer_transaction(transaction)\n''',
    '''def conclude(repo: Path, token: str, transaction: dict):\n    payload, meta = _task46_meta(token)\n    try:\n        mechanical_writer_tx = _mechanics.validate_transaction(repo, payload, transaction)\n    except _mechanics.MechanicalContractError as exc:\n        raise _core.CronicaError(str(exc)) from exc\n    if meta is None:\n        return _conclude_base(repo, token, mechanical_writer_tx)\n\n    ticket_id_original = _core.ticket_id(token)\n    base_token = _base_token(payload)\n    writer_tx = _sidequests46.writer_transaction(mechanical_writer_tx)\n''',
)
old_register = '''def register(*args, revalidate: bool = True, **kwargs):\n    token = args[1] if len(args) > 1 else kwargs.get("token")\n    if isinstance(token, str):\n        _, meta = _task46_meta(token)\n        if meta is not None:\n            raise _core.CronicaError(\n                "reparo Task46 repete cronica concluir com a mesma transação; registrar isolado não instala a sidequest"\n            )\n    original = _core._revalidate_ticket\n    _core._revalidate_ticket = globals()["_revalidate_ticket"]\n    try:\n        return _hot.register(\n            *args,\n            **kwargs,\n            revalidate_ticket=revalidate,\n        )\n    finally:\n        _core._revalidate_ticket = original\n'''
new_register = '''def register(\n    repo: Path,\n    token: str,\n    transaction: dict,\n    *,\n    revalidate: bool = True,\n):\n    payload, meta = _task46_meta(token)\n    if meta is not None:\n        raise _core.CronicaError(\n            "reparo Task46 repete cronica concluir com a mesma transação; registrar isolado não instala a sidequest"\n        )\n    try:\n        writer_tx = _mechanics.validate_transaction(repo, payload, transaction)\n    except _mechanics.MechanicalContractError as exc:\n        raise _core.CronicaError(str(exc)) from exc\n    original = _core._revalidate_ticket\n    _core._revalidate_ticket = globals()["_revalidate_ticket"]\n    try:\n        return _hot.register(\n            repo,\n            token,\n            writer_tx,\n            revalidate_ticket=revalidate,\n        )\n    finally:\n        _core._revalidate_ticket = original\n'''
replace_once(cronica, old_register, new_register)
replace_once(
    cronica,
    '''    prepare_parser.add_argument(\n        "--transito-urbano",\n        choices=[_hot.URBAN_TRANSIT_SCOPE],\n        help=(\n            "deslocamento material pela malha urbana; usa o mesmo preparar/concluir, "\n            "sem criar local canônico nem chamada adicional"\n        ),\n    )\n    sidequest_decision = prepare_parser.add_mutually_exclusive_group(required=True)\n''',
    '''    prepare_parser.add_argument(\n        "--transito-urbano",\n        choices=[_hot.URBAN_TRANSIT_SCOPE],\n        help=(\n            "deslocamento material pela malha urbana; usa o mesmo preparar/concluir, "\n            "sem criar local canônico nem chamada adicional"\n        ),\n    )\n    prepare_parser.add_argument(\n        "--mecanica-json",\n        help=(\n            "JSON com regras e obrigações mecânicas; fica congelado no mesmo ticket "\n            "de preparar e não cria endpoint nem chamada de orquestração adicional"\n        ),\n    )\n    sidequest_decision = prepare_parser.add_mutually_exclusive_group(required=True)\n''',
)
replace_once(
    cronica,
    '''def _run_session(repo: Path, command: str):\n''',
    '''def _mechanical_spec_from_args(args: argparse.Namespace) -> dict | None:\n    raw = getattr(args, "mecanica_json", None)\n    if raw is None:\n        return None\n    try:\n        data = json.loads(raw)\n    except json.JSONDecodeError as exc:\n        raise _core.CronicaError(f"--mecanica-json inválido: {exc.msg}") from exc\n    if not isinstance(data, dict):\n        raise _core.CronicaError("--mecanica-json precisa representar um objeto JSON")\n    return data\n\n\ndef _run_session(repo: Path, command: str):\n''',
)
replace_once(
    cronica,
    '''            urban_transit=getattr(args, "transito_urbano", None),\n            sidequest_signal=_sidequest_signal_from_args(args),\n''',
    '''            urban_transit=getattr(args, "transito_urbano", None),\n            mechanical_spec=_mechanical_spec_from_args(args),\n            sidequest_signal=_sidequest_signal_from_args(args),\n''',
)

campaign = ROOT / "campanha.yaml"
replace_once(campaign, "          task_6_integracao_cronica: false\n", "          task_6_integracao_cronica: true\n")
replace_once(
    campaign,
    '    nucleo_mecanico_5_5e: "ferramentas/mecanica_dnd_5_5e.py"\n',
    '    nucleo_mecanico_5_5e: "ferramentas/mecanica_dnd_5_5e.py"\n    contrato_mecanico_cronica: "ferramentas/mecanica_cronica.py"\n',
)

rules = ROOT / "regras/resolucao-de-acoes.md"
text = rules.read_text(encoding="utf-8")
section = '''\n---\n\n## Gasto de recursos de classe\n\nTodo gasto mecânico de recurso de classe precisa ser decidido antes de persistir a consequência. O turno só pode reduzir o recurso se o ticket preparado registrar a obrigação, o valor disponível naquele instante for suficiente e a resolução do turno confirmar o gasto.\n\nEnquanto o ruleset ativo for D&D 5e 2014, o recurso de Ren é **ki**. Quando a migração 5.5e for ativada, o mesmo contrato passa a proteger **Focus**. O writer nunca pode aceitar um gasto que deixe o recurso abaixo de zero.\n\n`cronica` valida a causalidade e a disponibilidade, mas não implementa a regra de D&D nem rola dados: resoluções de teste, salvaguarda e ataque são verificadas pelas primitivas do núcleo mecânico.\n'''
if "## Gasto de recursos de classe" not in text:
    rules.write_text(text.rstrip() + "\n" + section, encoding="utf-8")

catalog = ROOT / "regras/catalogo.yaml"
text = catalog.read_text(encoding="utf-8")
if "  - id: ataque_d20\n" not in text:
    text = text.rstrip() + '''\n\n  - id: ataque_d20\n    aliases:\n      - jogada de ataque\n      - attack roll\n    dominio: combate\n    ruleset: dnd_5e_2014\n    autoridade: ruleset_atual\n    fonte:\n      arquivo: regras/resolucao-de-acoes.md\n      secao: Fórmula básica\n    resumo_interno: >-\n      Ataques usam d20 mais bônus de ataque contra CA; 1 e 20 naturais seguem a resolução de ataque do núcleo mecânico.\n    executor: dados\n    persistencia: nenhuma\n    house_rule: null\n\n  - id: salvaguarda_d20\n    aliases:\n      - jogada de salvaguarda\n      - saving throw\n    dominio: resolucao\n    ruleset: dnd_5e_2014\n    autoridade: ruleset_atual\n    fonte:\n      arquivo: regras/resolucao-de-acoes.md\n      secao: Fórmula básica\n    resumo_interno: >-\n      Salvaguardas usam d20 mais bônus de salvaguarda contra a CD fixada antes da rolagem.\n    executor: dados\n    persistencia: nenhuma\n    house_rule: null\n\n  - id: gasto_recurso_classe\n    aliases:\n      - gasto de recurso\n      - gastar ki\n      - gastar focus\n      - class resource spend\n    dominio: recursos\n    ruleset: dnd_5e_2014\n    autoridade: ruleset_atual\n    fonte:\n      arquivo: regras/resolucao-de-acoes.md\n      secao: Gasto de recursos de classe\n    resumo_interno: >-\n      Gastos de Ki/Focus exigem obrigação preparada, disponibilidade suficiente e delta compatível antes da persistência.\n    executor: cronica\n    persistencia: turno_transacional\n    house_rule: null\n'''
    catalog.write_text(text + "\n", encoding="utf-8")

doc = ROOT / "docs/agente/regras-e-rolagens.md"
text = doc.read_text(encoding="utf-8")
marker = "## Ficha mecânica única de Ren\n"
section = '''## Contrato mecânico do turno\n\n`cronica preparar` aceita opcionalmente um contrato mecânico estruturado com IDs/aliases do `regras/catalogo.yaml` e obrigações do turno. Quando presente, o mesmo ticket congela ruleset, regras aplicáveis, parâmetros de teste/ataque/salvaguarda e snapshot de Ki/Focus necessário aos gastos.\n\nA rolagem continua fora de `cronica`, pela CLI `dados`. Em `cronica concluir`, a transação fornece os dados já rolados em `mecanica.resolucoes`; `cronica` os repassa ao núcleo mecânico para reconstruir deterministicamente escolhido, total e resultado. Só depois compara a consequência com os deltas e chama o writer.\n\nGasto de Ki/Focus sem obrigação correspondente é recusado. Mudança do recurso desde `preparar` torna o ticket mecânico obsoleto. O caminho sem mecânica não abre catálogo nem estado adicional e continua em exatamente duas chamadas de orquestração: `preparar` e `concluir`.\n\n'''
if "## Contrato mecânico do turno" not in text:
    if marker not in text:
        raise SystemExit("docs marker missing")
    doc.write_text(text.replace(marker, section + marker, 1), encoding="utf-8")

readme = ROOT / "ferramentas/README.md"
text = readme.read_text(encoding="utf-8")
marker = "### Rolagens em lote\n"
section = '''### Mecânica vinculada ao turno\n\nQuando um turno tiver consequência mecânica persistente, `cronica preparar` pode receber `--mecanica-json` com as regras e obrigações. A resposta devolve os IDs canônicos e congela tudo no mesmo ticket. Depois da rolagem com `dados`, `cronica concluir` recebe um bloco `mecanica.resolucoes`; o writer só vê a transação depois da validação causal.\n\nTurnos puramente narrativos omitem esse argumento e não pagam leituras mecânicas adicionais. Gastos de Ki/Focus nunca devem ser enviados como delta isolado sem obrigação preparada.\n\n'''
if "### Mecânica vinculada ao turno" not in text:
    if marker not in text:
        raise SystemExit("README marker missing")
    readme.write_text(text.replace(marker, section + marker, 1), encoding="utf-8")
