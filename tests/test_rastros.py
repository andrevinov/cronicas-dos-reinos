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

import rastros


class RastrosRepositoryTest(unittest.TestCase):
    def test_repo_real_reflete_rastros_correntes_sem_exigir_indice_vazio(self):
        result = rastros.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        status = rastros.status(ROOT)
        self.assertEqual(result["quantidade_rastros"], status["quantidade_indexada"])
        self.assertGreaterEqual(status["quantidade_indexada"], 0)

    def test_indice_real_permanece_minimo(self):
        path = ROOT / rastros.INDEX
        self.assertLessEqual(path.stat().st_size, 1024)


class RastrosSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.y(
            "narrador/rastros/index.yaml",
            {
                "schema_indice_rastros": 1,
                "natureza": "reservado",
                "descricao": "Índice ativo de evidências observáveis.",
                "rastros": {},
            },
        )
        self.y(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "11 Eleasis, 1372 DR",
                "hora_aproximada": "09:00 de 11 Eleasis",
            },
        )
        self.y(
            "estado/estado-atual.yaml",
            {
                "schema_estado": 1,
                "natureza": "estado_atual",
                "localizacao": {
                    "cidade": "Ravens Bluff",
                    "area": "Ponte Baixa",
                    "ponto_exato": "beco atrás do armazém",
                },
            },
        )
        source = self.repo / "sessoes/009/fatos.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "fato: Um mensageiro deixou lama azul junto à porta dos fundos.\n",
            encoding="utf-8",
        )
        knowledge = self.repo / "personagens/jogador/conhecimento/ativo.yaml"
        knowledge.parent.mkdir(parents=True, exist_ok=True)
        knowledge.write_text("schema_conhecimento_ativo: 1\nitens: []\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def y(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def spec(
        self,
        *,
        access="automatico",
        scope="area",
        area="Ponte Baixa",
        point=None,
        expires=None,
        evidence="Um mensageiro deixou lama azul junto à porta dos fundos.",
    ):
        loc = {"escopo": scope, "cidade": "Ravens Bluff"}
        if scope in {"area", "ponto"}:
            loc["area"] = area
        if scope == "ponto":
            loc["ponto"] = point or "beco atrás do armazém"
        return {
            "nome": "Lama azul na porta",
            "tipo": "fisico",
            "manifestacao": "Há respingos de lama azul seca perto da porta dos fundos.",
            "fato_observavel": "Alguém passou recentemente pela porta dos fundos trazendo lama azul nas botas.",
            "localizacao": loc,
            "acesso": access,
            "persistencia": {
                "disponivel_de": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
                "expira_em": expires,
            },
            "tags": ["lama", "porta", "passagem"],
            "origem": {
                "estatuto": "fato_canonico",
                "fonte": "sessoes/009/fatos.yaml",
                "evidencia": evidence,
                "referencia": "mensageiro_desconhecido",
            },
        }

    def test_registrar_e_idempotente_e_nao_altera_conhecimento(self):
        before = (self.repo / "personagens/jogador/conhecimento/ativo.yaml").read_bytes()
        first = rastros.register(self.repo, self.spec())
        second = rastros.register(self.repo, self.spec())
        after = (self.repo / "personagens/jogador/conhecimento/ativo.yaml").read_bytes()
        self.assertTrue(first["criado"])
        self.assertFalse(second["criado"])
        self.assertEqual(first["rastro_id"], second["rastro_id"])
        self.assertEqual(before, after)

    def test_candidato_automatico_mesma_area_sem_abrir_fragmento(self):
        trace_id = rastros.register(self.repo, self.spec())["rastro_id"]
        result = rastros.candidates(self.repo)
        self.assertEqual([x["id"] for x in result["rastros"]], [trace_id])
        self.assertNotIn(f"narrador/rastros/itens/{trace_id}.yaml", result["fontes_lidas"])

    def test_area_errada_bloqueia_rastro(self):
        rastros.register(self.repo, self.spec())
        result = rastros.candidates(self.repo, area="Outro Bairro")
        self.assertEqual(result["rastros"], [])

    def test_investigacao_exige_consulta_explicita(self):
        trace_id = rastros.register(self.repo, self.spec(access="investigacao"))["rastro_id"]
        self.assertEqual(rastros.candidates(self.repo)["rastros"], [])
        result = rastros.candidates(self.repo, access="investigacao", tags=["lama"])
        self.assertEqual([x["id"] for x in result["rastros"]], [trace_id])

    def test_expirado_nao_e_candidato(self):
        rastros.register(
            self.repo,
            self.spec(expires={"data": "11 Eleasis, 1372 DR", "hora": "08:00"}),
        )
        self.assertEqual(rastros.candidates(self.repo)["rastros"], [])

    def test_mostrar_redige_origem_reservada(self):
        trace_id = rastros.register(self.repo, self.spec())["rastro_id"]
        result = rastros.show(self.repo, trace_id)
        self.assertFalse(result["origem_reservada_exposta"])
        self.assertNotIn("origem", result["resultado"])
        self.assertEqual(
            result["fontes_lidas"],
            ["narrador/rastros/index.yaml", f"narrador/rastros/itens/{trace_id}.yaml"],
        )

    def test_preparar_descoberta_so_propoe_delta(self):
        trace_id = rastros.register(self.repo, self.spec())["rastro_id"]
        before_knowledge = (self.repo / "personagens/jogador/conhecimento/ativo.yaml").read_bytes()
        before_index = (self.repo / rastros.INDEX).read_bytes()
        result = rastros.prepare_discovery(self.repo, trace_id)
        self.assertFalse(result["instalou_conhecimento"])
        self.assertEqual(result["delta_sugerido"]["alvo"], "conhecimento")
        self.assertEqual(result["delta_sugerido"]["op"], "registrar")
        self.assertEqual(
            result["delta_sugerido"]["valor"]["texto"],
            "Alguém passou recentemente pela porta dos fundos trazendo lama azul nas botas.",
        )
        self.assertEqual(before_knowledge, (self.repo / "personagens/jogador/conhecimento/ativo.yaml").read_bytes())
        self.assertEqual(before_index, (self.repo / rastros.INDEX).read_bytes())

    def test_evidencia_inexistente_rejeita_registro(self):
        with self.assertRaises(rastros.TraceError):
            rastros.register(self.repo, self.spec(evidence="Isto não existe na fonte."))

    def test_carta_nao_resolvida_nao_pode_ser_fonte(self):
        card = self.repo / "narrador/eventos/cartas/x.yaml"
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text("premissa: algo pode acontecer\n", encoding="utf-8")
        spec = self.spec(evidence="algo pode acontecer")
        spec["origem"]["fonte"] = "narrador/eventos/cartas/x.yaml"
        with self.assertRaises(rastros.TraceError):
            rastros.register(self.repo, spec)


if __name__ == "__main__":
    unittest.main()
