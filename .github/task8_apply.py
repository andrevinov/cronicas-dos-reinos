from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write_text(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_yaml(rel: str):
    return yaml.safe_load(read_text(rel))


def write_yaml(rel: str, value) -> None:
    write_text(rel, yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110))


def replace_required(rel: str, old: str, new: str) -> None:
    text = read_text(rel)
    if old not in text:
        raise RuntimeError(f"marcador ausente em {rel}: {old!r}")
    write_text(rel, text.replace(old, new))


def replace_words(rel: str, *, lower: bool = True, upper: bool = True) -> None:
    text = read_text(rel)
    if lower:
        text = re.sub(r"(?<![A-Za-z0-9_])ki(?![A-Za-z0-9_])", "focus", text)
    if upper:
        text = re.sub(r"(?<![A-Za-z0-9_])Ki(?![A-Za-z0-9_])", "Focus", text)
    write_text(rel, text)


# ---------------------------------------------------------------------------
# 1. Contrato final de ruleset
# ---------------------------------------------------------------------------
campaign = read_yaml("campanha.yaml")
ruleset = campaign["sistema"]["ruleset"]
ruleset["atual"] = "dnd_5_5e"
ruleset["alvo"] = "dnd_5_5e"
ruleset["migracao"]["status"] = "concluida"
activation = ruleset["migracao"]["ativacao"]
activation["permitida"] = True
requirements = activation["requisitos"]
requirements["task_8_auditoria_final"] = True
requirements["integracao_completa"] = True
requirements["preflight_completo"] = True
campaign["sistema"]["edicao"].update(
    {
        "status": "definida",
        "valor": "5.5e",
        "base_mecanica": "D&D 5.5e",
        "observacao": "D&D 5.5e é o ruleset mecânico ativo. Material 2014 só entra como compatibilidade explicitamente aprovada.",
    }
)
refs = campaign["estrutura"]["arquivos_referenciados"]
refs.pop("adaptador_ficha_ren_5_5e", None)
refs.pop("personagem_resumo_poderes_5_5e", None)
refs["registro_migracao_ficha_ren_5_5e"] = refs.pop(
    "migracao_ficha_ren_5_5e", "personagens/jogador/migracao-5-5e.yaml"
)
refs["gate_consistencia_5_5e"] = "ferramentas/ruleset_5_5e.py"
campaign["fontes"]["status"] = "ruleset_5_5e_ativo"
campaign["fontes"]["observacao"] = (
    "D&D 5.5e é a autoridade mecânica ativa. D&D 5e 2014 permanece somente como fonte histórica/compatibilidade "
    "quando não houver equivalente aplicável e houver aprovação explícita. Materiais de AD&D são adaptados para 5.5e."
)
campaign["fontes"]["regras_base"] = list(campaign["fontes"].get("regras_alvo") or [])
campaign["fontes"]["regras_compatibilidade_2014"] = [
    "Livro do Jogador, D&D 5e 2014 — somente compatibilidade explicitamente aprovada",
    "Manual dos Monstros, D&D 5e 2014 — somente compatibilidade explicitamente aprovada",
]
write_yaml("campanha.yaml", campaign)


# ---------------------------------------------------------------------------
# 2. Promoção da ficha canônica de Ren
# ---------------------------------------------------------------------------
sheet = read_yaml("personagens/jogador/ficha.yaml")
migration = read_yaml("personagens/jogador/migracao-5-5e.yaml")
old_ki = dict(sheet["recursos_de_classe"]["ki"])
sheet["personagem"]["sistema"] = "Dungeons & Dragons 5.5e"
sheet["personagem"]["fonte_mecanica_principal"] = "Player's Handbook 2024 / D&D 5.5e"
sheet["identidade"]["subclasse"] = "Guerreiro das Sombras"
sheet["criacao"]["observacao"] = (
    "A criação original permanece canonizada pela DEC-0008: Humano Variante, Móvel, Actor e Observant não foram "
    "recomprados nem reconstruídos na ativação 5.5e. Elementos de Kozakura e Kara-Tur seguem como cenário/cultura."
)
for attack in sheet["combate"]["ataques"]:
    name = str(attack.get("nome", "")).casefold()
    if name == "golpe desarmado":
        attack["dano"] = "1d8 + 4 contundente"
        attack["observacao"] = "Golpe Desarmado do Monge; Empowered Strikes também permite dano de Força."
    elif name == "wakizashi":
        attack["dano"] = "1d8 + 4 perfurante"
        attack["observacao"] = "Mecanicamente espada curta e arma de Monge; o nome cultural é descritivo."

class_resources = sheet["recursos_de_classe"]
class_resources.pop("ki", None)
class_resources.pop("golpes_potencializados_por_ki", None)
class_resources.pop("aparar_projeteis", None)
class_resources.pop("quietude_da_mente", None)
class_resources["artes_marciais"] = {
    "dado": "1d8",
    "resumo": (
        "Pode usar Destreza para ataques/dano com Golpes Desarmados e armas de Monge; o Golpe Desarmado de ação "
        "bônus não exige usar a ação Atacar antes. Destreza também pode substituir Força para Agarrar/Empurrar."
    ),
}
class_resources["focus"] = {
    "pontos_maximos": int(migration["focus"]["pontos_maximos"]),
    "pontos_atuais": int(old_ki["pontos_atuais"]),
    "cd": int(migration["focus"]["cd"]),
    "recarga": migration["focus"]["recarga"],
    "calculo_cd": "8 + bônus de proficiência + modificador de Sabedoria",
    "usos": {
        "rajada_de_golpes": {
            "custo": 1,
            "resumo": "Como ação bônus, faz dois Golpes Desarmados; não exige usar a ação Atacar antes.",
        },
        "defesa_paciente": {
            "gratuito": "Desengajar como ação bônus",
            "custo_focus": 1,
            "resumo": "Com 1 Focus, Desengajar e Esquivar como a mesma ação bônus.",
        },
        "passo_do_vento": {
            "gratuito": "Disparada como ação bônus",
            "custo_focus": 1,
            "resumo": "Com 1 Focus, Desengajar e Disparada na mesma ação bônus e dobrar a distância de salto no turno.",
        },
        "ataque_atordoante": {
            "custo": 1,
            "limite": "uma vez por turno",
            "resumo": (
                "Depois de acertar com arma de Monge ou Golpe Desarmado, Constituição CD 14; na falha fica Atordoado "
                "até o início do próximo turno de Ren; no sucesso tem deslocamento pela metade e o próximo ataque "
                "contra ele antes disso tem vantagem."
            ),
        },
    },
}
class_resources["metabolismo_sobrenatural"] = {
    "nivel": 2,
    "gatilho": "ao rolar iniciativa",
    "recupera_focus": "todos os Focus gastos",
    "cura": "7 + 1d8 PV no nível 7",
    "recarga": "1 uso por descanso longo",
}
class_resources["desviar_ataques"] = {
    "nivel": 3,
    "reacao": True,
    "reducao": "1d10 + 11",
    "tipos": ["contundente", "perfurante", "cortante"],
    "redirecionar": {
        "condicao": "se a redução levar o dano a zero",
        "custo_focus": 1,
        "alcance_corpo_a_corpo": "5 pés",
        "alcance_distancia": "60 pés",
        "salvaguarda": "Destreza CD 14",
        "dano_falha": "2d8 + 4 do mesmo tipo do ataque original",
    },
}
class_resources["queda_lenta"] = {
    "nivel": 4,
    "reacao": True,
    "reducao": 35,
    "resumo": "Ao cair, usa a reação para reduzir o dano de queda em 35.",
}
class_resources["golpes_potencializados"] = {
    "nivel": 6,
    "resumo": "Golpes Desarmados podem causar dano de Força ou o tipo normal.",
}
class_resources["evasao"] = {
    "nivel": 7,
    "resumo": (
        "Em efeito com salvaguarda de Destreza que normalmente causa metade no sucesso, sofre zero no sucesso e "
        "metade na falha; não funciona enquanto Incapacitado."
    ),
}
class_resources["artes_sombrias"] = {
    "subclasse": "Guerreiro das Sombras",
    "nivel": 3,
    "visao_no_escuro": "60 pés",
    "ilusao_menor": {"conhece": True, "habilidade_conjuracao": "Sabedoria"},
    "escuridao": {
        "custo_focus": 1,
        "acao": "Magia",
        "componentes": "nenhum",
        "concentracao": True,
        "ve_dentro_da_propria_escuridao": True,
        "mover_area_no_inicio_do_turno": "até 60 pés",
    },
    "removidas_na_5_5e": ["Passos sem Pegadas", "Silêncio", "Visão no Escuro como magia paga com recurso"],
}
class_resources["passo_sombrio"] = {
    "subclasse": "Guerreiro das Sombras",
    "nivel": 6,
    "custo_focus": 0,
    "acao": "ação bônus",
    "alcance": "60 pés",
    "origem_e_destino": "luz baixa ou escuridão; destino desocupado e visível",
    "resumo": "Teleporta-se e recebe vantagem no próximo ataque corpo a corpo antes do fim do turno.",
}
write_yaml("personagens/jogador/ficha.yaml", sheet)

