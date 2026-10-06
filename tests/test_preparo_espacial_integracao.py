"""Porta pública em sandboxes: vínculo, envelope e retry sem desligar o mundo."""
from contextlib import ExitStack
from copy import deepcopy
import shutil
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

sys.path[:0] = [str(Path(__file__).parents[1] / "ferramentas")]
import cronica
import cronica_hotpath as hot
import locais
import memoria_cena as memory
import permanencia_espacial as stay
import preparo_espacial as retry
import transacoes
import context_and_memory as context_memory
import test_memoria_duravel_integracao as memory_fixtures
import test_locais as location_fixtures
import test_recompensas as reward_fixtures
import test_microeventos_transito as transit_fixtures
import test_permanencia_espacial as stay_fixtures


class SpatialPreparationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.f = memory_fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.registry = location_fixtures.LocalRegistrySyntheticTest()
        self.registry.repo = self.repo
        self.registry._write_registry({
            "abrigo_fixture": {"nome": "Abrigo da fixture", "aliases": ["abrigo"]},
            "circo_hooft": {"nome": "Circo da fixture", "aliases": ["circo"]},
        })
        self.registry._write_ecology(["abrigo_fixture", "circo_hooft"])
        time = yaml.safe_load((self.repo / "estado/tempo.yaml").read_text())
        self.f.write("estado/tempo.yaml", {"schema_tempo": 1, **time})
        reward_fixtures.RecompensasSinteticasTest._copy_base(self.repo)

    def prepare(self, scene, **kwargs):
        return cronica.prepare(self.repo, scene_id=scene, sidequest_signal=None,
                               memory_participants=self.f.people, **kwargs)

    def tx(self, tid, area=None):
        return {"id": tid, "jogador": "Ren entra no abrigo." if area else "Ren permanece atento.",
                "narracao": "Ren cruzou a porta do abrigo." if area else "O local continuou calmo.",
                "resumo": "Chegou ao abrigo." if area else "Nenhum incidente novo.",
                "modo": "exploração", "deltas": [] if area is None else [
                    {"alvo": "estado", "op": "set", "caminho": "localizacao.area", "valor": area}]}

    def location(self, area, local_id=None):
        doc = yaml.safe_load((self.repo / "estado/estado-atual.yaml").read_text())
        doc["localizacao"].update(area=area)
        if local_id is None:
            doc["localizacao"].pop("local_id", None)
        else:
            doc["localizacao"]["local_id"] = local_id
        self.f.write("estado/estado-atual.yaml", doc)

    def test_entrada_vincula_id_e_permanencia_herda_chegada_pendente_sem_mover_save(self):
        before = (self.repo / "estado/estado-atual.yaml").read_bytes()
        entered = self.prepare("chegada", place="abrigo", action="entrar", tier=1, danger="baixa")
        self.assertEqual(entered["ids"]["local"], "abrigo_fixture")
        self.assertLessEqual(memory.size(entered), 8192)
        tx = self.tx("chegada", "Interior do abrigo, junto à porta")
        cronica.conclude(self.repo, entered["ticket"], tx)
        self.assertEqual(before, (self.repo / "estado/estado-atual.yaml").read_bytes())
        self.assertEqual(locais.current(self.repo)["local_id"], "abrigo_fixture")
        self.assertIn(transacoes.PENDING_PATH.as_posix(), locais.current(self.repo)["fontes_lidas"])
        fixture = stay_fixtures.SpatialPermanenceTests()
        fixture.ecology = {}
        with ExitStack() as stack:
            # Produtores calmos controlados; resolução, reserva, memória e writer reais.
            for i, p in enumerate(fixture._patches()):
                if i not in {0, 2, 3}:
                    stack.enter_context(p)
            prepared = self.prepare("vigilia", permanence_local=True)
            self.assertEqual(prepared["ids"]["local"], "abrigo_fixture")
            self.assertTrue(prepared["reativa_espacial"])
            self.assertEqual(set(prepared[memory.KEY]["itens"]), set(self.f.people))
            self.assertLessEqual(memory.size(prepared), 8192)
            finished = cronica.conclude(self.repo, prepared["ticket"], self.tx("vigilia"))
            self.assertEqual(finished["fase"], "concluida")
            hashes = self.f.hashes()
            cronica.conclude(self.repo, prepared["ticket"], self.tx("vigilia"))
            self.assertEqual(hashes, self.f.hashes())

    def test_transito_real_entrega_baralho_e_tres_memorias_sem_aumentar_teto(self):
        deck = transit_fixtures.UrbanTransitDeckTest()
        deck.setUp()
        self.addCleanup(deck.tearDown)
        shutil.copytree(deck.repo, self.repo, dirs_exist_ok=True)
        before = self.f.hashes()
        compact = hot._decorate
        def redundant_envelope(result, *, reactive):
            prepared = compact(result, reactive=reactive)
            prepared["contrato_conclusao"] = hot._transaction_contract()
            return prepared
        # Contrafactual controlado: instruções estáticas anteriores disputavam
        # orçamento com o mesmo baralho e os mesmos participantes.
        with patch.object(hot, "_decorate", side_effect=redundant_envelope):
            with self.assertRaisesRegex(cronica.CronicaError, "memória indispensável"):
                self.prepare("travessia", urban_transit="ravens_bluff")
        out = self.prepare("travessia", urban_transit="ravens_bluff")
        after = self.f.hashes()
        self.assertEqual({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)},
                         {retry.PENDING.as_posix()})
        self.assertIn("transito_urbano", cronica.decode_ticket(out["ticket"]))
        self.assertEqual(set(out[memory.KEY]["itens"]), set(self.f.people))
        self.assertIn("medidores", out[memory.KEY]["itens"][self.f.people[0]])
        self.assertLessEqual(memory.size(out), 8192)
        self.assertNotIn("politica_civica_nv22", out["contrato_conclusao"])
        self.assertIn("contratos_complementares", out["contrato_conclusao"])
        finished = cronica.conclude(self.repo, out["ticket"], self.tx("travessia", "Via pública"))
        self.assertEqual(finished["fase"], "concluida")
        effective = transacoes.overlay_target(
            yaml.safe_load((self.repo / "estado/estado-atual.yaml").read_text()),
            transacoes.load_pending(self.repo), "estado")[0]
        self.assertIsNone(effective["localizacao"]["local_id"])
        hashes = self.f.hashes()
        cronica.conclude(self.repo, out["ticket"], self.tx("travessia", "Via pública"))
        self.assertEqual(hashes, self.f.hashes())

    def test_transito_preserva_promessa_e_medidores_no_envelope_suficiente(self):
        deck = transit_fixtures.UrbanTransitDeckTest()
        deck.setUp()
        self.addCleanup(deck.tearDown)
        shutil.copytree(deck.repo, self.repo, dirs_exist_ok=True)
        cronica.conclude(self.repo, self.f.token, self.f.promise())
        out = cronica.prepare(self.repo, scene_id="travessia-com-promessa", sidequest_signal=None,
                              urban_transit="ravens_bluff", memory_participants=self.f.people[:1])
        pack = out[memory.KEY]
        self.assertIn("Entregar o mapa a Silva.", memory.canonical(pack["itens"]["@compromissos"]))
        self.assertIn("memorias_importantes", pack["itens"][self.f.people[0]]["relacao"]["dados"])
        self.assertIn("medidores", pack["itens"][self.f.people[0]])
        self.assertLessEqual(memory.size(out), 8192)

    def test_falha_de_memoria_conserva_gatilho_e_reserva_em_retry(self):
        self.location("circo_hooft", "circo_hooft")
        neutral = self.prepare("fala-anterior")
        fixture = stay_fixtures.SpatialPermanenceTests()
        fixture.ecology = {"perfil": {"dummy": True}, "fontes_lidas": ["cenario/locais/ecologia.yaml"]}
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in fixture._patches()]
            with patch.object(context_memory, "attach", side_effect=memory.SceneMemoryError(
                    "preparo sem espaço para memória indispensável")):
                with self.assertRaisesRegex(cronica.CronicaError, "Retry espacial obrigatório"):
                    self.prepare("vigilia-falhou", permanence_local=True)
            reservation = (self.repo / stay.STATE).read_bytes()
            with self.assertRaisesRegex(cronica.CronicaError, "ticket neutro"):
                self.prepare("vigilia-falhou")
            with self.assertRaisesRegex(cronica.CronicaError, "novo cena-id"):
                self.prepare("novo-id")
            with self.assertRaisesRegex(cronica.CronicaError, "pendente"):
                cronica.conclude(self.repo, neutral["ticket"], self.tx("desvio"))
            with self.assertRaisesRegex(cronica.CronicaError, "pendente"):
                cronica.register(self.repo, neutral["ticket"], self.tx("desvio"))
            out = self.prepare("vigilia-falhou", permanence_local=True)
            self.assertEqual(reservation, (self.repo / stay.STATE).read_bytes())
            self.assertTrue(out["permanencia_espacial"]["reutilizado"])
            self.assertEqual(mocks[6].call_count, 1)  # micro.plan, congelado na primeira consulta
            self.assertEqual(mocks[9].call_count, 1)  # incidentes.plan
            cronica.conclude(self.repo, out["ticket"], self.tx("vigilia-concluida"))
        self.assertFalse((self.repo / retry.PENDING).exists())
        self.assertFalse(self.prepare("fala-breve")["reativa"])

    def test_prosa_desconhecida_nao_vira_restaurante_e_ambiguidade_e_explicita(self):
        self.location("Rua diante do restaurante da emboscada")
        with self.assertRaisesRegex(cronica.CronicaError, "local desconhecido"):
            self.prepare("local-sem-fonte", permanence_local=True)
        self.assertEqual(retry.load(self.repo)["tipo"], "permanencia")
        command = [sys.executable, str(Path(cronica.__file__).parent / "cronica.py"),
                   "--repo", str(self.repo), "preparar", "--cena-id", "outro-id",
                   "--sem-oportunidade-sidequest", "--sem-participantes"]
        cold = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(cold.returncode, 0)
        self.assertIn("ticket neutro", cold.stderr)
        self.registry._write_registry({
            "norte": {"nome": "Norte", "aliases": ["mercado"]},
            "sul": {"nome": "Sul", "aliases": ["mercado"]}})
        self.location("mercado")
        with self.assertRaisesRegex(cronica.CronicaError, "ambíguo"):
            self.prepare("local-sem-fonte", permanence_local=True)

    def test_delta_legado_de_saida_nao_herda_id_do_local_anterior(self):
        self.location("abrigo", "abrigo_fixture")
        neutral = self.prepare("saida-legada")
        # Simula buffer legado, anterior à compilação de vínculo espacial.
        record = {"sessao": 3, "deltas": self.tx("saida", "Circo da fixture")["deltas"]}
        with patch.object(transacoes, "load_pending", return_value=[record]):
            self.assertEqual(locais.current(self.repo)["local_id"], "circo_hooft")
        payload = cronica.decode_ticket(neutral["ticket"])
        compiled = retry.bind_location(self.repo, payload, self.tx("saida", "Via pública"))
        self.assertEqual(compiled["deltas"][-1]["valor"], None)

    def test_ticket_de_entrada_recusa_delta_para_outro_local(self):
        out = self.prepare("entrada-conflitante", place="abrigo", action="entrar", tier=1, danger="baixa")
        hashes = self.f.hashes()
        with self.assertRaisesRegex(cronica.CronicaError, "diverge"):
            cronica.conclude(self.repo, out["ticket"], self.tx("conflito", "circo_hooft"))
        after = self.f.hashes()
        self.assertEqual({p for p in hashes.keys() | after.keys() if hashes.get(p) != after.get(p)},
                         {retry.PENDING.as_posix()})
        with self.assertRaisesRegex(cronica.CronicaError, "pendente"):
            self.prepare("retirar-entrada")
        corrected = self.tx("conflito", "Abrigo da fixture")
        cronica.conclude(self.repo, out["ticket"], corrected)
        self.assertFalse((self.repo / retry.PENDING).exists())

    def test_identidade_espacial_do_elenco_usa_id_sem_fundir_pontos_exatos(self):
        a = {"localizacao": {"area": "Abrigo", "local_id": "abrigo_fixture", "ponto_exato": "porta"}}
        b = deepcopy(a)
        b["localizacao"]["area"] = "Abrigo da fixture"
        self.assertEqual(memory.location(a), memory.location(b))
        b["localizacao"]["ponto_exato"] = "andar superior"
        self.assertNotEqual(memory.location(a), memory.location(b))

    def test_desistencia_explicita_do_jogador_libera_operacao_e_conserva_reservas(self):
        self.location("circo_hooft", "circo_hooft")
        fixture = stay_fixtures.SpatialPermanenceTests()
        fixture.ecology = {"perfil": {"dummy": True}, "fontes_lidas": ["cenario/locais/ecologia.yaml"]}
        with ExitStack() as stack:
            for p in fixture._patches():
                stack.enter_context(p)
            with patch.object(context_memory, "attach", side_effect=memory.SceneMemoryError("sem espaço")):
                with self.assertRaises(cronica.CronicaError):
                    self.prepare("vigilia-desistida", permanence_local=True)
        reservation = (self.repo / stay.STATE).read_bytes()
        before = (self.repo / "estado/estado-atual.yaml").read_bytes()
        command = [sys.executable, str(Path(cronica.__file__).parent / "cronica.py"),
                   "--repo", str(self.repo), "preparar", "--cena-id", "fala-apos-desistencia",
                   "--sem-oportunidade-sidequest", "--sem-participantes",
                   "--abandonar-preparo-espacial", "O jogador desistiu da vigília e escolheu conversar."]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        audit = (self.repo / retry.CANCELLATIONS).read_bytes()
        self.assertIn(b'vigilia-desistida', audit)
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(audit, (self.repo / retry.CANCELLATIONS).read_bytes())
        self.assertEqual(before, (self.repo / "estado/estado-atual.yaml").read_bytes())
        self.assertEqual(reservation, (self.repo / stay.STATE).read_bytes())
        self.assertFalse((self.repo / retry.PENDING).exists())


if __name__ == "__main__":
    unittest.main()
