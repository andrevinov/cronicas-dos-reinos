from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import mundo
import sidequests_integracao_runtime as integration
import test_emergent_sidequest_authoring_registry_v2 as task41
import transacoes


class Task48SemanticSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41.task40_package()

    def meta(self, package: dict, *, source: str | None = integration.CLOCK_SOURCE_EXPLICIT):
        origin = package["origem"]
        reward = package["envelope_recompensa"]
        signal = {
            "origem_tipo": origin["tipo"],
            "origem_id": origin["id"],
            "ancora_tipo": origin["ancora_tipo"],
            "ancora": origin["ancora"],
            "npc_id": origin.get("npc_id"),
            "local_id": package["prazo_mundo"].get("local_id"),
            "periculosidade": reward["periculosidade"],
            "tier": reward["tier"],
            "agora": copy.deepcopy(package["prazo_mundo"]["agora"]),
        }
        if source is not None:
            signal["agora_fonte"] = source
        digest = (
            integration._base._digest(package)
            if source is None
            else integration._semantic_digest(package)
        )
        return {"schema": integration.SCHEMA, "sinal": signal, "pacote_digest": digest}

    def test_telemetria_fontes_e_orcamento_nao_mudam_digest_semantico(self):
        original = integration._semantic_digest(self.package)
        changed = copy.deepcopy(self.package)
        changed.setdefault("fontes_lidas", []).append("runtime/fonte-observacional-task48.yaml")
        changed.setdefault("metricas", {})["leituras_observacionais_task48"] = 999
        changed.setdefault("orcamento_pacote", {})["bytes"] = 1
        changed["horizonte_intencoes_canonicas"]["avaliadas"] = 999
        changed["horizonte_intencoes_canonicas"]["regra"] = "telemetria textual diferente"
        self.assertEqual(original, integration._semantic_digest(changed))

    def test_cada_dimensao_causal_relevante_invalida_digest(self):
        original = integration._semantic_digest(self.package)

        mutations = {
            "relacao": lambda p: p.__setitem__(
                "relacao_efetiva", {"npc_id": "silva_elkwood", "afinidade": 99}
            ),
            "quests": lambda p: p["quests"].__setitem__(
                "ativas", int(p["quests"].get("ativas", 0)) + 1
            ),
            "condicao_mundo": lambda p: p["prazo_mundo"].setdefault(
                "condicoes_persistentes", []
            ).append({"id": "task48-condicao", "tipo": "ameaca"}),
            "intencao_canonica": lambda p: p["horizonte_intencoes_canonicas"].setdefault(
                "compativeis", []
            ).append({"evento_id": "task48-intencao"}),
            "ator": lambda p: p.setdefault("atores_causalmente_disponiveis", []).append(
                {"id": "task48-ator", "papel": "ator_estrategico", "causal_agora": True}
            ),
            "juppongatana": lambda p: p.setdefault("juppongatana_possiveis", []).append(
                {"id": "task48-membro", "causal_agora": True}
            ),
            "recompensa": lambda p: p["envelope_recompensa"].__setitem__(
                "pontos", int(p["envelope_recompensa"].get("pontos", 0)) + 1
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(self.package)
                mutate(changed)
                self.assertNotEqual(original, integration._semantic_digest(changed))

    def test_revalidacao_aceita_mesmo_mundo_com_telemetria_diferente(self):
        meta = self.meta(self.package)
        changed = copy.deepcopy(self.package)
        changed.setdefault("fontes_lidas", []).append("estado/tempo.yaml")
        changed["metricas"] = {**changed.get("metricas", {}), "task48": 1}
        changed["orcamento_pacote"] = {**changed.get("orcamento_pacote", {}), "bytes": 7}
        with patch.object(integration._base.opportunity, "plan", return_value=changed):
            result = integration._plan_from_ticket(ROOT, meta)
        self.assertEqual(result, changed)

    def test_revalidacao_falha_quando_fato_causal_muda(self):
        meta = self.meta(self.package)
        changed = copy.deepcopy(self.package)
        changed["quests"]["ativas"] = int(changed["quests"].get("ativas", 0)) + 1
        with patch.object(integration._base.opportunity, "plan", return_value=changed):
            with self.assertRaisesRegex(
                integration.EmergentSidequestIntegrationError,
                "snapshot semântico Task40 mudou",
            ):
                integration._plan_from_ticket(ROOT, meta)

    def test_ticket_task46_legado_conserva_digest_bruto(self):
        meta = self.meta(self.package, source=None)
        with patch.object(integration._base.opportunity, "plan", return_value=self.package):
            result = integration._plan_from_ticket(ROOT, meta)
        self.assertEqual(result, self.package)

    def test_integrate_prepare_regrava_ticket_com_digest_semantico(self):
        package = copy.deepcopy(self.package)
        raw_meta = self.meta(package, source=None)
        payload = {
            "schema_cronica_ticket": cronica._core.SCHEMA,
            "preparacao_id": "turn-neutral-task48",
            "cena": cronica._core._request(
                scene_id="task48:semantic-ticket",
                npcs=[],
                place=None,
                action=None,
                tier=None,
                danger=None,
                context_tags=[],
                now=None,
                approach_preparacao=None,
                approach_informacao=None,
                approach_adequacao=None,
            ),
            integration.TICKET_KEY: raw_meta,
        }
        token, tid = cronica._core.encode_ticket(payload)
        fake = {
            "ticket": token,
            "ticket_id": tid,
            "sidequest_emergente": package,
            "sidequest_emergente_task46": {"integrada_ao_ticket": True},
            "sistemas_narrativos": ["emergent_sidequest_opportunity"],
        }
        explicit = mundo.parse_instant(
            package["prazo_mundo"]["agora"]["data"],
            package["prazo_mundo"]["agora"]["hora"],
        )
        with patch.object(integration._base, "integrate_prepare", return_value=fake):
            result = integration.integrate_prepare(
                ROOT,
                {},
                signal_raw={},
                decode_ticket=cronica.decode_ticket,
                encode_ticket=cronica._core.encode_ticket,
                now=explicit,
            )
        decoded = cronica.decode_ticket(result["ticket"])
        meta = decoded[integration.TICKET_KEY]
        self.assertEqual(meta["sinal"]["agora_fonte"], integration.CLOCK_SOURCE_EXPLICIT)
        self.assertEqual(meta["pacote_digest"], integration._semantic_digest(package))
        self.assertEqual(
            result["sidequest_emergente_task46"]["digest_pacote"],
            "semantico_task48_v1",
        )


class Task48EffectiveClockTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "runtime").mkdir(parents=True)
        self.canonical = mundo.parse_instant("10 Eleasis, 1372 DR", "19:38")
        (self.repo / mundo.TIME_PATH).write_text(
            yaml.safe_dump(
                {
                    "schema_tempo": 1,
                    "natureza": "tempo_atual",
                    "data_atual": "10 Eleasis, 1372 DR",
                    "hora_aproximada": "19:38",
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.repo / transacoes.PENDING_PATH).write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write_pending_instant(self, instant: mundo.WorldInstant) -> None:
        record = {
            "versao": transacoes.SCHEMA_VERSION,
            "id": "task48-clock",
            "sessao": 15,
            "resumo": "O turno anterior avançou o relógio efetivo sem checkpoint.",
            "deltas": [
                {
                    "alvo": "tempo",
                    "op": "instante",
                    "valor": mundo.instant_parts(instant),
                }
            ],
        }
        (self.repo / transacoes.PENDING_PATH).write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def test_sem_tempo_pendente_preserva_leitura_canonica_lazy_da_task40(self):
        with patch.object(integration._base.opportunity.mundo, "load_canonical_time") as canonical:
            now, source = integration._prepare_clock(self.repo, None)
        canonical.assert_not_called()
        self.assertIsNone(now)
        self.assertEqual(source, integration.CLOCK_SOURCE_CANONICAL)

    def test_overlay_temporal_pendente_vira_relogio_da_task40(self):
        effective = mundo.parse_instant("10 Eleasis, 1372 DR", "20:00")
        self.write_pending_instant(effective)
        now, source = integration._prepare_clock(self.repo, None)
        self.assertEqual(now, effective)
        self.assertEqual(source, integration.CLOCK_SOURCE_PENDING)
        self.assertEqual(integration._current_effective_now(self.repo), effective)

    def test_instante_explicito_tem_precedencia_sobre_overlay(self):
        pending = mundo.parse_instant("10 Eleasis, 1372 DR", "20:00")
        explicit = mundo.parse_instant("10 Eleasis, 1372 DR", "20:15")
        self.write_pending_instant(pending)
        now, source = integration._prepare_clock(self.repo, explicit)
        self.assertEqual(now, explicit)
        self.assertEqual(source, integration.CLOCK_SOURCE_EXPLICIT)

    def test_integracao_recebe_20h_sem_checkpoint_intermediario(self):
        effective = mundo.parse_instant("10 Eleasis, 1372 DR", "20:00")
        self.write_pending_instant(effective)
        fake = {
            "sidequest_emergente": {"resultado": "limite_ativas", "fontes_lidas": []},
            "sidequest_emergente_task46": {"integrada_ao_ticket": False},
        }
        with patch.object(integration._base, "integrate_prepare", return_value=fake) as base:
            integration.integrate_prepare(
                self.repo,
                {},
                signal_raw={},
                decode_ticket=lambda value: {},
                encode_ticket=lambda value: ("ticket", "id"),
                now=None,
            )
        self.assertEqual(base.call_args.kwargs["now"], effective)

    def test_revalidacao_de_relogio_derivado_enxerga_mudanca_real(self):
        effective = mundo.parse_instant("10 Eleasis, 1372 DR", "20:00")
        later = mundo.parse_instant("10 Eleasis, 1372 DR", "20:05")
        self.write_pending_instant(effective)
        package = copy.deepcopy(Task48SemanticSnapshotTest.package)
        package["prazo_mundo"]["agora"] = mundo.instant_parts(effective)
        meta = Task48SemanticSnapshotTest().meta(
            package, source=integration.CLOCK_SOURCE_PENDING
        )
        self.write_pending_instant(later)
        changed = copy.deepcopy(package)
        changed["prazo_mundo"]["agora"] = mundo.instant_parts(later)
        with patch.object(integration._base.opportunity, "plan", return_value=changed) as plan:
            with self.assertRaisesRegex(
                integration.EmergentSidequestIntegrationError,
                "snapshot semântico Task40 mudou",
            ):
                integration._plan_from_ticket(self.repo, meta)
        self.assertEqual(plan.call_args.kwargs["now"], later)


if __name__ == "__main__":
    unittest.main()
