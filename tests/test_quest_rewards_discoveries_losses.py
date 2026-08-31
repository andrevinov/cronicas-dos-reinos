from __future__ import annotations

import copy
import json
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

import mundo
import oportunidades
import recompensas_sidequest as qr
import sidequests_emergentes as emergent
import test_emergent_sidequest_authoring_registry_v2 as task41
import transacoes

EVIDENCE_TEXT = "Silva confirmou que a obrigação principal foi cumprida e que a rota segura permaneceu sob controle dos aliados ao fim da operação."
PROPERTY_TEXT = "A proprietária legítima da Casa do Salgueiro Seco declarou que somente ela pode conceder direito de uso, opção de compra ou transferir a propriedade."
DISCOVERY_TEXT = "A busca no compartimento falso revelou a bainha embrulhada sob as tábuas, antes que o esconderijo fosse destruído."
LOSS_TEXT = "A oposição identificou de forma durável a rota segura usada na entrega; o canal precisou ser abandonado e não pode mais servir como acesso discreto."


def base_contract() -> dict:
    return {
        "recompensa_principal": {"id": "pagamento_silva", "tipo": "dinheiro", "efeito": {"po": 300}, "autoridade_concedente": {"tipo": "quest_giver", "id": "silva_elkwood"}},
        "recompensas_opcionais": [],
        "recompensas_descobríveis": [],
        "recompensas_condicionais": [{"id": "favor_da_rede", "tipo": "favor", "efeito": {"ativo_id": "favor_entrega_segura", "nome": "Favor da rede protegida", "descricao": "Um favor concreto devido pela pessoa beneficiada pela entrega."}, "autoridade_concedente": {"tipo": "outro", "id": "beneficiario_entrega"}}],
        "perdas_possiveis": [{"id": "perda_rota_segura", "stake_tipo": "acesso", "stake_alvo": "rota_segura", "efeito": {"ativo_id": "rota_segura"}}],
    }


def discovered_spec(package: dict) -> dict:
    spec = task41.quest_spec(package)
    spec["recompensas"].append({"id": "katana_oculta", "tipo": "item_magico", "modo": "descoberta", "descricao": "Uma katana mágica escondida no interior da rota ameaçada.", "condicao": "O compartimento precisa ser encontrado antes de ser destruído.", "valor_aproximado": "baixo", "autoridade_concedente": "A posse decorre da descoberta legítima do tesouro abandonado."})
    return spec


def discovered_contract() -> dict:
    contract = base_contract()
    contract["recompensas_descobríveis"] = [{"id": "katana_oculta", "tipo": "item_magico", "efeito": {"nome": "Katana da Vigília Cinzenta", "quantidade": 1, "descricao_inventario": "Katana da Vigília Cinzenta, item mágico descoberto na sidequest", "tier": 2, "raridade": "incomum"}, "autoridade_concedente": {"tipo": "mundo", "id": "tesouro_abandonado"}, "descoberta": {"condicao": "O compartimento falso é localizado antes que a oposição destrua o esconderijo.", "teste": {"requerido": True, "pericia": "Investigação", "cd": 15}, "falha": "perdida_permanentemente", "momento_entrega": "imediata"}}]
    return contract


