from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ciclo_npcs
import entradas
import mundo


class CicloNpcsRepositoryTest(unittest.TestCase):
    def test_registro_real_comeca_valido_e_sem_mortes_retroativas(self):
        result = ciclo_npcs.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        status = ciclo_npcs.status(ROOT)
        self.assertEqual(status["mortos"], [])


class CicloNpcsSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (
            "estado/npcs",
            "estado",
            "narrador/mundo",
            "narrador/agentes",
            "narrador/agentes-leves",
            "narrador/entradas",
            "runtime",
        ):
            (self.repo / rel).mkdir(parents=True, exist_ok=True)
        self._yaml("narrador/mundo/ciclo-npcs.yaml", {
            "schema_ciclo_npcs": 1,
            "natureza": "controle_reservado",
            "mortos": {},
        })
        self._yaml("estado/tempo.yaml", {
            "schema_tempo": 1,
            "natureza": "tempo_atual",
            "data_atual": "12 Eleasis, 1372 DR",
            "hora_aproximada": "08:00 de 12 Eleasis",
        })
        self._yaml("narrador/mundo/agenda.yaml", {
            "schema_agenda_mundo": 1,
            "natureza": "reservado",
            "hora_amanhecer": "06:00",
            "reavaliacoes": {
                "estrategico": {
                    "cadencia": "amanhecer",
                    "intervalo_dias": 1,
                    "inicio": "11 Eleasis, 1372 DR",
                    "motivo": "teste",
                }
            },
            "agendamentos": [{
                "id": "viagem-estrategico",
                "tipo": "movimento",
                "agente": "estrategico",
                "agentes_afetados": ["estrategico"],
                "em": {"data": "13 Eleasis, 1372 DR", "hora": "09:00"},
                "motivo": "viajar",
            }],
        })
        self._yaml("narrador/mundo/estado.yaml", {
            "schema_estado_mundo": 1,
            "natureza": "controle_reservado",
            "processado_ate": {"data": "12 Eleasis, 1372 DR", "hora": "07:00"},
            "pendencias": [
                {
                    "id": "p-estrategico",
                    "tipo": "reavaliar_agente",
                    "agente": "estrategico",
                    "agentes_afetados": ["estrategico"],
                    "disparado_em": {"data": "12 Eleasis, 1372 DR", "hora": "06:00"},
                    "motivo": "teste",
                    "origem": "teste",
                },
                {
                    "id": "p-vivo",
                    "tipo": "expiracao",
                    "agentes_afetados": ["estrategico", "outro"],
                    "disparado_em": {"data": "12 Eleasis, 1372 DR", "hora": "06:30"},
                    "motivo": "teste",
                    "origem": "teste",
                },
            ],
            "concluidas_recentes": [],
        })
        self._yaml("narrador/agentes/index.yaml", {
            "schema_agentes": 2,
            "natureza": "reservado",
            "agentes": {
                "estrategico": {
                    "nome": "Estratégico",
                    "tipo": "npc",
                    "estado": "ativo",
                    "presenca": "presente",
                    "atuacao_local": "exige_presenca_fisica",
                    "arquivo": "narrador/agentes/estrategico.yaml",
                }
            },
        })
        self._yaml("narrador/agentes/estrategico.yaml", {
            "schema_agente": 2,
            "natureza": "reservado",
            "id": "estrategico",
            "nome": "Estratégico",
            "tipo": "npc",
            "estado": "ativo",
        })
        self._yaml("narrador/agentes-leves/index.yaml", {
            "schema_agentes_leves": 1,
            "natureza": "reservado",
            "orcamento": {
                "max_novas_por_checkpoint": 1,
                "max_pendencias_abertas": 2,
                "ordenacao": "mais_atrasado_prioridade_id",
            },
            "agentes": {
                "leve": {
                    "nome": "Leve",
                    "perfil_operacional": "recorrente_leve",
                    "estado": "ativo",
                    "prioridade": 1,
                    "intervalo_dias": 3,
                    "inicio": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
                    "arquivo": "narrador/agentes-leves/leve.yaml",
                }
            },
        })
        self._yaml("narrador/agentes-leves/estado.yaml", {
            "schema_estado_agentes_leves": 1,
            "natureza": "controle_reservado",
            "agentes": {
                "leve": {
                    "estado": "ativo",
                    "proxima_avaliacao": {"data": "13 Eleasis, 1372 DR", "hora": "06:00"},
                }
            },
        })
        self._yaml("narrador/entradas/index.yaml", {
            "schema_entradas": 1,
            "natureza": "reservado",
            "cadencia_padrao_dias": 3,
            "candidatos": {
                "entrada_morta": {
                    "nome": "Entrada Morta",
                    "ordem": 1,
                    "nivel_minimo_normal": 1,
                    "arquivo": "narrador/entradas/entrada_morta.yaml",
                },
                "entrada_viva": {
                    "nome": "Entrada Viva",
                    "ordem": 2,
                    "nivel_minimo_normal": 1,
                    "arquivo": "narrador/entradas/entrada_viva.yaml",
                },
            },
        })
        self._yaml("narrador/entradas/estado.yaml", {
            "schema_estado_entradas": 1,
            "natureza": "controle_reservado",
            "candidatos": {
                "entrada_morta": {
                    "estado": "latente",
                    "antecipado": False,
                    "proxima_avaliacao": {"data": "13 Eleasis, 1372 DR", "hora": "06:00"},
                    "historico_recente": [],
                },
                "entrada_viva": {
                    "estado": "latente",
                    "antecipado": False,
                    "proxima_avaliacao": None,
                    "historico_recente": [],
                },
            },
        })
        self._yaml("runtime/contexto.yaml", {"personagem": {"nivel": 6}})
        for cid in ("entrada_morta", "entrada_viva"):
            self._yaml(f"narrador/entradas/{cid}.yaml", {
                "schema_entrada": 1,
                "natureza": "reservado",
                "id": cid,
                "nome": "Entrada Morta" if cid == "entrada_morta" else "Entrada Viva",
                "ordem": 1 if cid == "entrada_morta" else 2,
                "nivel_minimo_normal": 1,
                "fontes_canonicas": ["fonte.md"],
                "ancoras": [{"fonte": "fonte.md", "evidencia": "x"}],
            })
        (self.repo / "fonte.md").write_text("x", encoding="utf-8")
        self._npc_index({
            "estrategico": "morto",
            "leve": "morto",
            "entrada_morta": "morto",
        })

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _npc_index(self, states):
        index = {"schema_npcs": 2, "natureza": "indice_medidores_npcs", "npcs": {}}
        for npc_id, state in states.items():
            rel = f"estado/npcs/{npc_id}.yaml"
            index["npcs"][npc_id] = {"arquivo": rel, "nome": npc_id}
            self._yaml(rel, {
                "schema_npc": 2,
                "natureza": "medidores_npc_atuais",
                "id": npc_id,
                "npc": {"nome": npc_id, "vida": {"estado": state}},
            })
        self._yaml("estado/npcs/index.yaml", index)

    def test_morte_desliga_todas_as_camadas_operacionais(self):
        result = ciclo_npcs.sync(self.repo)
        self.assertEqual(set(result["novos_mortos"]), {"estrategico", "leve", "entrada_morta"})

        strategic = yaml.safe_load((self.repo / "narrador/agentes/index.yaml").read_text())
        self.assertEqual(strategic["agentes"]["estrategico"]["estado"], "inativo")
        fragment = yaml.safe_load((self.repo / "narrador/agentes/estrategico.yaml").read_text())
        self.assertEqual(fragment["estado"], "inativo")

        light = yaml.safe_load((self.repo / "narrador/agentes-leves/index.yaml").read_text())
        light_state = yaml.safe_load((self.repo / "narrador/agentes-leves/estado.yaml").read_text())
        self.assertEqual(light["agentes"]["leve"]["estado"], "inativo")
        self.assertEqual(light_state["agentes"]["leve"]["estado"], "inativo")

        entry_state = entradas.load_state(self.repo)
        self.assertEqual(entry_state["candidatos"]["entrada_morta"]["estado"], "inviavel")
        self.assertIsNotNone(entry_state["candidatos"]["entrada_viva"]["proxima_avaliacao"])

        agenda = mundo.load_agenda(self.repo)
        self.assertNotIn("estrategico", agenda["reavaliacoes"])
        self.assertEqual(agenda["agendamentos"], [])

        world = mundo.load_world_state(self.repo)
        self.assertEqual([p["id"] for p in world["pendencias"]], ["p-vivo"])
        self.assertEqual(world["pendencias"][0]["agentes_afetados"], ["outro"])
        self.assertEqual(world["concluidas_recentes"][-1]["cancelada"], "ator_morto")

    def test_sync_e_idempotente(self):
        ciclo_npcs.sync(self.repo)
        first = mundo.load_world_state(self.repo)
        result = ciclo_npcs.sync(self.repo)
        second = mundo.load_world_state(self.repo)
        self.assertEqual(result["novos_mortos"], [])
        self.assertEqual(first, second)

    def test_ausencia_de_morte_nao_desativa_npc(self):
        self._npc_index({"estrategico": "vivo"})
        result = ciclo_npcs.sync(self.repo)
        self.assertEqual(result["mortos"], [])
        strategic = yaml.safe_load((self.repo / "narrador/agentes/index.yaml").read_text())
        self.assertEqual(strategic["agentes"]["estrategico"]["estado"], "ativo")

    def test_registro_morto_e_terminal_se_campo_some(self):
        ciclo_npcs.sync(self.repo)
        npc = yaml.safe_load((self.repo / "estado/npcs/estrategico.yaml").read_text())
        npc["npc"].pop("vida")
        self._yaml("estado/npcs/estrategico.yaml", npc)
        result = ciclo_npcs.sync(self.repo)
        self.assertIn("estrategico", result["mortos"])


if __name__ == "__main__":
    unittest.main()