migration["status"] = "ativada"
migration["ativacao"]["concluida"] = True
migration["ativacao"]["ativada_em_task"] = "task_8_auditoria_final"
migration["ativacao"]["ruleset_ativo"] = "dnd_5_5e"
migration["ativacao"]["observacao"] = (
    "Registro histórico da migração. A ficha canônica ativa já contém o perfil 5.5e; este arquivo não é fonte operacional."
)
write_yaml("personagens/jogador/migracao-5-5e.yaml", migration)

# Promove a documentação staged e aposenta os dois shims temporários da Task 5.
target_summary = read_text("personagens/jogador/resumo-de-poderes-5-5e.md")
lines = target_summary.splitlines()
body = []
for line in lines:
    if line.startswith("> **STAGED / NÃO OPERACIONAL:**"):
        continue
    body.append(line)
active_summary = "\n".join(body)
active_summary = active_summary.replace("# Resumo de poderes de Ren — alvo D&D 5.5e", "# Resumo de poderes de Ren — D&D 5.5e")
active_summary = active_summary.replace(
    "PV atuais são preservados do estado efetivo no momento da ativação;",
    "PV atuais seguem o estado canônico efetivo;",
)
active_summary = active_summary.replace(
    "Focus atual será o valor efetivo de Ki convertido 1:1 no momento da ativação;",
    "Focus atual segue o estado canônico; a ativação preservou o antigo Ki 1:1 sem restaurar pontos gastos;",
)
write_text("personagens/jogador/resumo-de-poderes.md", active_summary.strip() + "\n")
for obsolete in (
    "personagens/jogador/resumo-de-poderes-5-5e.md",
    "ferramentas/ficha_ren_5_5e.py",
):
    path = ROOT / obsolete
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# 3. Estado vivo: Ki 1/7 -> Focus 1/7, sem apagar efeito 2014 já em curso
# ---------------------------------------------------------------------------
state = read_yaml("estado/estado-atual.yaml")
state["personagem"]["subclasse"] = "Guerreiro das Sombras"
resources = state["recursos"]
ki_state = resources.pop("ki")
resources["focus"] = dict(ki_state)
resources["focus"]["recarga"] = "descanso curto ou longo"
availability = resources.get("disponibilidades")
if isinstance(availability, dict):
    availability.pop("silencio", None)
legacy_pwt = (state.get("efeitos_temporarios") or {}).get("passos_sem_pegadas")
if isinstance(legacy_pwt, dict):
    legacy_pwt["origem_ruleset"] = "dnd_5e_2014"
    legacy_pwt["preservado_por_migracao"] = True
    legacy_pwt["recastavel"] = False
    legacy_pwt["observacao_migracao"] = (
        "Efeito lançado legalmente antes do cutover; permanece somente até sua expiração original e não pode ser renovado pela ficha 5.5e."
    )
write_yaml("estado/estado-atual.yaml", state)


# ---------------------------------------------------------------------------
# 4. Catálogo operacional migra em bloco para 5.5e
# ---------------------------------------------------------------------------
catalog = read_yaml("regras/catalogo.yaml")
for rule in catalog["regras"]:
    rule["ruleset"] = "dnd_5_5e"
    if rule["id"] == "gasto_recurso_classe":
        rule["aliases"] = [alias for alias in rule["aliases"] if alias != "gastar ki"]
        rule["resumo_interno"] = (
            "Gastos de Focus exigem obrigação preparada, disponibilidade suficiente e delta compatível antes da persistência."
        )
write_yaml("regras/catalogo.yaml", catalog)

# O catálogo continua reconhecendo os dois rulesets como versões conhecidas para diagnosticar conflito/fallback.
replace_required(
    "ferramentas/catalogo_regras.py",
    "    known_rulesets = {current, target}\n",
    "    known_rulesets = {current, target, \"dnd_5e_2014\", \"dnd_5_5e\"}\n",
)


