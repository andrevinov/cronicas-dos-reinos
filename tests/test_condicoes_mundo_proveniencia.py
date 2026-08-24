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

import condicoes_mundo as conditions
import condicoes_mundo_cena
import mundo


class PersistentConditionProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        state = self.root / conditions.STATE
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            yaml.safe_dump(
                {
                    "schema_condicoes_mundo": 1,
                    "natureza": "controle_reservado",
                    "cidade": "ravens_bluff",
                    "condicoes": {},
                    "historico_recente": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        source = self.root / "sessoes/001/resumo.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "Uma tempestade forte começou sobre Ravens Bluff.\n"
            "Uma greve nova começou no porto dias depois.\n",
            encoding="utf-8",
        )
        self.start = mundo.parse_instant("17 Eleasis, 1372 DR", "18:00")

    def tearDown(self):
        self.tmp.cleanup()

    def _register_storm(self, now):
        return conditions.register(
            self.root,
            kind="clima",
            subject="tempestade costeira",
            intensity="forte",
            description="Chuva pesada e vento persistem sobre Ravens Bluff.",
            signals=["ruas encharcadas"],
            markers=["chuva_forte"],
            locals_=[],
            duration_hours=24,
            source="sessoes/001/resumo.md",
            evidence="Uma tempestade forte começou sobre Ravens Bluff.",
            now=now,
        )

    def test_retry_em_instante_diferente_preserva_mesmo_id(self):
        first = self._register_storm(self.start)
        later = mundo.WorldInstant(self.start.minute + 6 * 60)
        retry = self._register_storm(later)
        self.assertEqual(retry["resultado"], "ja_registrada")
        self.assertEqual(retry["condicao"]["id"], first["condicao"]["id"])
        self.assertEqual(len(conditions.load_state(self.root)["condicoes"]), 1)

    def test_evidencia_antiga_nao_ressuscita_condicao_expirada(self):
        first = self._register_storm(self.start)
        after_expiry = mundo.WorldInstant(self.start.minute + 30 * 60)
        replay = self._register_storm(after_expiry)
        self.assertEqual(replay["resultado"], "evidencia_ja_consumida")
        self.assertEqual(replay["condicao"]["id"], first["condicao"]["id"])
        self.assertEqual(conditions.project(self.root, now=after_expiry)["ativas"], [])

    def test_evidencia_continua_consumida_depois_de_compactada(self):
        first = self._register_storm(self.start)
        later = mundo.WorldInstant(self.start.minute + 48 * 60)
        conditions.register(
            self.root,
            kind="greve",
            subject="estivadores",
            intensity="moderada",
            description="O trabalho no porto opera com equipes reduzidas.",
            signals=["filas nos cais"],
            markers=["porto_lento"],
            locals_=[],
            duration_hours=48,
            source="sessoes/001/resumo.md",
            evidence="Uma greve nova começou no porto dias depois.",
            now=later,
        )
        state = conditions.load_state(self.root)
        self.assertTrue(any(item["id"] == first["condicao"]["id"] for item in state["historico_recente"]))
        replay = self._register_storm(later)
        self.assertEqual(replay["resultado"], "evidencia_ja_consumida")
        self.assertNotIn(first["condicao"]["id"], conditions.load_state(self.root)["condicoes"])

    def test_mesma_evidencia_nao_pode_mudar_definicao(self):
        self._register_storm(self.start)
        with self.assertRaises(conditions.WorldConditionError):
            conditions.register(
                self.root,
                kind="festival",
                subject="festa inventada",
                intensity="leve",
                description="Outro significado para o mesmo fato.",
                signals=[],
                markers=[],
                locals_=[],
                duration_hours=24,
                source="sessoes/001/resumo.md",
                evidence="Uma tempestade forte começou sobre Ravens Bluff.",
                now=self.start,
            )


class PersistentConditionCanonicalTagTest(unittest.TestCase):
    def test_alias_de_tag_local_converge_para_id_canonico(self):
        result = {
            "local": None,
            "contexto_tags": ["local:templo de Tyr"],
        }
        self.assertEqual(
            condicoes_mundo_cena._local_id(ROOT, result),
            "casa_de_tyr",
        )

    def test_alias_normalizado_com_underscore_tambem_converge(self):
        result = {
            "local": None,
            "contexto_tags": ["local:templo_de_tyr"],
        }
        self.assertEqual(
            condicoes_mundo_cena._local_id(ROOT, result),
            "casa_de_tyr",
        )


if __name__ == "__main__":
    unittest.main()