class Task43Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41.task40_package()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.repo = Path(self.temp.name)
        for rel in (oportunidades.INDEX, oportunidades.STATE, emergent.NPC_INDEX, qr.STATE_PATH, qr.SHEET_PATH):
            dst = self.repo / rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / rel, dst)
        task41.isolate_opportunity_state(self.repo)
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        (self.repo / "runtime").mkdir(parents=True, exist_ok=True)
        (self.repo / "runtime/contexto.yaml").write_text("sessao:\n  numero: 15\n  status: em_sessao\n", encoding="utf-8")
        (self.repo / transacoes.PENDING_PATH).write_text("", encoding="utf-8")
        (self.repo / "runtime/mundo-pendencias.yaml").write_text("schema_barreira_mundo: 1\nnatureza: runtime_derivado\nbloqueado: false\nquantidade: 0\ndisparo_mais_antigo: null\n", encoding="utf-8")
        session = self.repo / "sessoes/015"; session.mkdir(parents=True, exist_ok=True); (session / "transcricao.md").write_text("# Sessão 015 — fixture Task43\n", encoding="utf-8")
        self.evidence = session / "evidencia-task43.md"; self.evidence.write_text("\n".join([EVIDENCE_TEXT, PROPERTY_TEXT, DISCOVERY_TEXT, LOSS_TEXT]) + "\n", encoding="utf-8")

    def tearDown(self): self.temp.cleanup()
    def proof(self, text: str) -> dict: return {"fonte": "sessoes/015/evidencia-task43.md", "evidencia": text}

    def materialize(self, spec: dict | None = None) -> str:
        spec = copy.deepcopy(spec or task41.quest_spec(self.package)); prep = emergent.prepare(self.repo, package=self.package, quest=spec)
        result = emergent.materialize(self.repo, package=self.package, quest=spec, preparation_id=prep["preparacao_id"], offer_was_narrated=True, offer_scene_id="task43:oferta", offer_summary="Silva apresentou um pedido concreto e deixou claro que Ren poderia recusar a missão.")
        return result["mission_id"]

    def register(self, mid: str, contract: dict | None = None) -> dict:
        return qr.register_contract(self.repo, mid, package_raw=self.package, contract_raw=copy.deepcopy(contract or base_contract()))

    def now(self) -> mundo.WorldInstant:
        raw = self.package["prazo_mundo"]["agora"]; return mundo.parse_instant(raw["data"], raw["hora"])
    def accept(self, mid: str) -> None: oportunidades.respond(self.repo, mid, "aceitar", now=self.now())
    def complete(self, mid: str) -> None:
        self.accept(mid); oportunidades.finish(self.repo, mid, "concluida", reason="As condições objetivas da missão foram cumpridas.", now=mundo.WorldInstant(self.now().minute + 60))
    def fail(self, mid: str) -> None:
        self.accept(mid); oportunidades.finish(self.repo, mid, "falhada", reason="A oposição consolidou a falha objetiva prevista pela missão.", now=mundo.WorldInstant(self.now().minute + 60))
    def pending(self) -> list[dict]: return transacoes.load_pending(self.repo)


class Task43ContractTest(Task43Fixture):
    def test_toda_sidequest_materializada_exige_contrato_e_registro_e_idempotente(self):
        mid = self.materialize(); self.assertFalse(qr.check(self.repo)["ok"]); first = self.register(mid); second = self.register(mid)
        self.assertEqual(first["resultado"], "contrato_registrado"); self.assertEqual(second["resultado"], "contrato_ja_existia"); self.assertTrue(qr.check(self.repo)["ok"])

    def test_item_magico_respeita_tier_e_orcamento(self):
        mid = self.materialize(discovered_spec(self.package)); bad = discovered_contract(); bad["recompensas_descobríveis"][0]["efeito"]["tier"] = 3
        with self.assertRaisesRegex(qr.QuestRewardError, "tier 2|excede tier"): self.register(mid, bad)
        result = self.register(mid, discovered_contract()); self.assertEqual(result["orcamento"]["pontos_material"], 5); self.assertEqual(result["orcamento"]["pontos_disponiveis"], 5)

    def test_propriedade_exige_autoridade_canonica(self):
        spec = task41.quest_spec(self.package); spec["recompensas"][0] = {"id": "direito_sobre_casa", "tipo": "propriedade", "modo": "sucesso", "descricao": "Transferência ou opção juridicamente válida sobre uma propriedade específica.", "condicao": "A proprietária legítima mantém autoridade e a obrigação pactuada é cumprida.", "valor_aproximado": "especial", "autoridade_concedente": "Somente a proprietária legítima pode conceder o direito."}
        mid = self.materialize(spec); contract = base_contract(); contract["recompensa_principal"] = {"id": "direito_sobre_casa", "tipo": "propriedade", "efeito": {"ativo_id": "casa_salgueiro_seco", "nome": "Casa do Salgueiro Seco", "descricao": "Direito negociado sobre a Casa do Salgueiro Seco."}, "autoridade_concedente": {"tipo": "proprietario", "id": "proprietaria_casa_salgueiro"}}
        with self.assertRaisesRegex(qr.QuestRewardError, "prova canônica"): self.register(mid, contract)
        contract["recompensa_principal"]["autoridade_concedente"].update(self.proof(PROPERTY_TEXT)); self.assertEqual(self.register(mid, contract)["resultado"], "contrato_registrado")


