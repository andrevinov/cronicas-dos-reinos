from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:140]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"marker not unique in {path}: count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# campanha.yaml: fecha Task 7 e declara o contrato verificável sem ativar 5.5e.
campaign = ROOT / "campanha.yaml"
replace_once(
    campaign,
    "          task_7_gate_adnd: false\n",
    "          task_7_gate_adnd: true\n",
)
replace_once(
    campaign,
    '      material_adnd: "adaptar_para_ruleset_atual"\n',
    '''      material_adnd: "adaptar_para_ruleset_atual"\n      gate_adnd:\n        narrativa: livre\n        mecanica_literal_runtime: proibida\n        registro: regras/adaptacoes-mecanicas.yaml\n        alvo_preferencial_migracao: dnd_5_5e\n        fallback_2014: exige_declaracao_motivo_e_decisao\n''',
)
replace_once(
    campaign,
    '    contrato_mecanico_cronica: "ferramentas/mecanica_cronica.py"\n',
    '    contrato_mecanico_cronica: "ferramentas/mecanica_cronica.py"\n    gate_adnd: "regras/adaptacoes-mecanicas.yaml"\n    validador_gate_adnd: "ferramentas/gate_adnd.py"\n',
)

# mecanica_cronica.py: proveniência AD&D é opcional para mecânica nativa, mas
# obrigatoriamente passa pelo gate quando declarada. O caminho spec=None não muda.
mechanics = ROOT / "ferramentas/mecanica_cronica.py"
replace_once(
    mechanics,
    "import catalogo_regras\nimport mecanica_dnd_5_5e as dnd\n",
    "import catalogo_regras\nimport gate_adnd\nimport mecanica_dnd_5_5e as dnd\n",
)
replace_once(
    mechanics,
    '    extra = set(raw) - {"regras", "obrigacoes"}\n',
    '    extra = set(raw) - {"regras", "obrigacoes", "proveniencia"}\n',
)
replace_once(
    mechanics,
    '''    if extra:\n        raise MechanicalContractError(f"campos mecânicos desconhecidos: {sorted(extra)}")\n\n    try:\n        document = catalogo_regras.load_catalog(repo)\n''',
    '''    if extra:\n        raise MechanicalContractError(f"campos mecânicos desconhecidos: {sorted(extra)}")\n\n    provenance = None\n    if raw.get("proveniencia") is not None:\n        try:\n            provenance = gate_adnd.validate_runtime_provenance(\n                repo, raw["proveniencia"], raw\n            )\n        except gate_adnd.ADNDGateError as exc:\n            raise MechanicalContractError(f"gate AD&D: {exc}") from exc\n\n    try:\n        document = catalogo_regras.load_catalog(repo)\n''',
)
replace_once(
    mechanics,
    '''    return {\n        "schema_mecanica_cronica": SCHEMA,\n        "ruleset": _campaign_ruleset(repo),\n        "regras": rules,\n        "obrigacoes": obligations,\n        "snapshot_recursos": snapshot_by_resource,\n    }\n\n\ndef public_summary(contract: dict[str, Any]) -> dict[str, Any]:\n    return {\n        "ruleset": contract["ruleset"],\n        "regras": list(contract["regras"]),\n        "obrigacoes": [\n            {\n                "id": item["id"],\n                "tipo": item["tipo"],\n                "regra": item["regra"],\n                **({"recurso": item["recurso"], "custo": item["custo"]} if item["tipo"] == "gasto_recurso" else {}),\n            }\n            for item in contract["obrigacoes"]\n        ],\n        "resolucao": "registrar uma resolução por obrigação em transacao.mecanica.resolucoes",\n    }\n''',
    '''    contract = {\n        "schema_mecanica_cronica": SCHEMA,\n        "ruleset": _campaign_ruleset(repo),\n        "regras": rules,\n        "obrigacoes": obligations,\n        "snapshot_recursos": snapshot_by_resource,\n    }\n    if provenance is not None:\n        contract["proveniencia"] = provenance\n    return contract\n\n\ndef public_summary(contract: dict[str, Any]) -> dict[str, Any]:\n    summary = {\n        "ruleset": contract["ruleset"],\n        "regras": list(contract["regras"]),\n        "obrigacoes": [\n            {\n                "id": item["id"],\n                "tipo": item["tipo"],\n                "regra": item["regra"],\n                **({"recurso": item["recurso"], "custo": item["custo"]} if item["tipo"] == "gasto_recurso" else {}),\n            }\n            for item in contract["obrigacoes"]\n        ],\n        "resolucao": "registrar uma resolução por obrigação em transacao.mecanica.resolucoes",\n    }\n    provenance = contract.get("proveniencia")\n    if isinstance(provenance, dict):\n        summary["proveniencia"] = {\n            "edicao_origem": provenance.get("edicao_origem"),\n            "adaptado_para": provenance.get("adaptado_para"),\n            "fonte_mecanica": provenance.get("fonte_mecanica"),\n            **({"decisao": provenance["decisao"]} if provenance.get("decisao") else {}),\n            **({"fallback_2014": provenance["fallback_2014"]} if provenance.get("fallback_2014") else {}),\n        }\n    return summary\n''',
)

