from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import locais
import mundo
import oportunidade_sidequest
import oportunidades
import sidequests_emergentes as emergent


def task40_package() -> dict:
    return oportunidade_sidequest.plan(
        ROOT,
        signaled=True,
        origin_type="conversa_npc",
        origin_id="task41-silva-conversa",
        anchor_type="problema",
        anchor=(
            "Silva descreveu um problema concreto envolvendo uma entrega ameaçada e "
            "uma pessoa que precisa de ajuda antes que a situação piore."
        ),
        npc_id="silva_elkwood",
        local_id="jack_mooney_sons_circus",
        danger="media",
    )


def quest_spec(package: dict) -> dict:
    now = mundo.parse_instant(
        package["prazo_mundo"]["agora"]["data"],
        package["prazo_mundo"]["agora"]["hora"],
    )
    deadline = mundo.instant_parts(mundo.WorldInstant(now.minute + 24 * 60))
    origin = package["origem"]
    return {
        "titulo": "A Entrega que Não Pode Esperar",
        "tipo": "protecao",
        "origem_causal": {
            "tipo": origin["tipo"],
            "id": origin["id"],
            "npc_id": origin.get("npc_id"),
            "ancora_tipo": origin["ancora_tipo"],
            "ancora": origin["ancora"],
        },
        "quest_giver": {
            "tipo": "npc_existente",
            "id": "silva_elkwood",
            "nome": "Silva Elkwood",
            "legitimidade": (
                "Silva conhece diretamente a pessoa e a entrega em risco e pode pedir "
                "ajuda sem falar em nome de terceiros que não autorizou."
            ),
        },
        "oferta": {
            "premissa": (
                "Uma entrega ligada a uma pessoa vulnerável será interceptada se o "
                "problema continuar sem resposta."
            ),
            "pedido": (
                "Silva pede proteção para a janela da entrega e fornece os fatos que "
                "ela realmente conhece, sem presumir método ou aceite."
            ),
            "recusa_permitida": True,
        },
        "premissa": (
            "Uma entrega legítima cruzará uma rota sob pressão de uma rede hostil; "
            "a situação existe independentemente das escolhas de Ren."
        ),
        "prazo": {"tipo": "temporal", "expira_em": deadline},
        "objetivo": (
            "Manter a entrega e seu destinatário fora do controle da força opositora "
            "até que o material alcance um destino seguro."
        ),
        "fases": [
            {
                "id": "entender_rota",
                "titulo": "A rota ameaçada",
                "situacao": (
                    "Silva conhece o horário aproximado, mas a ameaça ainda não está "
                    "localizada com precisão."
                ),
                "condicao_avanco": (
                    "Uma rota e uma janela de risco ficam concretamente estabelecidas "
                    "por informação ou observação canônica."
                ),
                "locais": ["jack_mooney_sons_circus"],
            },
            {
                "id": "entrega_em_movimento",
                "titulo": "A entrega em movimento",
                "situacao": (
                    "A carga deixa o ponto seguro e passa a poder ser alcançada pelas "
                    "forças que tentam controlá-la."
                ),
                "condicao_avanco": (
                    "A entrega chega a um destino seguro, é tomada pela oposição ou "
                    "se torna impossível de recuperar dentro da janela."
                ),
                "locais": ["jack_mooney_sons_circus"],
            },
        ],
        "locais": [
            {
                "id": "jack_mooney_sons_circus",
                "tipo": "canonico",
                "funcao": "ponto seguro inicial e lugar onde a necessidade foi explicada",
            }
        ],
        "npcs_existentes": [
            {
                "id": "silva_elkwood",
                "funcao": "origem da necessidade, contato e autoridade sobre os fatos que oferece",
            }
        ],
        "npcs_novos": [
            {
                "id": "mensageiro_cinza_task41",
                "nome": "Mensageiro Cinza",
                "funcao": "portador potencial da entrega; identidade reservada até entrar canonicamente em cena",
                "estatuto": "reservado_nao_presente",
            }
        ],
        "antagonistas": [
            {
                "id": "masao_hirasawa",
                "tipo": "ator_task40",
                "funcao": "pressão estratégica indireta por meio da rede",
                "objetivo": (
                    "Impedir que material útil fortaleça a rede de apoio contrária sem "
                    "expor a estrutura de comando."
                ),
            }
        ],
        "juppongatana": [],
        "condicoes_sucesso": [
            "A entrega alcança um destino seguro ainda utilizável.",
            "O destinatário permanece fora do controle da força que buscava a entrega.",
        ],
        "condicoes_falha": [
            "A oposição obtém a entrega de forma durável.",
            "O prazo termina com a entrega ainda exposta e sem destino seguro disponível.",
        ],
        "stakes": {
            "em_risco": [
                "a segurança do portador",
                "a informação transportada",
                "a confiança de Silva na viabilidade da operação",
            ],
            "consequencia_expiracao": (
                "A rota deixa de ser segura e a oposição passa a controlar a entrega ou "
                "obriga seus responsáveis a abandoná-la."
            ),
            "perdas_possiveis": [
                {
                    "tipo": "acesso",
                    "alvo": "rota_segura",
                    "condicao": "A oposição identifica de forma durável a rota usada na entrega.",
                    "descricao": "A rota deixa de ser utilizável como canal discreto.",
                }
            ],
        },
        "recompensas": [
            {
                "id": "pagamento_silva",
                "tipo": "dinheiro",
                "modo": "sucesso",
                "descricao": "Pagamento modesto separado por Silva para o trabalho perigoso.",
                "condicao": "A obrigação principal é cumprida e Silva mantém autoridade para pagar.",
                "valor_aproximado": "moderado",
                "autoridade_concedente": "Silva Elkwood controla o pagamento prometido.",
            },
            {
                "id": "favor_da_rede",
                "tipo": "favor",
                "modo": "condicional",
                "descricao": "Um favor concreto da pessoa beneficiada pela entrega.",
                "condicao": "A pessoa beneficiada sobrevive, entende a ajuda recebida e decide oferecer o favor.",
                "valor_aproximado": "especial",
                "autoridade_concedente": "O próprio beneficiário decide se concede o favor.",
            },
        ],
        "relacao_canone": {
            "modo": "lateral",
            "intencoes_candidatas": [],
            "justificativa": (
                "A aventura nasce da situação local e não precisa reservar nenhuma "
                "intenção canônica nesta etapa."
            ),
        },
        "segredos": [
            "A identidade do intermediário que informou a oposição permanece reservada até descoberta legítima."
        ],
        "bifurcacoes": [
            {
                "id": "rota_comprometida",
                "se": "A oposição identifica a rota mas não obtém a entrega.",
                "efeito_no_mundo": (
                    "A entrega pode chegar ao destino, mas o canal deixa de ser seguro "
                    "para operações futuras."
                ),
            }
        ],
    }