class Task43RewardTest(Task43Fixture):
    def test_sucesso_concede_300_po_exatamente_uma_vez_e_retry_nao_duplica(self):
        mid = self.materialize(); self.register(mid); self.complete(mid); before = yaml.safe_load((self.repo / qr.STATE_PATH).read_text())["recursos"]["dinheiro"]["po"]
        first = qr.apply_success(self.repo, mid, optional_ids=[], evidences={}, narration="Silva cumpre o acordo e entrega a Ren as trezentas peças de ouro prometidas pela missão concluída.")
        second = qr.apply_success(self.repo, mid, optional_ids=[], evidences={}, narration="Silva cumpre o acordo e entrega a Ren as trezentas peças de ouro prometidas pela missão concluída.")
        self.assertEqual(first["resultado"], "recompensas_obtidas"); self.assertEqual(second["resultado"], "nenhuma_recompensa_nova"); self.assertEqual(len(self.pending()), 1)
        effective, _ = transacoes.overlay_target(yaml.safe_load((self.repo / qr.STATE_PATH).read_text()), self.pending(), "estado"); self.assertAlmostEqual(effective["recursos"]["dinheiro"]["po"], before + 300)

    def test_principal_e_condicional_coexistem_e_ativo_vai_para_estado(self):
        mid = self.materialize(); self.register(mid); self.complete(mid)
        result = qr.apply_success(self.repo, mid, optional_ids=[], evidences={"favor_da_rede": self.proof(EVIDENCE_TEXT)}, narration="Além do pagamento, a pessoa beneficiada reconhece a ajuda e concede a Ren um favor concreto para uso futuro.")
        self.assertEqual(set(result["reward_ids"]), {"pagamento_silva", "favor_da_rede"}); effective, _ = transacoes.overlay_target(yaml.safe_load((self.repo / qr.STATE_PATH).read_text()), self.pending(), "estado"); self.assertEqual(effective["ativos_narrativos"]["favor"][0]["id"], "favor_entrega_segura")

    def test_oculto_nao_e_concedido_sem_descoberta_e_item_obtido_transaciona_ficha_e_estado(self):
        mid = self.materialize(discovered_spec(self.package)); self.register(mid, discovered_contract()); self.complete(mid)
        result = qr.apply_success(self.repo, mid, optional_ids=[], evidences={}, narration="Silva paga a recompensa principal pela missão concluída, sem que nenhum tesouro oculto tenha sido encontrado."); self.assertNotIn("katana_oculta", result["reward_ids"]); self.assertFalse(any("Katana da Vigília" in json.dumps(x, ensure_ascii=False) for x in self.pending()))
        opp = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo)); opp["missoes"][mid]["estado"] = "aceita"; oportunidades.atomic(self.repo / oportunidades.STATE, opp)
        found = qr.resolve_discovery(self.repo, mid, "katana_oculta", success=True, evidence=self.proof(DISCOVERY_TEXT), test_result={"rotulo": "Investigação CD 15: sucesso", "sucesso": True}, narration="Ren encontra o compartimento falso antes de sua destruição e retira dali a Katana da Vigília Cinzenta.")
        self.assertEqual(found["resultado"], "obtida"); records = self.pending(); sheet, _ = transacoes.overlay_target(yaml.safe_load((self.repo / qr.SHEET_PATH).read_text()), records, "ficha"); state, _ = transacoes.overlay_target(yaml.safe_load((self.repo / qr.STATE_PATH).read_text()), records, "estado"); item = "Katana da Vigília Cinzenta, item mágico descoberto na sidequest"; self.assertIn(item, sheet["equipamento"]["itens"]); self.assertIn(item, state["equipamento_em_posse"]["itens_importantes"])

    def test_teste_falho_pode_perder_tesouro_permanentemente(self):
        mid = self.materialize(discovered_spec(self.package)); self.register(mid, discovered_contract()); self.accept(mid)
        result = qr.resolve_discovery(self.repo, mid, "katana_oculta", success=False, evidence=self.proof(DISCOVERY_TEXT), test_result={"rotulo": "Investigação CD 15: falha", "sucesso": False})
        self.assertEqual(result["resultado"], "perdida_permanentemente"); self.assertEqual(qr.status(self.repo, mid)["recompensas"]["katana_oculta"]["estado"], "perdida"); self.assertEqual(self.pending(), [])


