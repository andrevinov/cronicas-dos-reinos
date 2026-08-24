from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import oportunidades
import sidequests_canonicas as canonical


RECURRING = {
    "kethra_dunn",
    "bram_vask",
    "pell",
    "maerra_thandrel",
    "luath",
    "halessa_vorn",
    "silva_elkwood",
    "jack_mooney",
    "corven_dalm",
    "nera_vell",
    "brunna_torkel",
    "dessa_wren",
}
PROGRESSION_GATES = {"janela", "relacao", "conhecimento", "mundo", "identidade"}


class SecretNpcQuestCatalogRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.index = oportunidades.load_index(ROOT)
        self.router = self.index["sidequests_canonicas"]
        self.mapping, self.route_sources = canonical.catalog_refs(ROOT, self.index)

    def _gate_and_detail(self, npc_id, raw_ref):
        ref = {**raw_ref, "npc_id": npc_id}
        gate, gate_source = canonical._load_gate(ROOT, ref)
        detail, detail_source = canonical._load_detail(ROOT, gate)
        return ref, gate, detail, gate_source, detail_source

    def test_catalogo_tem_doze_quest_givers_e_trinta_e_seis_quests(self):
        self.assertEqual(set(self.mapping), RECURRING)
        self.assertTrue(all(len(refs) == 3 for refs in self.mapping.values()))
        self.assertEqual(sum(map(len, self.mapping.values())), 36)
        self.assertEqual(len(self.route_sources), 12)

        checked = canonical.check(ROOT)
        self.assertTrue(checked["ok"], checked["erros"])
        self.assertEqual(checked["quest_givers"], 12)
        self.assertEqual(checked["quests_roteadas"], 36)
        self.assertEqual(checked["detalhes_expostos"], 0)
        self.assertEqual(checked["roteadores_fragmentados"], 12)

    def test_cada_npc_tem_tres_tipos_e_catalogo_cobre_todo_lifecycle(self):
        global_types = set()
        for npc_id, refs in self.mapping.items():
            local_types = set()
            for raw_ref in refs:
                _, _, detail, _, _ = self._gate_and_detail(npc_id, raw_ref)
                local_types.add(detail["tipo"])
                global_types.add(detail["tipo"])
            with self.subTest(npc=npc_id):
                self.assertEqual(len(local_types), 3)
        self.assertEqual(global_types, oportunidades.VALID_TYPES)

    def test_indice_quente_e_roteadores_fragmentados_nao_expoem_spoilers(self):
        self.assertEqual(self.router["roteamento"], canonical.FRAGMENTED_ROUTING)
        self.assertNotIn("por_npc", self.router)
        router_text = yaml.safe_dump(self.router, allow_unicode=True, sort_keys=False)
        for forbidden in ("titulo:", "premissa:", "pedido:", "objetivo:", "consequencia_sem_ren:"):
            self.assertNotIn(forbidden, router_text)

        for npc_id, refs in self.mapping.items():
            route_path = ROOT / canonical._route_path(npc_id)
            route_doc = yaml.safe_load(route_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(route_doc),
                {"schema_roteador_sidequests_canonicas", "natureza", "npc_id", "refs"},
            )
            self.assertEqual(route_doc["npc_id"], npc_id)
            self.assertEqual(len(route_doc["refs"]), 3)
            for raw in route_doc["refs"]:
                self.assertEqual(set(raw), {"id", "gate", "prioridade"})
            route_text = route_path.read_text(encoding="utf-8")
            for forbidden in ("titulo:", "premissa:", "pedido:", "objetivo:"):
                self.assertNotIn(forbidden, route_text)

            for raw_ref in refs:
                self.assertEqual(set(raw_ref), {"id", "gate", "prioridade", "npc_id"})
                ref = {**raw_ref, "npc_id": npc_id}
                gate, _ = canonical._load_gate(ROOT, ref)
                self.assertEqual(
                    set(gate),
                    {
                        "schema_gate_sidequest_canonica",
                        "natureza",
                        "id",
                        "npc_id",
                        "detalhe",
                        "condicoes",
                    },
                )
                gate_text = yaml.safe_dump(gate, allow_unicode=True, sort_keys=False)
                for forbidden in ("titulo:", "premissa:", "pedido:", "objetivo:", "efeitos:"):
                    self.assertNotIn(forbidden, gate_text)

    def test_terceira_quest_tem_desbloqueio_real_sem_acoplar_ci_ao_tempo_vivo(self):
        """Task 33 nasceu com 2 hot por NPC, mas campanha futura deve poder liberar a 3ª.

        Em vez de reler tempo/relação vivos para sempre, congela a propriedade de
        design que importa: a referência de menor prioridade possui ao menos um
        gate real de progressão. Assim avanço legítimo da campanha não quebra CI.
        """
        for npc_id, refs in self.mapping.items():
            cold_ref = refs[-1]
            ref = {**cold_ref, "npc_id": npc_id}
            gate, _ = canonical._load_gate(ROOT, ref)
            conditions = gate.get("condicoes") or {}
            unlocks = set(conditions) & PROGRESSION_GATES
            with self.subTest(npc=npc_id, unlocks=sorted(unlocks)):
                self.assertTrue(unlocks)

    def test_hot_e_derivado_sem_booleano_artificial(self):
        for npc_id, refs in self.mapping.items():
            for raw_ref in refs:
                self.assertNotIn("hot", raw_ref)
                ref = {**raw_ref, "npc_id": npc_id}
                gate, _ = canonical._load_gate(ROOT, ref)
                self.assertNotIn("hot", gate)
                self.assertNotIn("ativo", gate)

    def test_todas_as_quests_permitam_recusa_e_fiquem_reservadas(self):
        for npc_id, refs in self.mapping.items():
            for raw_ref in refs:
                _, gate, detail, gate_source, detail_source = self._gate_and_detail(npc_id, raw_ref)
                self.assertTrue(detail["oferta"]["recusa_permitida"])
                self.assertEqual(gate["natureza"], "reservado")
                self.assertEqual(detail["natureza"], "reservado")
                self.assertTrue(gate_source.startswith("narrador/sidequests-canonicas/gates/"))
                self.assertTrue(detail_source.startswith("narrador/sidequests-canonicas/segredos/"))

    def test_task31_permanece_morta_e_nao_serve_de_catalogo(self):
        profiles = self.index["perfis"]
        self.assertEqual(set(profiles), RECURRING)
        self.assertTrue(all(meta["estado"] == "inativo" for meta in profiles.values()))
        self.assertFalse(self.index["regras"]["gate_procedural_operacional"])
        self.assertEqual(self.index["gate"]["estatuto"], "legado_congelado_nao_operacional")

    def test_npc_fora_do_catalogo_nao_abre_roteador_task33(self):
        refs, sources = canonical.route_for_npc_with_sources(ROOT, self.index, "sorn_kel")
        self.assertEqual(refs, [])
        self.assertEqual(sources, [])