# ---------------------------------------------------------------------------
# 5. Superfície operacional: Focus substitui Ki estruturalmente
# ---------------------------------------------------------------------------
# ficha_ren.py
text = read_text("ferramentas/ficha_ren.py")
for old, new in (
    ("    ki = _mapping(\n", "    focus = _mapping(\n"),
    ("_required(class_resources, \"ki\", \"recursos_de_classe\")", "_required(class_resources, \"focus\", \"recursos_de_classe\")"),
    ("\"recursos_de_classe.ki\",", "\"recursos_de_classe.focus\","),
    ("    ki_max = _integer(ki, \"pontos_maximos\", \"recursos_de_classe.ki\")\n", "    focus_max = _integer(focus, \"pontos_maximos\", \"recursos_de_classe.focus\")\n"),
    ("    ki_current = _integer(ki, \"pontos_atuais\", \"recursos_de_classe.ki\")\n", "    focus_current = _integer(focus, \"pontos_atuais\", \"recursos_de_classe.focus\")\n"),
    ("    ki_dc = _integer(ki, \"cd\", \"recursos_de_classe.ki\")\n", "    focus_dc = _integer(focus, \"cd\", \"recursos_de_classe.focus\")\n"),
    ("    if ki_max < 0 or not 0 <= ki_current <= ki_max:\n        raise RenSheetError(\"recursos_de_classe.ki possui faixa inválida\")\n", "    if focus_max < 0 or not 0 <= focus_current <= focus_max:\n        raise RenSheetError(\"recursos_de_classe.focus possui faixa inválida\")\n"),
    ("        \"ki\": {\n            \"pontos_maximos\": ki_max,\n            \"pontos_atuais\": ki_current,\n            \"cd\": ki_dc,\n        },", "        \"focus\": {\n            \"pontos_maximos\": focus_max,\n            \"pontos_atuais\": focus_current,\n            \"cd\": focus_dc,\n        },"),
):
    if old not in text:
        raise RuntimeError(f"ficha_ren.py marcador ausente: {old!r}")
    text = text.replace(old, new)
write_text("ferramentas/ficha_ren.py", text)

# Código operacional em que Ki é apenas o nome do recurso ativo.
for rel in (
    "ferramentas/gerar-runtime.py",
    "ferramentas/_consolidar_core.py",
    "ferramentas/_transacoes_core.py",
    "ferramentas/rodape_turno.py",
    "ferramentas/turno.py",
    "ferramentas/auditoria-final.py",
    "ferramentas/verificar-integridade.py",
):
    text = read_text(rel)
    for old, new in (
        ("state_ki", "state_focus"),
        ("current_ki", "current_focus"),
        ("max_ki", "max_focus"),
        ("base_ki", "base_focus"),
        ("effective_ki", "effective_focus"),
        ("ki_text", "focus_text"),
    ):
        text = text.replace(old, new)
    text = re.sub(r"(?<![A-Za-z0-9_])ki(?![A-Za-z0-9_])", "focus", text)
    text = re.sub(r"(?<![A-Za-z0-9_])Ki(?![A-Za-z0-9_])", "Focus", text)
    write_text(rel, text)

# Contrato causal deixa de aceitar o alias estrutural antigo.
text = read_text("ferramentas/mecanica_cronica.py")
text = text.replace('PROTECTED_RESOURCES = {"ki", "focus"}', 'PROTECTED_RESOURCES = {"focus"}')
text = text.replace("gasto de Ki/Focus", "gasto de Focus")
write_text("ferramentas/mecanica_cronica.py", text)

# O compactador legado sabe converter o campo histórico ki para o campo operacional Focus.
text = read_text("ferramentas/migrar-estado-atual.py")
text = text.replace(
    '            "ki",\n            "classe_de_armadura",',
    '            "focus",\n            "classe_de_armadura",',
)
needle = '    # A lista antiga era um diário cumulativo. Só preservamos o final operacional.\n'
insert = (
    '    if "focus" not in current_resources and "ki" in recursos:\n'
    '        current_resources["focus"] = deepcopy(recursos.get("ki"))\n'
    '    # A lista antiga era um diário cumulativo. Só preservamos o final operacional.\n'
)
if needle not in text:
    raise RuntimeError("marcador de migrar-estado-atual ausente")
text = text.replace(needle, insert, 1)
write_text("ferramentas/migrar-estado-atual.py", text)

# A palavra ki continua diegética; apenas contagem mecânica agora é Focus.
text = read_text("ferramentas/diegetico.py")
old_rule = '''    Rule(\n        "ki_pontos",\n        re.compile(\n            r"\\bpontos?\\s+de\\s+ki\\b|\\bki\\s+points?\\b|\\bki\\s*[:=/]\\s*\\d+\\b"\n            r"|\\b\\d+\\s+(?:pontos?\\s+de\\s+)?ki\\b",\n            re.IGNORECASE,\n        ),\n        "contagem de pontos de Ki",\n    ),'''
new_rule = '''    Rule(\n        "focus_pontos",\n        re.compile(\n            r"\\bpontos?\\s+de\\s+focus\\b|\\bfocus\\s+points?\\b|\\bfocus\\s*[:=/]\\s*\\d+\\b"\n            r"|\\b\\d+\\s+(?:pontos?\\s+de\\s+)?focus\\b",\n            re.IGNORECASE,\n        ),\n        "contagem de pontos de Focus",\n    ),'''
if old_rule not in text:
    raise RuntimeError("regra diegética de Ki não encontrada")
write_text("ferramentas/diegetico.py", text.replace(old_rule, new_rule))

# Prosa operacional curta.
for rel in (
    "ferramentas/contexto.py",
    "ferramentas/politica_acesso.py",
    "ferramentas/progressao_juppongatana.py",
):
    replace_words(rel)


# ---------------------------------------------------------------------------
# 6. Documentação operacional pós-ativação
# ---------------------------------------------------------------------------
# Regra de gasto.
text = read_text("regras/resolucao-de-acoes.md")
text = text.replace(
    "Enquanto o ruleset ativo for D&D 5e 2014, o recurso de Ren é **ki**. Quando a migração 5.5e for ativada, o mesmo contrato passa a proteger **Focus**. O writer nunca pode aceitar um gasto que deixe o recurso abaixo de zero.",
    "O recurso de classe ativo de Ren é **Focus**. O writer nunca pode aceitar um gasto que deixe Focus abaixo de zero. `ki` permanece apenas em registros históricos anteriores ao cutover.",
)
write_text("regras/resolucao-de-acoes.md", text)

