"""Personalidade na seleção NV03/NV05, sem nova chamada ou fonte canônica."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import memoria_relevante as relevant
import personalidade_decisoria as personality
import test_personalidade_decisoria as cases


def serialize(value, as_json=False):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n" if as_json
            else yaml.safe_dump(value, allow_unicode=True, sort_keys=False))


class PersonalitySelectionTest(unittest.TestCase):
    def test_campo_derivado_e_atomico_e_prioritario(self):
        doc = cases.document()
        base, fields = relevant._fields(doc)
        selected = [(path, value, rank) for path, value, rank in fields if path == (personality.KEY,)]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][2], 4)
        self.assertNotIn(personality.KEY, base["resultado"])
        self.assertNotIn(personality.KEY, doc["resultado"])

    def test_saida_npc_yamlejson_entrega_perfil_sem_alterar_argumento(self):
        doc = cases.document(tom_atual="Seca, após notícia recente.")
        original = deepcopy(doc)
        for as_json in (False, True):
            text, _ = relevant.fit(doc, 8192, as_json, serialize)
            out = json.loads(text) if as_json else yaml.safe_load(text)
            self.assertEqual(out["resultado"][personality.KEY], cases.profile())
            self.assertEqual(out["resultado"]["medidores"]["dados"]["tom_atual"], original["resultado"]["medidores"]["dados"]["tom_atual"])
            self.assertLessEqual(len(text.encode()), 8192)
        self.assertEqual(doc, original)

    def test_consulta_dirigida_recupera_derivado_e_sua_fonte(self):
        for path in ("/personalidade_decisoria/estavel/valores/texto", "/textura_narrativa/papel_conversacional/prioriza/1"):
            text, truncated = relevant.fit(relevant.request(cases.document(), campo=path), 8192, True, serialize)
            self.assertFalse(truncated)
            self.assertEqual(json.loads(text)["resultado"]["itens"][0]["valor"], cases.profile()["estavel"]["valores"]["texto"])

    def test_catalogo_inclui_perfil_para_aprofundamento(self):
        text, _ = relevant.fit(relevant.request(cases.document(), campos=True), 8192, True, serialize)
        entries = json.loads(text)["resultado"]["itens"]
        self.assertTrue(any(e["campo"] == "/personalidade_decisoria" and e["prioritario"] for e in entries))

    def test_sem_espaco_perfil_nao_e_cortado_nem_perde_limites(self):
        doc = cases.document()
        doc["resultado"]["medidores"]["dados"]["nome"] = "Nome sintético " * 5
        text, truncated = relevant.fit(doc, 1024, False, serialize)
        out = yaml.safe_load(text)
        self.assertLessEqual(len(text.encode()), 1024)
        self.assertTrue(truncated)
        self.assertNotIn(personality.KEY, out["resultado"])
        self.assertTrue(out.get("memoria_relevante", out["resultado"])["aprofundamento_necessario"])
        if "memoria_relevante" in out:
            self.assertIn("/personalidade_decisoria", [item["campo"] for item in out["memoria_relevante"]["pendentes"]])

    def test_derivacao_adiciona_zero_leituras(self):
        doc = cases.document()
        with patch.object(Path, "read_text", side_effect=AssertionError("I/O inesperado")):
            relevant.fit(doc, 8192, False, serialize)

    def test_fora_do_elenco_piloto_preserva_bytes_anteriores(self):
        doc = cases.document()
        doc["resultado"]["medidores"]["id"] = "outro_npc"
        new = relevant.fit(doc, 8192, False, serialize)
        with patch.object(personality, "enrich", side_effect=deepcopy):
            old = relevant.fit(doc, 8192, False, serialize)
        self.assertEqual(new, old)


class PersonalityMemoryIntegrationTest(unittest.TestCase):
    def setUp(self):
        import test_memoria_duravel_integracao as fixtures
        import cronica
        import contexto
        import consolidar
        import memoria_cena
        import retomada_cronica
        self.cronica, self.contexto = cronica, contexto
        self.consolidar, self.memory, self.resume = consolidar, memoria_cena, retomada_cronica
        self.f = fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.people = list(cases.roles())
        # IDs do piloto em cenário inteiramente temporário, não o estado vivo.
        for kind, plural in (("relacao", "relacoes"), ("npc", "npcs")):
            entries = {}
            for person, entry in cases.roles().items():
                path = f"estado/{plural}/{person}.yaml"
                payload = {"nome": entry["nome"]}
                if kind == "npc":
                    payload.update(medidores={"vinculo": 7, "confianca": 5, "risco_percebido": 1},
                                   tom_atual="Tom da fixture.", leitura_atual="Notícia recente da fixture.")
                self.f.write(path, {"id": person, f"schema_{kind}": 2, kind: payload})
                entries[person] = {"nome": entry["nome"], "aliases": [entry["nome"].split()[0]], "arquivo": path}
            self.f.write(f"estado/{plural}/index.yaml", {plural: entries, "quantidade": len(entries)})
        self.f.write("cenario/texturas/index.yaml", {"schema_texturas": 2, "npcs": cases.roles(), "locais": {}})

    def prepare(self, participants=None, **kwargs):
        return self.cronica.prepare(self.repo, scene_id="personalidade-fixture", sidequest_signal=None,
                                    memory_participants=participants, **kwargs)

    def promise(self):
        return self.f.tx("personalidade-promessa", "promessa", "Ren prometeu entregar o mapa a Silva antes do anoitecer.",
                         participantes=["ren", "silva_elkwood"], operacao="registrar",
                         compromisso={"tipo": "compromisso", "resumo": "Entregar o mapa a Silva."})

    def establish(self):
        prepared = self.prepare(["silva_elkwood"])
        self.cronica.conclude(self.repo, prepared["ticket"], self.promise())
        return prepared

    def test_preparar_publico_ja_entrega_perfil_sem_chamada_extra(self):
        before = self.f.hashes()
        prepared = self.prepare(["silva_elkwood"])
        item = prepared["memoria_cena"]["itens"]["silva_elkwood"]
        self.assertEqual(item[personality.KEY], cases.profile())
        self.assertEqual(self.f.hashes(), before)
        self.assertLessEqual(self.memory.size(prepared), 8192)
        self.assertLessEqual(self.memory.size(prepared["memoria_cena"]), 4096)
        self.assertNotIn(personality.KEY, self.memory.canonical(self.cronica.decode_ticket(prepared["ticket"])))

    def test_consulta_e_preparar_derivam_mesmo_perfil(self):
        prepared = self.prepare(["silva_elkwood"])
        doc = self.contexto.command_npc(self.repo, "silva_elkwood")
        text, _ = self.contexto.fit_budget(doc, 8192, False)
        self.assertEqual(yaml.safe_load(text)["resultado"][personality.KEY],
                         prepared["memoria_cena"]["itens"]["silva_elkwood"][personality.KEY])

    def test_reacao_pendente_muda_sem_reclassificar_personalidade(self):
        self.establish()
        first = self.prepare()["memoria_cena"]
        prepared = self.prepare()
        self.cronica.conclude(self.repo, prepared["ticket"], {
            "id": "noticia", "jogador": "Ren conta a notícia.", "narracao": "Silva ouviu a notícia e ficou mais séria.",
            "resumo": "Silva recebeu uma notícia.", "modo": "interação",
            "deltas": [{"alvo": "npc:silva_elkwood", "op": "set", "caminho": "tom_atual", "valor": "Séria após a notícia."}]})
        following = self.prepare(memory_base_in_context=first["recibo"])["memoria_cena"]
        old = first["itens"]["silva_elkwood"]
        new = following["itens"]["silva_elkwood"]
        self.assertEqual(new[personality.KEY], old[personality.KEY])
        self.assertEqual(new["medidores"]["dados"]["tom_atual"], "Séria após a notícia.")
        self.assertEqual(following["modo"], "delta")

    def test_promessa_sobrevive_junto_do_perfil_antes_e_depois_checkpoint(self):
        self.establish()
        before = self.prepare()["memoria_cena"]
        self.assertIn("Entregar o mapa a Silva.", self.memory.canonical(before))
        self.consolidar.consolidate(self.repo, "cena")
        cold = self.resume.current_snapshot(self.repo)["memoria_cena"]
        self.assertEqual(cold["modo"], "completa")
        self.assertEqual(cold["itens"]["silva_elkwood"][personality.KEY], cases.profile())
        self.assertIn("Entregar o mapa a Silva.", self.memory.canonical(cold))

    def test_retomada_cli_fria_em_subprocesso_yaml_json_e_sem_mutacao(self):
        self.establish()
        self.consolidar.consolidate(self.repo, "cena")
        before = self.f.hashes()
        for flags in ([], ["--json"]):
            run = subprocess.run([sys.executable, str(Path(self.contexto.__file__)), "--repo", str(self.repo),
                                  *flags, "retomada"], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            out = json.loads(run.stdout) if flags else yaml.safe_load(run.stdout)
            self.assertEqual(out["memoria_cena"]["itens"]["silva_elkwood"][personality.KEY], cases.profile())
            self.assertIn("Entregar o mapa a Silva.", run.stdout)
            self.assertLessEqual(len(run.stdout.encode()), 8192)
        self.assertEqual(self.f.hashes(), before)

    def test_tres_participantes_respeitam_orcamento_conjunto_e_lacunas(self):
        prepared = self.prepare(self.people)
        pack = prepared["memoria_cena"]
        self.assertLessEqual(self.memory.size(pack), 4096)
        self.assertLessEqual(self.memory.size(prepared), 8192)
        for person in self.people:
            item = pack["itens"][person]
            if personality.KEY in item:
                self.assertEqual(item[personality.KEY], cases.profile(person))
            else:
                self.assertTrue(item["memoria_relevante"]["aprofundamento_necessario"])

    def test_orcamento_compartilhado_prioriza_fatos_sobre_personalidade(self):
        doc = cases.document(nome="Silva da fixture")
        facts = {"vinculo": "Vínculo. " * 90,
                 "informacoes_recebidas": "Conhecimento. " * 65,
                 "acordos": "Promessa. " * 90}
        doc["resultado"]["relacao"] = {"id": "silva_elkwood", "dados": facts}
        pack = self.memory.project({"silva_elkwood": doc}, scope=self.memory.digest("disputa"), budget=4096)
        item = pack["itens"]["silva_elkwood"]
        self.assertEqual(item["relacao"]["dados"], facts)
        self.assertNotIn(personality.KEY, item)
        self.assertTrue(item["memoria_relevante"]["aprofundamento_necessario"])
        self.assertLessEqual(self.memory.size(pack), 4096)

    def test_aprofundamento_cli_de_perfil_derivado(self):
        run = subprocess.run([sys.executable, str(Path(self.contexto.__file__)), "--repo", str(self.repo),
                              "--json", "npc", "silva_elkwood", "--campo", "/personalidade_decisoria/estavel/valores/texto"],
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["resultado"]["itens"][0]["valor"], cases.profile()["estavel"]["valores"]["texto"])

    def test_fonte_muda_invalida_recibo_sem_reusar_personalidade_obsoleta(self):
        self.establish()
        first = self.prepare()["memoria_cena"]
        entry = cases.roles()
        entry["silva_elkwood"]["papel_conversacional"]["prioriza"][1] = "Prioridade diferente nesta fixture."
        self.f.write("cenario/texturas/index.yaml", {"schema_texturas": 2, "npcs": entry, "locais": {}})
        following = self.prepare(memory_base_in_context=first["recibo"])["memoria_cena"]
        profile = following["itens"]["silva_elkwood"][personality.KEY]
        self.assertIsNone(profile["estavel"]["valores"])
        self.assertIn("valores", profile["lacunas"])

    def test_medicao_de_bytes_isola_custo_sem_chamar_isso_de_tokens(self):
        reports = []
        for person in self.people:
            current = self.prepare([person])
            with patch.object(personality, "enrich", side_effect=deepcopy):
                previous = self.prepare([person])
            reports.append({"participante": person, "antes_bytes": self.memory.size(previous),
                            "depois_bytes": self.memory.size(current),
                            "mesmo_ticket": current["ticket"] == previous["ticket"], "tokens_nativos": None})
            self.assertEqual(current["ticket"], previous["ticket"])
            self.assertLessEqual(self.memory.size(current), 8192)
        self.establish()
        first = self.prepare()["memoria_cena"]
        following = self.prepare(memory_base_in_context=first["recibo"])["memoria_cena"]
        self.assertEqual(following["itens"], {})
        print("NV06_BYTES=" + json.dumps(reports, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
