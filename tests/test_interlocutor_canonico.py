"""Identidade por fonte, recuperação fria e ambiguidade sem fabricar presença."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
sys.path[:0] = [str(TOOLS), str(ROOT / "tests")]
import contexto
import cronica
import memoria_cena as memory
import iniciativa_elenco as initiative
import test_memoria_duravel_integracao as fixtures

SNAPSHOT = yaml.safe_load((ROOT / "tests/fixtures/interlocutor-canonico-s024.yaml").read_text())


class CanonicalInterlocutorTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.entry = deepcopy(SNAPSHOT["entrada_indice"])
        index = yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text())
        index["npcs"]["mori"] = self.entry
        index["quantidade"] = len(index["npcs"])
        self.f.write("estado/npcs/index.yaml", index)
        self.f.write(self.entry["arquivo"], SNAPSHOT["fragmento"])
        self.f.write("narrador/segredo-fixture.yaml", {"identidade_real": "SEGREDO_NAO_AUTORIZADO"})

    def cold(self, script):
        return subprocess.run([sys.executable, "-c",
            "import sys; sys.path.insert(0,sys.argv.pop(1)); " + script,
            str(TOOLS), str(self.repo)], capture_output=True, text=True, check=True)

    def test_aliases_recuperam_mesmo_ator_em_processo_frio_sem_abrir_segredos(self):
        before = self.f.hashes()
        for alias in ["mori", "Mori", "senhor Mori", "homem do casaco cinza"]:
            completed = self.cold("import contexto,json; from pathlib import Path; "
                f"print(json.dumps(contexto.command_npc(Path(sys.argv[1]), {alias!r}),ensure_ascii=False))")
            data = json.loads(completed.stdout)
            actor = data["resultado"]["medidores"]
            self.assertEqual(actor["id"], "mori")
            self.assertEqual(actor["dados"]["identidade"], SNAPSHOT["fragmento"]["npc"]["identidade"])
            self.assertIn(self.entry["arquivo"], data["fontes"])
            self.assertNotIn("SEGREDO_NAO_AUTORIZADO", completed.stdout)
            self.assertFalse(any(source.startswith("narrador/") for source in data["fontes"]))
            self.assertIsNone(data["resultado"]["relacao"])
            self.assertNotIn("dialogo_relacional", data["resultado"])
        self.assertEqual(before, self.f.hashes())

    def test_preparo_frio_recupera_interlocutor_presente_com_fonte_e_lacunas(self):
        state = yaml.safe_load((self.repo / "estado/estado-atual.yaml").read_text())
        state.setdefault("estado_narrativo", {})["elenco_cena"] = {"versao": 1, "cena_id": "confronto-fixture",
            "local": memory.location(state), "participantes": ["mori"]}
        self.f.write("estado/estado-atual.yaml", state)
        before = self.f.hashes()
        completed = self.cold("import cronica,json; from pathlib import Path; "
            "print(json.dumps(cronica.prepare(Path(sys.argv[1]),scene_id='retomada-fria',"
            "sidequest_signal=None,initiative_interlocutors=['mori']),ensure_ascii=False))")
        data = json.loads(completed.stdout)
        pack = data[memory.KEY]
        self.assertEqual(pack["modo"], "completa")
        actor = pack["itens"]["mori"]["medidores"]["dados"]
        self.assertEqual(actor["identidade"], SNAPSHOT["fragmento"]["npc"]["identidade"])
        self.assertIn(self.entry["arquivo"], pack["fontes"])
        row = data[initiative.PUBLIC_KEY]["itens"][0]
        self.assertEqual(row["npc_id"], "mori")
        self.assertEqual(row["presenca"], "elenco_cena")
        self.assertFalse(row["requer_decisao"])
        self.assertLessEqual(memory.size(data), 8192)
        self.assertEqual(before, self.f.hashes())

    def test_selecao_prospectiva_nao_cria_presenca_nem_capacidade(self):
        data = cronica.prepare(self.repo, scene_id="prospectivo", sidequest_signal=None,
            memory_participants=["Mori"], initiative_interlocutors=["mori"])
        actor = data[memory.KEY]["itens"]["mori"]["medidores"]["dados"]
        self.assertNotIn("medidores", actor)
        self.assertNotIn("capacidades", actor)
        row = data[initiative.PUBLIC_KEY]["itens"][0]
        self.assertNotEqual(row["presenca"], "elenco_cena")
        self.assertFalse(row["requer_decisao"])

    def test_alias_ambiguo_entre_indices_falha_antes_de_carregar_ou_mutar(self):
        index = yaml.safe_load((self.repo / "estado/relacoes/index.yaml").read_text())
        index["relacoes"]["silva_fixture"]["aliases"] = ["Mori"]
        self.f.write("estado/relacoes/index.yaml", index)
        before = self.f.hashes()
        with self.assertRaisesRegex(ValueError, "ambígua.*mori.*silva_fixture"):
            contexto.command_npc(self.repo, "Mori")
        failed = subprocess.run([sys.executable, str(TOOLS / "contexto.py"),
            "--repo", str(self.repo), "npc", "Mori"], capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("ambígua", failed.stdout + failed.stderr)
        with self.assertRaisesRegex(cronica.CronicaError, "ambígua"):
            cronica.prepare(self.repo, scene_id="ambiguidade", sidequest_signal=None,
                            memory_participants=["Mori"])
        result = contexto.command_npc(self.repo, "mori")["resultado"]
        self.assertEqual(result["medidores"]["id"], "mori")
        self.assertIsNone(result["relacao"])
        self.assertEqual(before, self.f.hashes())

    def test_grafia_aproximada_nao_resolve_e_alias_da_relacao_nao_funde_outro_ator(self):
        self.assertFalse(contexto.command_npc(self.repo, "Mor")["resultado"]["encontrado"])
        index = yaml.safe_load((self.repo / "estado/relacoes/index.yaml").read_text())
        index["relacoes"]["silva_fixture"]["aliases"] = ["testemunha"]
        self.f.write("estado/relacoes/index.yaml", index)
        result = contexto.command_npc(self.repo, "testemunha")["resultado"]
        self.assertEqual(result["medidores"]["id"], "silva_fixture")
        self.assertEqual(result["relacao"]["id"], "silva_fixture")

    def test_vinculo_instalado_e_evidencia_literal_permanecem_coerentes(self):
        # Integração canônica: invariantes do vínculo, sem congelar status ou medidores.
        index = yaml.safe_load((ROOT / "estado/npcs/index.yaml").read_text())
        actor = contexto.command_npc(ROOT, "mori")["resultado"]["medidores"]
        self.assertEqual(actor["id"], "mori")
        source = actor["dados"]["identidade"]["fonte"]
        self.assertIn(source["trecho"], (ROOT / source["arquivo"]).read_text())
        self.assertTrue((ROOT / index["npcs"]["mori"]["historico"]).is_file())

    def test_textura_por_aproximacao_ou_de_outro_ator_nao_contamina_consulta(self):
        self.f.write("cenario/texturas/npcs/outro.yaml", {"nome": "Mori distante", "paleta": "OUTRO_ATOR"})
        self.f.write("cenario/texturas/index.yaml", {"npcs": {"mori_distante": {
            "nome": "Mori distante", "arquivo": "cenario/texturas/npcs/outro.yaml"}}})
        self.assertFalse(contexto.command_npc(self.repo, "Mor")["resultado"]["encontrado"])
        data = contexto.command_npc(self.repo, "mori")
        self.assertNotIn("OUTRO_ATOR", json.dumps(data))
        self.f.write("cenario/texturas/index.yaml", {"npcs": {"outro": {
            "nome": "Outro", "aliases": ["Mori"], "arquivo": "cenario/texturas/npcs/outro.yaml"}}})
        with self.assertRaisesRegex(ValueError, "outro NPC"):
            contexto.command_npc(self.repo, "Mori")


if __name__ == "__main__":
    unittest.main()
