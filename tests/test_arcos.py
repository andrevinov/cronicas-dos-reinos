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

import arcos


class ArcosTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._base_two_arcs()
        self._references()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _contract(self, arc_id: str, title: str, *, antagonists: list[str], allies: list[str], directions: list[str], start: str, end: str) -> dict:
        return {
            "schema_arco": 4,
            "natureza": "reservado",
            "estatuto": "contrato_orquestrador_de_arco",
            "id": arc_id,
            "titulo": title,
            "principio": "Fixture de contrato orquestrador sem conteúdo narrativo duplicado.",
            "inicio": {"tipo": "fato_canonico", "marcador": start, "fonte": "campanha.yaml"},
            "termino": {"tipo": "marco_explicito", "marcador": end, "fonte": "campanha.yaml"},
            "orquestracao": {
                "fontes": {
                    "plano_mestre": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"},
                    "marcos_antagonistas": {"tipo": "documento_reservado", "arquivo": "narrador/juppongatana/marcos-de-aparicao.md"},
                },
                "plano_mestre": {"agente": "masao", "objetivo": f"objetivo_{arc_id}", "referencia": "plano_mestre"},
            },
            "habilitacoes": {
                "politica_nao_listados": "bloqueados",
                "antagonistas": antagonists,
                "aliados": allies,
                "direcoes": directions,
            },
            "linhas_operacionais": {
                f"linha_{arc_id}": {
                    "objetivo": f"necessidade_{arc_id}",
                    "executores": [antagonists[0]] if antagonists else ["masao"],
                    "referencia": "plano_mestre",
                }
            },
        }

    def _base_two_arcs(self):
        self._write(
            "narrador/arcos/index.yaml",
            {
                "schema_arcos": 1,
                "natureza": "roteador_reservado",
                "arcos": {
                    "parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": "parte_2"},
                    "parte_2": {"titulo": "Parte 2", "ordem": 2, "arquivo": "narrador/arcos/parte_2.yaml", "proximo": None},
                },
            },
        )
        self._write(
            "narrador/arcos/estado.yaml",
            {"schema_estado_arcos": 2, "natureza": "controle_reservado", "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": []},
        )
        self._write("narrador/arcos/parte_1.yaml", self._contract("parte_1", "Parte 1", antagonists=["shizune", "kurobane"], allies=["shen"], directions=["ponte"], start="chegada_ren", end="perda_ponte"))
        self._write("narrador/arcos/parte_2.yaml", self._contract("parte_2", "Parte 2", antagonists=["anji"], allies=["joen"], directions=["shin"], start="perda_ponte", end="fim_parte_2"))
        self._write("campanha.yaml", "campanha: teste\n")
        self._write("narrador/masao/plano.md", "# Plano\n")
        self._write("narrador/juppongatana/marcos-de-aparicao.md", "# Marcos\n")

    def _references(self):
        self._write(
            "narrador/agentes/index.yaml",
            {"schema_agentes": 2, "agentes": {k: {"nome": k, "arquivo": f"narrador/agentes/{k}.yaml"} for k in ["masao", "shizune", "kurobane", "anji"]}},
        )
        self._write(
            "narrador/entradas/index.yaml",
            {"schema_entradas": 1, "candidatos": {"shen": {"nome": "Shen", "arquivo": "narrador/entradas/shen.yaml"}, "joen": {"nome": "Joen", "arquivo": "narrador/entradas/joen.yaml"}}},
        )
        self._write(
            "narrador/direcoes/index.yaml",
            {"schema_direcoes": 1, "direcoes": {"ponte": {"nome": "Ponte", "arquivo": "narrador/direcoes/ponte.yaml"}, "shin": {"nome": "Shin", "arquivo": "narrador/direcoes/shin.yaml"}}},
        )
        self._write("narrador/agentes/masao.yaml", {"id": "masao"})
        self._write(
            "narrador/agentes/shizune.yaml",
            {
                "id": "shizune",
                "metodos_operacionais": {
                    "linha_parte_1": [
                        {
                            "id": "invalidar_prova",
                            "abordagem": "Criar contradição documental sem remover a prova.",
                            "modalidade": "indireta",
                            "tags": ["documentos", "registros"],
                        }
                    ]
                },
            },
        )
        self._write("narrador/agentes/kurobane.yaml", {"id": "kurobane"})
        self._write(
            "narrador/agentes/anji.yaml",
            {
                "id": "anji",
                "metodos_operacionais": {
                    "linha_parte_2": [
                        {
                            "id": "pressionar_estrutura",
                            "abordagem": "Aplicar pressão física coerente com a necessidade do arco.",
                            "modalidade": "fisica",
                            "tags": ["estrutura", "pressao"],
                        }
                    ]
                },
            },
        )
        self._write("narrador/entradas/shen.yaml", "id: shen\n")
        self._write("narrador/entradas/joen.yaml", "id: joen\n")
        self._write("narrador/direcoes/ponte.yaml", "id: ponte\n")
        self._write("narrador/direcoes/shin.yaml", "id: shin\n")

    def test_status_expõe_um_unico_arco_corrente(self):
        info = arcos.current(self.repo)
        self.assertEqual(info["id"], "parte_1")
        self.assertEqual(info["proximo"], "parte_2")
        self.assertEqual(info["habilitacoes"]["politica_nao_listados"], "bloqueados")

    def test_habilitado_e_nao_listado_sao_distintos(self):
        yes = arcos.eligibility(self.repo, "antagonistas", "shizune")
        no = arcos.eligibility(self.repo, "antagonistas", "anji")
        self.assertTrue(yes["permitido"])
        self.assertFalse(no["permitido"])
        self.assertEqual(no["motivo"], "nao_listado_bloqueado_pelo_arco")

    def test_grupos_sao_independentes(self):
        self.assertTrue(arcos.eligibility(self.repo, "aliados", "shen")["permitido"])
        self.assertTrue(arcos.eligibility(self.repo, "direcoes", "ponte")["permitido"])
        self.assertFalse(arcos.eligibility(self.repo, "direcoes", "shin")["permitido"])

    def test_validacao_confere_referencias_reais_dos_contratos(self):
        result = arcos.validate(self.repo)
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantidade_arcos"], 2)
        self.assertEqual(result["arco_atual"], "parte_1")

    def test_antagonista_inexistente_falha_na_validacao(self):
        contract = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        contract["habilitacoes"]["antagonistas"].append("fantasma")
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "antagonista inexistente"):
            arcos.validate(self.repo)

    def test_aliado_inexistente_falha_na_validacao(self):
        contract = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        contract["habilitacoes"]["aliados"] = ["fantasma"]
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "aliado inexistente"):
            arcos.validate(self.repo)

    def test_direcao_inexistente_falha_na_validacao(self):
        contract = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        contract["habilitacoes"]["direcoes"] = ["fantasma"]
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "direção inexistente"):
            arcos.validate(self.repo)

    def test_nao_listados_precisam_ser_bloqueados(self):
        contract = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        contract["habilitacoes"]["politica_nao_listados"] = "permitidos"
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "não listados"):
            arcos.load_contract(self.repo, "parte_1")

    def test_indice_rejeita_transicao_para_tras(self):
        index = yaml.safe_load((self.repo / "narrador/arcos/index.yaml").read_text())
        index["arcos"]["parte_2"]["proximo"] = "parte_1"
        self._write("narrador/arcos/index.yaml", index)
        with self.assertRaisesRegex(arcos.ArcContractError, "deve avançar"):
            arcos.load_index(self.repo)

    def test_transicao_exige_proximo_declarado_e_marco_exato(self):
        with self.assertRaisesRegex(arcos.ArcContractError, "marco de término incorreto"):
            arcos.transition(self.repo, target="parte_2", marker="marco_errado", origin="teste", note="teste")
        with self.assertRaisesRegex(arcos.ArcContractError, "só pode avançar"):
            arcos.transition(self.repo, target="parte_1", marker="perda_ponte", origin="teste", note="teste")

    def test_transicao_deterministica_muda_elegibilidade(self):
        result = arcos.transition(self.repo, target="parte_2", marker="perda_ponte", origin="direcao:ponte", note="controle exclusivo perdido")
        self.assertEqual(result["para"], "parte_2")
        self.assertFalse(arcos.eligibility(self.repo, "antagonistas", "shizune")["permitido"])
        self.assertTrue(arcos.eligibility(self.repo, "antagonistas", "anji")["permitido"])
        state = arcos.load_state(self.repo)
        self.assertEqual(state["historico_transicoes"][-1]["marco"], "perda_ponte")

    def test_retry_de_transicao_nao_pula_arco(self):
        arcos.transition(self.repo, target="parte_2", marker="perda_ponte", origin="direcao:ponte", note="ok")
        with self.assertRaisesRegex(arcos.ArcContractError, "ainda não declara próximo arco"):
            arcos.transition(self.repo, target="parte_2", marker="fim_parte_2", origin="retry", note="retry")

    def test_plano_mestre_aponta_agente_e_fonte_sem_executar_nada(self):
        info = arcos.current(self.repo)
        self.assertEqual(info["plano_mestre"]["agente"], "masao")
        self.assertEqual(info["plano_mestre"]["fonte"], "narrador/masao/plano.md")
        self.assertNotIn("acao", info["plano_mestre"])


    def test_manifesto_resolve_fontes_sem_abrir_fragmentos(self):
        result = arcos.manifest(self.repo)
        by_group = result["habilitados"]
        self.assertEqual([item["id"] for item in by_group["antagonistas"]], ["shizune", "kurobane"])
        self.assertEqual(by_group["antagonistas"][0]["arquivo"], "narrador/agentes/shizune.yaml")
        self.assertEqual(by_group["aliados"][0]["arquivo"], "narrador/entradas/shen.yaml")
        self.assertEqual(by_group["direcoes"][0]["arquivo"], "narrador/direcoes/ponte.yaml")
        self.assertFalse(any(source.endswith("/shizune.yaml") for source in result["fontes_lidas"]))
        self.assertFalse(any(source.endswith("/shen.yaml") for source in result["fontes_lidas"]))
        self.assertEqual(result["fontes_orquestradas"]["plano_mestre"]["arquivo"], "narrador/masao/plano.md")

    def test_resolver_peca_habilitada_devolve_ponteiros_sem_conteudo(self):
        result = arcos.resolve_piece(self.repo, "antagonistas", "shizune")
        self.assertTrue(result["permitido"])
        self.assertEqual(result["fonte_especializada"], "narrador/agentes/shizune.yaml")
        self.assertEqual(result["referencias_estrategicas"]["plano_mestre"], "narrador/masao/plano.md")
        self.assertEqual(result["referencias_estrategicas"]["marcos_antagonistas"], "narrador/juppongatana/marcos-de-aparicao.md")
        self.assertNotIn("recursos", result)
        self.assertNotIn("plano_atual", result)
        self.assertNotIn("narrador/agentes/shizune.yaml", result["fontes_lidas"])

    def test_resolver_peca_bloqueada_para_antes_do_indice_especializado(self):
        result = arcos.resolve_piece(self.repo, "antagonistas", "anji")
        self.assertFalse(result["permitido"])
        self.assertIsNone(result["fonte_especializada"])
        self.assertEqual(len(result["fontes_lidas"]), 3)
        self.assertNotIn("narrador/agentes/index.yaml", result["fontes_lidas"])

    def test_mudar_fragmento_do_agente_nao_exige_reescrever_contrato(self):
        contract_path = self.repo / "narrador/arcos/parte_1.yaml"
        before = contract_path.read_bytes()
        agent_path = self.repo / "narrador/agentes/shizune.yaml"
        agent_path.write_text("id: shizune\nplano_atual: mudou_sem_tocar_o_arco\n", encoding="utf-8")
        resolved = arcos.resolve_piece(self.repo, "antagonistas", "shizune")
        self.assertEqual(resolved["fonte_especializada"], "narrador/agentes/shizune.yaml")
        self.assertEqual(contract_path.read_bytes(), before)

    def test_contrato_rejeita_conteudo_operacional_duplicado(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["plano_atual"] = {"acao": "isto pertence ao agente, não ao arco"}
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "campos não permitidos"):
            arcos.load_contract(self.repo, "parte_1")

    def test_plano_mestre_referencia_fonte_nomeada_e_nao_copia_prosa(self):
        contract = arcos.load_contract(self.repo, "parte_1")
        master = contract["orquestracao"]["plano_mestre"]
        self.assertEqual(master["referencia"], "plano_mestre")
        self.assertEqual(set(master), {"agente", "objetivo", "referencia"})
        self.assertNotIn("descricao", master)
        self.assertNotIn("acoes", master)

    def test_validacao_detecta_fragmento_referenciado_ausente(self):
        (self.repo / "narrador/agentes/shizune.yaml").unlink()
        with self.assertRaisesRegex(arcos.ArcContractError, "fonte de antagonista inexistente"):
            arcos.validate(self.repo)

    def test_validacao_detecta_fonte_orquestrada_ausente(self):
        (self.repo / "narrador/juppongatana/marcos-de-aparicao.md").unlink()
        with self.assertRaisesRegex(arcos.ArcContractError, "fonte inexistente"):
            arcos.validate(self.repo)



    def test_linhas_operacionais_listam_problemas_e_executores_sem_fragmentos(self):
        result = arcos.operational_lines(self.repo)
        self.assertEqual(result["arco_id"], "parte_1")
        self.assertEqual(len(result["linhas"]), 1)
        line = result["linhas"][0]
        self.assertEqual(line["id"], "linha_parte_1")
        self.assertEqual(line["objetivo"], "necessidade_parte_1")
        self.assertEqual(line["executores"], ["shizune"])
        self.assertEqual(line["fonte_estrategica"], "narrador/masao/plano.md")
        self.assertFalse(any(source.endswith("/shizune.yaml") for source in result["fontes_lidas"]))

    def test_linha_resolve_executor_permitido_sem_abrir_indice_de_agentes(self):
        result = arcos.resolve_operational_line(
            self.repo, "linha_parte_1", executor="shizune"
        )
        self.assertTrue(result["permitida"])
        self.assertTrue(result["executor_permitido"])
        self.assertEqual(len(result["fontes_lidas"]), 3)
        self.assertNotIn("narrador/agentes/index.yaml", result["fontes_lidas"])

    def test_executor_habilitado_no_arco_mas_nao_na_linha_e_recusado(self):
        result = arcos.resolve_operational_line(
            self.repo, "linha_parte_1", executor="kurobane"
        )
        self.assertTrue(result["permitida"])
        self.assertFalse(result["executor_permitido"])
        self.assertEqual(result["motivo_executor"], "executor_nao_habilitado_para_linha")

    def test_linha_inexistente_nao_vira_operacao_generica(self):
        result = arcos.resolve_operational_line(self.repo, "linha_fantasma")
        self.assertFalse(result["permitida"])
        self.assertEqual(result["motivo"], "linha_nao_declarada_no_arco")
        self.assertEqual(len(result["fontes_lidas"]), 3)

    def test_executor_de_linha_precisa_pertencer_ao_espaco_estrategico_do_arco(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["linha_parte_1"]["executores"] = ["anji"]
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "executor não habilitado no arco"):
            arcos.load_contract(self.repo, "parte_1")

    def test_agente_do_plano_mestre_pode_ser_executor_sem_virar_antagonista_de_aparicao(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["linha_parte_1"]["executores"] = ["masao"]
        self._write("narrador/arcos/parte_1.yaml", contract)
        loaded = arcos.load_contract(self.repo, "parte_1")
        self.assertEqual(loaded["linhas_operacionais"]["linha_parte_1"]["executores"], ["masao"])
        self.assertNotIn("masao", loaded["habilitacoes"]["antagonistas"])

    def test_referencia_da_linha_precisa_existir_no_orquestrador(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["linha_parte_1"]["referencia"] = "fonte_inexistente"
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "referencia inexistente"):
            arcos.load_contract(self.repo, "parte_1")

    def test_linhas_rejeitam_campos_de_acao_concreta(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["linha_parte_1"]["acao"] = "roubar documento"
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "campos não permitidos"):
            arcos.load_contract(self.repo, "parte_1")

    def test_objetivos_de_linha_nao_podem_ser_aliases_duplicados(self):
        path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["outra_linha"] = {
            "objetivo": "necessidade_parte_1",
            "executores": ["kurobane"],
            "referencia": "plano_mestre",
        }
        self._write("narrador/arcos/parte_1.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "objetivo duplicado"):
            arcos.load_contract(self.repo, "parte_1")



    def test_metodos_abrem_so_fragmento_do_executor_autorizado(self):
        result = arcos.resolve_agent_methods(
            self.repo, "linha_parte_1", executor="shizune"
        )
        self.assertTrue(result["executor_permitido"])
        self.assertEqual([m["id"] for m in result["metodos"]], ["invalidar_prova"])
        self.assertEqual(result["fonte_agente"], "narrador/agentes/shizune.yaml")
        self.assertEqual(len(result["fontes_lidas"]), 5)
        self.assertEqual(
            sum(source.endswith("/shizune.yaml") for source in result["fontes_lidas"]), 1
        )

    def test_executor_nao_autorizado_nao_abre_indice_nem_fragmento(self):
        (self.repo / "narrador/agentes/index.yaml").unlink()
        result = arcos.resolve_agent_methods(
            self.repo, "linha_parte_1", executor="kurobane"
        )
        self.assertFalse(result["executor_permitido"])
        self.assertEqual(result["metodos"], [])
        self.assertIsNone(result["fonte_agente"])
        self.assertEqual(len(result["fontes_lidas"]), 3)

    def test_mesma_linha_pode_ter_traducoes_distintas_por_agente(self):
        contract_path = self.repo / "narrador/arcos/parte_1.yaml"
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"]["linha_parte_1"]["executores"] = [
            "shizune", "kurobane"
        ]
        self._write("narrador/arcos/parte_1.yaml", contract)
        self._write(
            "narrador/agentes/kurobane.yaml",
            {
                "id": "kurobane",
                "metodos_operacionais": {
                    "linha_parte_1": [
                        {
                            "id": "interceptar_documento",
                            "abordagem": "Intervir fisicamente no trânsito do documento.",
                            "modalidade": "fisica",
                            "tags": ["documentos", "mensageiro"],
                        }
                    ]
                },
            },
        )
        shizune = arcos.resolve_agent_methods(
            self.repo, "linha_parte_1", executor="shizune"
        )
        kurobane = arcos.resolve_agent_methods(
            self.repo, "linha_parte_1", executor="kurobane"
        )
        self.assertEqual(shizune["metodos"][0]["modalidade"], "indireta")
        self.assertEqual(kurobane["metodos"][0]["modalidade"], "fisica")
        self.assertNotEqual(shizune["metodos"][0]["id"], kurobane["metodos"][0]["id"])

    def test_orcamento_da_traducao_dirigida_congela_fontes_e_fragmento(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml").read_text(encoding="utf-8")
        )["limites"]["traducao_linha_por_agente"]
        result = arcos.resolve_agent_methods(
            self.repo, "linha_parte_1", executor="shizune"
        )
        self.assertLessEqual(len(result["fontes_lidas"]), budget["max_fontes"])
        fragments = [s for s in result["fontes_lidas"] if s.endswith("/shizune.yaml")]
        self.assertLessEqual(len(fragments), budget["max_fragmentos_narrativos"])
        self.assertLessEqual(len(result["metodos"]), budget["max_metodos_por_linha_agente"])

    def test_validacao_exige_traducao_para_cada_executor_de_linha(self):
        (self.repo / "narrador/agentes/shizune.yaml").write_text(
            "id: shizune\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(arcos.ArcContractError, "não possui tradução"):
            arcos.validate(self.repo)

    def test_validacao_rejeita_metodo_orfao_de_linha(self):
        self._write(
            "narrador/agentes/kurobane.yaml",
            {
                "id": "kurobane",
                "metodos_operacionais": {
                    "linha_fantasma": [
                        {
                            "id": "metodo_fantasma",
                            "abordagem": "Não deveria sobreviver à validação.",
                            "modalidade": "fisica",
                            "tags": ["teste"],
                        }
                    ]
                },
            },
        )
        with self.assertRaisesRegex(arcos.ArcContractError, "linha inexistente"):
            arcos.validate(self.repo)

    def test_linha_operacional_precisa_de_id_globalmente_unico(self):
        path = self.repo / "narrador/arcos/parte_2.yaml"
        contract = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract["linhas_operacionais"] = {
            "linha_parte_1": {
                "objetivo": "necessidade_parte_2",
                "executores": ["anji"],
                "referencia": "plano_mestre",
            }
        }
        self._write("narrador/arcos/parte_2.yaml", contract)
        with self.assertRaisesRegex(arcos.ArcContractError, "globalmente único"):
            arcos.validate(self.repo)



class ArcosBundleTest(unittest.TestCase):
    def test_parte_1_real_tem_guardrails_minimos(self):
        info = arcos.current(ROOT)
        self.assertEqual(info["id"], "parte_1_uma_ponte_para_kozakura")
        self.assertEqual(info["plano_mestre"]["agente"], "masao_hirasawa")
        self.assertIn("ponte_de_kozakura", info["habilitacoes"]["direcoes"])
        self.assertIn("shen_meihua", info["habilitacoes"]["aliados"])
        self.assertNotIn("yukyuzan_anji", info["habilitacoes"]["antagonistas"])
        self.assertEqual(info["habilitacoes"]["politica_nao_listados"], "bloqueados")

    def test_parte_1_real_tem_linhas_operacionais_curadas_e_compactas(self):
        result = arcos.operational_lines(ROOT)
        by_id = {line["id"]: line for line in result["linhas"]}
        self.assertEqual(len(by_id), 12)
        self.assertEqual(
            by_id["impedir_consolidacao_de_provas"]["executores"],
            ["kurobane_jinzaburo", "kajiwara_shizune"],
        )
        self.assertEqual(
            by_id["mascarar_origem_kozakuriana"]["executores"],
            ["kajiwara_shizune", "pan_chu"],
        )
        self.assertIn("sawagejo_cho", by_id["pressionar_identidade_marcial_de_ren"]["executores"])
        self.assertIn("pan_chu", by_id["desgastar_autoridade_de_ravens_bluff"]["executores"])
        self.assertIn("masao_hirasawa", by_id["ocupar_espaco_urbano"]["executores"])
        self.assertLessEqual(
            (ROOT / "narrador/arcos/parte_1_uma_ponte_para_kozakura.yaml").stat().st_size,
            arcos.MAX_CONTRACT_BYTES,
        )

    def test_parte_1_real_tem_traducao_para_todo_executor_de_linha(self):
        contract = arcos.load_contract(ROOT, "parte_1_uma_ponte_para_kozakura")
        for line_id, line in contract["linhas_operacionais"].items():
            for executor in line["executores"]:
                path = ROOT / f"narrador/agentes/{executor}.yaml"
                self.assertTrue(path.is_file(), (line_id, executor))
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                import metodos_agentes
                methods = metodos_agentes.for_line(
                    data, line_id, expected_agent_id=executor
                )
                self.assertGreaterEqual(len(methods), 1, (line_id, executor))

    def test_kurobane_e_shizune_traduzem_mesma_linha_de_formas_diferentes(self):
        import metodos_agentes
        kurobane = yaml.safe_load(
            (ROOT / "narrador/agentes/kurobane_jinzaburo.yaml").read_text(encoding="utf-8")
        )
        shizune = yaml.safe_load(
            (ROOT / "narrador/agentes/kajiwara_shizune.yaml").read_text(encoding="utf-8")
        )
        km = metodos_agentes.for_line(kurobane, "impedir_consolidacao_de_provas")
        sm = metodos_agentes.for_line(shizune, "impedir_consolidacao_de_provas")
        self.assertTrue(all(method["modalidade"] == "fisica" for method in km))
        self.assertTrue(all(method["modalidade"] == "indireta" for method in sm))
        self.assertTrue(set(km[0]["tags"]) != set(sm[0]["tags"]))

    def test_pan_chu_tem_repertorio_sem_ser_ativado_por_ele(self):
        import metodos_agentes
        pan = yaml.safe_load(
            (ROOT / "narrador/agentes/pan_chu.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(pan["estado"], "latente")
        self.assertEqual(pan["presenca"]["estado"], "indeterminado")
        methods = metodos_agentes.for_line(pan, "proteger_cadeia_logistica")
        self.assertGreaterEqual(len(methods), 1)


if __name__ == "__main__":
    unittest.main()
