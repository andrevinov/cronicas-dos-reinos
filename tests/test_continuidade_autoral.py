from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import continuidade_autoral


class ContinuidadeAutoralTest(unittest.TestCase):
    def _write_yaml(self, root: Path, relative: str, data: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _fixture(self, root: Path) -> dict:
        source = {"fio": {"verdade": "instalada"}}
        destination = {"npcs": {"exemplo": {"arquivo": "estado/npcs/exemplo.yaml"}}}
        registry = {
            "schema_continuidade_autoral": 1,
            "natureza": "indice_reservado_de_compromissos",
            "cobertura": {
                "fonte_canonica": "narrador/segredos/fonte.yaml",
                "chaves_nao_narrativas": [],
            },
            "compromissos": {
                "fio_exemplo": {
                    "tipo": "npc",
                    "consultas": ["fio_exemplo", "exemplo"],
                    "estado": "aberto_em_jogo",
                    "ancoras": [
                        {
                            "arquivo": "narrador/segredos/fonte.yaml",
                            "chave": "fio",
                        }
                    ],
                    "destinos_operacionais": [
                        {"arquivo": "estado/npcs/index.yaml", "chave": "npcs.exemplo"}
                    ],
                    "retomada": {
                        "modo": "gatilho_causal",
                        "gatilho": "nova evidência em cena",
                    },
                }
            },
        }
        self._write_yaml(root, "narrador/segredos/fonte.yaml", source)
        self._write_yaml(root, "estado/npcs/index.yaml", destination)
        self._write_yaml(root, continuidade_autoral.REGISTRY.as_posix(), registry)
        return registry

    def test_registro_canonico_cobre_fontes_sem_mutar_o_repo(self):
        paths = [
            ROOT / continuidade_autoral.REGISTRY,
            ROOT / "narrador/segredos/continuidade-lacunas.yaml",
        ]
        before = {path: path.read_bytes() for path in paths}
        result = continuidade_autoral.validate_repo(ROOT)
        after = {path: path.read_bytes() for path in paths}
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(before, after)

    def test_nova_chave_canonica_exige_classificacao_explicita(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            self._fixture(repo)
            source_path = repo / "narrador/segredos/fonte.yaml"
            source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
            source["fio_novo"] = {"verdade": "a decidir"}
            self._write_yaml(repo, "narrador/segredos/fonte.yaml", source)
            result = continuidade_autoral.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("fio_novo", result["erros"][0])

    def test_compromisso_aberto_exige_gatilho_causal(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            registry = copy.deepcopy(self._fixture(repo))
            registry["compromissos"]["fio_exemplo"]["retomada"] = {
                "modo": "nenhuma",
                "motivo": "esquecido",
            }
            self._write_yaml(repo, continuidade_autoral.REGISTRY.as_posix(), registry)
            result = continuidade_autoral.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("gatilho_causal", result["erros"][0])

    def test_destino_inexistente_falha_sem_criar_stub(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            registry = copy.deepcopy(self._fixture(repo))
            registry["compromissos"]["fio_exemplo"]["destinos_operacionais"][0][
                "chave"
            ] = "npcs.ausente"
            self._write_yaml(repo, continuidade_autoral.REGISTRY.as_posix(), registry)
            before = sorted(path.relative_to(repo) for path in repo.rglob("*") if path.is_file())
            result = continuidade_autoral.validate_repo(repo)
            after = sorted(path.relative_to(repo) for path in repo.rglob("*") if path.is_file())
        self.assertFalse(result["ok"])
        self.assertEqual(before, after)

    def test_lookup_exato_abre_so_registro_e_ancora(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            self._fixture(repo)
            result, sources = continuidade_autoral.lookup(repo, "exemplo")
        self.assertTrue(result["encontrado"])
        self.assertEqual(
            sources,
            [
                "narrador/continuidade-autoral.yaml",
                "narrador/segredos/fonte.yaml",
            ],
        )
        self.assertEqual(result["compromissos"][0]["id"], "fio_exemplo")

    def test_lookup_aproximado_sugere_mas_nao_escolhe_verdade(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            self._fixture(repo)
            result, sources = continuidade_autoral.lookup(repo, "fio exmplo")
        self.assertFalse(result["encontrado"])
        self.assertTrue(result["candidatos"])
        self.assertEqual(sources, ["narrador/continuidade-autoral.yaml"])


if __name__ == "__main__":
    unittest.main()