class Task41PreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task40_package()

    def test_preparar_e_read_only_e_nao_cria_npc_ou_quest(self):
        spec = quest_spec(self.package)
        state_before = (ROOT / oportunidades.STATE).read_bytes()
        npc_index_before = (ROOT / emergent.NPC_INDEX).read_bytes()
        result = emergent.prepare(ROOT, package=self.package, quest=spec)
        self.assertEqual(result["fase"], "preparacao")
        self.assertEqual(result["resultado"], "pronta_para_oferta")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["mutacoes_aplicadas"])
        self.assertLessEqual(
            len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")),
            emergent.MAX_PREP_OUTPUT_BYTES,
        )
        self.assertEqual((ROOT / oportunidades.STATE).read_bytes(), state_before)
        self.assertEqual((ROOT / emergent.NPC_INDEX).read_bytes(), npc_index_before)
        self.assertFalse((ROOT / emergent._quest_path(result["quest_id"])).exists())
        self.assertEqual(result["resumo_estrutura"]["antagonistas"], 1)
        self.assertEqual(result["resumo_estrutura"]["recompensas"], 2)

    def test_plano_nao_pode_escrever_escolha_futura_de_ren(self):
        spec = quest_spec(self.package)
        spec["fases"][0]["situacao"] = "Ren vai investigar o armazém e depois seguirá o mensageiro."
        with self.assertRaisesRegex(
            emergent.EmergentSidequestAuthoringError,
            "agência de Ren|escolha/ação futura de Ren",
        ):
            emergent.prepare(ROOT, package=self.package, quest=spec)

    def test_antagonistas_e_recompensas_sao_obrigatorios(self):
        spec = quest_spec(self.package)
        spec["antagonistas"] = []
        with self.assertRaisesRegex(emergent.EmergentSidequestAuthoringError, "antagonistas"):
            emergent.prepare(ROOT, package=self.package, quest=spec)
        spec = quest_spec(self.package)
        spec["recompensas"] = []
        with self.assertRaisesRegex(emergent.EmergentSidequestAuthoringError, "recompensas"):
            emergent.prepare(ROOT, package=self.package, quest=spec)

    def test_recompensa_material_nao_fura_envelope_task40(self):
        spec = quest_spec(self.package)
        spec["recompensas"][0]["valor_aproximado"] = "alto"
        with self.assertRaisesRegex(emergent.EmergentSidequestAuthoringError, "excede teto"):
            emergent.prepare(ROOT, package=self.package, quest=spec)

    def test_propriedade_especial_pode_ser_declarada_com_autoridade(self):
        spec = quest_spec(self.package)
        spec["recompensas"][0] = {
            "id": "direito_sobre_casa",
            "tipo": "propriedade",
            "modo": "sucesso",
            "descricao": "Direito negociado sobre uma propriedade específica.",
            "condicao": "A proprietária legítima mantém autoridade e a condição acordada é satisfeita.",
            "valor_aproximado": "especial",
            "autoridade_concedente": "Somente a proprietária legítima pode conceder ou transferir o direito.",
        }
        result = emergent.prepare(ROOT, package=self.package, quest=spec)
        self.assertEqual(result["recompensas_planejadas"][0]["tipo"], "propriedade")

    def test_relacao_canone_nao_lateral_so_pode_usar_intencao_do_pacote(self):
        spec = quest_spec(self.package)
        compatible = self.package["horizonte_intencoes_canonicas"]["compativeis"]
        if compatible:
            spec["relacao_canone"] = {
                "modo": "candidata_ponte",
                "intencoes_candidatas": [compatible[0]["evento_id"]],
                "justificativa": "O clímax pode ser planejado como ponte causal, sem rewrite nesta Task.",
            }
            result = emergent.prepare(ROOT, package=self.package, quest=spec)
            self.assertEqual(result["relacao_canone"]["modo"], "candidata_ponte")
        bad = quest_spec(self.package)
        bad["relacao_canone"] = {
            "modo": "candidata_ponte",
            "intencoes_candidatas": ["evento_que_nao_veio_da_task40"],
            "justificativa": "Tentativa inválida de abrir cânone fora do horizonte dirigido.",
        }
        with self.assertRaisesRegex(
            emergent.EmergentSidequestAuthoringError,
            "Task41 só pode citar intenções",
        ):
            emergent.prepare(ROOT, package=self.package, quest=bad)