# Regras da casa: preserva política de fallback, muda autoridade atual.
text = read_text("regras/regras-da-casa.md")
text = text.replace(
    "A campanha usa **D&D 5e 2014** como ruleset mecânico ativo durante a migração e tem **D&D 5.5e** como ruleset alvo.",
    "A campanha usa **D&D 5.5e** como ruleset mecânico ativo. A migração 5e 2014 → 5.5e foi concluída na Task 8.",
)
text = text.replace(
    "O contrato executável fica em `campanha.yaml`, em `sistema.ruleset`. Enquanto `sistema.ruleset.migracao.status` não for `concluida` e o gate `task_8_auditoria_final` não permitir a ativação, regras 5.5e podem ser consultadas para preparar a migração, mas **não substituem silenciosamente a mecânica ativa de 2014 em sessão**.",
    "O contrato executável fica em `campanha.yaml`, em `sistema.ruleset`. `dnd_5_5e` é a autoridade operacional; material 2014 só pode entrar como compatibilidade explicitamente aprovada.",
)
text = text.replace(
    "Material de AD&D e outras edições pode ser usado como cenário, aventura, NPC, local, item ou inspiração, mas suas mecânicas devem ser adaptadas para o **ruleset atual**. Antes da ativação final isso significa 5e 2014; depois da ativação, significa 5.5e.",
    "Material de AD&D e outras edições pode ser usado como cenário, aventura, NPC, local, item ou inspiração, mas suas mecânicas devem ser adaptadas para o **ruleset atual: D&D 5.5e**.",
)
text = text.replace(
    "Durante a migração, D&D 5.5e é fonte de preparação, comparação e conversão, não autoridade mecânica da sessão.",
    "D&D 5.5e é a autoridade mecânica da sessão. D&D 5e 2014 só participa por fallback explicitamente registrado.",
)
text = text.replace(
    "Até a ativação final da 5.5e, o rolador e a ficha continuam resolvendo a mecânica do ruleset 5e 2014.",
    "O rolador, a ficha, o runtime e a persistência resolvem a mecânica operacional em D&D 5.5e.",
)
text = text.replace(
    "A troca do alvo de adaptação para 5.5e ocorrerá automaticamente quando `sistema.ruleset.atual` for ativado como `dnd_5_5e`; não é necessário alterar o cânone de cenário para isso.",
    "O alvo de novas adaptações mecânicas é 5.5e. O cânone de cenário não muda por causa da edição mecânica.",
)
write_text("regras/regras-da-casa.md", text)

# Fontes: reescreve apenas o cabeçalho/contrato; mantém tabelas históricas como documentação de compatibilidade.
text = read_text("regras/fontes.md")
text = text.replace(
    "A campanha está em migração controlada de **D&D 5e 2014** para **D&D 5.5e**. Enquanto o gate final não for satisfeito, D&D 5e 2014 continua sendo o ruleset mecânico ativo; 5.5e é fonte de comparação, preparação e conversão, mas ainda não substitui a mecânica usada em sessão.",
    "A migração controlada de **D&D 5e 2014** para **D&D 5.5e** foi concluída. D&D 5.5e é o ruleset mecânico ativo; material 2014 permanece somente como histórico ou compatibilidade explicitamente aprovada.",
)
text = text.replace("- ruleset atual: `dnd_5e_2014`;", "- ruleset atual: `dnd_5_5e`;")
text = text.replace("- status: `em_andamento`;", "- status: `concluida`;")
text = text.replace(
    "- ativação 5.5e: proibida até `task_8_auditoria_final` concluir todos os requisitos e o preflight completo.",
    "- ativação 5.5e: concluída por `task_8_auditoria_final`, após integração e preflight completos.",
)
text = text.replace(
    "- antes da ativação, material 5.5e serve somente à migração;\n- depois da ativação, material 5e 2014 só pode permanecer como fallback quando não houver equivalente 5.5e aplicável e houver aprovação explícita;",
    "- D&D 5.5e é a fonte mecânica corrente;\n- material 5e 2014 só pode permanecer como fallback quando não houver equivalente 5.5e aplicável e houver aprovação explícita;",
)
text = text.replace(
    "O catálogo não pode promover uma regra de `dnd_5_5e` enquanto `campanha.yaml` mantiver `dnd_5e_2014` como ruleset atual.",
    "O catálogo operacional deve declarar `dnd_5_5e`; qualquer entrada 2014 precisa sair do catálogo ativo e passar pela política explícita de compatibilidade.",
)
text = text.replace("## Regras-base ativas — D&D 5e 2014", "## Regras de compatibilidade — D&D 5e 2014")
text = text.replace(
    "Estas fontes continuam sustentando a resolução mecânica **até a ativação final de 5.5e**.",
    "Estas fontes deixaram de ser a base ativa e só podem sustentar fallback explicitamente aprovado.",
)
text = text.replace(
    "Enquanto `sistema.ruleset.atual` for `dnd_5e_2014`, nenhuma regra 5.5e entra automaticamente em uma sessão só por ser mais recente.",
    "Nenhuma regra 2014 retorna automaticamente a uma sessão apenas por existir em material legado.",
)
text = text.replace("## Regras-base alvo — D&D 5.5e", "## Regras-base ativas — D&D 5.5e")
text = text.replace(
    "Estas fontes definem o ruleset para o qual a campanha está migrando. Durante as Tasks 1–7 elas podem orientar comparação e implementação; só se tornam autoridade mecânica corrente após o gate da Task 8.",
    "Estas fontes definem o ruleset mecânico ativo desde a conclusão da Task 8.",
)
write_text("regras/fontes.md", text)

# Documentos de agente e ferramentas: Focus atual, 5.5e ativo.
for rel in (
    "ferramentas/README.md",
    "docs/agente/narracao-e-mundo.md",
    "docs/agente/acesso-e-operacoes.md",
    "docs/agente/auditoria-final.md",
    "docs/agente/consolidacao-transacional.md",
    "docs/agente/memoria-de-sessoes.md",
    "docs/agente/personagem-e-tempo.md",
    "docs/agente/densidade-narrativa.md",
):
    replace_words(rel)

text = read_text("docs/agente/regras-e-rolagens.md")
text = text.replace("- `ruleset.atual = dnd_5e_2014`;", "- `ruleset.atual = dnd_5_5e`;")
text = text.replace("- `ruleset.alvo = dnd_5_5e`;", "- `ruleset.alvo = dnd_5_5e`;")
text = text.replace(
    "Durante a migração iniciada pela Task 1:",
    "Após a ativação concluída pela Task 8:",
)
text = text.replace(
    "- material 5.5e pode ser consultado para comparação, preparação e conversão;\n- material 5.5e **não pode substituir silenciosamente** uma regra 2014 durante narração ao vivo;\n- a ativação de 5.5e exige `migracao.status = concluida`, `migracao.ativacao.permitida = true` e todos os requisitos do gate satisfeitos;\n- o gate final é `task_8_auditoria_final`.",
    "- D&D 5.5e é a autoridade mecânica corrente;\n- material 2014 só entra por compatibilidade explicitamente aprovada;\n- `migracao.status = concluida` e `migracao.ativacao.permitida = true`;\n- o gate concluído foi `task_8_auditoria_final`.",
)
text = text.replace(
    "Durante a migração, fonte 5.5e não entra no passo 4 enquanto `ruleset.atual` continuar `dnd_5e_2014`; ela é fonte de trabalho para a migração.",
    "Fonte 5.5e ocupa o passo 4 como ruleset atual; fonte 2014 só entra no passo seguinte quando houver compatibilidade explicitamente aprovada.",
)
text = text.replace(
    "D&D 5.5e continua proibido como regra operacional enquanto `ruleset.atual` for `dnd_5e_2014`.",
    "D&D 5.5e é a regra operacional; fallback textual não pode inventar autoridade 2014.",
)
text = text.replace(
    "A Task 5 materializa a conversão de Ren sem furar o gate da Task 1. `personagens/jogador/migracao-5-5e.yaml` descreve a promoção prospectiva e `ferramentas/ficha_ren_5_5e.py` deriva uma visão mecânica completa a partir da ficha canônica **sem alterar a ficha ativa**. `personagens/jogador/resumo-de-poderes-5-5e.md` é documentação alvo e deve ser ignorado em narração ao vivo enquanto `ruleset.atual` continuar `dnd_5e_2014`.",
    "A Task 8 promoveu a conversão preparada na Task 5. `personagens/jogador/ficha.yaml` e `resumo-de-poderes.md` são agora as fontes operacionais 5.5e; `personagens/jogador/migracao-5-5e.yaml` permanece somente como registro auditável da promoção. Os shims staged da Task 5 foram removidos.",
)
text = text.replace(
    "O adaptador alvo deve sempre derivar PV atuais e a quantidade atual de Focus do estado efetivo: no gate final, Ki é mapeado 1:1 para Focus em vez de restaurar ou gastar recurso por efeito da migração.",
    "Na ativação, Ki foi mapeado 1:1 para Focus a partir do estado efetivo, sem restaurar nem gastar recurso. Daqui em diante a ficha e o estado usam somente Focus.",
)
text = re.sub(r"(?<![A-Za-z0-9_])Ki(?![A-Za-z0-9_])", "Focus", text)
write_text("docs/agente/regras-e-rolagens.md", text)

