from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cena_mundo
import cena_mundo_v4
import condicoes_mundo as conditions
import condicoes_mundo_cena
import incidentes_mundo_cena
import mundo


class ConditionFixture:
    def __init__(self, root: Path):
        self.root = root
        (root / conditions.STATE.parent).mkdir(parents=True, exist_ok=True)
        (root / conditions.STATE).write_text(
            yaml.safe_dump(
                {
                    "schema_condicoes_mundo": 1,
                    "natureza": "controle_reservado",
                    "cidade": "ravens_bluff",
                    "condicoes": {},
                    "historico_recente": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        source = root / "sessoes/001/resumo.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "A chuva pesada se instalou sobre a cidade por dois dias.\n"
            "Os estivadores declararam greve aberta no porto.\n"
            "A chuva cessou e o céu abriu sobre Ravens Bluff.\n"
            "Uma feira pública começou nas ruas centrais.\n",
            encoding="utf-8",
        )

    def add(
        self,
        *,
        kind="clima",
        subject="tempestade costeira",
        intensity="forte",
        description="Chuva pesada e rajadas persistem sobre a cidade.",
        signals=None,
        markers=None,
        locals_=None,
        duration=48,
        evidence="A chuva pesada se instalou sobre a cidade por dois dias.",
        now=None,
    ):
        return conditions.register(
            self.root,
            kind=kind,
            subject=subject,
            intensity=intensity,
            description=description,
            signals=signals or ["ruas molhadas"],
            markers=markers or ["chuva_forte"],
            locals_=locals_ or [],
            duration_hours=duration,
            source="sessoes/001/resumo.md",
            evidence=evidence,
            now=now or mundo.parse_instant("17 Eleasis, 1372 DR", "18:00"),
        )


class PersistentConditionStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fx = ConditionFixture(self.root)
        self.start = mundo.parse_instant("17 Eleasis, 1372 DR", "18:00")

    def tearDown(self):
        self.tmp.cleanup()

    def test_estado_vazio_nao_inventa_condicao_retroativa(self):
        before = (self.root / conditions.STATE).read_bytes()
        result = conditions.project(self.root, local_id="casa_teste", now=self.start)
        self.assertEqual(result["ativas"], [])
        self.assertEqual(result["fontes_lidas"], [conditions.STATE.as_posix()])
        self.assertEqual((self.root / conditions.STATE).read_bytes(), before)

    def test_condicao_persiste_varias_cenas_e_expira_sem_escrever(self):
        created = self.fx.add(now=self.start)
        cid = created["condicao"]["id"]
        next_day = mundo.WorldInstant(self.start.minute + 24 * 60)
        active = conditions.project(self.root, local_id="qualquer_local", now=next_day)
        self.assertEqual([item["id"] for item in active["ativas"]], [cid])

        before_expiry_read = (self.root / conditions.STATE).read_bytes()
        later = mundo.WorldInstant(self.start.minute + 60 * 60)
        expired = conditions.project(self.root, local_id="qualquer_local", now=later)
        self.assertEqual(expired["ativas"], [])
        self.assertEqual((self.root / conditions.STATE).read_bytes(), before_expiry_read)

    def test_escrita_futura_compacta_expirada_para_historico(self):
        first = self.fx.add(now=self.start, duration=24)
        later = mundo.WorldInstant(self.start.minute + 48 * 60)
        second = self.fx.add(
            kind="greve",
            subject="estivadores",
            intensity="moderada",
            description="Parte do trabalho portuário está paralisada.",
            signals=["cais com equipes reduzidas"],
            markers=["porto_lento", "servico_reduzido"],
            duration=72,
            evidence="Os estivadores declararam greve aberta no porto.",
            now=later,
        )
        self.assertEqual(second["compactadas"], 1)
        state = conditions.load_state(self.root)
        self.assertNotIn(first["condicao"]["id"], state["condicoes"])
        self.assertEqual(state["historico_recente"][-1]["motivo"], "fim_previsto_alcancado")

    def test_encerramento_explicito_move_para_historico_e_retry_e_idempotente(self):
        created = self.fx.add(now=self.start, duration=None)
        cid = created["condicao"]["id"]
        ended_at = mundo.WorldInstant(self.start.minute + 5 * 60)
        ended = conditions.close(
            self.root,
            cid,
            source="sessoes/001/resumo.md",
            evidence="A chuva cessou e o céu abriu sobre Ravens Bluff.",
            reason="a frente de chuva se dissipou",
            now=ended_at,
        )
        self.assertEqual(ended["resultado"], "encerrada")
        retry = conditions.close(
            self.root,
            cid,
            source="sessoes/001/resumo.md",
            evidence="A chuva cessou e o céu abriu sobre Ravens Bluff.",
            reason="a frente de chuva se dissipou",
            now=ended_at,
        )
        self.assertEqual(retry["resultado"], "ja_encerrada")
        self.assertEqual(conditions.project(self.root, now=ended_at)["ativas"], [])

    def test_escopo_local_e_cidade_sao_deterministicos(self):
        city = self.fx.add(now=self.start, subject="chuva municipal")
        local = self.fx.add(
            kind="festival",
            subject="feira de bairro",
            intensity="leve",
            description="Barracas e público ocupam o entorno imediato.",
            signals=["barracas abertas"],
            markers=["multidao"],
            locals_=["casa_teste"],
            duration=12,
            evidence="Uma feira pública começou nas ruas centrais.",
            now=self.start,
        )
        here = conditions.project(self.root, local_id="casa_teste", now=self.start)
        elsewhere = conditions.project(self.root, local_id="outro_local", now=self.start)
        self.assertEqual({item["id"] for item in here["ativas"]}, {city["condicao"]["id"], local["condicao"]["id"]})
        self.assertEqual([item["id"] for item in elsewhere["ativas"]], [city["condicao"]["id"]])

    def test_todos_os_seis_tipos_sao_aceitos(self):
        evidence = "Uma feira pública começou nas ruas centrais."
        for index, kind in enumerate(sorted(conditions.VALID_TYPES)):
            with self.subTest(kind=kind):
                root = self.root / f"case-{index}"
                fx = ConditionFixture(root)
                created = fx.add(
                    kind=kind,
                    subject=f"assunto {kind}",
                    intensity="leve",
                    description=f"Condição persistente do tipo {kind}.",
                    signals=[],
                    markers=[f"marca_{index}"],
                    duration=24,
                    evidence=evidence,
                    now=self.start,
                )
                self.assertEqual(created["condicao"]["tipo"], kind)

    def test_fonte_reservada_nao_pode_canonizar_condicao(self):
        secret = self.root / "narrador/fato.yaml"
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_text("A tempestade começou de verdade agora.\n", encoding="utf-8")
        with self.assertRaises(conditions.WorldConditionError):
            conditions.register(
                self.root,
                kind="clima",
                subject="tempestade",
                intensity="forte",
                description="Chove.",
                signals=[],
                markers=[],
                locals_=[],
                duration_hours=24,
                source="narrador/fato.yaml",
                evidence="A tempestade começou de verdade agora.",
                now=self.start,
            )

    def test_projecao_publica_nao_expoe_fonte_ou_evidencia(self):
        self.fx.add(now=self.start)
        item = conditions.project(self.root, now=self.start)["ativas"][0]
        self.assertNotIn("fonte", item)
        self.assertNotIn("evidencia", item)


class PersistentConditionSceneTest(unittest.TestCase):
    def test_cena_sem_contexto_espacial_nao_consulta_task34(self):
        base = {
            "local": None,
            "contexto_tags": [],
            "resumo": {},
            "fontes_lidas": ["fonte-base.yaml"],
            "regra": "base",
        }
        with mock.patch.object(condicoes_mundo_cena, "_BASE_OPEN_SCENE", return_value=base), mock.patch.object(
            condicoes_mundo_cena.condicoes_mundo,
            "for_scene",
            side_effect=AssertionError("não deve ler condição em cena sem local"),
        ):
            result = condicoes_mundo_cena.open_scene(ROOT, scene_id="sem-local")
        self.assertEqual(result["fontes_lidas"], ["fonte-base.yaml"])

    def test_cena_espacial_anexa_condicoes_e_fonte_ao_fingerprint(self):
        base = {
            "local": {"local_id": "casa_de_tyr"},
            "contexto_tags": [],
            "resumo": {},
            "fontes_lidas": ["fonte-base.yaml"],
            "regra": "base",
        }
        projection = {
            "ativas": [
                {
                    "id": "cnd-0123456789abcdef",
                    "tipo": "toque_de_recolher",
                    "assunto": "ordem noturna",
                    "intensidade": "forte",
                    "descricao": "Circulação civil está restrita.",
                    "sinais": ["patrulhas reforçadas"],
                    "marcadores": ["patrulha_reforcada"],
                    "fim_previsto": None,
                }
            ],
            "fontes_lidas": [conditions.STATE.as_posix()],
        }
        with mock.patch.object(condicoes_mundo_cena, "_BASE_OPEN_SCENE", return_value=base), mock.patch.object(
            condicoes_mundo_cena.condicoes_mundo, "for_scene", return_value=projection
        ) as call:
            result = condicoes_mundo_cena.open_scene(ROOT, scene_id="com-local")
        call.assert_called_once_with(ROOT, "casa_de_tyr", now=None)
        self.assertEqual(len(result["condicoes_mundo"]), 1)
        self.assertIn(conditions.STATE.as_posix(), result["fontes_lidas"])
        self.assertEqual(result["resumo"]["condicoes_persistentes_ativas"], 1)
        self.assertIn("não impõem teste", result["regra"])

    def test_porta_publica_instala_task35_depois_da_task34(self):
        self.assertIs(cena_mundo_v4._core.open_scene, incidentes_mundo_cena.open_scene)
        self.assertIs(cena_mundo.open_scene, incidentes_mundo_cena.open_scene)
        self.assertIs(incidentes_mundo_cena._BASE_OPEN_SCENE, condicoes_mundo_cena.open_scene)


class PersistentConditionRepositoryAndBudgetTest(unittest.TestCase):
    def test_repo_real_comeca_vazio_e_valido_sem_retroatividade(self):
        state = conditions.load_state(ROOT)
        self.assertEqual(state["condicoes"], {})
        result = conditions.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["condicoes_abertas"], 0)
        self.assertEqual(result["ativas_agora"], 0)

    def test_contrato_congela_custo_e_sem_scheduler(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/persistent-world-conditions-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = budget["limites"]
        self.assertEqual(limits["condicoes_abertas_max"], conditions.MAX_CONDITIONS)
        self.assertEqual(limits["historico_recente_max"], conditions.MAX_HISTORY)
        self.assertEqual(limits["estado_bytes_max"], conditions.MAX_STATE_BYTES)
        self.assertEqual(limits["leituras_extras_cena_sem_local"], 0)
        self.assertEqual(limits["leituras_estado_cena_espacial"], 1)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["scans_globais"], 0)
        self.assertTrue(all(budget["invariantes"].values()))
        self.assertLessEqual((ROOT / conditions.STATE).stat().st_size, conditions.MAX_STATE_BYTES)


if __name__ == "__main__":
    unittest.main()