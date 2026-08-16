from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "consolidar.py"
spec = importlib.util.spec_from_file_location("consolidar", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

import transacoes
import turno

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class ConsolidacaoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._make_repo()

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def _read_yaml(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _make_repo(self):
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "estado/relacoes").mkdir(parents=True)
        (self.repo / "estado/npcs").mkdir(parents=True)
        (self.repo / "personagens/jogador/conhecimento").mkdir(parents=True)

        self._write_yaml(
            "estado/estado-atual.yaml",
            {
                "campanha": {"status": "em_sessao", "sessao_atual": 3, "modo_de_cena_atual": "interacao"},
                "personagem": {
                    "nome": "Ren Kagehira",
                    "arquivo_ficha": "personagens/jogador/ficha.yaml",
                    "nivel": 6,
                    "classe": "Monge",
                    "subclasse": "Caminho da Sombra",
                },
                "localizacao": {
                    "plano": "Material",
                    "mundo": "Toril",
                    "continente": "Faerûn",
                    "regiao": "The Vast",
                    "cidade": "Ravens Bluff",
                    "area": "estrada",
                    "ponto_exato": "cerca",
                    "descricao_operacional": "Ren está junto à cerca.",
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
                    "ki": {"atuais": 5, "maximos": 6},
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
                "recursos_de_classe": {"ki": {"pontos_atuais": 5, "pontos_maximos": 6}},
                "equipamento": {"dinheiro": {"po": 45}},
                "progressao": {"metodo": "marcos narrativos"},
            },
        )
        self._write_yaml(
            "estado/relacoes/index.yaml",
            {"schema_relacoes": 2, "natureza": "indice_relacoes_atuais", "quantidade": 0, "relacoes": {}},
        )
        self._write_yaml(
            "estado/npcs/index.yaml",
            {"schema_npcs": 2, "natureza": "indice_medidores_npcs", "quantidade": 0, "npcs": {}},
        )
        self._write_yaml(
            "personagens/jogador/conhecimento/index.yaml",
            {"schema_conhecimento": 2, "natureza": "indice_fragmentado", "topicos": [], "sessoes": {}},
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
                    "ki": {"atuais": 5, "maximos": 6},
                    "ca": 17,
                    "dinheiro_po": 45,
                },
                "tempo": {"data": "7 Eleasis, 1372 DR", "hora_aproximada": "08:03"},
                "localizacao": {"area": "estrada", "ponto_exato": "cerca"},
            },
        )
        self._write_yaml(
            "runtime/cena.yaml",
            {
                "sessao": 3,
                "modo": "interacao",
                "localizacao": {"area": "estrada", "ponto_exato": "cerca"},
                "tempo": {"data": "7 Eleasis, 1372 DR", "hora_aproximada": "08:03"},
                "mecanica_imediata": {"pv": "45/45", "ki": "5/6", "ca": 17},
            },
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n\n---\n", encoding="utf-8")

    def register(self, txid: str, deltas, *, summary="Mudança de teste.", hidden=None, mode="interação"):
        return turno.register_transaction(
            self.repo,
            {
                "id": txid,
                "jogador": f"ação {txid}",
                "narracao": f"resultado {txid}",
                "resumo": summary,
                "modo": mode,
                "deltas": deltas,
                "rolagens_ocultas": hidden or [],
            },
        )

    def test_cena_aplica_recursos_espelha_ficha_e_limpa_buffer(self):
        self.register(
            "tx-recursos",
            [
                {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -2},
                {"alvo": "estado", "op": "inc", "caminho": "recursos.pontos_de_vida.atuais", "valor": -4},
                {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": "08:07"},
                {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "ponte"},
            ],
        )
        result = mod.consolidate(self.repo, "cena")
        self.assertFalse(result["recuperada"])
        self.assertEqual(len(result["transacoes"]), 1)

        state = self._read_yaml("estado/estado-atual.yaml")
        sheet = self._read_yaml("personagens/jogador/ficha.yaml")
        time = self._read_yaml("estado/tempo.yaml")
        runtime = self._read_yaml("runtime/contexto.yaml")
        self.assertEqual(state["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(sheet["recursos_de_classe"]["ki"]["pontos_atuais"], 3)
        self.assertEqual(state["recursos"]["pontos_de_vida"]["atuais"], 41)
        self.assertEqual(sheet["combate"]["pontos_de_vida"]["atuais"], 41)
        self.assertEqual(time["hora_aproximada"], "08:07")
        self.assertEqual(state["tempo"]["hora_aproximada"], "08:07")
        self.assertEqual(runtime["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(runtime["localizacao"]["ponto_exato"], "ponte")
        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")

        ledger = mod.load_ledger(self.repo, 3)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["transacoes"], ["tx-recursos"])

        again = mod.consolidate(self.repo, "cena")
        self.assertTrue(again["sem_pendencias"])
        self.assertEqual(self._read_yaml("estado/estado-atual.yaml")["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(len(mod.load_ledger(self.repo, 3)), 1)

    def test_entidades_conhecimento_e_consequencia_sao_consolidados(self):
        self.register(
            "tx-memorias",
            [
                {"alvo": "relacao:aliada_nova", "op": "set", "caminho": "nome", "valor": "Aliada Nova"},
                {"alvo": "relacao:aliada_nova", "op": "set", "caminho": "confianca", "valor": "moderada"},
                {"alvo": "npc:aliada_nova", "op": "set", "caminho": "nome", "valor": "Aliada Nova"},
                {"alvo": "npc:aliada_nova", "op": "set", "caminho": "medidores.confianca", "valor": 6},
                {
                    "alvo": "conhecimento",
                    "op": "registrar",
                    "valor": {"assunto": "porto", "texto": "há uma porta azul sob o cais"},
                },
                {
                    "alvo": "consequencia",
                    "op": "registrar",
                    "valor": {"titulo": "Porta observada", "descricao": "A porta azul pode voltar a importar."},
                },
            ],
            summary="Ren conhece uma nova aliada e descobre a porta azul.",
        )
        mod.consolidate(self.repo, "cena")

        relation = self._read_yaml("estado/relacoes/aliada_nova.yaml")
        npc = self._read_yaml("estado/npcs/aliada_nova.yaml")
        self.assertEqual(relation["relacao"]["confianca"], "moderada")
        self.assertEqual(npc["npc"]["medidores"]["confianca"], 6)
        self.assertTrue((self.repo / "historico/relacoes/aliada_nova.yaml").is_file())
        self.assertTrue((self.repo / "historico/npcs/aliada_nova.yaml").is_file())
        self.assertIn("aliada_nova", self._read_yaml("estado/relacoes/index.yaml")["relacoes"])
        self.assertIn("aliada_nova", self._read_yaml("estado/npcs/index.yaml")["npcs"])

        knowledge_index = self._read_yaml("personagens/jogador/conhecimento/index.yaml")
        incremental_index = knowledge_index["incrementais"]["3"]["index"]
        inc = self._read_yaml(incremental_index)
        knowledge_path = inc["fragmentos"][0]["arquivo"]
        self.assertIn("porta azul", (self.repo / knowledge_path).read_text(encoding="utf-8"))
        active = self._read_yaml("personagens/jogador/conhecimento/ativo.yaml")
        self.assertEqual(active["incrementais_recentes"][0]["transacao"], "tx-memorias")
        self.assertIn(
            "Porta observada",
            (self.repo / "sessoes/003/consequencias.md").read_text(encoding="utf-8"),
        )

    def test_queda_no_meio_da_instalacao_e_recuperada_sem_reaplicar_delta(self):
        self.register(
            "tx-crash",
            [
                {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -2},
                {"alvo": "estado", "op": "inc", "caminho": "recursos.dinheiro.po", "valor": -5},
            ],
        )
        plan = mod.build_plan(self.repo, "cena")
        journal = mod.stage_plan(self.repo, plan)
        with self.assertRaises(mod.ConsolidationError):
            mod.install_staged(self.repo, journal, fail_after=2)
        self.assertTrue((self.repo / mod.JOURNAL_PATH).exists())
        with self.assertRaises(transacoes.TransactionError):
            transacoes.load_pending(self.repo)

        recovered = mod.resume_consolidation(self.repo)
        self.assertEqual(recovered["transacoes"], ["tx-crash"])
        self.assertFalse((self.repo / mod.JOURNAL_PATH).exists())
        self.assertFalse((self.repo / mod.STAGE_DIR).exists())
        state = self._read_yaml("estado/estado-atual.yaml")
        self.assertEqual(state["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(state["recursos"]["dinheiro"]["po"], 40)
        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")
        self.assertEqual(len(mod.load_ledger(self.repo, 3)), 1)

    def test_delta_reservado_nunca_vaza_para_estado_publico(self):
        self.register(
            "tx-segredo",
            [
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "estado_narrativo.segredo",
                    "valor": "não revelar",
                    "visibilidade": "narrador",
                }
            ],
        )
        with self.assertRaises(mod.ConsolidationError):
            mod.build_plan(self.repo, "cena")
        self.assertNotIn("estado_narrativo", self._read_yaml("estado/estado-atual.yaml"))
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)

    def test_rolagens_ocultas_e_relogio_ficam_reservados(self):
        self.register(
            "tx-oculto",
            [
                {
                    "alvo": "relogio:busca_inimiga",
                    "op": "set",
                    "caminho": "progresso",
                    "valor": 2,
                    "visibilidade": "narrador",
                }
            ],
            hidden=["Percepção inimiga: d20 17 + 4 = 21."],
            summary="Ren segue sem perceber resposta inimiga.",
        )
        mod.consolidate(self.repo, "cena")
        clock = self._read_yaml("narrador/relogios/busca_inimiga.yaml")
        self.assertEqual(clock["relogio"]["progresso"], 2)
        hidden = (self.repo / "narrador/sessoes/003/rolagens-ocultas.md").read_text(encoding="utf-8")
        self.assertIn("Percepção inimiga", hidden)
        public = (self.repo / "sessoes/003/resumo.md").read_text(encoding="utf-8")
        self.assertNotIn("d20 17", public)
        self.assertNotIn("progresso", public)

    def test_fechamento_de_sessao_preserva_texto_manual_e_registra_progressao(self):
        (self.repo / "sessoes/003/experiencia.md").write_text(
            "# Experiência - Sessão 003\n\nTexto manual que não pode sumir.\n",
            encoding="utf-8",
        )
        self.register(
            "tx-progressao",
            [
                {
                    "alvo": "progressao",
                    "op": "registrar",
                    "valor": {"descricao": "Marco de teste alcançado sem aplicar nível automaticamente."},
                }
            ],
            summary="Ren alcança um marco de teste.",
        )
        mod.consolidate(self.repo, "sessao")
        experience = (self.repo / "sessoes/003/experiencia.md").read_text(encoding="utf-8")
        self.assertIn("Texto manual que não pode sumir.", experience)
        self.assertIn("Marco de teste", experience)
        alterations = self._read_yaml("sessoes/003/alteracoes-de-estado.yaml")
        self.assertEqual(alterations["status"], "encerrada")


if __name__ == "__main__":
    unittest.main()
