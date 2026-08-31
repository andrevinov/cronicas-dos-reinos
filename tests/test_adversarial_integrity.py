from __future__ import annotations

import copy
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

import agentes
import canon_bridge
import canon_bridge_runtime
import integridade_adversarial as adversarial
import locais
import mundo
import oportunidades
import rede_protegida
import sidequests_emergentes as emergent
import test_emergent_sidequest_authoring_registry_v2 as task41_cases


def _masao_fact() -> str:
    agent = agentes.load_agent(ROOT, "masao_hirasawa")["resultado"]
    return next(
        item["fato"] for item in agent["conhecimento"]
        if item["id"] == "ravens_bluff_primeiro_degrau"
    )


def adversarial_contract(spec: dict) -> dict:
    masao_objective = next(
        item["objetivo"] for item in spec["antagonistas"]
        if item["id"] == "masao_hirasawa"
    )
    return {
        "objetivos_antagonistas": [
            {"antagonista_id": "masao_hirasawa", "objetivo": masao_objective}
        ],
        "capacidades_disponiveis": [
            {
                "antagonista_id": "masao_hirasawa",
                "capacidade_id": "compartimentar_pressao_sobre_ren",
                "fonte": "agente",
                "descricao": "Pressão compartimentada por intermediários para impedir uma operação sem expor comando.",
            },
            {
                "antagonista_id": "masao_hirasawa",
                "capacidade_id": "substituir_moradores_gradualmente",
                "fonte": "agente",
                "descricao": "Coação, ameaça, desaparecimento ou documentação podem remover um elo quando isso serve à infraestrutura.",
            },
        ],
        "conhecimentos_disponiveis": [
            {
                "antagonista_id": "masao_hirasawa",
                "conhecimento_id": "ravens_bluff_primeiro_degrau",
                "fonte": "agente",
                "evidencia": _masao_fact(),
            }
        ],
        "estado_se_ren_nao_intervier": (
            "A entrega continua exposta à rede e os intermediários de Masao tentam "
            "converter o elo mais vulnerável em custo operacional antes do fim da janela."
        ),
        "escaladas_possiveis": [
            {
                "id": "interceptar_mensageiro",
                "antagonista_id": "masao_hirasawa",
                "condicao": "A rede identifica a janela da entrega enquanto o mensageiro ainda está alcançável.",
                "capacidade_id": "compartimentar_pressao_sobre_ren",
                "conhecimentos_requeridos": ["ravens_bluff_primeiro_degrau"],
                "alvos": ["mensageiro_cinza_task41"],
                "gravidade": "moderada",
                "reversibilidade": "incerta",
                "classe_impacto": "liberdade",
                "consequencia": "O mensageiro pode ser interceptado e removido da rota por uma célula compartimentada.",
                "prioridade": "preferencial",
                "bloqueios_causais": ["A rota deixa de ser alcançável pela célula antes da janela."],
            },
            {
                "id": "silenciar_elo_critico",
                "antagonista_id": "masao_hirasawa",
                "condicao": "Silva se torna o elo crítico ainda alcançável cuja permanência inviabiliza a operação da rede.",
                "capacidade_id": "substituir_moradores_gradualmente",
                "conhecimentos_requeridos": ["ravens_bluff_primeiro_degrau"],
                "alvos": ["silva_elkwood"],
                "gravidade": "grave",
                "reversibilidade": "incerta",
                "classe_impacto": "liberdade",
                "consequencia": "A rede tenta remover Silva da circulação por coerção ou desaparecimento em vez de preservar o elo por conveniência narrativa.",
                "prioridade": "obrigatoria_se_condicao",
                "bloqueios_causais": [
                    "Silva fica materialmente fora do alcance da rede antes que a remoção possa ser executada."
                ],
            },
        ],
        "consequencias_de_falha": ["interceptar_mensageiro"],
        "consequencias_de_inacao": ["silenciar_elo_critico"],
        "alvos_em_risco": [
            {
                "id": "mensageiro_cinza_task41",
                "tipo": "npc",
                "gravidade_maxima": "grave",
                "descricao": "Portador reservado da entrega e elo material da operação.",
            },
            {
                "id": "silva_elkwood",
                "tipo": "npc",
                "gravidade_maxima": "grave",
                "descricao": "Contato existente que pode se tornar elo crítico se fatos posteriores o colocarem nessa posição.",
            },
        ],
        "gravidade_maxima_causal": "grave",
    }


