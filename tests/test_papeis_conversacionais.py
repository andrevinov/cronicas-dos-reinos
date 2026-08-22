from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto
import texturas

EXPECTED = {
    "iria_doss": "clinico_pratico",
    "nera_vell": "espelho_afetivo",
    "silva_elkwood": "guardia_pragmatica",
    "maerra_thandrel": "pastoral_moral",
    "luath": "operacional_civico",
    "halessa_vorn": "institucional_probatorio",
    "jack_mooney": "patrono_pragmatico",
    "kethra_dunn": "sobrevivencia_civil",
}


class ConversationalRoleRepositoryTest(unittest.TestCase):
    def test_oito_perfis_iniciais_sao_opt_in_e_apontam_npcs_canonicos(self):
        index = texturas.load_yaml(ROOT / texturas.INDEX_PATH)
        relations = yaml.safe_load(
            (ROOT / "estado/relacoes/index.yaml").read_text(encoding="utf-8")
        )["relacoes"]
        profiles = {
            npc_id: entry["papel_conversacional"]["papel"]
            for npc_id, entry in index["npcs"].items()
            if "papel_conversacional" in entry
        }
        self.assertEqual(profiles, EXPECTED)
        self.assertTrue(set(profiles).issubset(relations))
        self.assertEqual(texturas.validate(ROOT), [])

    def test_nera_recebe_papel_na_mesma_consulta_l2_sem_fragmento_extra(self):
        data = contexto.command_npc(ROOT, "Nera")
        self.assertEqual(data["nivel"], "L2")
        result = data["resultado"]
        self.assertTrue(result["encontrado"])
        texture = result["textura_narrativa"]
        self.assertEqual(texture["id"], "nera_vell")
        self.assertEqual(texture["papel_conversacional"]["papel"], "espelho_afetivo")
        self.assertIn(texturas.INDEX_PATH.as_posix(), data["fontes"])
        self.assertFalse(any(source.startswith("cenario/texturas/npcs/") for source in data["fontes"]))
        self.assertFalse(any(source.startswith("narrador/agentes/") for source in data["fontes"]))
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)
        delivered = yaml.safe_load(rendered)
        self.assertEqual(
            delivered["resultado"]["textura_narrativa"]["papel_conversacional"]["papel"],
            "espelho_afetivo",
        )

    def test_iria_combina_textura_existente_com_papel_conversacional(self):
        data = contexto.command_npc(ROOT, "Iria Doss")
        texture = data["resultado"]["textura_narrativa"]
        self.assertEqual(texture["papel_conversacional"]["papel"], "clinico_pratico")
        self.assertIn("paleta", texture)
        self.assertIn("cenario/texturas/npcs/iria_doss.yaml", data["fontes"])

    def test_npc_sem_opt_in_permanece_sem_papel(self):
        data = contexto.command_npc(ROOT, "Pell")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIsNone(data["resultado"].get("textura_narrativa"))

    def test_mesma_consulta_retorna_perfil_deterministico(self):
        first = contexto.command_npc(ROOT, "Silva")["resultado"]["textura_narrativa"]
        second = contexto.command_npc(ROOT, "Silva Elkwood")["resultado"]["textura_narrativa"]
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["papel_conversacional"], second["papel_conversacional"])

    def test_status_e_cena_nao_carregam_papeis_conversacionais(self):
        status = contexto.command_status(ROOT)
        scene = contexto.command_scene(ROOT)
        self.assertNotIn(texturas.INDEX_PATH.as_posix(), status["fontes"])
        self.assertNotIn(texturas.INDEX_PATH.as_posix(), scene["fontes"])
        self.assertNotIn("papel_conversacional", yaml.safe_dump(status, allow_unicode=True))
        self.assertNotIn("papel_conversacional", yaml.safe_dump(scene, allow_unicode=True))


class ConversationalRoleSchemaTest(unittest.TestCase):
    def valid_profile(self):
        return {
            "papel": "espelho_afetivo",
            "prioriza": ["autonomia"],
            "forma_de_responder": ["devolver uma pergunta concreta"],
            "evita": ["dar certeza que não possui"],
            "limite_de_autoridade": "usa somente o que sabe",
        }

    def test_schema_rejeita_papel_desconhecido(self):
        profile = self.valid_profile()
        profile["papel"] = "guru_que_sabe_tudo"
        with self.assertRaises(ValueError):
            texturas._conversation_profile(profile, "teste")

    def test_schema_rejeita_lista_grande_e_texto_grande(self):
        profile = self.valid_profile()
        profile["prioriza"] = ["a", "b", "c", "d"]
        with self.assertRaises(ValueError):
            texturas._conversation_profile(profile, "teste")

        profile = self.valid_profile()
        profile["limite_de_autoridade"] = "x" * (texturas.MAX_CONVERSATION_TEXT + 1)
        with self.assertRaises(ValueError):
            texturas._conversation_profile(profile, "teste")


class ConversationalRoleBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_perfil_sem_agente_scheduler_ou_fragmento(self):
        data = yaml.safe_load(
            (ROOT / "baseline/papeis-conversacionais-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["schema_orcamento_papeis_conversacionais"], 1)
        self.assertEqual(data["limites"]["perfis_iniciais"], 8)
        self.assertEqual(data["limites"]["max_itens_por_lista"], 3)
        self.assertEqual(data["limites"]["fragmentos_adicionais_para_perfil_inline"], 0)
        self.assertEqual(data["limites"]["leituras_extras_status_cena"], 0)
        inv = data["invariantes"]
        self.assertTrue(inv["perfil_e_opt_in"])
        self.assertTrue(inv["papel_nao_cria_conhecimento"])
        self.assertTrue(inv["papel_nao_abre_agente_estrategico"])
        self.assertTrue(inv["resposta_continua_emergente_nao_scriptada"])


if __name__ == "__main__":
    unittest.main()
