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

import gate_adnd
import mecanica_cronica


class GateRepo:
    def __init__(self, root: Path, *, current: str = "dnd_5e_2014") -> None:
        self.root = root
        (root / "regras").mkdir(parents=True)
        campaign = {
            "sistema": {
                "ruleset": {
                    "atual": current,
                    "alvo": "dnd_5_5e",
                }
            }
        }
        (root / "campanha.yaml").write_text(
            yaml.safe_dump(campaign, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self.write_registry([])

    def write_registry(self, materials: list[dict]) -> None:
        document = {
            "schema_gate_adnd": 1,
            "natureza": "registro_adaptacoes_mecanicas",
            "materiais": materials,
        }
        (self.root / gate_adnd.REGISTRY_PATH).write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def provenance_55() -> dict:
    return {
        "edicao_origem": "adnd_2e",
        "adaptado_para": "dnd_5_5e",
        "fonte_mecanica": {
            "ruleset": "dnd_5_5e",
            "referencia": "Monster Manual 2025 — bloco equivalente convertido",
        },
    }


def provenance_2014(*, fallback: bool) -> dict:
    data = {
        "edicao_origem": "adnd_2e",
        "adaptado_para": "dnd_5e_2014",
        "fonte_mecanica": {
            "ruleset": "dnd_5e_2014",
            "referencia": "Monster Manual 2014 — bloco equivalente convertido",
        },
    }
    if fallback:
        data["fallback_2014"] = {
            "declarado": True,
            "motivo": "ponte temporária enquanto o ruleset ativo ainda é 2014",
            "decisao": "DEC-TESTE-FALLBACK-2014",
        }
    return data


class FormalADNDGateTest(unittest.TestCase):
    def test_fixture_adnd_puramente_narrativa_passa_sem_metadados_mecanicos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            material = {
                "edicao_origem": "adnd_2e",
                "natureza": "narrativa",
                "texto": "A guilda controla os cais e responde ao conselho da cidade.",
            }
            result = gate_adnd.validate_material(repo, material)
            self.assertFalse(result["mecanica_ativa"])
            self.assertEqual(result["resultado"], "narrativa_ou_inativo")

    def test_statblock_adnd_literal_falha_mesmo_com_destino_moderno(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            material = {
                "mecanica_ativa": True,
                "proveniencia_mecanica": provenance_55(),
                "mecanica": {
                    "nome": "Veterano de Ravens Bluff",
                    "THAC0": 17,
                    "armor_class_descending": 3,
                },
            }
            with self.assertRaisesRegex(gate_adnd.ADNDGateError, "mecânica AD&D literal proibida"):
                gate_adnd.validate_material(repo, material)

    def test_adaptacao_5_5e_preparada_passa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            material = {
                "mecanica_ativa": True,
                "proveniencia_mecanica": provenance_55(),
                "mecanica": {
                    "armor_class": 16,
                    "hit_points": 58,
                    "attack_bonus": 6,
                    "saving_throws": {"dex": 4, "wis": 3},
                },
            }
            result = gate_adnd.validate_material(repo, material)
            self.assertEqual(result["resultado"], "adaptacao_mecanica_validada")
            self.assertEqual(
                result["proveniencia_mecanica"]["adaptado_para"],
                "dnd_5_5e",
            )

    def test_5_5e_preparada_nao_fura_ruleset_2014_do_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo, current="dnd_5e_2014")
            with self.assertRaisesRegex(gate_adnd.ADNDGateError, "não pode entrar no runtime"):
                gate_adnd.normalize_provenance(repo, provenance_55(), for_runtime=True)

    def test_uso_excepcional_2014_exige_fallback_explicitamente_declarado(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo, current="dnd_5e_2014")
            with self.assertRaisesRegex(gate_adnd.ADNDGateError, "fallback_2014"):
                gate_adnd.normalize_provenance(repo, provenance_2014(fallback=False))

            valid = gate_adnd.normalize_provenance(
                repo,
                provenance_2014(fallback=True),
                for_runtime=True,
            )
            self.assertTrue(valid["fallback_2014"]["declarado"])
            self.assertEqual(valid["adaptado_para"], "dnd_5e_2014")

    def test_fonte_mecanica_precisa_ter_mesma_versao_do_destino(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            bad = provenance_55()
            bad["fonte_mecanica"]["ruleset"] = "dnd_5e_2014"
            with self.assertRaisesRegex(gate_adnd.ADNDGateError, "coincidir com adaptado_para"):
                gate_adnd.normalize_provenance(repo, bad)

    def test_integridade_detecta_material_ativo_sem_versao_mecanica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = GateRepo(repo)
            fixture.write_registry(
                [
                    {
                        "id": "guarda_lc2",
                        "status": "ativo",
                        "proveniencia_mecanica": {
                            "edicao_origem": "adnd_2e",
                            "fonte_mecanica": {
                                "ruleset": "dnd_5_5e",
                                "referencia": "Monster Manual 2025",
                            },
                        },
                        "mecanica": {"armor_class": 15},
                    }
                ]
            )
            errors = gate_adnd.validate_repository(repo)
            self.assertTrue(any("adaptado_para" in error for error in errors), errors)

    def test_integridade_ignora_lore_adnd_fora_do_registro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            narrative = {
                "edicao_origem": "adnd_2e",
                "natureza": "narrativa",
                "texto": "Rumores do porto sem efeito mecânico.",
            }
            errors = gate_adnd.validate_repository(
                repo,
                {
                    gate_adnd.REGISTRY_PATH.as_posix(): yaml.safe_load(
                        (repo / gate_adnd.REGISTRY_PATH).read_text(encoding="utf-8")
                    ),
                    "cenario/lore.yaml": narrative,
                },
            )
            self.assertEqual(errors, [])

    def test_cronica_congela_proveniencia_aprovada_e_recusa_destino_nao_ativo(self) -> None:
        base = {
            "regras": ["teste_d20_basico"],
            "obrigacoes": [
                {
                    "id": "teste_adaptado",
                    "tipo": "teste",
                    "regra": "teste_d20_basico",
                    "bonus": 3,
                    "alvo": 14,
                }
            ],
        }
        approved = dict(base)
        approved["proveniencia"] = provenance_55()
        contract = mecanica_cronica.normalize_spec(ROOT, approved)
        self.assertEqual(contract["proveniencia"]["edicao_origem"], "adnd_2e")
        self.assertEqual(contract["proveniencia"]["adaptado_para"], "dnd_5_5e")
        self.assertNotIn("fallback_2014", contract["proveniencia"])

        legacy = dict(base)
        legacy["proveniencia"] = provenance_2014(fallback=True)
        with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "gate AD&D"):
            mecanica_cronica.normalize_spec(ROOT, legacy)

    def test_integridade_nao_confunde_mecanica_nativa_com_adnd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            GateRepo(repo)
            registry = yaml.safe_load(
                (repo / gate_adnd.REGISTRY_PATH).read_text(encoding="utf-8")
            )
            errors = gate_adnd.validate_repository(
                repo,
                {
                    gate_adnd.REGISTRY_PATH.as_posix(): registry,
                    "regras/material-nativo.yaml": {
                        "mecanica_ativa": True,
                        "mecanica": {"armor_class": 17},
                    },
                },
            )
            self.assertEqual(errors, [])

    def test_verificador_principal_chama_subgate_adnd(self) -> None:
        source = (ROOT / "ferramentas/verificar-integridade.py").read_text(encoding="utf-8")
        self.assertIn("gate_adnd.validate_repository", source)


if __name__ == "__main__":
    unittest.main()