def _copy_common(repo: Path, *, canon: bool = False) -> None:
    for rel in (oportunidades.INDEX, oportunidades.STATE, emergent.NPC_INDEX):
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    task41_cases.isolate_opportunity_state(repo)
    shutil.copytree(ROOT / locais.INDEX.parent, repo / locais.INDEX.parent)
    shutil.copytree(ROOT / "narrador/agentes", repo / "narrador/agentes")
    for rel in (adversarial.POLICY, rede_protegida.INDEX):
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    if canon:
        shutil.copytree(ROOT / "narrador/arcos/parte_1", repo / "narrador/arcos/parte_1")
        bridge_path = repo / canon_bridge.STATE
        bridge = yaml.safe_load(bridge_path.read_text(encoding="utf-8")) or {}
        bridge["reservas"] = {}
        bridge["resolucoes"] = {}
        bridge["historico_recente"] = []
        bridge_path.write_text(
            yaml.safe_dump(bridge, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        for rel in (mundo.TIME_PATH, mundo.AGENDA_PATH, mundo.WORLD_STATE_PATH):
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)


def _materialize_task41(repo: Path, package: dict, spec: dict) -> tuple[str, str]:
    prep = emergent.prepare(repo, package=package, quest=spec)
    result = emergent.materialize(
        repo,
        package=package,
        quest=spec,
        preparation_id=prep["preparacao_id"],
        offer_was_narrated=True,
        offer_scene_id="sessao-015:task44-oferta",
        offer_summary=(
            "A necessidade e os riscos foram explicados explicitamente, com recusa possível e sem prescrever ação do jogador."
        ),
    )
    return result["quest_id"], result["mission_id"]


def _proof(repo: Path, name: str, text: str) -> dict:
    path = repo / "sessoes/015" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return {"fonte": path.relative_to(repo).as_posix(), "evidencia": text}


class Task44ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41_cases.task40_package()
        cls.spec = task41_cases.quest_spec(cls.package)
        cls.contract = adversarial_contract(cls.spec)

    def test_preparacao_e_read_only_e_congela_stakes_antes_do_aceite(self):
        result = adversarial.prepare(
            ROOT, package=self.package, quest=self.spec, contract=self.contract
        )
        self.assertTrue(result["read_only"])
        self.assertFalse(result["mutacoes_aplicadas"])
        self.assertEqual(result["gravidade_maxima_causal"], "grave")
        self.assertEqual(result["resumo"]["escaladas"], 2)
        self.assertLessEqual(
            len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")),
            adversarial.MAX_PREP_BYTES,
        )

    def test_agente_nao_recebe_capacidade_inventada(self):
        bad = copy.deepcopy(self.contract)
        bad["capacidades_disponiveis"][0]["capacidade_id"] = "matar_qualquer_testemunha_por_conveniencia"
        with self.assertRaisesRegex(adversarial.AdversarialIntegrityError, "capacidade inventada"):
            adversarial.prepare(ROOT, package=self.package, quest=self.spec, contract=bad)

    def test_juppongatana_nao_age_sobre_segredo_que_nao_conhece(self):
        result = adversarial.agent_option(
            ROOT,
            "kajiwara_shizune",
            "fabricar_registro_contraditorio",
            required_knowledge=["segredo_que_shizune_nao_conhece"],
        )
        self.assertFalse(result["permitida"])
        self.assertEqual(result["motivo"], "conhecimento_canonico_ausente")

    def test_shizune_tem_metodos_reais_sem_ganhar_eliminacao_fisica_automatica(self):
        valid = adversarial.agent_option(ROOT, "kajiwara_shizune", "fabricar_registro_contraditorio")
        self.assertTrue(valid["permitida"])
        lethal = adversarial.agent_option(ROOT, "kajiwara_shizune", "eliminar_testemunha")
        self.assertFalse(lethal["permitida"])
        self.assertEqual(lethal["motivo"], "capacidade_nao_disponivel")

    def test_materializacao_e_idempotente_e_obrigatoria_para_quest_materializada(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _copy_common(repo)
            qid, mid = _materialize_task41(repo, self.package, self.spec)
            before = adversarial.validate_repo(repo)
            self.assertFalse(before["ok"])
            prep = adversarial.prepare(repo, package=self.package, quest=self.spec, contract=self.contract)
            first = adversarial.materialize(
                repo,
                package=self.package,
                quest=self.spec,
                contract=self.contract,
                preparation_id=prep["preparacao_id"],
            )
            second = adversarial.materialize(
                repo,
                package=self.package,
                quest=self.spec,
                contract=self.contract,
                preparation_id=prep["preparacao_id"],
            )
            self.assertEqual(first["resultado"], "materializado")
            self.assertEqual(second["resultado"], "ja_materializado")
            self.assertEqual(first["quest_id"], qid)
            self.assertEqual(first["mission_id"], mid)
            self.assertTrue(adversarial.validate_repo(repo)["ok"])


class Task44CompetentVillainTest(unittest.TestCase):
    def test_pan_chu_nao_bombardeia_por_ordem_simples_mas_coercao_abre_escalada(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            shutil.copytree(ROOT / "narrador/agentes", repo / "narrador/agentes")
            denied = adversarial.agent_conditional_escalation(
                repo, "pan_chu", "tentativa_de_expulsao"
            )
            self.assertFalse(denied["permitida"])
            self.assertEqual(denied["motivo"], "gatilho_nao_demonstrado")
            proof = _proof(
                repo,
                "golden-lily.md",
                "A autoridade tentou apreender o Golden Lily por força e cercou o navio para removê-lo do porto.",
            )
            allowed = adversarial.agent_conditional_escalation(
                repo, "pan_chu", "tentativa_de_expulsao", proof=proof
            )
            self.assertTrue(allowed["permitida"])
            self.assertIn("força naval destrutiva", allowed["escalada"]["abordagem"])

    def test_masao_nao_pode_ser_amaciado_quando_escalada_obrigatoria_foi_provada(self):
        package = task41_cases.task40_package()
        spec = task41_cases.quest_spec(package)
        contract = adversarial_contract(spec)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _copy_common(repo)
            _, mid = _materialize_task41(repo, package, spec)
            prep = adversarial.prepare(repo, package=package, quest=spec, contract=contract)
            adversarial.materialize(
                repo, package=package, quest=spec, contract=contract,
                preparation_id=prep["preparacao_id"],
            )
            now = mundo.parse_instant(
                package["prazo_mundo"]["agora"]["data"], package["prazo_mundo"]["agora"]["hora"]
            )
            oportunidades.respond(repo, mid, "aceitar", now=now)
            mandatory_proof = _proof(
                repo,
                "masao-stake.md",
                "Silva se tornou o elo crítico ainda alcançável e sua permanência inviabiliza a operação da rede.",
            )
            with self.assertRaisesRegex(adversarial.AdversarialIntegrityError, "consequência mais branda"):
                adversarial.resolve_escalation_choice(
                    repo,
                    mid,
                    chosen_escalation_id="interceptar_mensageiro",
                    proofs={"silenciar_elo_critico": mandatory_proof},
                )
            blocker_proof = _proof(
                repo,
                "silva-fora-alcance.md",
                "Silva deixou a área sob proteção institucional e ficou materialmente fora do alcance da rede.",
            )
            resolved = adversarial.resolve_escalation_choice(
                repo,
                mid,
                chosen_escalation_id="interceptar_mensageiro",
                proofs={"silenciar_elo_critico": mandatory_proof},
                blocker={
                    "escalada_id": "silenciar_elo_critico",
                    "indice": 0,
                    **blocker_proof,
                },
            )
            self.assertEqual(resolved["escolhida"], "interceptar_mensageiro")
            self.assertIsNotNone(resolved["bloqueio_causal"])


class Task44ProtectedCoreAuthorityTest(unittest.TestCase):
    def test_procedural_grave_continua_bloqueado_mas_evento_canonico_pode_expor_nucleo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for rel in (adversarial.POLICY, rede_protegida.INDEX):
                target = repo / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            consequence = {
                "titulo": "Risco real",
                "descricao": "Nera fica em risco grave por uma ação já materializada.",
                "gravidade": "grave",
                "reversibilidade": "incerta",
                "classe_impacto": "vida",
                "alvos_npc": ["nera_vell"],
            }
            with self.assertRaises(adversarial.AdversarialIntegrityError):
                adversarial.authorize_external_consequence(
                    repo, consequence, authority="procedural"
                )
            proof = _proof(
                repo,
                "evento-canonico.md",
                "O agressor alcançou Nera durante o evento canônico e sua vida passou a estar diretamente em risco.",
            )
            allowed = adversarial.authorize_external_consequence(
                repo, consequence, authority="evento_canonico", proof=proof
            )
            self.assertEqual(allowed["autoridade"], "evento_canonico")
            self.assertEqual(allowed["alvos_protegidos"], ["nera_vell"])

    def test_sidequest_lateral_nao_pode_sequestrar_silva_gravemente(self):
        package = task41_cases.task40_package()
        spec = task41_cases.quest_spec(package)
        contract = adversarial_contract(spec)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _copy_common(repo)
            _, mid = _materialize_task41(repo, package, spec)
            prep = adversarial.prepare(repo, package=package, quest=spec, contract=contract)
            adversarial.materialize(
                repo, package=package, quest=spec, contract=contract,
                preparation_id=prep["preparacao_id"],
            )
            now = mundo.parse_instant(
                package["prazo_mundo"]["agora"]["data"], package["prazo_mundo"]["agora"]["hora"]
            )
            oportunidades.respond(repo, mid, "aceitar", now=now)
            proof = _proof(
                repo,
                "silva-alvo.md",
                "Silva se tornou o elo crítico ainda alcançável e a rede iniciou a remoção dele da circulação.",
            )
            with self.assertRaisesRegex(adversarial.AdversarialIntegrityError, "grave bloqueada"):
                adversarial.authorize_sidequest_consequence(
                    repo,
                    mid,
                    {
                        "titulo": "Remoção de Silva",
                        "descricao": "A rede tenta remover Silva da circulação.",
                        "escalada_id": "silenciar_elo_critico",
                        "gravidade": "grave",
                        "reversibilidade": "incerta",
                        "classe_impacto": "liberdade",
                        "alvos_npc": ["silva_elkwood"],
                    },
                    proof=proof,
                )

    def test_sidequest_formalmente_ligada_ao_canone_pode_expor_core_sem_teleporte(self):
        package = task41_cases.task40_package()
        compatible = package["horizonte_intencoes_canonicas"]["compativeis"]
        if not compatible:
            self.skipTest("horizonte Task40 sem intenção compatível")
        candidate = compatible[0]
        spec = task41_cases.quest_spec(package)
        spec["relacao_canone"] = {
            "modo": "candidata_ponte",
            "intencoes_candidatas": [candidate["evento_id"]],
            "justificativa": "A fase final coincide com a janela canônica sem determinar presença ou ação de Ren.",
        }
        spec["prazo"] = {"tipo": "temporal", "expira_em": copy.deepcopy(candidate["ativacao"])}
        contract = adversarial_contract(spec)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _copy_common(repo, canon=True)
            _, mid = _materialize_task41(repo, package, spec)
            prep = adversarial.prepare(repo, package=package, quest=spec, contract=contract)
            adversarial.materialize(
                repo, package=package, quest=spec, contract=contract,
                preparation_id=prep["preparacao_id"],
            )
            now = mundo.parse_instant(
                package["prazo_mundo"]["agora"]["data"], package["prazo_mundo"]["agora"]["hora"]
            )
            accepted = canon_bridge_runtime.respond(repo, mid, "aceitar", now=now)
            self.assertEqual(accepted["canon_bridge"]["resultado"], "reserva_criada")
            proof = _proof(
                repo,
                "silva-canonico.md",
                "Silva se tornou o elo crítico ainda alcançável e a rede iniciou a remoção dele da circulação.",
            )
            allowed = adversarial.authorize_sidequest_consequence(
                repo,
                mid,
                {
                    "titulo": "Remoção de Silva",
                    "descricao": "A rede tenta remover Silva da circulação.",
                    "escalada_id": "silenciar_elo_critico",
                    "gravidade": "grave",
                    "reversibilidade": "incerta",
                    "classe_impacto": "liberdade",
                    "alvos_npc": ["silva_elkwood"],
                },
                proof=proof,
            )
            self.assertEqual(allowed["autoridade"], "sidequest_canonica")
            self.assertEqual(allowed["alvos_protegidos"], ["silva_elkwood"])
            self.assertIn("vinculo_canonico", allowed["valor"])


class Task44BudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo_e_zero_infra_automatica(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/adversarial-integrity-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        self.assertEqual(limits["contrato_por_quest_bytes_max"], adversarial.MAX_CONTRACT_BYTES)
        self.assertEqual(limits["preparacao_saida_bytes_max"], adversarial.MAX_PREP_BYTES)
        self.assertEqual(limits["objetivos_antagonistas_max"], adversarial.MAX_OBJECTIVES)
        self.assertEqual(limits["capacidades_max"], adversarial.MAX_CAPABILITIES)
        self.assertEqual(limits["conhecimentos_max"], adversarial.MAX_KNOWLEDGE)
        self.assertEqual(limits["escaladas_max"], adversarial.MAX_ESCALATIONS)
        self.assertEqual(limits["alvos_em_risco_max"], adversarial.MAX_RISK_TARGETS)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["scans_globais"], 0)
        source = (ROOT / "ferramentas/integridade_adversarial.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("rglob(", source)
        self.assertNotIn("glob(", source)

    def test_repo_real_com_sidequests_emergentes_permanece_valido(self):
        result = adversarial.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        state = oportunidades.load_state(ROOT, oportunidades.load_index(ROOT))
        expected = sum(
            1
            for mission in state["missoes"].values()
            if mission.get("origem") == "sidequest_emergente"
        )
        self.assertEqual(result["contratos"], expected)


if __name__ == "__main__":
    unittest.main()
