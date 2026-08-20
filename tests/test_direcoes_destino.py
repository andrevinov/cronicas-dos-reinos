from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

import arcos
import direcoes_destino


class DestinosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self._yaml(
            "narrador/arcos/index.yaml",
            {
                "schema_arcos": 1,
                "natureza": "roteador_reservado",
                "arcos": {
                    "parte_1": {
                        "titulo": "Parte 1",
                        "ordem": 1,
                        "arquivo": "narrador/arcos/parte_1.yaml",
                        "proximo": None,
                    }
                },
            },
        )
        self._yaml(
            "narrador/arcos/estado.yaml",
            {
                "schema_estado_arcos": 2,
                "natureza": "controle_reservado",
                "arco_atual": "parte_1",
                "estado": "ativo",
                "historico_transicoes": [],
            },
        )
        self._yaml(
            "narrador/arcos/parte_1.yaml",
            {
                "schema_arco": 4,
                "natureza": "reservado",
                "estatuto": "contrato_orquestrador_de_arco",
                "id": "parte_1",
                "titulo": "Parte 1",
                "principio": "Limitar o espaço estratégico sem escrever a história.",
                "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "fontes/inicio.md"},
                "termino": {"tipo": "marco_direcao", "marcador": "fim", "fonte": "fontes/fim.md"},
                "orquestracao": {
                    "fontes": {
                        "plano": {"tipo": "documento_reservado", "arquivo": "fontes/plano.md"}
                    },
                    "plano_mestre": {
                        "agente": "masao",
                        "objetivo": "preservar_ponte",
                        "referencia": "plano",
                    },
                },
                "habilitacoes": {
                    "politica_nao_listados": "bloqueados",
                    "antagonistas": [],
                    "aliados": [],
                    "direcoes": ["ponte"],
                },
                "linhas_operacionais": {},
            },
        )
        self._yaml(
            "narrador/direcoes/index.yaml",
            {
                "schema_direcoes": 1,
                "natureza": "reservado",
                "direcoes": {
                    "ponte": {
                        "nome": "Ponte",
                        "arquivo": "narrador/direcoes/ponte.yaml",
                        "avaliacao": {"cadencia": "amanhecer", "intervalo_dias": 2, "inicio": "12 Eleasis, 1372 DR"},
                        "ativacao": None,
                    },
                    "bairro": {
                        "nome": "Bairro",
                        "arquivo": "narrador/direcoes/bairro.yaml",
                        "avaliacao": {"cadencia": "amanhecer", "intervalo_dias": 7, "inicio": "12 Eleasis, 1372 DR"},
                        "ativacao": None,
                    },
                },
            },
        )
        self._yaml(
            "narrador/direcoes/estado.yaml",
            {
                "schema_estado_direcoes": 1,
                "natureza": "controle_reservado",
                "direcoes": {
                    "ponte": {"estado": "ativa", "marco_atual": "pistas", "marcos_concluidos": [], "historico_recente": []},
                    "bairro": {"estado": "latente", "marco_atual": "uso", "marcos_concluidos": [], "historico_recente": []},
                },
            },
        )
        self._direction("ponte", "Ponte", "pistas")
        self._direction("bairro", "Bairro", "uso")
        for rel, text in {
            "fontes/inicio.md": "inicio",
            "fontes/fim.md": "fim",
            "fontes/plano.md": "plano",
            "sessoes/010/consequencias.md": "Ren e os investigadores compararam manifestos incompatíveis e encontraram volumes impossíveis.",
        }.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _direction(self, did: str, name: str, milestone: str) -> None:
        self._yaml(
            f"narrador/direcoes/{did}.yaml",
            {
                "schema_direcao": 1,
                "natureza": "reservado",
                "id": did,
                "nome": name,
                "estatuto": "canonica_obrigatoria",
                "principio": "Destino obrigatório, caminho emergente.",
                "fontes_canonicas": ["fontes/plano.md"],
                "marcos": [
                    {
                        "id": milestone,
                        "ordem": 1,
                        "titulo": milestone.title(),
                        "fonte": "fontes/plano.md",
                        "evidencia": "plano",
                        "criterio_para_avancar": "Fatos canônicos acumulados sustentam a próxima etapa.",
                        "guardrails": ["Não avançar por conveniência."],
                    }
                ],
            },
        )

    def test_projecao_e_destino_nao_executavel(self):
        before = (self.repo / "narrador/direcoes/estado.yaml").read_bytes()
        result = direcoes_destino.project(self.repo, "ponte")
        self.assertTrue(result["permitido"])
        self.assertEqual(result["papel"], "restricao_destino")
        self.assertFalse(result["executavel"])
        self.assertEqual(result["marco_atual"]["id"], "pistas")
        self.assertIn("criterio_para_avancar", result["marco_atual"])
        self.assertIn("guardrails", result["marco_atual"])
        for forbidden in ("executor", "acao", "metodo", "alvo"):
            self.assertNotIn(forbidden, result)
        self.assertEqual(before, (self.repo / "narrador/direcoes/estado.yaml").read_bytes())

    def test_direcao_fora_do_arco_para_antes_do_fragmento(self):
        (self.repo / "narrador/direcoes/bairro.yaml").unlink()
        result = direcoes_destino.project(self.repo, "bairro")
        self.assertFalse(result["permitido"])
        self.assertEqual(result["motivo"], "direcao_bloqueada_pelo_arco")
        self.assertNotIn("narrador/direcoes/bairro.yaml", result["fontes_lidas"])

    def test_direcao_latente_nao_abre_fragmento(self):
        arc = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        arc["habilitacoes"]["direcoes"] = ["bairro"]
        self._yaml("narrador/arcos/parte_1.yaml", arc)
        (self.repo / "narrador/direcoes/bairro.yaml").unlink()
        result = direcoes_destino.project(self.repo, "bairro")
        self.assertFalse(result["permitido"])
        self.assertEqual(result["motivo"], "direcao_nao_ativa")
        self.assertNotIn("narrador/direcoes/bairro.yaml", result["fontes_lidas"])

    def test_fragmento_rejeita_executor_ou_acao(self):
        path = self.repo / "narrador/direcoes/ponte.yaml"
        data = yaml.safe_load(path.read_text())
        data["executor"] = "kurobane"
        self._yaml("narrador/direcoes/ponte.yaml", data)
        with self.assertRaises(direcoes_destino.DestinationDirectionError):
            direcoes_destino.project(self.repo, "ponte")

    def test_marco_rejeita_acao_concreta(self):
        path = self.repo / "narrador/direcoes/ponte.yaml"
        data = yaml.safe_load(path.read_text())
        data["marcos"][0]["acao"] = "Kurobane rouba o documento"
        self._yaml("narrador/direcoes/ponte.yaml", data)
        with self.assertRaises(direcoes_destino.DestinationDirectionError):
            direcoes_destino.project(self.repo, "ponte")

    def test_preparar_avanco_exige_evidencia_literal_e_nao_muta(self):
        before = (self.repo / "narrador/direcoes/estado.yaml").read_bytes()
        result = direcoes_destino.prepare_advance(
            self.repo,
            "ponte",
            source="sessoes/010/consequencias.md",
            evidence="compararam manifestos incompatíveis",
            note="A comparação sustenta o critério do marco.",
        )
        self.assertEqual(result["fato_base"]["fonte"], "sessoes/010/consequencias.md")
        self.assertFalse(result["mutou_estado"])
        self.assertEqual(before, (self.repo / "narrador/direcoes/estado.yaml").read_bytes())

    def test_evidencia_inexistente_falha(self):
        with self.assertRaises(direcoes_destino.DestinationDirectionError):
            direcoes_destino.prepare_advance(
                self.repo,
                "ponte",
                source="sessoes/010/consequencias.md",
                evidence="texto inventado que não está na fonte",
                note="não importa",
            )

    def test_direcao_nao_pode_provar_a_si_mesma(self):
        with self.assertRaises(direcoes_destino.DestinationDirectionError):
            direcoes_destino.prepare_advance(
                self.repo,
                "ponte",
                source="narrador/direcoes/ponte.yaml",
                evidence="Destino obrigatório",
                note="documento prescritivo não é fato-base",
            )

    def test_arco_rejeita_direcao_como_linha_operacional(self):
        arc = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        arc["habilitacoes"]["antagonistas"] = ["masao"]
        arc["linhas_operacionais"]["ponte"] = {
            "objetivo": "fazer_ponte",
            "executores": ["masao"],
            "referencia": "plano",
        }
        self._yaml("narrador/arcos/parte_1.yaml", arc)
        with self.assertRaises(arcos.ArcContractError):
            arcos.current(self.repo)


if __name__ == "__main__":
    unittest.main()