# Integridade: o novo subgate lê o mesmo conjunto YAML já carregado; sem scan extra
# para o caso normal além da travessia em memória.
integrity = ROOT / "ferramentas/verificar-integridade.py"
replace_once(
    integrity,
    '''except ImportError as exc:\n    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc\n\n\nclass DuplicateKeyLoader''',
    '''except ImportError as exc:\n    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc\n\nimport gate_adnd\n\n\nclass DuplicateKeyLoader''',
)
replace_once(
    integrity,
    '    "regras/resolucao-de-acoes.md",\n',
    '    "regras/resolucao-de-acoes.md",\n    "regras/adaptacoes-mecanicas.yaml",\n',
)
replace_once(
    integrity,
    '    "ferramentas/texturas.py",\n',
    '    "ferramentas/texturas.py",\n    "ferramentas/gate_adnd.py",\n',
)
replace_once(
    integrity,
    '    errors.extend(validate_agent_router(repo, yaml_docs))\n\n    campanha = yaml_docs.get("campanha.yaml")\n',
    '    errors.extend(validate_agent_router(repo, yaml_docs))\n    errors.extend(gate_adnd.validate_repository(repo, yaml_docs))\n\n    campanha = yaml_docs.get("campanha.yaml")\n',
)

# Preflight: expõe o gate como etapa própria, embora a Integridade também o invoque.
preflight = ROOT / "ferramentas/preflight.py"
replace_once(
    preflight,
    '''            Check("runtime derivado", (python, "ferramentas/gerar-runtime.py", "--check"), "estrutura"),\n            Check(\n                "integridade estrutural e semântica",\n''',
    '''            Check("runtime derivado", (python, "ferramentas/gerar-runtime.py", "--check"), "estrutura"),\n            Check(\n                "gate AD&D para ruleset moderno",\n                (python, "ferramentas/gate_adnd.py", "check"),\n                "integridade",\n            ),\n            Check(\n                "integridade estrutural e semântica",\n''',
)

# Fontes: transforma a política conceitual em contrato concreto.
sources = ROOT / "regras/fontes.md"
replace_once(
    sources,
    '''- material de AD&D é sempre adaptado para o ruleset atual, nunca aplicado mecanicamente de forma literal.\n\n---\n\n## Catálogo estruturado de regras\n''',
    '''- material de AD&D é sempre adaptado para o ruleset atual, nunca aplicado mecanicamente de forma literal.\n\n### Gate formal AD&D → ruleset moderno\n\nA Task 7 torna essa última regra verificável. Conteúdo puramente narrativo de AD&D continua livre e não precisa carregar metadados mecânicos. Quando uma preparação de AD&D passa a conter **mecânica ativa ou preparada**, ela deve atravessar `ferramentas/gate_adnd.py` e declarar `proveniencia_mecanica` com:\n\n- `edicao_origem`: `adnd_1e` ou `adnd_2e`;\n- `adaptado_para`: o ruleset moderno da conversão;\n- `fonte_mecanica.ruleset` e `fonte_mecanica.referencia`: autoridade moderna usada para reconstruir os números;\n- `decisao`, quando uma decisão de campanha participar da conversão.\n\n`regras/adaptacoes-mecanicas.yaml` registra adaptações persistentes. THAC0, CA descendente, tabelas antigas de salvamento e campos equivalentes podem ser consultados como **entrada histórica de conversão**, mas não podem sobreviver no bloco mecânico preparado nem entrar no runtime.\n\nDurante a migração, `dnd_5_5e` é o destino preferencial para novas adaptações persistentes. Se uma adaptação precisar permanecer em `dnd_5e_2014`, ela deve declarar `fallback_2014.declarado=true`, motivo e decisão explícita. Isso impede que uma conversão provisória de 2014 sobreviva silenciosamente à ativação final.\n\nNo runtime vale ainda uma segunda barreira: `adaptado_para` precisa coincidir com `sistema.ruleset.atual`. Portanto uma adaptação AD&D→5.5e pode ser preparada e validada agora, mas não roda em sessão enquanto 2014 continuar ativo.\n\n---\n\n## Catálogo estruturado de regras\n''',
)

