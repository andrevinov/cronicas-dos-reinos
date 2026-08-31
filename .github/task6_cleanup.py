from pathlib import Path

cronica = Path("ferramentas/cronica.py")
text = cronica.read_text(encoding="utf-8")
injected = '''    fields = contract.get("campos")
    if isinstance(fields, dict):
        fields["mecanica"] = {
            "resolucoes": (
                "somente quando a preparação devolver mecanica.obrigacoes; uma resolução "
                "estruturada por obrigação, antes dos deltas mecânicos"
            )
        }
    contract["causalidade_mecanica_task6"] = (
        "Deltas de Ki/Focus e efeitos declarados no ticket exigem resolução compatível; "
        "cronica valida pelo núcleo mecânico antes do writer."
    )
'''
text = text.replace(injected, "")
cronica.write_text(text, encoding="utf-8")

path = Path("tests/test_cronica_mecanica.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    'budget["orcamento"]["chamadas_operacionais_por_turno"]',
    'budget["fluxo_preferencial"]["chamadas_operacionais_por_turno"]',
)
text = text.replace(
    'budget["orcamento"]["novos_endpoints_deterministicos_max"]',
    'budget["limites"]["max_endpoints_novos"]',
)
path.write_text(text, encoding="utf-8")
