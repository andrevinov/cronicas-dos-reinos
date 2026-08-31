from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import consolidar
import correcao
import recompensas
import transacoes
import turno


class CanonicalCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._make_repo()

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def _read_yaml(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _make_repo(self) -> None:
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "estado/relacoes").mkdir(parents=True)
        (self.repo / "estado/npcs").mkdir(parents=True)
        (self.repo / "personagens/jogador/conhecimento").mkdir(parents=True)

        self._write_yaml(
            "estado/estado-atual.yaml",
            {
                "campanha": {
                    "status": "em_sessao",
                    "sessao_atual": 3,
                    "modo_de_cena_atual": "interacao",
                },
                "personagem": {
                    "nome": "Ren Kagehira",
                    "arquivo_ficha": "personagens/jogador/ficha.yaml",
                    "nivel": 6,
                    "classe": "Monge",
                    "subclasse": "Guerreiro das Sombras",
                },
                "localizacao": {
                    "plano": "Material",
                    "mundo": "Toril",
                    "continente": "Faerûn",
                    "regiao": "The Vast",
                    "cidade": "Ravens Bluff",
                    "area": "Rua da Cal",
                    "ponto_exato": "esquina",
                    "descricao_operacional": "Ren está na Rua da Cal.",
                },
                "tempo": {
                    "data_exata": "7 Eleasis, 1372 DR",
                    "hora_aproximada": "08:03",
                    "periodo_do_dia": "manhã",
                    "clima": "úmido",
                    "prazo_relevante": "nenhum",
                },
                "recursos": {
                    "pontos_de_vida": {"atuais": 45, "maximos": 45},
                    "focus": {"atuais": 5, "maximos": 6},
                    "classe_de_armadura": 17,
                    "deslocamento": "55 pés",
                    "dinheiro": {"po": 45},
                },
            },
        )
        self._write_yaml(
            "estado/tempo.yaml",
            {
                "data_atual": "7 Eleasis, 1372 DR",
                "hora_aproximada": "08:03",
                "periodo_do_dia": "manhã",
                "clima": "úmido",
                "prazo_relevante": "nenhum",
            },
        )
        self._write_yaml(
            "personagens/jogador/ficha.yaml",
            {
                "personagem": {"nome": "Ren Kagehira"},
                "identidade": {"nivel": 6},
                "combate": {
                    "classe_de_armadura": {"valor": 17},
                    "pontos_de_vida": {"atuais": 45, "maximos": 45},
                },
                "recursos_de_classe": {"focus": {"pontos_atuais": 5, "pontos_maximos": 6}},
                "equipamento": {"dinheiro": {"po": 45}},
                "progressao": {"metodo": "marcos narrativos"},
            },
        )
        self._write_yaml(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "natureza": "indice_relacoes_atuais",
                "quantidade": 0,
                "relacoes": {},
            },
        )
        self._write_yaml(
            "estado/npcs/index.yaml",
            {
                "schema_npcs": 2,
                "natureza": "indice_medidores_npcs",
                "quantidade": 0,
                "npcs": {},
            },
        )
        self._write_yaml(
            "personagens/jogador/conhecimento/index.yaml",
            {
                "schema_conhecimento": 2,
                "natureza": "indice_fragmentado",
                "topicos": [],
                "sessoes": {},
            },
        )
        self._write_yaml(
            "personagens/jogador/conhecimento/ativo.yaml",
            {
                "schema_conhecimento_ativo": 2,
                "natureza": "roteador_derivado",
                "sessao_atual_da_campanha": 3,
                "topicos_prioritarios": [],
                "descobertas_recentes": [],
            },
        )
        self._write_yaml(
            "runtime/contexto.yaml",
            {
                "sessao": {"numero": 3, "status": "em_sessao", "modo_de_cena": "interacao"},
                "personagem": {"nome": "Ren Kagehira", "nivel": 6},
                "recursos": {
                    "pv": {"atuais": 45, "maximos": 45},
                    "focus": {"atuais": 5, "maximos": 6},
                    "ca": 17,
                    "dinheiro_po": 45,
                },
                "tempo": {"data": "7 Eleasis, 1372 DR", "hora_aproximada": "08:03"},
                "localizacao": {"area": "Rua da Cal", "ponto_exato": "esquina"},
            },
        )
        self._write_yaml(
            "runtime/cena.yaml",
            {
                "sessao": 3,
                "modo": "interacao",
                "localizacao": {"area": "Rua da Cal", "ponto_exato": "esquina"},
                "tempo": {"data": "7 Eleasis, 1372 DR", "hora_aproximada": "08:03"},
                "mecanica_imediata": {"pv": "45/45", "focus": "5/6", "ca": 17},
            },
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n\n---\n", encoding="utf-8")
        shutil.copytree(ROOT / "narrador/recompensas", self.repo / "narrador/recompensas")

    def _register(self, txid: str, deltas, summary: str) -> None:
        turno.register_transaction(
            self.repo,
            {
                "id": txid,
                "jogador": f"ação {txid}",
                "narracao": f"resultado narrativo {txid}",
                "resumo": summary,
                "modo": "interacao",
                "deltas": deltas,
            },
        )

    def _wrong_scene(self) -> None:
        self._register(
            "tx-valida-anterior",
            [
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "recursos.dinheiro.po",
                    "valor": 44,
                }
            ],
            "Cena anterior válida ajustou o dinheiro.",
        )
        consolidar.consolidate(self.repo, "cena")
        self._register(
            "tx-cena-errada",
            [
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "localizacao.area",
                    "valor": "Casa de Iria Doss",
                },
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "localizacao.ponto_exato",
                    "valor": "quarto dos fundos",
                },
                {
                    "alvo": "relacao:sella_rove",
                    "op": "set",
                    "caminho": "nome",
                    "valor": "Sella Rove",
                },
                {
                    "alvo": "relacao:sella_rove",
                    "op": "set",
                    "caminho": "confianca",
                    "valor": "erroneamente_alta",
                },
            ],
            "A cena foi atribuída ao abrigo errado.",
        )
        consolidar.consolidate(self.repo, "cena")
        recompensas.ensure(self.repo, "refugio_errado", 1, "baixa")

    def _payload(self):
        return {
            "motivo": "A abertura foi associada ao refúgio errado durante a resolução da cena.",
            "retificacao": "O primeiro refúgio correto era o Lavadouro dos Três Tanques, ligado a Sella Rove.",
            "resumo": "Substitui Casa de Iria Doss pelo Lavadouro e corrige a relação com Sella.",
            "deltas": [
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "localizacao.area",
                    "valor": "Lavadouro dos Três Tanques",
                },
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "localizacao.ponto_exato",
                    "valor": "pátio coberto",
                },
                {
                    "alvo": "relacao:sella_rove",
                    "op": "set",
                    "caminho": "confianca",
                    "valor": "cautelosa",
                },
            ],
            "invalidar_mapas": ["refugio_errado"],
        }

    def test_preparar_e_estritamente_read_only(self):
        self._wrong_scene()
        watched = [
            "estado/estado-atual.yaml",
            "runtime/contexto.yaml",
            "runtime/eventos-pendentes.jsonl",
            "sessoes/003/transcricao.md",
            "narrador/recompensas/index.yaml",
            "narrador/recompensas/itens-index.yaml",
        ]
        before = {rel: (self.repo / rel).read_bytes() for rel in watched}
        result = correcao.prepare_correction(self.repo, "tx-cena-errada", self._payload())
        after = {rel: (self.repo / rel).read_bytes() for rel in watched}
        self.assertEqual(before, after)
        self.assertTrue(result["preparacao_id"].startswith("corr-prep-"))
        self.assertEqual(result["alvo_estado"], "consolidada")
        self.assertEqual(result["mapas"][0]["estado"], "remover")

    def test_correcao_substitui_estado_derivado_sem_apagar_historia_valida(self):
        self._wrong_scene()
        payload = self._payload()
        prepared = correcao.prepare_correction(self.repo, "tx-cena-errada", payload)

        with mock.patch.object(
            correcao,
            "_force_checkpoint",
            side_effect=lambda repo: consolidar.consolidate(repo, "cena"),
        ):
            result = correcao.apply_correction(
                self.repo,
                "tx-cena-errada",
                prepared["preparacao_id"],
                payload,
            )

        state = self._read_yaml("estado/estado-atual.yaml")
        runtime = self._read_yaml("runtime/contexto.yaml")
        relation = self._read_yaml("estado/relacoes/sella_rove.yaml")
        reward_index = recompensas.load_index(self.repo)
        item_index = recompensas.load_item_index(self.repo)

        self.assertEqual(state["localizacao"]["area"], "Lavadouro dos Três Tanques")
        self.assertEqual(state["localizacao"]["ponto_exato"], "pátio coberto")
        self.assertEqual(runtime["localizacao"]["area"], "Lavadouro dos Três Tanques")
        self.assertEqual(runtime["localizacao"]["ponto_exato"], "pátio coberto")
        self.assertEqual(relation["relacao"]["confianca"], "cautelosa")
        self.assertEqual(state["recursos"]["dinheiro"]["po"], 44)
        self.assertNotIn("refugio_errado", reward_index["mapas"])
        self.assertFalse(any(meta.get("local_id") == "refugio_errado" for meta in item_index["recompensas"].values()))
        self.assertFalse((self.repo / "narrador/recompensas/mapas/refugio_errado.yaml").exists())

        transcript = (self.repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8")
        self.assertIn("resultado narrativo tx-valida-anterior", transcript)
        self.assertIn("resultado narrativo tx-cena-errada", transcript)
        self.assertIn("CORREÇÃO CANÔNICA", transcript)
        self.assertIn("não representa um novo acontecimento do mundo", transcript)

        corrections = correcao._read_jsonl(self.repo / "sessoes/003/correcoes.jsonl")
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0]["corrige"], "tx-cena-errada")
        self.assertTrue(corrections[0]["nao_e_evento_novo"])
        self.assertEqual(corrections[0]["mapas_invalidados"], ["refugio_errado"])
        self.assertFalse((self.repo / correcao.JOURNAL).exists())
        self.assertEqual(result["mapas_invalidados"], ["refugio_errado"])
        self.assertTrue(correcao.check(self.repo)["ok"])

    def test_retry_de_correcao_e_idempotente(self):
        self._wrong_scene()
        payload = self._payload()
        prepared = correcao.prepare_correction(self.repo, "tx-cena-errada", payload)
        with mock.patch.object(
            correcao,
            "_force_checkpoint",
            side_effect=lambda repo: consolidar.consolidate(repo, "cena"),
        ):
            correcao.apply_correction(
                self.repo, "tx-cena-errada", prepared["preparacao_id"], payload
            )
            second = correcao.apply_correction(
                self.repo, "tx-cena-errada", prepared["preparacao_id"], payload
            )
        self.assertTrue(second["ja_aplicada"])
        self.assertEqual(len(correcao._read_jsonl(self.repo / "sessoes/003/correcoes.jsonl")), 1)
        transcript = (self.repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8")
        self.assertEqual(transcript.count("CORREÇÃO CANÔNICA"), 1)

    def test_nao_corrige_evento_antigo_se_ha_turno_posterior(self):
        self._wrong_scene()
        self._register(
            "tx-posterior",
            [{"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "rua"}],
            "Turno posterior depende do estado atual.",
        )
        with self.assertRaisesRegex(correcao.CorrectionError, "ponta causal"):
            correcao.prepare_correction(self.repo, "tx-cena-errada", self._payload())

    def test_mapas_descobertos_ou_planejados_nao_sao_apagados(self):
        self._wrong_scene()
        index = recompensas.load_index(self.repo)
        meta = index["mapas"]["refugio_errado"]
        map_path = self.repo / meta["arquivo"]
        data = yaml.safe_load(map_path.read_text(encoding="utf-8"))
        data["recompensas"][0]["estado"] = "descoberto"
        map_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(correcao.CorrectionError, "destrutiva"):
            correcao.prepare_correction(self.repo, "tx-cena-errada", self._payload())

    def test_correcao_rejeita_inc_append_e_registrar(self):
        self._wrong_scene()
        payload = self._payload()
        payload["deltas"] = [
            {
                "alvo": "estado",
                "op": "inc",
                "caminho": "recursos.dinheiro.po",
                "valor": 1,
            }
        ]
        with self.assertRaisesRegex(correcao.CorrectionError, "set/remove"):
            correcao.prepare_correction(self.repo, "tx-cena-errada", payload)


if __name__ == "__main__":
    unittest.main()
