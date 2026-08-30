from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import eventos_canonicos
import intencoes_canonicas


class CanonicalIntentRewriteContractRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.index = intencoes_canonicas.load_index(ROOT)
        self.catalog = eventos_canonicos.load_catalog(ROOT)
        self.frozen = set(self.index["passado_congelado"])
        self.future = [
            event_id for event_id in self.catalog["eventos"] if event_id not in self.frozen
        ]

    def test_repositorio_real_tem_contrato_task39_completo(self):
        result = intencoes_canonicas.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["eventos"], 21)
        self.assertEqual(result["passado_congelado"], 2)
        self.assertEqual(result["futuros_com_intencao"], 19)
        self.assertEqual(result["intencoes_unicas"], 19)
        self.assertEqual(result["schedulers_novos"], 0)
        self.assertEqual(result["estados_novos"], 0)
        self.assertEqual(result["rng_novo"], 0)
        self.assertEqual(result["scans_globais_hot_path"], 0)

    def test_task39_congela_todo_passado_materializado_na_instalacao(self):
        self.assertEqual(
            self.frozen,
            {"emboscada_do_restaurante", "shinta_incriminado"},
        )
        for event_id, digest in self.index["passado_congelado"].items():
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            self.assertEqual(eventos_canonicos.event_digest(event), digest)
            self.assertFalse((ROOT / intencoes_canonicas._intent_path(event_id)).exists())

    def test_futuro_separa_intencao_de_realizacao_padrao(self):
        seen: set[str] = set()
        for event_id in self.future:
            intent = intencoes_canonicas.load_intent(
                ROOT,
                event_id,
                index=self.index,
                catalog=self.catalog,
            )
            intent_id = intent["intencao_canonica"]["id"]
            self.assertNotIn(intent_id, seen)
            seen.add(intent_id)
            self.assertTrue(intent["intencao_canonica"]["funcao"])
            self.assertTrue(intent["intencao_canonica"]["criterios_satisfacao"])
            self.assertEqual(
                intent["realizacao_padrao"],
                {
                    "fonte": "evento_canonico_task36",
                    "nucleo": "nucleo_obrigatorio",
                    "forma": "forma_preferencial",
                },
            )
            rewrite = intent["contrato_rewrite"]
            self.assertTrue(rewrite["preserva_intencao"])
            self.assertEqual(rewrite["sem_rewrite"], "realizacao_padrao")
            self.assertNotIn("cancelar", rewrite["modos_permitidos"])
            self.assertLessEqual(
                rewrite["atraso_maximo_horas"],
                self.index["atraso_maximo_global_horas"],
            )
        self.assertEqual(len(seen), 19)

    def test_consulta_dirigida_nao_abre_fragmento_narrativo_task36(self):
        event_id = self.future[0]
        intent_path = intencoes_canonicas._intent_path(event_id)
        event_fragment = Path(self.catalog["eventos"][event_id]["fragmento"])
        opened: list[Path] = []
        original_intent_load = intencoes_canonicas._load
        original_event_load = eventos_canonicos._load

        def tracked_intent(path: Path):
            opened.append(path.relative_to(ROOT))
            return original_intent_load(path)

        def tracked_event(path: Path):
            opened.append(path.relative_to(ROOT))
            return original_event_load(path)

        with (
            patch.object(
                intencoes_canonicas,
                "_load",
                side_effect=tracked_intent,
            ),
            patch.object(
                eventos_canonicos,
                "_load",
                side_effect=tracked_event,
            ),
        ):
            projection = intencoes_canonicas.projection(ROOT, event_id)

        self.assertTrue(projection["ok"])
        self.assertEqual(
            opened,
            [
                intencoes_canonicas.INDEX,
                eventos_canonicos.CATALOG,
                intent_path,
            ],
        )
        self.assertNotIn(event_fragment, opened)
        self.assertEqual(
            projection["realizacao_padrao"]["fragmento_evento"],
            event_fragment.as_posix(),
        )

    def test_orcamento_task39_permanece_frio_e_compacto(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/canonical-intent-rewrite-contract-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = budget["limites"]
        self.assertLessEqual(
            (ROOT / intencoes_canonicas.INDEX).stat().st_size,
            limits["indice_intencoes_bytes_max"],
        )
        for event_id in self.future:
            self.assertLessEqual(
                (ROOT / intencoes_canonicas._intent_path(event_id)).stat().st_size,
                limits["fragmento_intencao_bytes_max"],
                event_id,
            )
        self.assertEqual(limits["eventos_total"], 21)
        self.assertEqual(limits["passado_congelado"], 2)
        self.assertEqual(limits["futuros_com_intencao"], 19)
        self.assertEqual(limits["leituras_task39_turno_normal"], 0)
        self.assertEqual(limits["indices_consulta_intencao"], 2)
        self.assertEqual(limits["fragmentos_intencao_consulta_max"], 1)
        self.assertEqual(limits["fragmentos_evento_task36_consulta_intencao"], 0)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["estados_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["scans_globais_hot_path"], 0)
        self.assertTrue(all(budget["invariantes"].values()))

    def test_documentacao_task39_permanece_spoiler_light(self):
        public = (ROOT / "docs/task39-canonical-intent-rewrite-contract.md").read_text(
            encoding="utf-8"
        )
        for event_id in self.future:
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            self.assertNotIn(event_id, public)
            self.assertNotIn(event["titulo"], public)


class CanonicalIntentRewriteContractValidationTest(unittest.TestCase):
    def _valid_rewrite(self) -> dict:
        return {
            "preserva_intencao": True,
            "sem_rewrite": "realizacao_padrao",
            "modos_permitidos": [
                "satisfazer",
                "transformar",
                "adiar",
                "reancorar",
            ],
            "atraso_maximo_horas": 48,
            "integracao_sidequest": True,
            "satisfacao_antecipada": True,
            "reancoragem_local": True,
            "troca_de_atores": True,
        }

    def test_cancelamento_nao_e_modo_de_rewrite(self):
        raw = self._valid_rewrite()
        raw["modos_permitidos"].append("cancelar")
        with self.assertRaises(intencoes_canonicas.CanonicalIntentError):
            intencoes_canonicas._validate_rewrite(raw, "evento_teste")

    def test_atraso_nao_pode_ultrapassar_limite_global(self):
        raw = self._valid_rewrite()
        raw["atraso_maximo_horas"] = intencoes_canonicas.MAX_GLOBAL_DELAY_HOURS + 1
        with self.assertRaises(intencoes_canonicas.CanonicalIntentError):
            intencoes_canonicas._validate_rewrite(raw, "evento_teste")

    def test_adiar_exige_limite_temporal_positivo(self):
        raw = self._valid_rewrite()
        raw["atraso_maximo_horas"] = 0
        with self.assertRaises(intencoes_canonicas.CanonicalIntentError):
            intencoes_canonicas._validate_rewrite(raw, "evento_teste")

    def test_intencao_exige_criterio_de_satisfacao(self):
        raw = {
            "id": "icp1-evento_teste",
            "funcao": "Preservar função narrativa sem impor forma.",
            "criterios_satisfacao": [],
        }
        with self.assertRaises(intencoes_canonicas.CanonicalIntentError):
            intencoes_canonicas._validate_intent(raw, "evento_teste")


if __name__ == "__main__":
    unittest.main()
