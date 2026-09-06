"""Critérios de personalidade sobre snapshot isolado; nunca ações da campanha."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import personalidade_decisoria as personality

FIXTURE = Path(__file__).parent / "fixtures/personalidade-papeis.yaml"


def roles():
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["npcs"]


def profile(person="silva_elkwood"):
    return personality.project(person, roles()[person]["papel_conversacional"])


def document(person="silva_elkwood", **state):
    return {"consulta": {"comando": "npc", "termo": person}, "fontes": ["cenario/texturas/index.yaml"],
            "resultado": {"encontrado": True, "medidores": {"id": person, "dados": state},
                          "textura_narrativa": roles()[person]}}


def option(oid, supports=None, opposes=None, **gates):
    return {"id": oid, "conduta": oid.replace("_", " "),
            "favorece": {key: reason for key, reason in (supports or {}).items()},
            "contraria": {key: reason for key, reason in (opposes or {}).items()},
            "viabilidade": {key: gates.get(key, True) for key in personality.GATES}}


def dilemma():
    # Mesmo problema e mesmas alternativas: uma pessoa conhecida chega abalada.
    # Relações entre alternativa e critério são anotadas, não inferidas pela IA.
    return [option("oferecer_abrigo", {"cuidado_concreto": "Dar água e lugar para descansar.",
                                       "rotina_segura": "Reduzir exposição imediata."}),
            option("escutar_e_combinar", {"reciprocidade": "Perguntar também o que a pessoa quer.",
                                           "franqueza_pessoal": "Expor seu próprio limite com franqueza."}),
            option("preservar_prova", {"prova_utilizavel": "Preservar o documento trazido.",
                                       "perguntas_decisivas": "Perguntar somente o necessário para a guarda."})]


class PersonalityProjectionTest(unittest.TestCase):
    def test_tres_perfis_curados_tem_seis_eixos_e_origem_literal(self):
        for person, entry in roles().items():
            with self.subTest(person=person):
                role = entry["papel_conversacional"]
                out = personality.project(person, role)
                self.assertEqual(set(out["estavel"]), set(personality.AXES))
                for value in out["estavel"].values():
                    if value is None:
                        continue
                    source = role
                    for part in value["origem"].strip("/").split("/"):
                        source = source[int(part)] if isinstance(source, list) else source[part]
                    self.assertIn(value["texto"], source)
                self.assertLessEqual(len(yaml.safe_dump(out, allow_unicode=True).encode()), personality.MAX_PROFILE_BYTES)

    def test_lacunas_nao_viram_tracos_negativos_ou_padrao(self):
        for person in roles():
            out = profile(person)
            self.assertIsNone(out["estavel"]["receios"])
            self.assertIn("receios", out["lacunas"])
        self.assertIsNone(profile("luath")["estavel"]["desejos"])

    def test_fonte_ausente_e_lacuna_sem_inventar_traco(self):
        out = personality.project("silva_elkwood", None)
        self.assertTrue(all(value is None for value in out["estavel"].values()))
        self.assertEqual(set(out["lacunas"]), set(personality.AXES))

    def test_frase_negada_invalida_recorte_mesmo_com_substring_preservada(self):
        role = roles()["silva_elkwood"]["papel_conversacional"]
        role["prioriza"][1] = "não prioriza " + role["prioriza"][1]
        out = personality.project("silva_elkwood", role)
        self.assertIsNone(out["estavel"]["valores"])
        self.assertIn("alterada", out["lacunas"]["valores"])
        self.assertIsNotNone(out["estavel"]["metodos_preferidos"])

    def test_papel_trocado_nao_reaproveita_classificacao_antiga(self):
        role = roles()["silva_elkwood"]["papel_conversacional"]
        role["papel"] = "outro"
        self.assertTrue(all(v is None for v in personality.project("silva_elkwood", role)["estavel"].values()))

    def test_whitespace_yaml_nao_muda_semantica(self):
        role = roles()["silva_elkwood"]["papel_conversacional"]
        role["prioriza"][1] = role["prioriza"][1].replace(" ", "\n ")
        self.assertEqual(personality.project("silva_elkwood", role), profile())

    def test_humor_tom_risco_e_reacao_nao_reescrevem_personalidade(self):
        original = document(tom_atual="tranquila", leitura_atual="Ouviu um relato.", humor_atual="serena")
        changed = deepcopy(original)
        changed["resultado"]["medidores"]["dados"].update(tom_atual="seca", leitura_atual="Recebeu má notícia.",
                                                           humor_atual="irritada", medidores={"risco_percebido": 10})
        before = personality.enrich(original)
        after = personality.enrich(changed)
        self.assertEqual(before["resultado"][personality.KEY], after["resultado"][personality.KEY])
        self.assertEqual(after["resultado"]["medidores"]["dados"]["humor_atual"], "irritada")
        self.assertNotIn("Recebeu má notícia", str(after["resultado"][personality.KEY]))

    def test_sem_humor_registrado_tom_nao_e_convertido_em_humor(self):
        out = personality.enrich(document(tom_atual="seca"))
        self.assertNotIn("humor_atual", out["resultado"]["medidores"]["dados"])

    def test_nao_usa_nome_ou_alias_para_fabricar_opt_in(self):
        doc = document()
        doc["resultado"]["medidores"]["id"] = "silva_nova"
        self.assertNotIn(personality.KEY, personality.enrich(doc)["resultado"])
        self.assertIsNone(personality.project("Silva", roles()["silva_elkwood"]["papel_conversacional"]))

    def test_identidades_conflitantes_falham(self):
        doc = document()
        doc["resultado"]["relacao"] = {"id": "nera_vell", "dados": {}}
        with self.assertRaises(ValueError):
            personality.enrich(doc)

    def test_projecao_pura_sem_escrita_leitura_ou_mutacao_de_argumentos(self):
        doc = document()
        before = deepcopy(doc)
        with patch.object(Path, "read_text", side_effect=AssertionError("I/O")), \
                patch.object(Path, "write_text", side_effect=AssertionError("I/O")):
            first = personality.enrich(doc)
            second = personality.enrich(doc)
        self.assertEqual(first, second)
        self.assertEqual(doc, before)

    def test_fixture_declara_instante_e_nao_congela_estado_vivo(self):
        data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["natureza"], "snapshot_historico_isolado")
        self.assertIn("futuros", data["motivo"])
        self.assertTrue(data["instante"])


class PersonalityDeliberationTest(unittest.TestCase):
    def test_mesmo_problema_e_alternativas_produzem_preferencias_distintas(self):
        choices = dilemma()
        expected = {"silva_elkwood": "oferecer_abrigo", "nera_vell": "escutar_e_combinar", "luath": "preservar_prova"}
        for person, oid in expected.items():
            out = personality.evaluate_options(profile(person), choices)
            self.assertEqual(out["preferiveis"], [oid])
            selected = next(row for row in out["alternativas"] if row["id"] == oid)
            self.assertTrue(selected["justificativas"])
            self.assertFalse(out["executa_acao"])
            self.assertFalse(out["sucesso_garantido"])

    def test_aliada_preocupada_nao_vira_sermao_por_padrao(self):
        out = personality.evaluate_options(profile(), [
            option("cuidar", {"cuidado_concreto": "Oferecer ajuda concreta."}),
            option("repetir_bronca", {"rotina_segura": "Declara querer proteger."},
                   {"sem_tutela_moral": "Repetir censura sem risco ou fato novo."})])
        self.assertEqual(out["preferiveis"], ["cuidar"])
        self.assertEqual(out["alternativas"][1]["status"], "contraria_limite")

    def test_crueldade_nao_substitui_capacidade_nem_estrategia(self):
        cruel = {"versao": 1, "estavel": {axis: None for axis in personality.AXES}}
        cruel["estavel"]["valores"] = {"id": "crueldade", "texto": "Crueldade instrumental (fixture, não campanha)."}
        cruel["estavel"]["metodos_preferidos"] = {"id": "coercao", "texto": "Prefere coerção com vantagem demonstrável."}
        out = personality.evaluate_options(cruel, [
            option("pressionar_com_vantagem", {"coercao": "Usar vantagem já declarada no cenário."}),
            option("atacar_sem_meios", {"crueldade": "Deseja ferir."}, capacidade=False, recursos=False)])
        self.assertEqual(out["preferiveis"], ["pressionar_com_vantagem"])
        self.assertEqual(out["alternativas"][0]["status"], "inviavel_declarada")
        self.assertFalse(out["sucesso_garantido"])

    def test_gate_desconhecido_nao_vira_permissao(self):
        for key in personality.GATES:
            out = personality.evaluate_options(profile(), [option("cuidar", {"cuidado_concreto": "Ajuda."}, **{key: None})])
            self.assertEqual(out["preferiveis"], [])
            self.assertIn(key, out["alternativas"][0]["lacunas_viabilidade"])

    def test_gate_falso_prevalece_sobre_afinidade(self):
        for key in personality.GATES:
            out = personality.evaluate_options(profile(), [option("cuidar", {"cuidado_concreto": "Ajuda."}, **{key: False})])
            self.assertEqual(out["preferiveis"], [])
            self.assertIn(key, out["alternativas"][0]["bloqueios"])

    def test_criterio_de_outro_perfil_nao_conta_como_fundamento(self):
        out = personality.evaluate_options(profile(), [option("cuidar", {"poder_inventado": "Sem fonte."})])
        self.assertEqual(out["preferiveis"], [])
        self.assertEqual(out["alternativas"][0]["criterios_nao_presentes"], ["poder_inventado"])

    def test_empate_e_conflito_nao_sao_resolvidos_por_escore_psicologico(self):
        opts = [option("a", {"cuidado_concreto": "Ajuda."}), option("b", {"verdade_verificavel": "Verificar."})]
        out = personality.evaluate_options(profile(), opts)
        self.assertEqual(out["preferiveis"], ["a", "b"])
        self.assertEqual(out, personality.evaluate_options(profile(), list(reversed(opts))))

    def test_custo_contrario_e_preservado_na_justificativa(self):
        out = personality.evaluate_options(profile(), [option("cuidado_arriscado", {"cuidado_concreto": "Ajuda."},
                                                                             {"rotina_segura": "Expõe a rotina."})])
        row = out["alternativas"][0]
        self.assertEqual(row["contraria"], ["rotina_segura"])
        self.assertTrue(any(j["efeito"] == "contraria" for j in row["justificativas"]))

    def test_opcao_dominada_nao_apaga_alternativas(self):
        opts = [option("a", {"cuidado_concreto": "Ajuda."}),
                option("b", {"cuidado_concreto": "Ajuda."}, {"rotina_segura": "Risco adicional."})]
        out = personality.evaluate_options(profile(), opts)
        self.assertEqual(out["preferiveis"], ["a"])
        self.assertEqual(len(out["alternativas"]), 2)

    def test_deliberacao_nao_muta_perfil_ou_opcoes(self):
        p, opts = profile(), dilemma()
        before = deepcopy((p, opts))
        personality.evaluate_options(p, opts)
        self.assertEqual((p, opts), before)

    def test_contratos_invalidos_falham_sem_resultado_parcial(self):
        base = option("a", {"cuidado_concreto": "Ajuda."})
        cases = [[], [base] * 7, [base, base]]
        for field, value in (("viabilidade", {}), ("favorece", {"x": ""}), ("conduta", "")):
            cases.append([{**base, field: value}])
        cases.append([{**base, "contraria": deepcopy(base["favorece"])}])
        cases.append([{**base, "viabilidade": {**base["viabilidade"], "capacidade": 1}}])
        for choices in cases:
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                personality.evaluate_options(profile(), choices)
        with self.assertRaises(ValueError):
            personality.evaluate_options({"versao": True, "estavel": {}}, [base])


if __name__ == "__main__":
    unittest.main()
