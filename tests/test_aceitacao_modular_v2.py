from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ferramentas import aceitacao_modular_v2


ROOT = Path(__file__).parents[1]
AUTHORITATIVE_PATHS = (
    "campanha.yaml",
    "estado",
    "personagens",
    "narrador",
    "runtime",
    "sessoes",
)


def _authoritative_hashes() -> dict[str, str]:
    paths: list[Path] = []
    for relative in AUTHORITATIVE_PATHS:
        target = ROOT / relative
        paths.extend([target] if target.is_file() else target.rglob("*"))
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
        if path.is_file()
    }


class ModularV2AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        before = _authoritative_hashes()
        cls.result = aceitacao_modular_v2.check(ROOT)
        cls.after = _authoritative_hashes()
        cls.before = before

    def test_gate_tecnico_fica_verde_sem_fingir_sessao_real(self) -> None:
        self.assertTrue(self.result["ok"], self.result.get("erros"))
        self.assertIn(
            self.result["estado"],
            {"pronta_para_primeira_sessao_real", "aceita"},
        )
        self.assertTrue(self.result["validacao_externa"]["ok"])
        self.assertEqual(self.result["validacao_externa"]["sessao_origem"], "022")
        real = self.result["primeira_sessao_real"]
        self.assertEqual(real["aceite_final"], real["estado"] == "aceita")
        self.assertFalse(self.result["contrato"]["fixture_inaugura_serie_real"])

    def test_nove_episodios_tem_ancoras_permanentes(self) -> None:
        self.assertEqual(len(self.result["episodios_ancorados"]), 9)
        self.assertEqual(len(set(self.result["episodios_ancorados"])), 9)
        self.assertEqual(
            self.result["execucao_episodios"],
            {"ok": True, "quantidade": 9},
        )

    def test_pacote_tem_doze_modulos_interacoes_e_custo_observado(self) -> None:
        technical = self.result["aceitacao_tecnica"]
        observed = technical["observado"]
        baseline = json.loads(
            (ROOT / "baseline/modules-v2-technical-acceptance.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(observed, baseline["observado"])
        self.assertEqual(observed["modulos_pais"], 12)
        self.assertEqual(observed["interacoes_total"], 6)
        self.assertEqual(observed["interacoes_incompletas"], 1)
        self.assertEqual(
            observed["tokens_atribuidos_pais"], observed["tokens_narrativos"]
        )
        self.assertTrue(technical["pacote"]["regeneracao_idempotente"])
        self.assertTrue(technical["pacote"]["reproducao_byte_a_byte"])
        self.assertRegex(technical["pacote"]["entrada_id"], r"^[0-9a-f]{64}$")
        self.assertTrue(technical["pacote"]["versoes_historicas_preservadas"])

    def test_checker_nao_escreve_em_fontes_autoritativas(self) -> None:
        self.assertEqual(self.before, self.after)

    def test_historico_de_releases_tem_corrente_explicito(self) -> None:
        releases = self.result["releases"]
        self.assertEqual(releases["schema"], 2)
        self.assertEqual(releases["releases_correntes"], 12)
        self.assertGreaterEqual(releases["releases_historicos"], 12)
        self.assertEqual(set(releases["current_release_ids"]), aceitacao_modular_v2.catalog_contract.MODULE_IDS)


class FirstRealSessionAcceptanceTest(unittest.TestCase):
    def status(self, observed, *, module_count=12, blocked_module=False):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            package = repo / "evaluation/sessions/001"
            package.mkdir(parents=True)
            entry_id = "a" * 64
            module_rows = [
                {
                    "modulo": f"modulo-{index}",
                    "aplicabilidade_avaliacao": (
                        "falha_instrumentacao" if blocked_module and index == 0 else "avaliavel"
                    ),
                }
                for index in range(12)
            ]
            files = {
                repo / aceitacao_modular_v2.SESSION_INDEX: {
                    "sessoes": [{"serie_avaliacao": "modules-v2", "sessao_id": "001", "caminho": "001"}]
                },
                package / "manifest.json": {
                    "serie_avaliacao": "modules-v2",
                    "versoes_modulos": [{}] * module_count,
                    "proveniencia_medicao": {
                        "modo": "entrada_congelada",
                        "entrada_id": entry_id,
                        "conclusao_reprodutivel_permitida": True,
                    },
                    "artefatos": {"proveniencia_medicao": "proveniencia-medicao.json"},
                },
                package / "scorecard.json": {
                    "eixos": {},
                    "status_avaliacao": "provisoria",
                    "conclusao_medicao": {
                        "schema_conclusao_medicao": 1,
                        "entrada_congelada": True,
                        "reproducao_verificada": True,
                        "permitida": not blocked_module,
                        "bloqueios": ([{"codigo": "falha_instrumentacao_modular"}] if blocked_module else []),
                    },
                    "agregacao_modular": {
                        "schema": 1,
                        "status": "bloqueada_instrumentacao" if blocked_module else "completa",
                        "conclusao_permitida": not blocked_module,
                        "modulos_bloqueados": ([{"module_id": "modulo-0"}] if blocked_module else []),
                    },
                    "violacoes_criticas": [],
                },
                package / "interacoes.json": {"interactions": observed},
                package / "resumo-modulos.json": {"modulos": module_rows},
                package / "proveniencia-medicao.json": {
                    "schema_proveniencia_medicao": 1,
                    "modo": "entrada_congelada",
                    "entrada_id": entry_id,
                    "conclusao_reprodutivel_permitida": True,
                    "diagnosticos": [],
                },
            }
            for path, value in files.items():
                path.write_text(json.dumps(value), encoding="utf-8")
            return aceitacao_modular_v2.first_real_session_status(repo)

    def test_referencia_ausente_mantem_aceite_real_pendente(self):
        result = self.status([
            {"response_present": True, "visible_exactly_once": True},
            {"response_present": True, "visible_exactly_once": False},
        ])
        self.assertEqual(result["estado"], "pendente")
        self.assertFalse(result["aceite_final"])
        self.assertEqual(result["interacoes_observadas"], 2)
        self.assertEqual(result["interacoes_sem_referencia_unica"], 1)

    def test_sem_respostas_observadas_nao_inaugura_baseline(self):
        result = self.status([])
        self.assertFalse(result["aceite_final"])
        self.assertEqual(result["interacoes_observadas"], 0)

    def test_referencias_unicas_permitem_aceite_real(self):
        result = self.status([{"response_present": True, "visible_exactly_once": True}])
        self.assertEqual(result["estado"], "aceita")
        self.assertTrue(result["aceite_final"])
        self.assertEqual(result["bloqueios"], [])

    def test_instrumentacao_falha_bloqueia_mesmo_com_referencia_unica(self):
        result = self.status(
            [{"response_present": True, "visible_exactly_once": True}],
            blocked_module=True,
        )
        self.assertEqual(result["estado"], "pendente")
        self.assertFalse(result["aceite_final"])
        codes = {item["codigo"] for item in result["bloqueios"]}
        self.assertIn("agregacao_modular_bloqueada", codes)
        self.assertIn("modulos_com_falha_instrumentacao", codes)

    def test_sessao_023_historica_nao_e_promovida_depois_do_diagnostico(self):
        result = aceitacao_modular_v2.first_real_session_status(ROOT)
        self.assertEqual(result["sessao_id"], "023")
        self.assertFalse(result["aceite_final"])
        codes = {item["codigo"] for item in result["bloqueios"]}
        self.assertIn("conclusao_medicao_ausente", codes)
        self.assertIn("agregacao_modular_ausente", codes)
        self.assertIn("artefato_proveniencia_nao_declarado", codes)

    def test_pacote_estruturalmente_invalido_continua_bloqueando_gate(self):
        with self.assertRaises(aceitacao_modular_v2.ModularAcceptanceError):
            self.status([], module_count=11)


if __name__ == "__main__":
    unittest.main()