class Task43LossAndRecoveryTest(Task43Fixture):
    def test_falha_nao_inventa_perda_sem_contrato_ou_sem_causalidade(self):
        mid = self.materialize(); self.register(mid); self.fail(mid)
        with self.assertRaisesRegex(qr.QuestRewardError, "não contratada"): qr.apply_losses(self.repo, mid, evidences={"roubar_200_po": self.proof(LOSS_TEXT)}, narration="A falha custa dinheiro a Ren de modo arbitrário.")
        with self.assertRaisesRegex(qr.QuestRewardError, "não existe|não pode inventar perda"): qr.apply_losses(self.repo, mid, evidences={"perda_rota_segura": self.proof(LOSS_TEXT)}, narration="A rota comprometida deixa de servir como acesso seguro depois da falha da operação.")
        self.assertEqual(self.pending(), [])

    def test_perda_contratada_com_ativo_existente_e_prova_aplica_uma_vez(self):
        state = yaml.safe_load((self.repo / qr.STATE_PATH).read_text()); state.setdefault("ativos_narrativos", {}).setdefault("acesso", []).append({"id": "rota_segura", "tipo": "acesso", "nome": "Rota segura", "descricao": "Canal discreto disponível", "origem": "fixture"}); (self.repo / qr.STATE_PATH).write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
        mid = self.materialize(); self.register(mid); self.fail(mid)
        first = qr.apply_losses(self.repo, mid, evidences={"perda_rota_segura": self.proof(LOSS_TEXT)}, narration="A oposição consolida a identificação da rota, que deixa de existir como canal seguro para Ren."); second = qr.apply_losses(self.repo, mid, evidences={"perda_rota_segura": self.proof(LOSS_TEXT)}, narration="A oposição consolida a identificação da rota, que deixa de existir como canal seguro para Ren.")
        self.assertEqual(first["resultado"], "perdas_aplicadas"); self.assertEqual(second["resultado"], "nenhuma_perda_nova"); self.assertEqual(len(self.pending()), 1)

    def test_retry_pos_checkpoint_repara_ledger_task43_sem_reaplicar(self):
        mid = self.materialize(); self.register(mid); self.complete(mid); result = qr.apply_success(self.repo, mid, optional_ids=[], evidences={}, narration="Silva entrega a Ren o pagamento prometido pela missão concluída, encerrando a obrigação principal."); tx = self.pending()[0]; txid = result["transacao_id"]
        state = yaml.safe_load((self.repo / qr.STATE_PATH).read_text()); sheet = yaml.safe_load((self.repo / qr.SHEET_PATH).read_text())
        for delta in tx["deltas"]:
            if delta["alvo"] == "estado": transacoes.apply_delta(state, delta)
            elif delta["alvo"] == "ficha": transacoes.apply_delta(sheet, delta)
        sheet["equipamento"]["dinheiro"]["po"] = state["recursos"]["dinheiro"]["po"]; (self.repo / qr.STATE_PATH).write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"); (self.repo / qr.SHEET_PATH).write_text(yaml.safe_dump(sheet, allow_unicode=True, sort_keys=False), encoding="utf-8"); (self.repo / transacoes.PENDING_PATH).write_text("", encoding="utf-8"); (self.repo / "sessoes/015/consolidacoes.jsonl").write_text(json.dumps({"id": "fixture", "transacoes": [txid]}, ensure_ascii=False) + "\n", encoding="utf-8")
        _, _, mission = qr._mission(self.repo, mid); doc, rel = qr._load_contract(self.repo, mission, mid); doc["estado"]["recompensas"]["pagamento_silva"]["estado"] = "pendente"; doc["estado"]["recompensas"]["pagamento_silva"]["transacao"] = None; qr._atomic(self.repo / rel, doc); before = state["recursos"]["dinheiro"]["po"]
        repaired = qr.apply_success(self.repo, mid, optional_ids=[], evidences={}, narration="Silva entrega a Ren o pagamento prometido pela missão concluída, encerrando a obrigação principal."); after = yaml.safe_load((self.repo / qr.STATE_PATH).read_text())["recursos"]["dinheiro"]["po"]
        self.assertEqual(repaired["transacao_id"], txid); self.assertEqual(self.pending(), []); self.assertEqual(after, before); self.assertEqual(qr.status(self.repo, mid)["recompensas"]["pagamento_silva"]["estado"], "obtida")


class Task43BudgetTest(unittest.TestCase):
    def test_repo_real_sem_sidequest_emergente_permanece_valido_e_sem_infra_automatica(self):
        result = qr.check(ROOT); self.assertTrue(result["ok"], result["erros"]); self.assertEqual(result["scheduler_novo"], 0); self.assertEqual(result["rng_novo"], 0); self.assertEqual(result["scans_globais"], 0)
        source = (ROOT / "ferramentas/recompensas_sidequest.py").read_text(encoding="utf-8"); self.assertNotIn("rglob(", source); self.assertNotIn("random.", source)


if __name__ == "__main__": unittest.main()
