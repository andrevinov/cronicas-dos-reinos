"""Adaptador de planos usa operações reais; não duplica combate ou seus efeitos."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
import planos_personagens as plans
import mundo
import transacoes
import operacoes_concorrentes as operations
import resolver_fronteira as batch
from tests.test_concurrent_world_operations import ConcurrentOperationFixture, ACTOR_ID, RESULT_EVIDENCE


class PlansOperationTest(ConcurrentOperationFixture):
    def hashes(self):
        return {str(p.relative_to(self.repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.repo.rglob("*") if p.is_file()}

    def event(self, kind, revision, **extra):
        return {"evento": kind, "revisao": revision, "fato": RESULT_EVIDENCE, **extra}

    def record(self, value, key):
        return transacoes.build_pending_record({"id": key, "modo": "mundo", "narracao": value["fato"],
            "deltas": [{"alvo": "plano:rota", "op": "registrar", "visibilidade": "narrador", "valor": value}]}, 1)

    def stage_event(self, value, key):
        before = self.hashes()
        world, agenda = plans.compute(self.repo, [self.record(value, key)])
        self.assertEqual(before, self.hashes())  # o adaptador não instala estado por conta própria
        self.yaml(mundo.WORLD_STATE_PATH, world)
        self.yaml(mundo.AGENDA_PATH, agenda)
        return world[plans.KEY]["rota"]

    def define(self):
        actor = yaml.safe_load((self.repo / f"narrador/agentes/{ACTOR_ID}.yaml").read_text())
        step = {"id": "tomar_matriz", "acao": "Tentar tomar a matriz documental.", "em": mundo.instant_parts(self.now),
            "duracao_minutos": 0, "local": "rua_da_guarda", "condicoes": [], "conhecimento": [], "recursos": [],
            "resolucao": {"tipo": "operacao", "operacao_id": "ataque_comitiva"}}
        return self.stage_event(self.event("definir", 0, agente={"tipo": "estrategico", "id": ACTOR_ID},
                                objetivo=actor["objetivo_atual"], passo=step), "definir-operacao")

    def resolution(self, outcome="sucesso", follow="concluir"):
        return self.event("resolver", 2, resultado=outcome, seguimento=follow,
                          motivo="A operação teve resultado canônico e o agente decide como continuar.",
                          passo=None, retomar_em=None, rolagem=None, prova=None)

    def test_operacao_sem_compromisso_nao_autoriza_tentativa_do_plano(self):
        self.materialize_group()
        self.define()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "comprometida"):
            plans.compute(self.repo, [self.record(self.event("tentar", 1), "tentativa")])
        self.assertEqual(before, self.hashes())

    def test_resultado_da_operacao_avanca_plano_sem_reaplicar_seus_efeitos(self):
        group, _ = self.materialize_group()
        operations.commit_group(self.repo, group["grupo_operacoes_id"])
        self.define()
        self.stage_event(self.event("tentar", 1), "tentativa")
        with self.assertRaisesRegex(ValueError, "resultado canônico"):
            plans.compute(self.repo, [self.record(self.resolution(), "resultado")])
        operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(RESULT_EVIDENCE), RESULT_EVIDENCE, desfecho="sucesso")
        operation_bytes = (self.repo / operations.STATE).read_bytes()
        plan = self.stage_event(self.resolution(), "resultado")
        self.assertEqual(plan["estado"], "concluido")
        self.assertEqual(plan["ultima_tentativa"]["resultado"]["operacao"]["desfecho"], "sucesso")
        self.assertEqual(operation_bytes, (self.repo / operations.STATE).read_bytes())
        other = operations._operation_context(self.repo, "extracao_testemunha")[2]
        self.assertEqual(other["estado"], "comprometida")

    def test_prosa_de_operacao_legada_nao_vira_sucesso_implicitamente(self):
        group, _ = self.materialize_group()
        operations.commit_group(self.repo, group["grupo_operacoes_id"])
        self.define()
        self.stage_event(self.event("tentar", 1), "tentativa")
        operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(RESULT_EVIDENCE), RESULT_EVIDENCE)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "desfecho estruturado"):
            plans.compute(self.repo, [self.record(self.resolution(), "resultado")])
        self.assertEqual(before, self.hashes())

    def test_desfecho_incompativel_nao_promove_falha_a_objetivo_concluido(self):
        group, _ = self.materialize_group()
        operations.commit_group(self.repo, group["grupo_operacoes_id"])
        self.define()
        self.stage_event(self.event("tentar", 1), "tentativa")
        operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(RESULT_EVIDENCE), RESULT_EVIDENCE, desfecho="falha")
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "desfecho estruturado"):
            plans.compute(self.repo, [self.record(self.resolution(), "resultado")])
        self.assertEqual(before, self.hashes())
        plan = self.stage_event(self.resolution("falha", "desistir"), "resultado-falho")
        self.assertEqual(plan["estado"], "desistiu")

    def test_validacao_pura_de_grupo_preserva_arquivos_e_mecanica(self):
        group, _ = self.materialize_group()
        before = self.hashes()
        result = operations.commit_group(self.repo, group["grupo_operacoes_id"], validate_only=True)
        self.assertFalse(result["mutante"])
        self.assertEqual(before, self.hashes())
        with self.assertRaises(ValueError):
            operations.commit_group(self.repo, group["grupo_operacoes_id"], {
                "ataque_comitiva": {"motivo": "Ocorreu um impedimento verificável.",
                                    "prova": self.proof("Não existe este fato na fonte.")}}, validate_only=True)
        self.assertEqual(before, self.hashes())

    def test_prevalidacao_nao_recupera_journal_aberto_por_efeito_colateral(self):
        group, _ = self.materialize_group()
        with self.assertRaises(operations.ConcurrentOperationError):
            operations.commit_group(self.repo, group["grupo_operacoes_id"], fail_after=1)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "journal"):
            operations.commit_group(self.repo, group["grupo_operacoes_id"], validate_only=True)
        self.assertEqual(before, self.hashes())

    def test_cli_registra_desfecho_estruturado_sem_novo_motor(self):
        group, _ = self.materialize_group()
        operations.commit_group(self.repo, group["grupo_operacoes_id"])
        run = subprocess.run([sys.executable, str(TOOLS / "operacoes_concorrentes.py"), "--repo", str(self.repo),
            "resolver", "ataque_comitiva", "--resultado", RESULT_EVIDENCE, "--desfecho", "sucesso"],
            input=yaml.safe_dump(self.proof(RESULT_EVIDENCE), allow_unicode=True), capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(operations._operation_context(self.repo, "ataque_comitiva")[2]["resolucao"]["desfecho"], "sucesso")

    def test_capacidade_adversaria_nao_contorna_operacoes_com_teste_simples(self):
        self.materialize_group()
        plan = self.define()
        plan["passo"]["resolucao"] = {"tipo": "factual", "sem_oposicao": {
            "arquivo": "narrador/agentes/index.yaml", "caminho": "autorizacao", "valor": True}}
        before = self.hashes()
        blockers = plans._gates(plans.View(self.repo, []), plan, self.now)
        self.assertIn("agente adversarial", " ".join(blockers))
        self.assertEqual(before, self.hashes())


if __name__ == "__main__":
    unittest.main()
