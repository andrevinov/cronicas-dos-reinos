from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load_module("fase3_policy", TOOLS / "politica_acesso.py")
analyzer = load_module("fase3_rollout", TOOLS / "analisar-rollout.py")
consolidation_tests = load_module("fase3_consolidation_fixture", ROOT / "tests/test_consolidacao.py")


class RecursosEfeitosTest(unittest.TestCase):
    def test_recurso_e_consulta_dirigida_l2(self):
        decision = policy.classify("recurso")
        self.assertEqual(decision.level, "L2")
        self.assertIsNone(decision.required_after)

    def test_telemetria_classifica_recurso_e_local_como_l2(self):
        self.assertEqual(
            analyzer._access_level_from_command(
                "python3 ferramentas/contexto.py recurso 'Broche do Semblante Humilde'"
            ),
            "L2",
        )
        self.assertEqual(
            analyzer._access_level_from_command(
                "python3 ferramentas/contexto.py local 'casa de Iria Doss'"
            ),
            "L2",
        )

    def test_efeito_temporario_consolida_e_pode_ser_consumido(self):
        fixture = consolidation_tests.ConsolidacaoTest(methodName="test_cena_aplica_recursos_espelha_ficha_e_limpa_buffer")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)

        effect = {
            "nome": "Ensaio do corredor",
            "efeito": "vantagem no primeiro teste relevante para seguir sem exposição",
            "origem": "Investigação 24 no reconhecimento físico",
            "gatilho_consumo": "primeiro teste da perseguição em que o preparo ajude",
            "expira": "fim da operação de perseguição",
        }
        fixture.register(
            "efeito-criar",
            [
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "efeitos_temporarios.vantagem_corredor",
                    "valor": effect,
                }
            ],
            summary="Ren prepara o corredor para a perseguição.",
        )
        consolidation_tests.mod.consolidate(fixture.repo, "cena")

        state = fixture._read_yaml("estado/estado-atual.yaml")
        runtime = fixture._read_yaml("runtime/contexto.yaml")
        scene = fixture._read_yaml("runtime/cena.yaml")
        self.assertEqual(
            state["efeitos_temporarios"]["vantagem_corredor"]["nome"],
            "Ensaio do corredor",
        )
        self.assertIn("vantagem_corredor", runtime["efeitos_temporarios"])
        self.assertIn("vantagem_corredor", scene["efeitos_temporarios"])

        fixture.register(
            "efeito-consumir",
            [
                {
                    "alvo": "estado",
                    "op": "remove",
                    "caminho": "efeitos_temporarios.vantagem_corredor",
                }
            ],
            summary="A vantagem preparada foi consumida.",
        )
        consolidation_tests.mod.consolidate(fixture.repo, "cena")

        state_after = fixture._read_yaml("estado/estado-atual.yaml")
        runtime_after = fixture._read_yaml("runtime/contexto.yaml")
        scene_after = fixture._read_yaml("runtime/cena.yaml")
        self.assertNotIn("vantagem_corredor", state_after.get("efeitos_temporarios", {}))
        self.assertNotIn("efeitos_temporarios", runtime_after)
        self.assertNotIn("efeitos_temporarios", scene_after)


if __name__ == "__main__":
    unittest.main()