# Regras da casa: o procedimento operacional passa a apontar para o gate.
house = ROOT / "regras/regras-da-casa.md"
replace_once(
    house,
    '''## Adaptação de material antigo\n\nAo adaptar material de AD&D para o ruleset atual:\n''',
    '''## Adaptação de material antigo\n\nA Task 7 separa formalmente lore de mecânica. Lore e aventura de AD&D podem ser usados sem envelope especial. Uma adaptação que produza números, testes, statblock, recurso ou outra mecânica ativa precisa declarar `proveniencia_mecanica` e passar por `ferramentas/gate_adnd.py` antes de chegar ao runtime. Adaptações persistentes entram em `regras/adaptacoes-mecanicas.yaml`.\n\nTHAC0, CA descendente, categorias antigas de salvamento e outros campos mecânicos de AD&D nunca são persistidos como regra operacional; são somente insumo para construir uma equivalência moderna. Uma conversão para 2014 é fallback excepcional e exige declaração, motivo e decisão explícita.\n\nAo adaptar material de AD&D para o ruleset atual:\n''',
)

# Manual do agente: registra a barreira antes do catálogo/cronica.
agent = ROOT / "docs/agente/regras-e-rolagens.md"
replace_once(
    agent,
    '''Materiais de AD&D continuam seguindo a mesma regra conceitual: cenário e aventura podem ser preservados, mas qualquer mecânica que entre em jogo é adaptada para o `ruleset.atual`. Assim, o alvo da conversão muda de 2014 para 5.5e somente quando a ativação final ocorrer.\n\n## Catálogo executável de regras\n''',
    '''Materiais de AD&D continuam seguindo a mesma regra conceitual: cenário e aventura podem ser preservados, mas qualquer mecânica que entre em jogo é adaptada para o `ruleset.atual`. Assim, o alvo da conversão muda de 2014 para 5.5e somente quando a ativação final ocorrer.\n\n### Gate formal de material AD&D\n\nA Task 7 torna essa disciplina executável. Prosa narrativa de AD&D não paga gate nem precisa de versão mecânica. Qualquer material AD&D marcado como mecânico ativo/preparado deve declarar `proveniencia_mecanica.edicao_origem`, `adaptado_para` e `fonte_mecanica`; adaptações persistentes são registradas em `regras/adaptacoes-mecanicas.yaml`.\n\nO validador recusa transporte literal de THAC0, CA descendente, salvamentos antigos e campos equivalentes. Para material preparado, AD&D→5.5e é válido como alvo de migração. Para entrar no runtime, porém, `adaptado_para` precisa ser igual ao `ruleset.atual`. Enquanto 2014 estiver ativo, uso AD&D→2014 só passa com `fallback_2014` explicitamente declarado, com motivo e decisão; depois da Task 8 esse mesmo ticket/material deixa de ser elegível se o ruleset mudar.\n\n`cronica preparar --mecanica-json` aceita `proveniencia` somente quando houver esse vínculo com fonte antiga; o gate roda antes de o contrato ser anexado ao ticket. A ausência de `--mecanica-json` continua não abrindo nenhum material mecânico.\n\n## Catálogo executável de regras\n''',
)