class Task41MaterializationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task40_package()
        cls.spec = quest_spec(cls.package)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (oportunidades.INDEX, oportunidades.STATE, emergent.NPC_INDEX):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        shutil.copytree(ROOT / locais.INDEX.parent, self.repo / locais.INDEX.parent)

    def tearDown(self):
        self.temp.cleanup()

    def test_sem_oferta_narrada_nao_nasce_quest_fantasma(self):
        prep = emergent.prepare(self.repo, package=self.package, quest=self.spec)
        before = (self.repo / oportunidades.STATE).read_bytes()
        result = emergent.materialize(
            self.repo,
            package=self.package,
            quest=self.spec,
            preparation_id=prep["preparacao_id"],
            offer_was_narrated=False,
        )
        self.assertEqual(result["resultado"], "oferta_nao_materializada")
        self.assertEqual(result["fontes_lidas"], [])
        self.assertEqual((self.repo / oportunidades.STATE).read_bytes(), before)
        self.assertFalse((self.repo / emergent._quest_path(prep["quest_id"])).exists())

    def test_materializa_fragmento_e_reusa_lifecycle_existente(self):
        prep = emergent.prepare(self.repo, package=self.package, quest=self.spec)
        result = emergent.materialize(
            self.repo,
            package=self.package,
            quest=self.spec,
            preparation_id=prep["preparacao_id"],
            offer_was_narrated=True,
            offer_scene_id="sessao-015:task41-oferta-silva",
            offer_summary=(
                "Silva explicou o risco da entrega e pediu explicitamente ajuda para "
                "proteger a janela, deixando claro que a recusa era possível."
            ),
        )
        self.assertEqual(result["resultado"], "materializada")
        self.assertEqual(result["estado"], "oferecida")
        self.assertTrue((self.repo / result["arquivo"]).is_file())
        listing = emergent.list_quests(self.repo)
        self.assertEqual(listing["quantidade"], 1)
        self.assertEqual(listing["quests"][0]["estado"], "oferecida")
        self.assertEqual(
            listing["fontes_lidas"],
            [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()],
        )
        shown = emergent.show(self.repo, result["quest_id"])
        self.assertEqual(shown["quest"]["titulo"], self.spec["titulo"])
        self.assertEqual(
            shown["quest"]["guardrails_execucao"]["recompensas"],
            "declaradas_nao_concedidas_task43_45",
        )
        self.assertEqual(
            shown["quest"]["guardrails_execucao"]["stakes"],
            "declarados_nao_executados_task45",
        )
        self.assertEqual(shown["quest"]["npcs_novos"][0]["estatuto"], "reservado_nao_presente")
        npc_index = yaml.safe_load((self.repo / emergent.NPC_INDEX).read_text(encoding="utf-8"))
        self.assertNotIn("mensageiro_cinza_task41", npc_index["npcs"])
        now = mundo.parse_instant(
            self.package["prazo_mundo"]["agora"]["data"],
            self.package["prazo_mundo"]["agora"]["hora"],
        )
        oportunidades.respond(self.repo, result["mission_id"], "aceitar", now=now)
        self.assertEqual(emergent.list_quests(self.repo)["quests"][0]["estado"], "aceita")

    def test_retry_e_idempotente(self):
        prep = emergent.prepare(self.repo, package=self.package, quest=self.spec)
        kwargs = dict(
            package=self.package,
            quest=self.spec,
            preparation_id=prep["preparacao_id"],
            offer_was_narrated=True,
            offer_scene_id="sessao-015:task41-retry",
            offer_summary=(
                "Silva fez o pedido concreto de proteção da entrega e a oferta foi "
                "efetivamente narrada antes do registro."
            ),
        )
        first = emergent.materialize(self.repo, **kwargs)
        state_after = (self.repo / oportunidades.STATE).read_bytes()
        fragment_after = (self.repo / first["arquivo"]).read_bytes()
        second = emergent.materialize(self.repo, **kwargs)
        self.assertEqual(second["resultado"], "ja_materializada")
        self.assertFalse(second["mutacoes_aplicadas"])
        self.assertEqual((self.repo / oportunidades.STATE).read_bytes(), state_after)
        self.assertEqual((self.repo / first["arquivo"]).read_bytes(), fragment_after)

    def test_preparacao_obsoleta_falha_antes_de_materializar(self):
        prep = emergent.prepare(self.repo, package=self.package, quest=self.spec)
        npc_path = self.repo / emergent.NPC_INDEX
        npc_data = yaml.safe_load(npc_path.read_text(encoding="utf-8"))
        npc_data["task41_fixture_touch"] = True
        npc_path.write_text(yaml.safe_dump(npc_data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(emergent.EmergentSidequestAuthoringError, "obsoleta"):
            emergent.materialize(
                self.repo,
                package=self.package,
                quest=self.spec,
                preparation_id=prep["preparacao_id"],
                offer_was_narrated=True,
                offer_scene_id="sessao-015:task41-stale",
                offer_summary=(
                    "A oferta foi narrada, mas o contexto estrutural mudou antes da "
                    "materialização e precisa ser preparado novamente."
                ),
            )
        self.assertFalse((self.repo / emergent._quest_path(prep["quest_id"])).exists())


class Task41BudgetContractTest(unittest.TestCase):
    def test_contrato_congela_limites_e_zero_infra_automatica(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/emergent-sidequest-authoring-v2-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        self.assertEqual(limits["fragmento_bytes_max"], emergent.MAX_FRAGMENT_BYTES)
        self.assertEqual(limits["preparacao_saida_bytes_max"], emergent.MAX_PREP_OUTPUT_BYTES)
        self.assertEqual(limits["fases_max"], emergent.MAX_PHASES)
        self.assertEqual(limits["antagonistas_max"], emergent.MAX_ANTAGONISTS)
        self.assertEqual(limits["recompensas_max"], emergent.MAX_REWARDS)
        for key in (
            "escritas_preparar", "escritas_sem_oferta", "schedulers_novos", "rng_novo",
            "scans_globais", "transcricoes_hot",
        ):
            self.assertEqual(limits[key], 0)
        self.assertEqual(limits["escritas_materializar_max"], 2)
        self.assertTrue(all(contract["invariantes"].values()))

    def test_engine_nao_varre_repo_nem_importa_rng_scheduler(self):
        source = (ROOT / "ferramentas/sidequests_emergentes.py").read_text(encoding="utf-8")
        for forbidden in (
            "import random", "threading", "asyncio", "subprocess", "os.walk", ".rglob(", ".glob(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