# A documentação diegética precisa preservar ki como conceito ficcional.
text = read_text("docs/agente/mecanica-diegetica.md")
text = text.replace("- pontos ou contagem numérica de Ki;", "- pontos ou contagem numérica de Focus;")
text = text.replace(
    "A palavra **ki** continua permitida como conceito diegético quando não é usada como contador mecânico. “Ren sente o ki se concentrar no baixo ventre” é válido; “Ren ainda tem 4 Ki” não é.",
    "A palavra **ki** continua permitida como conceito diegético. O contador mecânico atual é **Focus**: “Ren sente o ki se concentrar no baixo ventre” é válido; “Ren ainda tem 4 Focus” não é.",
)
write_text("docs/agente/mecanica-diegetica.md", text)

# README raiz e docs atuais de personagem.
text = read_text("README.md")
text = text.replace("A campanha usará **Dungeons & Dragons 5ª edição** como base mecânica.", "A campanha usa **Dungeons & Dragons 5.5e** como base mecânica.")
text = text.replace("suas mecânicas deverão ser adaptadas para 5e.", "suas mecânicas deverão ser adaptadas para 5.5e.")
write_text("README.md", text)

text = read_text("personagens/jogador/conceito.md")
text = re.sub(
    r"Em termos mecânicos, usa \*\*Dungeons & Dragons 5e\*\*, classe \*\*Monge\*\*, nível \d+, subclasse \*\*Caminho da Sombra\*\*\.",
    "Em termos mecânicos, usa **Dungeons & Dragons 5.5e**, classe **Monge**, nível 7, subclasse **Guerreiro das Sombras**.",
    text,
)
text = text.replace("tradição monástica: Caminho da Sombra", "tradição monástica: Guerreiro das Sombras")
write_text("personagens/jogador/conceito.md", text)
text = read_text("personagens/jogador/README.md").replace("Caminho da Sombra", "Guerreiro das Sombras")
write_text("personagens/jogador/README.md", text)
replace_words("regras/dificuldade.md")

# Nova decisão prospectiva; DEC-0008 permanece intacta como registro da preparação.
decisions = read_text("regras/decisoes.md").rstrip()
if "DEC-0009 — Ativação operacional do D&D 5.5e" not in decisions:
    decisions += """

## DEC-0009 — Ativação operacional do D&D 5.5e

- Contexto: as Tasks 1–7 prepararam contrato, catálogo, fonte única da ficha, núcleo mecânico, conversão de Ren, integração causal do `cronica` e gate AD&D sem alterar o ruleset vivo.
- Decisão: a Task 8 ativa prospectivamente `dnd_5_5e` como ruleset atual. A ficha canônica passa a usar Monge 7 / Guerreiro das Sombras e Focus; Ki 1/7 é convertido em Focus 1/7 sem restaurar recurso.
- Consequência atual preservada: **Passos sem Pegadas** já estava ativo às 23:12 de 19 Eleasis por uma conjuração válida de 2014. O efeito permanece até sua expiração original às 23:30, marcado como legado não recastável. A ficha 5.5e não permite nova conjuração de Passos sem Pegadas nem Silêncio.
- Compatibilidade: regras 2014 futuras só entram quando não houver equivalente 5.5e aplicável e houver aprovação explícita; material AD&D mecânico deve continuar atravessando o gate de proveniência.
- Retroatividade: nenhuma sessão, rolagem, gasto, descoberta ou consequência anterior é recalculada ou reescrita.
- Estado: permanente e prospectivo.
"""
write_text("regras/decisoes.md", decisions.strip() + "\n")


