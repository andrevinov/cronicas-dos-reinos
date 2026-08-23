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

import agentes_leves as light


class LightAgentNoopRepositoryTest(unittest.TestCase):
    def test_repositorio_real_usa_schema2_com_fontes_causais_compactas(self):
        index = light.load_index(ROOT)
        self.assertEqual(index["schema_agentes_leves"], 2)
        self.assertEqual(index["orcamento"]["max_checks_cache_negativo_por_checkpoint"], 1)
        for agent_id, meta in index["agentes"].items():
            self.assertEqual(
                meta["fontes_causais"],
                [f"estado/relacoes/{agent_id}.yaml"],
            )
            self.assertEqual(len(meta["perfil_blob_git"]), 40)
        validated = light.validate_repo(ROOT)
        self.assertTrue(validated["ok"], validated["erros"])
        self.assertEqual(validated["schema"], 2)

    def test_cache_real_so_existe_com_noop_causal_concluido_e_assinatura_atual(self):
        index = light.load_index(ROOT)
        state = light.load_state(ROOT, index)
        world = light.mundo.load_world_state(ROOT)
        completed = {
            item.get("id"): item
            for item in world.get("concluidas_recentes") or []
            if isinstance(item, dict) and item.get("id")
        }
        for agent_id, item in state["agentes"].items():
            cache = item.get("cache_negativo")
            if cache is None:
                continue
            origin = cache["pendencia_origem"]
            self.assertIn(origin, completed)
            conclusion = completed[origin]
            self.assertEqual(conclusion.get("tipo"), "reavaliar_agente_leve")
            self.assertEqual(conclusion.get("resultado"), light.NOOP_RESULT)
            self.assertEqual(conclusion.get("agente_leve"), agent_id)
            signature, _ = light.causal_signature(ROOT, agent_id, index["agentes"][agent_id])
            self.assertEqual(cache["assinatura_causal"], signature)


class LightAgentNoopSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "12 Eleasis, 1372 DR",
                "hora_aproximada": "08:00 de 12 Eleasis",
            },
        )
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        self._yaml(
            "estado/relacoes/a.yaml",
            {
                "schema_relacao": 2,
                "id": "a",
                "texto": "Rotina comprovada. Objetivo comprovado. Iniciativa comprovada.",
            },
        )
        self._write_profile()
        self._write_index()
        self._yaml(
            "narrador/agentes-leves/estado.yaml",
            {
                "schema_estado_agentes_leves": 2,
                "natureza": "controle_reservado",
                "agentes": {
                    "a": {
                        "estado": "ativo",
                        "proxima_avaliacao": {"data": "10 Eleasis, 1372 DR", "hora": "06:00"},
                        "cache_negativo": None,
                    }
                },
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _write_profile(self, extra: str | None = None) -> None:
        self._yaml(
            "narrador/agentes-leves/a.yaml",
            {
                "schema_agente_leve": 1,
                "natureza": "reservado",
                "id": "a",
                "nome": "A",
                "perfil_operacional": "recorrente_leve",
                "rotina_padrao": {
                    "descricao": "Rotina.",
                    "fonte": "estado/relacoes/a.yaml",
                    "evidencia": "Rotina comprovada.",
                },
                "objetivo_atual": {
                    "descricao": "Objetivo.",
                    "fonte": "estado/relacoes/a.yaml",
                    "evidencia": "Objetivo comprovado.",
                },
                "iniciativas_possiveis": [
                    {
                        "descricao": extra or "Pode agir.",
                        "fonte": "estado/relacoes/a.yaml",
                        "evidencia": "Iniciativa comprovada.",
                    }
                ],
                "regra_de_reavaliacao": "Rotina é o padrão.",
                "fontes_canonicas": ["estado/relacoes/a.yaml"],
            },
        )

    def _write_index(self) -> None:
        blob = light._git_blob_sha(self.repo / "narrador/agentes-leves/a.yaml")
        self._yaml(
            "narrador/agentes-leves/index.yaml",
            {
                "schema_agentes_leves": 2,
                "natureza": "reservado",
                "orcamento": {
                    "max_novas_por_checkpoint": 1,
                    "max_pendencias_abertas": 2,
                    "ordenacao": "mais_atrasado_prioridade_id",
                    "max_checks_cache_negativo_por_checkpoint": 1,
                },
                "agentes": {
                    "a": {
                        "nome": "A",
                        "perfil_operacional": "recorrente_leve",
                        "estado": "ativo",
                        "prioridade": 1,
                        "intervalo_dias": 3,
                        "inicio": {"data": "10 Eleasis, 1372 DR", "hora": "06:00"},
                        "arquivo": "narrador/agentes-leves/a.yaml",
                        "perfil_blob_git": blob,
                        "fontes_causais": ["estado/relacoes/a.yaml"],
                    }
                },
            },
        )

    def _set_time(self, date: str) -> None:
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": date,
                "hora_aproximada": f"08:00 de {date.split(',')[0]}",
            },
        )

    def _open_pending(self) -> dict:
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])
        self.assertEqual(len(result["novas_pendencias"]), 1)
        self.assertNotIn("estado/relacoes/a.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/agentes-leves/a.yaml", result["fontes_lidas"])
        return result["novas_pendencias"][0]

    def _install_noop(self) -> tuple[dict, dict]:
        pending = self._open_pending()
        result = light.conclude_noop(self.repo, pending["id"], "rotina permaneceu estável")
        self.assertFalse(result["ja_concluida"])
        self.assertEqual(result["concluida"]["resultado"], light.NOOP_RESULT)
        self.assertIn("estado/relacoes/a.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/agentes-leves/a.yaml", result["fontes_lidas"])
        return pending, result

    def test_noop_explicito_instala_cache_e_remove_pendencia(self):
        pending, result = self._install_noop()
        state = light.load_state(self.repo, light.load_index(self.repo))
        cache = state["agentes"]["a"]["cache_negativo"]
        self.assertEqual(cache["pendencia_origem"], pending["id"])
        self.assertEqual(cache["acertos_compactados"], 0)
        world = light.mundo.load_world_state(self.repo)
        self.assertEqual(world["pendencias"], [])
        self.assertEqual(world["concluidas_recentes"][-1]["resultado"], light.NOOP_RESULT)
        self.assertEqual(result["pendencias_restantes"], 0)

    def test_cache_inalterado_compacta_cadencia_sem_fragmento_ou_pendencia(self):
        self._install_noop()
        self._set_time("13 Eleasis, 1372 DR")
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertEqual([item["agente_leve"] for item in result["noops_compactados"]], ["a"])
        self.assertEqual(result["orcamento"]["checks_cache_negativo"], 1)
        self.assertIn("estado/relacoes/a.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/agentes-leves/a.yaml", result["fontes_lidas"])
        state = light.load_state(self.repo, light.load_index(self.repo))
        self.assertEqual(state["agentes"]["a"]["cache_negativo"]["acertos_compactados"], 1)
        self.assertEqual(light.mundo.load_world_state(self.repo)["pendencias"], [])

    def test_mudanca_causal_invalida_cache_e_reabre_avaliacao_normal(self):
        self._install_noop()
        relation = self.repo / "estado/relacoes/a.yaml"
        relation.write_text(
            relation.read_text(encoding="utf-8") + "mudanca: nova pista concreta\n",
            encoding="utf-8",
        )
        self._set_time("13 Eleasis, 1372 DR")
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["caches_invalidados"], ["a"])
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])
        self.assertEqual(result["noops_compactados"], [])
        self.assertNotIn("narrador/agentes-leves/a.yaml", result["fontes_lidas"])
        state = light.load_state(self.repo, light.load_index(self.repo))
        self.assertIsNone(state["agentes"]["a"]["cache_negativo"])

    def test_mudanca_de_perfil_versionada_tambem_invalida_cache(self):
        self._install_noop()
        self._write_profile(extra="Pode agir de outra maneira.")
        self._write_index()
        self._set_time("13 Eleasis, 1372 DR")
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["caches_invalidados"], ["a"])
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])

    def test_validacao_detecta_perfil_editado_sem_atualizar_versao(self):
        self._write_profile(extra="Perfil mudou sem atualizar índice.")
        result = light.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("perfil_blob_git desatualizado", result["erros"][0])

    def test_retry_de_concluir_noop_e_idempotente(self):
        pending, _ = self._install_noop()
        again = light.conclude_noop(self.repo, pending["id"])
        self.assertTrue(again["ja_concluida"])
        world = light.mundo.load_world_state(self.repo)
        self.assertEqual(
            sum(item.get("id") == pending["id"] for item in world["concluidas_recentes"]),
            1,
        )

    def test_cache_ausente_preserva_comportamento_sem_leitura_causal(self):
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])
        self.assertEqual(result["noops_compactados"], [])
        self.assertEqual(result["orcamento"]["checks_cache_negativo"], 0)
        self.assertNotIn("estado/relacoes/a.yaml", result["fontes_lidas"])


if __name__ == "__main__":
    unittest.main()