# README operacional.
readme = ROOT / "ferramentas/README.md"
replace_once(
    readme,
    '''Turnos puramente narrativos omitem esse argumento e não pagam leituras mecânicas adicionais. Gastos de Ki/Focus nunca devem ser enviados como delta isolado sem obrigação preparada.\n\n### Rolagens em lote\n''',
    '''Turnos puramente narrativos omitem esse argumento e não pagam leituras mecânicas adicionais. Gastos de Ki/Focus nunca devem ser enviados como delta isolado sem obrigação preparada.\n\nQuando a mecânica foi preparada a partir de AD&D, o mesmo JSON acrescenta `proveniencia`. O gate exige edição de origem, destino moderno e fonte mecânica; números antigos literais são recusados antes do ticket. Uma adaptação 5.5e pode existir como preparação durante a migração, mas não entra no runtime enquanto 2014 estiver ativo.\n\nVerificação do registro de adaptações antigas:\n\n```bash\npython3 ferramentas/gate_adnd.py check\n```\n\nMaterial AD&D puramente narrativo não precisa ser registrado. Uso AD&D→2014 é fallback explícito e precisa carregar motivo + decisão.\n\n### Rolagens em lote\n''',
)

# Contrato de migração: Task 7 passa a ser requisito satisfeito e a política ganha
# metadados verificáveis sem alterar ruleset.atual.
ruleset_test = ROOT / "tests/test_ruleset_migration_contract.py"
replace_once(
    ruleset_test,
    '''        self.assertTrue(migration["ativacao"]["requisitos"]["task_1_contrato"])\n''',
    '''        self.assertTrue(migration["ativacao"]["requisitos"]["task_1_contrato"])\n        self.assertTrue(migration["ativacao"]["requisitos"]["task_7_gate_adnd"])\n''',
)
replace_once(
    ruleset_test,
    '''        self.assertEqual(\n            compatibility["material_adnd"],\n            "adaptar_para_ruleset_atual",\n        )\n\n    def test_sessoes_e_decisoes_antigas_sao_preservadas(self) -> None:\n''',
    '''        self.assertEqual(\n            compatibility["material_adnd"],\n            "adaptar_para_ruleset_atual",\n        )\n        gate = compatibility["gate_adnd"]\n        self.assertEqual(gate["narrativa"], "livre")\n        self.assertEqual(gate["mecanica_literal_runtime"], "proibida")\n        self.assertEqual(gate["alvo_preferencial_migracao"], "dnd_5_5e")\n        self.assertEqual(gate["fallback_2014"], "exige_declaracao_motivo_e_decisao")\n\n    def test_sessoes_e_decisoes_antigas_sao_preservadas(self) -> None:\n''',
)

# Teste de integração com cronica: prova que proveniência vira contrato somente
# quando o gate de runtime aprova.
gate_test = ROOT / "tests/test_gate_adnd.py"
replace_once(
    gate_test,
    "import gate_adnd\n",
    "import gate_adnd\nimport mecanica_cronica\n",
)
replace_once(
    gate_test,
    '''    def test_verificador_principal_chama_subgate_adnd(self) -> None:\n        source = (ROOT / "ferramentas/verificar-integridade.py").read_text(encoding="utf-8")\n        self.assertIn("gate_adnd.validate_repository", source)\n\n\nif __name__ == "__main__":\n''',
    '''    def test_cronica_congela_proveniencia_aprovada_e_recusa_destino_nao_ativo(self) -> None:\n        base = {\n            "regras": ["teste_d20_basico"],\n            "obrigacoes": [\n                {\n                    "id": "teste_adaptado",\n                    "tipo": "teste",\n                    "regra": "teste_d20_basico",\n                    "bonus": 3,\n                    "alvo": 14,\n                }\n            ],\n        }\n        approved = dict(base)\n        approved["proveniencia"] = provenance_2014(fallback=True)\n        contract = mecanica_cronica.normalize_spec(ROOT, approved)\n        self.assertEqual(contract["proveniencia"]["edicao_origem"], "adnd_2e")\n        self.assertTrue(contract["proveniencia"]["fallback_2014"]["declarado"])\n\n        future = dict(base)\n        future["proveniencia"] = provenance_55()\n        with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "gate AD&D"):\n            mecanica_cronica.normalize_spec(ROOT, future)\n\n    def test_verificador_principal_chama_subgate_adnd(self) -> None:\n        source = (ROOT / "ferramentas/verificar-integridade.py").read_text(encoding="utf-8")\n        self.assertIn("gate_adnd.validate_repository", source)\n\n\nif __name__ == "__main__":\n''',
)