# ---------------------------------------------------------------------------
# 7. Gate permanente contra regressão híbrida
# ---------------------------------------------------------------------------
validator = r'''#!/usr/bin/env python3
"""Gate permanente de consistência do ruleset D&D 5.5e após a Task 8."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OBSOLETE_SHIMS = (
    "ferramentas/ficha_ren_5_5e.py",
    "personagens/jogador/resumo-de-poderes-5-5e.md",
)


def load(repo: Path, rel: str) -> Any:
    return yaml.safe_load((repo / rel).read_text(encoding="utf-8"))


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        campaign = load(repo, "campanha.yaml")
        sheet = load(repo, "personagens/jogador/ficha.yaml")
        state = load(repo, "estado/estado-atual.yaml")
        context = load(repo, "runtime/contexto.yaml")
        scene = load(repo, "runtime/cena.yaml")
        catalog = load(repo, "regras/catalogo.yaml")
        migration = load(repo, "personagens/jogador/migracao-5-5e.yaml")
    except Exception as exc:
        return [f"não foi possível carregar contrato 5.5e: {exc}"]

    ruleset = (((campaign or {}).get("sistema") or {}).get("ruleset") or {})
    activation = ((ruleset.get("migracao") or {}).get("ativacao") or {})
    requirements = activation.get("requisitos") or {}
    if ruleset.get("atual") != "dnd_5_5e" or ruleset.get("alvo") != "dnd_5_5e":
        errors.append("ruleset atual/alvo precisa ser dnd_5_5e")
    if (ruleset.get("migracao") or {}).get("status") != "concluida":
        errors.append("migração 5.5e precisa estar concluída")
    if activation.get("permitida") is not True:
        errors.append("ativação 5.5e precisa permanecer permitida")
    if not isinstance(requirements, dict) or not requirements or not all(value is True for value in requirements.values()):
        errors.append("todos os requisitos do gate de ativação precisam permanecer true")

    identity = (sheet or {}).get("identidade") or {}
    class_resources = (sheet or {}).get("recursos_de_classe") or {}
    if ((sheet or {}).get("personagem") or {}).get("sistema") != "Dungeons & Dragons 5.5e":
        errors.append("ficha ativa não declara Dungeons & Dragons 5.5e")
    if identity.get("subclasse") != "Guerreiro das Sombras":
        errors.append("ficha ativa não usa Guerreiro das Sombras")
    if "focus" not in class_resources or "ki" in class_resources:
        errors.append("ficha ativa precisa usar Focus e não pode manter Ki estrutural")
    old_features = {"aparar_projeteis", "quietude_da_mente", "golpes_potencializados_por_ki"}
    leftover = sorted(old_features & set(class_resources))
    if leftover:
        errors.append(f"ficha ativa ainda contém características 2014 substituídas: {leftover}")
    shadow = class_resources.get("artes_sombrias") or {}
    rendered_shadow = yaml.safe_dump(shadow, allow_unicode=True).casefold()
    if "passos sem pegadas" in rendered_shadow or "silêncio" in rendered_shadow or "silencio" in rendered_shadow:
        errors.append("Shadow Arts ativa ainda oferece magia removida da versão 2014")

    state_resources = (state or {}).get("recursos") or {}
    state_person = (state or {}).get("personagem") or {}
    if state_person.get("subclasse") != "Guerreiro das Sombras":
        errors.append("estado vivo não usa Guerreiro das Sombras")
    if "focus" not in state_resources or "ki" in state_resources:
        errors.append("estado vivo precisa usar Focus e não pode manter Ki estrutural")
    availability = state_resources.get("disponibilidades") or {}
    if "silencio" in availability or "silêncio" in availability:
        errors.append("estado vivo ainda oferece Silêncio como capacidade recastável")

    legacy = ((state or {}).get("efeitos_temporarios") or {}).get("passos_sem_pegadas")
    if legacy is not None:
        if not isinstance(legacy, dict):
            errors.append("efeito legado Passos sem Pegadas precisa ser mapa")
        else:
            if legacy.get("origem_ruleset") != "dnd_5e_2014":
                errors.append("Passos sem Pegadas preservado precisa declarar origem 2014")
            if legacy.get("preservado_por_migracao") is not True or legacy.get("recastavel") is not False:
                errors.append("Passos sem Pegadas legado precisa ser preservado e não recastável")

    focus_sheet = class_resources.get("focus") or {}
    focus_state = state_resources.get("focus") or {}
    if focus_sheet.get("pontos_atuais") != focus_state.get("atuais") or focus_sheet.get("pontos_maximos") != focus_state.get("maximos"):
        errors.append("Focus diverge entre ficha e estado")

    context_resources = (context or {}).get("recursos") or {}
    scene_mechanics = (scene or {}).get("mecanica_imediata") or {}
    if "focus" not in context_resources or "ki" in context_resources:
        errors.append("runtime/contexto precisa usar Focus sem Ki")
    expected_focus = {"atuais": focus_state.get("atuais"), "maximos": focus_state.get("maximos")}
    if context_resources.get("focus") != expected_focus:
        errors.append("Focus do runtime diverge do estado")
    expected_text = f"{focus_state.get('atuais')}/{focus_state.get('maximos')}"
    if scene_mechanics.get("focus") != expected_text or "ki" in scene_mechanics:
        errors.append("runtime/cena precisa expor Focus coerente sem Ki")

    rules = (catalog or {}).get("regras") or []
    bad_rules = [item.get("id") for item in rules if isinstance(item, dict) and item.get("ruleset") != "dnd_5_5e"]
    if bad_rules:
        errors.append(f"catálogo operacional contém regras fora de 5.5e: {bad_rules}")

    if (migration or {}).get("status") != "ativada" or ((migration or {}).get("ativacao") or {}).get("concluida") is not True:
        errors.append("registro de migração de Ren não está marcado como ativado")
    for rel in OBSOLETE_SHIMS:
        if (repo / rel).exists():
            errors.append(f"shim temporário da migração ainda existe: {rel}")
    summary = (repo / "personagens/jogador/resumo-de-poderes.md").read_text(encoding="utf-8")
    if "STAGED / NÃO OPERACIONAL" in summary or "Guerreiro das Sombras" not in summary:
        errors.append("resumo de poderes ativo não foi promovido corretamente")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["check"], default="check")
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.repo.resolve())
    if errors:
        print("FALHA — consistência D&D 5.5e")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK — ruleset D&D 5.5e ativo e sem estado híbrido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
write_text("ferramentas/ruleset_5_5e.py", validator)

# Integra gate permanente no preflight e na auditoria acumulada.
text = read_text("ferramentas/preflight.py")
marker = '            Check(\n                "gate AD&D para ruleset moderno",\n'
insert = '            Check(\n                "consistência ruleset D&D 5.5e",\n                (python, "ferramentas/ruleset_5_5e.py", "check"),\n                "integridade",\n            ),\n'
if insert not in text:
    if marker not in text:
        raise RuntimeError("marcador preflight ausente")
    text = text.replace(marker, insert + marker, 1)
write_text("ferramentas/preflight.py", text)

text = read_text("ferramentas/auditoria-final.py")
text = text.replace(
    '    "ferramentas/comparar-rollouts.py",\n',
    '    "ferramentas/comparar-rollouts.py",\n    "ferramentas/ruleset_5_5e.py",\n',
)
command_marker = '        [sys.executable, "ferramentas/gerar-runtime.py", "--check"],\n'
if '[sys.executable, "ferramentas/ruleset_5_5e.py", "check"]' not in text:
    text = text.replace(
        command_marker,
        command_marker + '        [sys.executable, "ferramentas/ruleset_5_5e.py", "check"],\n',
        1,
    )
write_text("ferramentas/auditoria-final.py", text)

# Integridade estrutural chama o mesmo gate permanente sem subprocesso.
text = read_text("ferramentas/verificar-integridade.py")
if "ruleset_5_5e" not in text.split("class DuplicateKeyLoader", 1)[0]:
    import_block = '''try:\n    import ruleset_5_5e\nexcept ModuleNotFoundError:\n    import importlib.util as _ruleset_importlib_util\n\n    _ruleset_path = Path(__file__).with_name("ruleset_5_5e.py")\n    _ruleset_spec = _ruleset_importlib_util.spec_from_file_location("ruleset_5_5e", _ruleset_path)\n    if _ruleset_spec is None or _ruleset_spec.loader is None:\n        raise\n    ruleset_5_5e = _ruleset_importlib_util.module_from_spec(_ruleset_spec)\n    _ruleset_spec.loader.exec_module(ruleset_5_5e)\n\n\n'''
    text = text.replace("\n\nclass DuplicateKeyLoader", "\n\n" + import_block + "class DuplicateKeyLoader", 1)
if "errors.extend(ruleset_5_5e.validate(repo))" not in text:
    text = text.replace(
        "    errors.extend(gate_adnd.validate_repository(repo, yaml_docs))\n",
        "    errors.extend(gate_adnd.validate_repository(repo, yaml_docs))\n    errors.extend(ruleset_5_5e.validate(repo))\n",
        1,
    )
write_text("ferramentas/verificar-integridade.py", text)


# ---------------------------------------------------------------------------
# 8. Testes operacionais existentes migram para Focus/Guerreiro das Sombras
# ---------------------------------------------------------------------------
operational_tests = (
    "tests/test_checkpoint.py",
    "tests/test_correcao_canonica.py",
    "tests/test_transacoes.py",
    "tests/test_auditoria_final.py",
    "tests/test_consolidacao.py",
    "tests/test_compromissos.py",
    "tests/test_ficha_ren.py",
    "tests/test_politica_acesso.py",
    "tests/test_talentos_ren.py",
    "tests/test_turno_transacional.py",
    "tests/test_correcao_recuperacao.py",
    "tests/test_contexto.py",
    "tests/test_rodape_turno.py",
    "tests/test_contexto_transacional.py",
    "tests/test_densidade_narrativa.py",
    "tests/test_ciclo_sessoes.py",
    "tests/test_memoria_sessoes.py",
    "tests/test_checkpoints_mundo.py",
    "tests/test_unified_session_lifecycle.py",
)
for rel in operational_tests:
    text = read_text(rel)
    text = re.sub(r"(?<![A-Za-z0-9_])ki(?![A-Za-z0-9_])", "focus", text)
    text = re.sub(r"(?<![A-Za-z0-9_])Ki(?![A-Za-z0-9_])", "Focus", text)
    text = text.replace("Caminho da Sombra", "Guerreiro das Sombras")
    write_text(rel, text)

# Diegético: conceito de ki continua permitido; contagem de Focus é que falha.
text = read_text("tests/test_diegetico.py")
text = text.replace('"ki": "Ren ainda possui 4 pontos de Ki."', '"focus": "Ren ainda possui 4 pontos de Focus."')
text = text.replace('self.assertIn("ki",', 'self.assertIn("focus",')
write_text("tests/test_diegetico.py", text)

# Catálogo real agora é 5.5; conflito passa a ser a reintrodução de 2014.
text = read_text("tests/test_rules_catalog.py")
text = text.replace(
    "def test_conflito_de_versao_nao_promove_5_5e_antes_do_gate(self) -> None:",
    "def test_conflito_de_versao_nao_reintroduz_2014_no_catalogo_ativo(self) -> None:",
)
text = text.replace('document["regras"][0]["ruleset"] = "dnd_5_5e"', 'document["regras"][0]["ruleset"] = "dnd_5e_2014"')
text = text.replace('self.assertEqual(result["ruleset"], "dnd_5e_2014")', 'self.assertEqual(result["ruleset"], "dnd_5_5e")')
write_text("tests/test_rules_catalog.py", text)

# Contrato Task1 vira contrato pós-cutover.
ruleset_test = r'''from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


class RulesetMigrationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        cls.ruleset = cls.campaign["sistema"]["ruleset"]
        cls.sources = (ROOT / "regras/fontes.md").read_text(encoding="utf-8")
        cls.house_rules = (ROOT / "regras/regras-da-casa.md").read_text(encoding="utf-8")
        cls.agent_rules = (ROOT / "docs/agente/regras-e-rolagens.md").read_text(encoding="utf-8")

    def test_schema_declara_5_5e_ativo_e_migracao_concluida(self) -> None:
        self.assertEqual(self.ruleset["atual"], "dnd_5_5e")
        self.assertEqual(self.ruleset["alvo"], "dnd_5_5e")
        migration = self.ruleset["migracao"]
        self.assertEqual(migration["status"], "concluida")
        activation = migration["ativacao"]
        self.assertEqual(activation["gate"], "task_8_auditoria_final")
        self.assertTrue(activation["permitida"])
        self.assertTrue(all(activation["requisitos"].values()))
        self.assertTrue(activation["requisitos"]["task_8_auditoria_final"])

    def test_hierarquia_mecanica_e_estavel(self) -> None:
        self.assertEqual(
            self.ruleset["hierarquia_mecanica"],
            ["decisoes_campanha", "regras_da_casa", "ruleset_atual", "compatibilidade_aprovada", "fontes_adaptadas"],
        )

    def test_2014_so_pode_voltar_com_compatibilidade_explicita(self) -> None:
        compatibility = self.ruleset["compatibilidade"]
        self.assertEqual(
            compatibility["fallback_5e_2014_apos_ativacao"],
            "somente_sem_equivalente_5_5e_e_com_aprovacao_explicita",
        )
        self.assertEqual(compatibility["material_adnd"], "adaptar_para_ruleset_atual")

    def test_sessoes_e_decisoes_antigas_continuam_preservadas(self) -> None:
        preservation = self.ruleset["preservacao_historica"]
        self.assertEqual(preservation["sessoes_concluidas"], "preservar")
        self.assertEqual(
            preservation["decisoes_existentes"],
            "preservar_ate_substituicao_explicita_prospectiva",
        )
        self.assertFalse(preservation["reescrita_retroativa"])
        self.assertIn("não reescreve sessões concluídas", self.sources)
        self.assertIn("não reescrever sessões concluídas", self.house_rules)
        self.assertIn("não reescrever sessões concluídas", self.agent_rules)


if __name__ == "__main__":
    unittest.main()
'''
write_text("tests/test_ruleset_migration_contract.py", ruleset_test)

# Teste da Task5 passa a provar promoção e aposentadoria dos shims.
migration_test = r'''from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren


class Ren55MigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheet_raw = yaml.safe_load((ROOT / "personagens/jogador/ficha.yaml").read_text(encoding="utf-8"))
        cls.migration = yaml.safe_load((ROOT / "personagens/jogador/migracao-5-5e.yaml").read_text(encoding="utf-8"))
        cls.mechanics = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")

    def test_task8_promove_5_5e_e_aposenta_shims(self) -> None:
        campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        ruleset = campaign["sistema"]["ruleset"]
        self.assertEqual(ruleset["atual"], "dnd_5_5e")
        self.assertTrue(ruleset["migracao"]["ativacao"]["permitida"])
        self.assertTrue(ruleset["migracao"]["ativacao"]["requisitos"]["task_8_auditoria_final"])
        self.assertEqual(self.migration["status"], "ativada")
        self.assertFalse((ROOT / "ferramentas/ficha_ren_5_5e.py").exists())
        self.assertFalse((ROOT / "personagens/jogador/resumo-de-poderes-5-5e.md").exists())

    def test_ficha_canonica_e_o_perfil_5_5e(self) -> None:
        self.assertEqual(self.sheet_raw["personagem"]["sistema"], "Dungeons & Dragons 5.5e")
        self.assertEqual(self.sheet_raw["identidade"]["subclasse"], "Guerreiro das Sombras")
        self.assertIn("focus", self.sheet_raw["recursos_de_classe"])
        self.assertNotIn("ki", self.sheet_raw["recursos_de_classe"])
        self.assertEqual(self.mechanics.resources["focus"], {"pontos_maximos": 7, "pontos_atuais": 1, "cd": 14})

    def test_numeros_centrais_e_ataques_convertidos(self) -> None:
        self.assertEqual(self.mechanics.armor_class, 17)
        self.assertEqual(self.mechanics.hit_points, {"atuais": 45, "maximos": 52})
        self.assertEqual(self.mechanics.speed, 55)
        self.assertEqual(self.mechanics.attacks["golpe_desarmado"].damage, "1d8+4")
        self.assertEqual(self.mechanics.attacks["wakizashi"].damage, "1d8+4")
        self.assertEqual(self.mechanics.attacks["shuriken"].damage, "1d4+4")

    def test_shadow_arts_5_5e_e_beneficios_canonizados(self) -> None:
        resources = self.sheet_raw["recursos_de_classe"]
        shadow = resources["artes_sombrias"]
        self.assertEqual(shadow["escuridao"]["custo_focus"], 1)
        self.assertTrue(shadow["escuridao"]["ve_dentro_da_propria_escuridao"])
        self.assertNotIn("magias_com_ki", shadow)
        self.assertIn("Passos sem Pegadas", shadow["removidas_na_5_5e"])
        self.assertIn("Silêncio", shadow["removidas_na_5_5e"])
        self.assertIn("Actor", self.sheet_raw["criacao"]["talentos_bonus_retroativos"])
        self.assertIn("Observant", self.sheet_raw["criacao"]["talentos_bonus_retroativos"])
        self.assertEqual(self.mechanics.passives, {"percepcao": 21, "investigacao": 20, "intuicao": 16})

    def test_decisoes_preservam_migracao_prospectiva(self) -> None:
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0008", text)
        self.assertIn("DEC-0009", text)
        self.assertIn("Ki 1/7 é convertido em Focus 1/7", text)
        self.assertIn("nenhuma sessão, rolagem, gasto, descoberta ou consequência anterior", text)


if __name__ == "__main__":
    unittest.main()
'''
write_text("tests/test_migracao_ren_5_5e.py", migration_test)

# Fixture sintética: encontro originário de AD&D já convertido, sem copiar statblock publicado.
fixture = {
    "id": "sentinela_portuaria_convertida_task8",
    "mecanica_ativa": True,
    "proveniencia_mecanica": {
        "edicao_origem": "adnd_2e",
        "adaptado_para": "dnd_5_5e",
        "fonte_mecanica": {
            "ruleset": "dnd_5_5e",
            "referencia": "equivalente sintético 5.5e usado somente no teste E2E da Task 8",
        },
        "decisao": "TASK8-E2E-ADND",
    },
    "mecanica": {
        "ataque": {"bonus": 4, "ca_alvo": 15, "dano": "1d6+2"},
        "observacao": "Valores sintéticos; nenhuma estatística publicada foi transportada literalmente.",
    },
}
write_yaml("tests/fixtures/adnd-encounter-5-5e.yaml", fixture)

activation_test = r'''from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren
import gate_adnd
import mecanica_dnd_5_5e as dnd
import ruleset_5_5e

_spec = importlib.util.spec_from_file_location("rolar_dados_publico_task8", TOOLS / "rolar-dados.py")
assert _spec is not None and _spec.loader is not None
rolar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rolar)


class FixedRng:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def randint(self, low: int, high: int) -> int:
        value = self.values[self.index]
        self.index += 1
        if not low <= value <= high:
            raise AssertionError(value)
        return value


class Ruleset55ActivationE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheet = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")
        cls.state = yaml.safe_load((ROOT / "estado/estado-atual.yaml").read_text(encoding="utf-8"))

    def test_gate_final_nao_encontra_estado_hibrido(self) -> None:
        self.assertEqual(ruleset_5_5e.validate(ROOT), [])

    def test_furtividade_e_actor_continuam_operacionais(self) -> None:
        stealth = dnd.perform_check(self.sheet.skills["furtividade"], 15, "normal", rng=FixedRng([10]))
        self.assertTrue(stealth.success)
        self.assertEqual(stealth.roll.total, 17)
        argv, note = rolar._apply_actor(["ren", "pericia", "enganacao", "--cd", "12", "--actor-outra-identidade"])
        self.assertIn("--vantagem", argv)
        self.assertIn("Actor", note)

    def test_combate_e_critico_usam_artes_marciais_d8(self) -> None:
        attack = self.sheet.attacks["golpe_desarmado"]
        self.assertEqual((attack.attack_bonus, attack.damage), (7, "1d8+4"))
        result = dnd.perform_attack(attack.attack_bonus, 17, "normal", rng=FixedRng([20]))
        self.assertTrue(result.critical)
        damage = dnd.roll_damage(attack.damage, critical=True, rng=FixedRng([4, 5]))
        self.assertEqual(damage.rolls, (4, 5))
        self.assertEqual(damage.total, 13)

    def test_focus_e_shadow_monk_estao_ativos_sem_recaste_2014(self) -> None:
        self.assertEqual(self.state["recursos"]["focus"]["atuais"], 1)
        self.assertNotIn("ki", self.state["recursos"])
        resources = yaml.safe_load((ROOT / "personagens/jogador/ficha.yaml").read_text(encoding="utf-8"))["recursos_de_classe"]
        self.assertEqual(resources["artes_sombrias"]["escuridao"]["custo_focus"], 1)
        self.assertNotIn("magias_com_ki", resources["artes_sombrias"])
        legacy = self.state["efeitos_temporarios"]["passos_sem_pegadas"]
        self.assertEqual(legacy["origem_ruleset"], "dnd_5e_2014")
        self.assertFalse(legacy["recastavel"])
        self.assertEqual(legacy["termino"], "23:30 de 19 Eleasis, 1372 DR")

    def test_encontro_adnd_convertido_atravessa_gate_e_nucleo_5_5e(self) -> None:
        fixture = yaml.safe_load((ROOT / "tests/fixtures/adnd-encounter-5-5e.yaml").read_text(encoding="utf-8"))
        validated = gate_adnd.validate_material(ROOT, fixture, for_runtime=True)
        self.assertEqual(validated["proveniencia_mecanica"]["adaptado_para"], "dnd_5_5e")
        attack = fixture["mecanica"]["ataque"]
        result = dnd.perform_attack(attack["bonus"], attack["ca_alvo"], "normal", rng=FixedRng([12]))
        self.assertTrue(result.hit)
        self.assertEqual(result.roll.total, 16)


if __name__ == "__main__":
    unittest.main()
'''
write_text("tests/test_ruleset_5_5e_activation.py", activation_test)

print("Task 8 functional cutover staged.")
