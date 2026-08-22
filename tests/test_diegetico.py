from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
sys.path.insert(0, str(TOOLS))

import diegetico
import transacoes

TURN_PATH = TOOLS / "turno.py"
spec = importlib.util.spec_from_file_location("turno_diegetico", TURN_PATH)
turno = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(turno)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DiegeticGuardUnitTest(unittest.TestCase):
    def test_prosa_normal_e_diegética(self):
        text = (
            "O homem apoia a mão na parede. A respiração vem curta e a guarda já não sobe com a mesma firmeza.\n"
            "— Ainda consigo lutar — rosna ele."
        )
        self.assertEqual(diegetico.validate_narration(text), text)

    def test_sete_categorias_mecanicas_falham_na_prosa(self):
        cases = {
            "pv": "O homem ainda tem 8 PV.",
            "ca": "A armadura dele concede CA 18.",
            "ca_nome": "A Classe de Armadura dele é dezoito.",
            "cd": "A fechadura tem CD 15.",
            "cd_nome": "A Classe de Dificuldade da fechadura é quinze.",
            "nivel": "Ele é um guerreiro de nível 7.",
            "ki": "Ren ainda possui 4 pontos de Ki.",
            "slots": "A maga gastou todos os slots de magia.",
            "bonus": "O guarda tem bônus de +5 no ataque.",
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(diegetico.DiegeticMechanicsError):
                    diegetico.validate_narration(text)

    def test_fala_de_npc_nao_fura_guardrail(self):
        with self.assertRaises(diegetico.DiegeticMechanicsError):
            diegetico.validate_narration('— Minha CA é 18 — diz o mercenário.')

    def test_linha_mecanica_explicita_e_permitida(self):
        text = (
            "O guarda estreita os olhos para Shinta.\n\n"
            "MECÂNICA — Faça um teste de Enganação, CD 14."
        )
        self.assertEqual(diegetico.validate_narration(text), text)
        self.assertEqual(diegetico.violations(text), [])

    def test_marcador_mecanico_vazio_falha(self):
        with self.assertRaises(diegetico.DiegeticMechanicsError):
            diegetico.validate_narration("O guarda espera.\nMECÂNICA —")

    def test_palavras_diegéticas_nao_viram_falso_positivo(self):
        text = (
            "Ren sente o ki se concentrar no baixo ventre. "
            "O nível da água sobe até a canela. "
            "O capataz promete um bônus de cinco moedas pelo serviço noturno."
        )
        self.assertEqual(diegetico.violations(text), [])

    def test_resumo_e_delta_continuam_podendo_ser_mecanicos(self):
        tx = {
            "narracao": "O golpe entra sob as costelas e Ren perde o fôlego por um instante.",
            "resumo": "Ren perde 7 PV.",
            "deltas": [
                {
                    "alvo": "estado",
                    "op": "inc",
                    "caminho": "recursos.pontos_de_vida.atuais",
                    "valor": -7,
                }
            ],
        }
        record = transacoes.build_pending_record(tx, 3)
        self.assertEqual(record["resumo"], "Ren perde 7 PV.")
        self.assertEqual(record["deltas"][0]["valor"], -7)


class DiegeticGuardWriterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "runtime/contexto.yaml").write_text(
            "sessao:\n  numero: 3\n  status: em_sessao\n", encoding="utf-8"
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text(
            "# Sessão 003\n\n---\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def tx(self, narration: str) -> dict[str, object]:
        return {
            "jogador": "Ren observa o adversário.",
            "narracao": narration,
            "resumo": "Ren observa o adversário.",
            "modo": "interação",
            "deltas": [],
        }

    def test_falha_antes_de_transcricao_e_buffer(self):
        transcript = self.repo / "sessoes/003/transcricao.md"
        pending = self.repo / "runtime/eventos-pendentes.jsonl"
        before = (digest(transcript), digest(pending))
        with self.assertRaises(transacoes.TransactionError):
            turno.register_transaction(self.repo, self.tx("O homem está com 9 PV e tenta fugir."))
        self.assertEqual(before, (digest(transcript), digest(pending)))

    def test_linha_mecanica_pode_ser_registrada_na_mesma_transacao(self):
        result = turno.register_transaction(
            self.repo,
            self.tx(
                "O guarda aperta os olhos e espera a resposta.\n\n"
                "MECÂNICA — Teste de Enganação, CD 14."
            ),
        )
        self.assertTrue(result["transcricao_escrita"])
        text = (self.repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8")
        self.assertIn("MECÂNICA — Teste de Enganação, CD 14.", text)

    def test_transcricao_historica_nao_e_varrida_retroativamente(self):
        path = self.repo / "sessoes/003/transcricao.md"
        path.write_text(
            "# Sessão 003\n\n**Narrador**\n\nLegado antigo: PV 20/20, CA 15.\n\n---\n",
            encoding="utf-8",
        )
        result = turno.register_transaction(
            self.repo,
            self.tx("O adversário baixa a faca e recua para perto da porta."),
        )
        self.assertTrue(result["transcricao_escrita"])


class DiegeticBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_guardrail_sem_custo_operacional(self):
        import yaml

        data = yaml.safe_load(
            (ROOT / "baseline/diegetico-orcamento.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(data["schema_orcamento_diegetico"], 1)
        self.assertEqual(data["limites"]["max_categorias_regex"], 7)
        self.assertEqual(data["limites"]["leituras_extras_turno_comum"], 0)
        self.assertEqual(data["limites"]["escritas_extras_turno_comum"], 0)
        inv = data["invariantes"]
        self.assertTrue(inv["validacao_e_pura"])
        self.assertTrue(inv["falha_antes_de_transcricao_e_buffer"])
        self.assertTrue(inv["mecanica_explicita_exige_linha_marcada"])
        self.assertTrue(inv["transcricoes_historicas_nao_sao_varridas"])


if __name__ == "__main__":
    unittest.main()