class SecretNpcQuestCatalogBudgetTest(unittest.TestCase):
    def test_contrato_congela_catalogo_sem_nova_infra(self):
        data = yaml.safe_load(
            (ROOT / "baseline/secret-npc-quest-catalog-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = data["limites"]
        self.assertEqual(limits["quest_givers_recorrentes"], 12)
        self.assertEqual(limits["quests_por_quest_giver"], 3)
        self.assertEqual(limits["quests_totais"], 36)
        self.assertEqual(limits["max_hot_por_quest_giver"], 2)
        self.assertEqual(limits["tipos_distintos_por_npc_min"], 3)
        self.assertEqual(limits["tipos_distintos_globais_min"], 12)
        self.assertEqual(limits["refs_opacas_por_npc"], 3)
        self.assertEqual(limits["detalhes_publicos_no_roteador"], 0)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["estados_persistentes_novos"], 0)
        self.assertTrue(all(data["invariantes"].values()))

    def test_documentacao_publica_nao_lista_ids_ou_titulos_secretos(self):
        doc = (ROOT / "docs/task33-secret-npc-quest-catalog.md").read_text(encoding="utf-8")
        self.assertNotIn("qsc-7e", doc)
        self.assertNotIn("narrador/sidequests-canonicas/segredos/qsc-", doc)
        self.assertNotIn("### Kethra", doc)


if __name__ == "__main__":
    unittest.main()
