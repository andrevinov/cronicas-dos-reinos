from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agentes
import agentes_leves
import direcoes
import direcoes_mundo
import entradas
import eventos_mundo
import relogios

BUDGET_PATH = ROOT / "baseline/mundo-vivo-orcamento-contexto.yaml"
SNAPSHOT_PATH = ROOT / "tests/fixtures/mundo-vivo/sessao-008.yaml"
ROLLOUT_TARGETS = ROOT / "baseline/metas-rollout-pos-refatoracao.json"


def _fragment_source(path: str) -> bool:
    if path.startswith("narrador/agentes/"):
        return path != "narrador/agentes/index.yaml"
    if path.startswith("narrador/agentes-leves/"):
        return path not in {
            "narrador/agentes-leves/index.yaml",
            "narrador/agentes-leves/estado.yaml",
        }
    if path.startswith("narrador/entradas/"):
        return path not in {
            "narrador/entradas/index.yaml",
            "narrador/entradas/estado.yaml",
        }
    if path.startswith("narrador/direcoes/"):
        return path not in {
            "narrador/direcoes/index.yaml",
            "narrador/direcoes/estado.yaml",
        }
    if path.startswith("narrador/eventos/cartas/"):
        return True
    if path.startswith("narrador/rastros/itens/"):
        return True
    if path.startswith("narrador/relogios/"):
        return path not in {
            "narrador/relogios/index.yaml",
            "narrador/relogios/vinculos.yaml",
        }
    return False


class MundoVivoContextBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = yaml.safe_load(BUDGET_PATH.read_text(encoding="utf-8"))
        cls.limits = cls.contract["limites"]

    def test_contrato_de_orcamento_tem_schema_e_tetos_duros(self):
        self.assertEqual(self.contract["schema_orcamento_contexto_mundo_vivo"], 1)
        lookup = self.limits["lookup_dirigido"]
        self.assertEqual(lookup["max_fontes"], 4)
        self.assertEqual(lookup["max_fragmentos_narrativos"], 1)
        self.assertLessEqual(lookup["max_payload_bytes"], 12288)
        self.assertTrue(lookup["proibir_transcricao"])
        self.assertEqual(self.limits["checkpoint_automatico"]["max_fragmentos_narrativos_expostos"], 0)

    def test_lookup_dirigido_real_fica_em_um_fragmento_e_payload_pequeno(self):
        cases = {
            "agente": agentes.load_agent(ROOT, "Red Sail"),
            "agente_leve": agentes_leves.load_agent(ROOT, "Luath"),
            "direcao": direcoes.show(ROOT, "Shin-Kozakura"),
            "entrada": entradas.show(ROOT, "Shen"),
            "evento": eventos_mundo.show(ROOT, "procissao_local"),
            "relogio": relogios.show(ROOT, "rastro_fraco_no_pomar"),
        }
        limit = self.limits["lookup_dirigido"]
        for label, result in cases.items():
            with self.subTest(label=label):
                sources = list(result.get("fontes_lidas") or [])
                self.assertLessEqual(len(sources), limit["max_fontes"], sources)
                self.assertLessEqual(
                    sum(1 for source in sources if _fragment_source(source)),
                    limit["max_fragmentos_narrativos"],
                    sources,
                )
                self.assertFalse(any("transcricao" in source for source in sources), sources)
                payload = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
                self.assertLessEqual(len(payload), limit["max_payload_bytes"], (label, len(payload)))

    def test_roteadores_quentes_reais_nao_podem_inchar_silenciosamente(self):
        limit = self.limits["arquivos_quentes"]
        sizes = {}
        for rel in self.contract["arquivos_quentes"]:
            path = ROOT / rel
            self.assertTrue(path.is_file(), rel)
            sizes[rel] = path.stat().st_size
            self.assertLessEqual(sizes[rel], limit["max_bytes_por_roteador"], (rel, sizes[rel]))
        self.assertLessEqual(sum(sizes.values()), limit["max_bytes_total_roteadores"], sizes)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 12288)

    def test_todas_as_cartas_respeitam_orcamento_de_agentes_sem_fragmentos(self):
        index = eventos_mundo.load_index(ROOT)
        context = eventos_mundo.routing_context(ROOT)
        event_limit = self.limits["evento"]
        self.assertEqual(
            sum(1 for source in context["fontes_lidas"] if _fragment_source(source)),
            0,
            context["fontes_lidas"],
        )
        for event_id, meta in index["cartas"].items():
            with self.subTest(evento=event_id):
                routed = eventos_mundo.route_agents(meta["tags"], context)
                self.assertLessEqual(len(routed["estrategicos"]), event_limit["max_agentes_estrategicos"])
                self.assertLessEqual(len(routed["leves"]), event_limit["max_agentes_leves"])
                self.assertLessEqual(
                    len(routed["estrategicos"]) + len(routed["leves"]),
                    event_limit["max_agentes_total"],
                )

    def test_checkpoint_automatico_do_snapshot_expoe_zero_fragmentos(self):
        snapshot = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for rel, document in snapshot["arquivos"].items():
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=110),
                    encoding="utf-8",
                )
            time_path = repo / "estado/tempo.yaml"
            time = yaml.safe_load(time_path.read_text(encoding="utf-8"))
            time["data_atual"] = "12 Eleasis, 1372 DR"
            time["hora_aproximada"] = "06:05"
            time_path.write_text(
                yaml.safe_dump(time, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            result = direcoes_mundo.process_checkpoint(repo)
            exposed = [source for source in result["fontes_lidas"] if _fragment_source(source)]
            self.assertLessEqual(
                len(exposed),
                self.limits["checkpoint_automatico"]["max_fragmentos_narrativos_expostos"],
                exposed,
            )

    def test_metas_de_rollout_continuam_alinhadas_ao_hot_path(self):
        targets = json.loads(ROLLOUT_TARGETS.read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in targets["narration"]["rules"]}
        self.assertEqual(
            rules["write-targets"]["value"],
            float(self.limits["turno_comum"]["max_alvos_escrita"]),
        )
        self.assertEqual(
            rules["canonical-writes"]["value"],
            float(self.limits["turno_comum"]["max_escritas_canonicas"]),
        )
        self.assertLessEqual(rules["transcript-reads"]["value"], 0.05)


if __name__ == "__main__":
    unittest.main()
