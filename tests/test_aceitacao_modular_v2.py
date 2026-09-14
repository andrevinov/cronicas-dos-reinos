from __future__ import annotations

import hashlib
import json
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
        self.assertTrue(technical["pacote"]["versoes_historicas_preservadas"])

    def test_checker_nao_escreve_em_fontes_autoritativas(self) -> None:
        self.assertEqual(self.before, self.after)

    def test_historico_de_releases_tem_corrente_explicito(self) -> None:
        releases = self.result["releases"]
        self.assertEqual(releases["schema"], 2)
        self.assertEqual(releases["releases_correntes"], 12)
        self.assertGreaterEqual(releases["releases_historicos"], 12)
        self.assertEqual(set(releases["current_release_ids"]), aceitacao_modular_v2.catalog_contract.MODULE_IDS)


if __name__ == "__main__":
    unittest.main()
