from __future__ import annotations

from pathlib import Path

# A ficha única continua sendo testada pelos valores operacionais após o cutover.
path = Path("tests/test_ficha_ren.py")
text = path.read_text(encoding="utf-8")
text = text.replace('(\"Golpe desarmado\", 7, \"1d6+4\", \"contundente\")', '(\"Golpe desarmado\", 7, \"1d8+4\", \"contundente\")')
text = text.replace('(\"Wakizashi\", 7, \"1d6+4\", \"perfurante\")', '(\"Wakizashi\", 7, \"1d8+4\", \"perfurante\")')
path.write_text(text, encoding="utf-8")

# Passos sem Pegadas não é mais recurso da ficha 5.5e; a consulta L2 ainda deve
# encontrar o efeito já lançado, marcado como legado 2014 e não recastável.
path = Path("tests/test_contexto.py")
text = path.read_text(encoding="utf-8")
old = '''    def test_recurso_passos_sem_pegadas_encontra_custo_sem_disponibilidade_explicita(self):
        data = mod.command_resource(REPO, "passos sem pegadas")
        self.assertTrue(data["resultado"]["encontrado"])
        mechanic = data["resultado"]["mecanica"]
        self.assertEqual(mechanic["dados"]["nome"], "passos sem pegadas")
        self.assertEqual(mechanic["dados"]["custo"], 2)
        self.assertIsNone(data["resultado"]["disponibilidade"])
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(
            data["fontes"][:2],
            ["personagens/jogador/ficha.yaml", "estado/estado-atual.yaml"],
        )
        self.assertTrue(
            set(data["fontes"]).issubset(
                {
                    "personagens/jogador/ficha.yaml",
                    "estado/estado-atual.yaml",
                    "runtime/eventos-pendentes.jsonl",
                }
            )
        )'''
new = '''    def test_recurso_passos_sem_pegadas_encontra_apenas_efeito_legado_nao_recastavel(self):
        data = mod.command_resource(REPO, "passos sem pegadas")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIsNone(data["resultado"]["mecanica"])
        self.assertIsNone(data["resultado"]["disponibilidade"])
        effects = data["resultado"]["efeitos_temporarios_relacionados"]
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0]["id"], "passos_sem_pegadas")
        legacy = effects[0]["dados"]
        self.assertEqual(legacy["origem_ruleset"], "dnd_5e_2014")
        self.assertTrue(legacy["preservado_por_migracao"])
        self.assertFalse(legacy["recastavel"])
        self.assertEqual(legacy["termino"], "23:30 de 19 Eleasis, 1372 DR")
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(
            data["fontes"][:2],
            ["personagens/jogador/ficha.yaml", "estado/estado-atual.yaml"],
        )
        self.assertTrue(
            set(data["fontes"]).issubset(
                {
                    "personagens/jogador/ficha.yaml",
                    "estado/estado-atual.yaml",
                    "runtime/eventos-pendentes.jsonl",
                }
            )
        )'''
if old not in text:
    raise SystemExit("contexto Passos sem Pegadas legacy-test marker not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

print("Task 8 post-cutover live assertions updated.")
