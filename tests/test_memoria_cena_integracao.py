"""Preparar/concluir/retomar reais sobre fixtures temporárias, nunca o save vivo."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "ferramentas"))
import yaml
import cronica
import contexto
import consolidar
import memoria_cena as memory
import retomada_cronica
import checkpoint
import transacoes
import test_memoria_duravel_integracao as fixtures


class SceneMemoryIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.scene = "memoria-fixture"
        self.people = self.f.people
        for npc in self.people:
            path = f"estado/relacoes/{npc}.yaml"
            doc = yaml.safe_load((self.repo / path).read_text())
            doc["relacao"].update(personalidade="Prática e leal, sem onisciência.",
                                   vinculo="Ren a ajudou durante uma noite difícil.")
            self.f.write(path, doc)

    def prepare(self, participants=None, **kwargs):
        return cronica.prepare(self.repo, scene_id=self.scene, sidequest_signal=None,
                               memory_participants=participants, **kwargs)

    def simple(self, tid="conversa", deltas=None):
        return {"id": tid, "jogador": "Ren escuta sua aliada.",
                "narracao": "A aliada se sentou ao lado dele para continuar a conversa.",
                "resumo": "Continuaram a conversa.", "modo": "interação", "deltas": deltas or []}

    def establish(self, participants=None):
        prepared = self.prepare(self.people[:1] if participants is None else participants)
        cronica.conclude(self.repo, prepared["ticket"], self.simple())
        return prepared

    def test_preparar_entrega_personalidade_relacao_sem_consulta_extra_do_narrador(self):
        before = self.f.hashes()
        out = self.prepare(["silva_fixture"])
        self.assertEqual(before, self.f.hashes())
        self.assertFalse(out["reativa"])
        rel = out[memory.KEY]["itens"]["silva_fixture"]["relacao"]["dados"]
        self.assertIn("personalidade", rel)
        self.assertIn("vinculo", rel)
        self.assertLessEqual(memory.size(out), 8192)

    def test_elenco_e_promessa_ficam_visiveis_antes_do_checkpoint(self):
        out = self.prepare(["silva_fixture"])
        before = self.f.hashes()
        cronica.conclude(self.repo, out["ticket"], self.f.promise())
        after = self.f.hashes()
        self.assertEqual({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)},
                         {"runtime/eventos-pendentes.jsonl", "sessoes/003/transcricao.md"})
        following = self.prepare()[memory.KEY]
        self.assertIn("silva_fixture", following["itens"])
        self.assertIn("Entregar o mapa a Silva.", memory.canonical(following))
        self.assertIn("@compromissos", following["itens"])

    def test_retomada_fria_reconstroi_em_outro_processo_apos_checkpoint(self):
        out = self.prepare(["silva_fixture"])
        cronica.conclude(self.repo, out["ticket"], self.f.promise())
        consolidar.consolidate(self.repo, "cena")
        script = "import json,sys; from pathlib import Path; import retomada_cronica; print(json.dumps(retomada_cronica.current_snapshot(Path(sys.argv[1])),ensure_ascii=False))"
        completed = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,sys.argv.pop(1)); " + script,
                                    str(Path(cronica.__file__).parent), str(self.repo)],
                                   check=True, capture_output=True, text=True)
        cold = json.loads(completed.stdout)
        self.assertEqual(cold[memory.KEY]["modo"], "completa")
        self.assertIn("silva_fixture", cold[memory.KEY]["itens"])
        self.assertIn("Entregar o mapa a Silva.", completed.stdout)
        self.assertFalse(cold["transcricao_lida"])
        self.assertLessEqual(memory.size(cold), 8192)

    def test_confianca_efetiva_e_aplicada_antes_da_projecao(self):
        out = self.prepare(["silva_fixture"])
        cronica.conclude(self.repo, out["ticket"], self.f.relationship_tx())
        npc = self.prepare()[memory.KEY]["itens"]["silva_fixture"]
        self.assertEqual(npc["medidores"]["dados"]["medidores"]["confianca"], 6)
        self.assertIn("dialogo_relacional", npc)

    def test_rumor_continua_rumor_e_nao_e_transferido_ao_outro_npc(self):
        out = self.prepare(["silva_fixture", "nera_fixture"])
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        tx = self.f.tx("rumor-cena", "informacao", text, emissor="ren", destinatario="silva_fixture",
                       canal="presencial", estatuto="rumor")
        cronica.conclude(self.repo, out["ticket"], tx)
        pack = self.prepare()[memory.KEY]
        self.assertIn('"estatuto":"rumor"', memory.canonical(pack["itens"]["silva_fixture"]))
        self.assertNotIn("barqueiro", memory.canonical(pack["itens"]["nera_fixture"]))

    def test_recibo_so_e_usado_quando_base_foi_declarada_no_contexto(self):
        self.establish()
        first = self.prepare()[memory.KEY]
        following = self.prepare(memory_base_in_context=memory.canonical(first["recibo"]))[memory.KEY]
        self.assertEqual(following["modo"], "delta")
        self.assertEqual(following["itens"], {})
        self.assertEqual(self.prepare()[memory.KEY]["modo"], "completa")

    def test_cache_no_disco_nao_prova_contexto(self):
        self.establish()
        before = self.prepare()[memory.KEY]
        (self.repo / "runtime/cache-memoria-cena.json").write_text(json.dumps(before))
        self.assertEqual(self.prepare()[memory.KEY]["modo"], "completa")
        self.assertEqual(retomada_cronica.current_snapshot(self.repo)[memory.KEY]["modo"], "completa")

    def test_alteracao_de_um_fragmento_reenvia_apenas_ele(self):
        self.establish(["silva_fixture", "nera_fixture"])
        first = self.prepare()[memory.KEY]
        path = "estado/relacoes/silva_fixture.yaml"
        doc = yaml.safe_load((self.repo / path).read_text())
        doc["relacao"]["vinculo"] = "Um novo fato mudou este vínculo."
        self.f.write(path, doc)
        following = self.prepare(memory_base_in_context=first["recibo"])[memory.KEY]
        self.assertEqual(following["modo"], "delta")
        self.assertEqual(set(following["itens"]), {"silva_fixture"})

    def test_nao_abre_outros_npcs_transcricao_ou_dominios_secretos(self):
        base = self.prepare(["silva_fixture"])
        reads = []
        original = Path.read_text
        def read(path, *args, **kwargs):
            reads.append(path.relative_to(self.repo).as_posix())
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            memory.attach(self.repo, base, decode_ticket=cronica.decode_ticket,
                          encode_ticket=cronica.encode_ticket, participants=["silva_fixture"])
        self.assertFalse(any("nera_fixture.yaml" in p or "luath_fixture.yaml" in p
                             or "transcricao" in p or p.startswith(("narrador/", "historico/")) for p in reads))
        self.assertEqual(len(reads), len(set(reads)))

    def test_mencao_tag_e_fato_relacional_nao_fabricam_presenca(self):
        out = self.prepare()
        payload = cronica.decode_ticket(out["ticket"])
        payload["cena"]["context_tags"] = ["pessoa:silva_fixture"]
        out["ticket"], _ = cronica.encode_ticket(payload)
        result = memory.attach(self.repo, out, decode_ticket=cronica.decode_ticket,
                               encode_ticket=cronica.encode_ticket)
        self.assertIsNone(result[memory.KEY]["participantes"])
        self.assertTrue(result[memory.KEY]["aprofundamento_necessario"])

    def test_cena_solo_e_diferente_de_elenco_desconhecido(self):
        out = self.establish([])
        self.assertEqual(out[memory.KEY]["itens"], {})
        following = self.prepare()[memory.KEY]
        self.assertEqual(following["itens"], {})
        self.assertFalse(following["aprofundamento_necessario"])

    def test_cena_nova_nao_herda_elenco_antigo(self):
        self.establish()
        self.scene = "outra-cena"
        out = self.prepare()[memory.KEY]
        self.assertIsNone(out["participantes"])

    def test_deslocamento_nao_teletransporta_aliado_na_retomada(self):
        self.establish()
        out = self.prepare()
        tx = self.simple("mudanca", [{"alvo": "estado", "op": "set",
                                       "caminho": "localizacao.area", "valor": "porto"}])
        cronica.conclude(self.repo, out["ticket"], tx)
        cold = retomada_cronica.current_snapshot(self.repo)[memory.KEY]
        self.assertIsNone(cold["participantes"])

    def test_retry_antigo_nao_ressuscita_elenco_apos_saida(self):
        old = self.establish()
        out = self.prepare([])
        cronica.conclude(self.repo, out["ticket"], self.simple("saida"))
        before = self.f.hashes()
        cronica.conclude(self.repo, old["ticket"], self.simple())
        self.assertEqual(before, self.f.hashes())
        self.assertEqual(self.prepare()[memory.KEY]["itens"], {})

    def test_retry_frio_nao_duplica_elenco_ou_fatos(self):
        old = self.prepare(["silva_fixture"])
        tx = self.f.promise()
        cronica.conclude(self.repo, old["ticket"], tx)
        consolidar.consolidate(self.repo, "cena")
        before = self.f.hashes()
        cronica.conclude(self.repo, old["ticket"], tx)
        self.assertEqual(before, self.f.hashes())

    def test_compromisso_cumprido_some_da_parte_ativa_sem_apagar_memoria(self):
        out = self.prepare(["silva_fixture"])
        cronica.conclude(self.repo, out["ticket"], self.f.promise())
        out = self.prepare()
        cronica.conclude(self.repo, out["ticket"], self.f.complete("cumprir"))
        pack = self.prepare()[memory.KEY]
        self.assertNotIn("@compromissos", pack["itens"])
        self.assertIn("cumprir", memory.canonical(pack))

    def test_nova_hora_reclassifica_prazo_sem_executar_compromisso(self):
        out = self.prepare(["silva_fixture"])
        tx = self.f.promise()
        tx["memoria"]["fatos"][0]["compromisso"]["janela"] = {
            "inicio": {"data": "7 Eleasis, 1372 DR", "hora": "09:00"},
            "fim": {"data": "7 Eleasis, 1372 DR", "hora": "10:00"}}
        cronica.conclude(self.repo, out["ticket"], tx)
        self.assertIn("futuro", memory.canonical(self.prepare()[memory.KEY]))
        out = self.prepare()
        cronica.conclude(self.repo, out["ticket"], self.simple("hora", [
            {"alvo": "tempo", "op": "instante", "valor": {"data": "7 Eleasis, 1372 DR", "hora": "09:10"}}]))
        pack = self.prepare()[memory.KEY]
        self.assertIn("em_janela", memory.canonical(pack))
        self.assertIn("@compromissos", pack["itens"])

    def test_elenco_desconhecido_ou_ambiguo_falha_sem_escrita(self):
        before = self.f.hashes()
        with self.assertRaises(ValueError):
            self.prepare(["silvva"])
        self.assertEqual(before, self.f.hashes())

    def test_barreira_de_mundo_continua_antes_de_qualquer_leitura_de_memoria(self):
        gate = {"fase": "bloqueada_pendencias_mundo"}
        with patch.object(cronica._pending_gate, "prepare_gate", return_value=gate), \
                patch.object(cronica._pressure52, "routable_operation_pendings", return_value=None), \
                patch.object(memory, "load_scene", side_effect=AssertionError("leitura indevida")):
            self.assertEqual(self.prepare(["silva_fixture"]), gate)

    def test_parser_adiciona_opcoes_na_mesma_porta_e_nao_confunde_gatilhos(self):
        args = cronica.build_parser().parse_args(["preparar", "--cena-id", "c", "--sem-oportunidade-sidequest",
                                                 "--participante", "silva_fixture"])
        self.assertEqual(args.participante, ["silva_fixture"])
        self.assertFalse(args.npc)

    def test_cli_publica_imprime_pacote_no_mesmo_preparar(self):
        completed = subprocess.run([sys.executable, str(Path(cronica.__file__)), "--repo", str(self.repo),
                                    "preparar", "--cena-id", self.scene, "--sem-oportunidade-sidequest",
                                    "--participante", "silva_fixture"], check=True, capture_output=True, text=True)
        out = yaml.safe_load(completed.stdout)
        self.assertIn("silva_fixture", out[memory.KEY]["itens"])
        self.assertLessEqual(len(completed.stdout.encode()), 8192)

    def test_metadados_de_ticket_nao_repetem_biografia_ou_memorias(self):
        out = self.prepare(["silva_fixture"])
        payload = cronica.decode_ticket(out["ticket"])
        self.assertIn(memory.TICKET_KEY, payload)
        self.assertNotIn("Prática e leal", memory.canonical(payload))
        self.assertNotIn(memory.TICKET_KEY, cronica.decode_ticket(cronica._base_token(payload)))

    def test_contexto_retomada_inclui_memoria_sem_compactacao_cega(self):
        # A porta legada exige handoff/índice, criados pelo checkpoint existente.
        checkpoint.refresh_memory(self.repo, "cena")
        self.establish()
        direct = contexto.command_resume(self.repo)
        self.assertIn("silva_fixture", direct[memory.KEY]["itens"])
        for option in ([], ["--json"]):
            completed = subprocess.run([sys.executable, str(Path(contexto.__file__)), "--repo", str(self.repo),
                                        *option, "retomada"], check=True, capture_output=True, text=True)
            output = yaml.safe_load(completed.stdout)
            self.assertEqual(output[memory.KEY]["modo"], "completa")
            self.assertIn("silva_fixture", output[memory.KEY]["itens"])
            self.assertLessEqual(len(completed.stdout.encode()), 8192)

    def test_elenco_final_desconhecido_falha_antes_do_writer(self):
        out = self.prepare(["silva_fixture"])
        selected = deepcopy(cronica.decode_ticket(out["ticket"])[memory.TICKET_KEY]["elenco"])
        selected["participantes"] = ["npc_inventado"]
        tx = self.simple("invalido", [{"alvo":"estado", "op":"set", "caminho":memory.CAST_PATH, "valor":selected}])
        before = self.f.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, out["ticket"], tx)
        self.assertEqual(before, self.f.hashes())

    def test_local_resultante_e_elenco_explicitamente_narrado_podem_coexistir(self):
        out = self.prepare(["silva_fixture"])
        selected = deepcopy(cronica.decode_ticket(out["ticket"])[memory.TICKET_KEY]["elenco"])
        selected["local"]["ponto_exato"] = "junto ao portão"
        tx = self.simple("caminhada", [
            {"alvo":"estado", "op":"set", "caminho":"localizacao.ponto_exato", "valor":"junto ao portão"},
            {"alvo":"estado", "op":"set", "caminho":memory.CAST_PATH, "valor":selected}])
        tx["narracao"] = "Ren e Silva caminharam juntos e pararam junto ao portão."
        cronica.conclude(self.repo, out["ticket"], tx)
        cold = retomada_cronica.current_snapshot(self.repo)
        self.assertIn("silva_fixture", cold[memory.KEY]["itens"])
        self.assertEqual(cold["agora"]["local"]["ponto_exato"], "junto ao portão")

    def test_preparo_obsoleto_nao_sobrescreve_elenco_mais_recente(self):
        self.establish()
        old = self.prepare(["nera_fixture"])
        newer = self.prepare(["luath_fixture"])
        cronica.conclude(self.repo, newer["ticket"], self.simple("elenco-novo"))
        before = self.f.hashes()
        with self.assertRaisesRegex(ValueError, "obsoleta"):
            cronica.conclude(self.repo, old["ticket"], self.simple("outra-transacao"))
        self.assertEqual(before, self.f.hashes())
        self.assertEqual(set(self.prepare()[memory.KEY]["itens"]), {"luath_fixture"})

    def test_preparo_obsoleto_continua_bloqueado_apos_checkpoint(self):
        self.establish()
        old = self.prepare(["nera_fixture"])
        newer = self.prepare([])
        cronica.conclude(self.repo, newer["ticket"], self.simple("saida-recente"))
        consolidar.consolidate(self.repo, "cena")
        before = self.f.hashes()
        with self.assertRaisesRegex(ValueError, "obsoleta"):
            cronica.conclude(self.repo, old["ticket"], self.f.relationship_tx())
        self.assertEqual(before, self.f.hashes())

    def test_preparo_antigo_com_elenco_explicito_tambem_e_revalidado(self):
        self.establish()
        old = self.prepare()
        selected = deepcopy(cronica.decode_ticket(old["ticket"])[memory.TICKET_KEY]["elenco"])
        selected["participantes"] = ["nera_fixture"]
        newer = self.prepare([])
        cronica.conclude(self.repo, newer["ticket"], self.simple("todos-sairam"))
        tx = self.simple("outro-id", [{"alvo": "estado", "op": "set", "caminho": memory.CAST_PATH,
                                       "valor": selected}])
        before = self.f.hashes()
        with self.assertRaisesRegex(ValueError, "obsoleta"):
            cronica.conclude(self.repo, old["ticket"], tx)
        self.assertEqual(before, self.f.hashes())

    def test_retry_com_id_derivado_preserva_identidade_depois_de_mudar_elenco(self):
        old = self.prepare(["silva_fixture"])
        tx = self.f.promise()
        tx.pop("id", None)
        cronica.conclude(self.repo, old["ticket"], tx)
        newer = self.prepare([])
        cronica.conclude(self.repo, newer["ticket"], self.simple("saida-apos-promessa"))
        consolidar.consolidate(self.repo, "cena")
        before = self.f.hashes()
        cronica.conclude(self.repo, old["ticket"], tx)
        self.assertEqual(before, self.f.hashes())


if __name__ == "__main__":
    unittest.main()
