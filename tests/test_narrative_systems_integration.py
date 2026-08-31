from __future__ import annotations

import ast
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
import condicoes_mundo as conditions
import contexto
import ecologia_local
import eventos_canonicos
import incidentes_mundo as incidents
import iniciativa_social
import mundo
import oportunidades
import sidequests_canonicas as canonical

CONTRACT = ROOT / "baseline/narrative-systems-integration-budget-regression-orcamento.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class NarrativeSystemsBudgetMatrixTest(unittest.TestCase):
    def test_contrato_final_reutiliza_tetos_existentes_sem_aumenta_los(self):
        final = load_yaml(CONTRACT)
        layers = final["camadas"]

        cronica = load_yaml(ROOT / "baseline/unified-cronica-turn-cli-orcamento.yaml")
        self.assertEqual(
            layers["turno_neutro"]["chamadas_orquestracao"],
            cronica["fluxo_preferencial"]["chamadas_operacionais_por_turno"],
        )
        self.assertEqual(layers["turno_neutro"]["chamadas_orquestracao"], 2)

        social = load_yaml(ROOT / "baseline/npc-social-initiative-orcamento.yaml")["limites"]
        self.assertEqual(layers["npc_relacao_iniciativa"]["fontes_extras_iniciativa"], social["fontes_extras_por_consulta_npc"])
        self.assertEqual(layers["npc_relacao_iniciativa"]["leituras_iniciativa_status_cena"], social["leituras_extras_status_cena"])

        incidental = load_yaml(ROOT / "baseline/incidental-presence-orcamento.yaml")["limites"]
        self.assertEqual(layers["presenca_social_local"]["candidatos_incidentais_por_cena_max"], incidental["max_candidatos_por_cena"])

        quests = load_yaml(ROOT / "baseline/canonical-secret-quest-engine-orcamento.yaml")["limites"]
        self.assertEqual(layers["sidequests_canonicas"]["detalhes_lidos_quando_gate_bloqueia"], quests["detalhes_lidos_quando_nenhum_gate_passa"])
        self.assertEqual(layers["sidequests_canonicas"]["detalhes_por_cena_max"], quests["detalhes_secretos_por_cena"])
        self.assertEqual(layers["sidequests_canonicas"]["scans_globais"], quests["scans_globais"])

        weather = load_yaml(ROOT / "baseline/persistent-world-conditions-orcamento.yaml")["limites"]
        self.assertEqual(layers["condicoes_persistentes"]["leituras_cena_espacial"], weather["leituras_estado_cena_espacial"])
        self.assertEqual(layers["condicoes_persistentes"]["estado_bytes_max"], weather["estado_bytes_max"])

        incident = load_yaml(ROOT / "baseline/world-local-incidents-v2-orcamento.yaml")["limites"]
        self.assertEqual(layers["incidentes"]["leituras_cena_espacial"], incident["leituras_task35_cena_espacial"])
        self.assertEqual(layers["incidentes"]["incidentes_por_cena_max"], incident["max_incidentes_por_cena"])
        self.assertEqual(layers["incidentes"]["scans_globais"], incident["scans_globais"])

        canon = load_yaml(ROOT / "baseline/secret-canon-v2-orcamento.yaml")["limites"]
        self.assertEqual(layers["canon_principal"]["fragmentos_turno_sem_evento_devido"], canon["leituras_fragmentos_turno_sem_evento"])
        self.assertEqual(layers["canon_principal"]["fragmentos_por_evento_devido_max"], canon["leituras_fragmento_evento_devido_max"])

        boundary = load_yaml(ROOT / "baseline/batch-world-boundary-resolution-orcamento.yaml")["limites"]
        self.assertEqual(layers["fronteira_mundo"]["pendencias_por_lote_max"], boundary["max_pendencias_por_lote"])
        self.assertEqual(layers["fronteira_mundo"]["chamadas_preparar"], boundary["max_orquestracoes_preparar"])
        self.assertEqual(layers["fronteira_mundo"]["chamadas_aplicar"], boundary["max_orquestracoes_aplicar"])

        tournament = load_yaml(ROOT / "baseline/underground-tournament-mini-arc-orcamento.yaml")["limites"]
        self.assertEqual(layers["torneio_clandestino"]["fragmentos_rodada_por_consulta_max"], tournament["fragmentos_rodada_abertos_por_consulta"])
        self.assertEqual(layers["torneio_clandestino"]["pendencias_mundo_novas"], tournament["pendencias_mundo_novas"])

        self.assertTrue(all(final["invariantes"].values()))
        self.assertTrue(all(value == 0 for key, value in final["limites"].items() if key.startswith(("schedulers_", "estados_persistentes_", "endpoints_", "scans_repo_", "chamadas_telemetria_"))))


class NarrativeSystemsHotPathTest(unittest.TestCase):
    def test_consulta_npc_projeta_relacao_e_iniciativa_sem_abrir_outras_fichas(self):
        data = contexto.command_npc(ROOT, "Nera")
        sources = list(data["fontes"])
        npc_fragments = [source for source in sources if source.startswith("estado/npcs/") and source != "estado/npcs/index.yaml"]
        relation_fragments = [source for source in sources if source.startswith("estado/relacoes/") and source != "estado/relacoes/index.yaml"]
        self.assertLessEqual(len(npc_fragments), 1)
        self.assertLessEqual(len(relation_fragments), 1)
        self.assertFalse(any(source.startswith("personagens/") for source in sources))
        self.assertNotIn("ferramentas/iniciativa_social.py", sources)
        social = data["resultado"]["dialogo_relacional"]["iniciativa_social"]
        iniciativa_social.validate_projection(social)

    def test_cena_local_nao_acorda_iniciativa_social_nem_fichas_de_npc(self):
        now = mundo.parse_instant("17 Eleasis, 1372 DR", "18:00")
        with mock.patch.object(
            iniciativa_social,
            "project",
            side_effect=AssertionError("cena local não deve projetar iniciativa de NPC"),
        ):
            preview = cena_mundo.prepare_scene(
                ROOT,
                scene_id="task38-local-sem-wake-all",
                place="Galeria dos Escribas",
                action="entrar",
                tier=1,
                danger="baixa",
                now=now,
            )
        incidentals = list(preview.get("presencas_incidentais") or [])
        self.assertLessEqual(len(incidentals), 1)
        self.assertNotIn("iniciativa_social", yaml.safe_dump(preview, allow_unicode=True))
        self.assertFalse(any(source.startswith("estado/npcs/") and source != "estado/npcs/index.yaml" for source in preview["fontes_lidas"]))
        self.assertFalse(any(source.startswith("estado/relacoes/") and source != "estado/relacoes/index.yaml" for source in preview["fontes_lidas"]))
        for candidate in incidentals:
            self.assertNotIn("dialogo", candidate)
            self.assertNotIn("acao", candidate)

    def test_sidequest_bloqueada_mantem_detalhe_secreto_fora_do_contexto(self):
        index = oportunidades.load_index(ROOT)
        npc_id = sorted(canonical.quest_giver_ids(index, ROOT))[0]
        refs, _ = canonical.route_for_npc_with_sources(ROOT, index, npc_id)
        self.assertTrue(refs)
        with (
            mock.patch.object(canonical._core, "_lifecycle_allows", return_value=(False, "historico_bloqueado")),
            mock.patch.object(canonical._core, "_load_detail", side_effect=AssertionError("detalhe frio não deve abrir")),
        ):
            result = canonical.select_from_refs(
                ROOT,
                refs,
                now=mundo.parse_instant("17 Eleasis, 1372 DR", "18:00"),
                diagnostics=True,
            )
        self.assertEqual(result["detalhes_lidos"], 0)
        self.assertFalse(any("sidequests-canonicas/segredos/" in source for source in result["fontes_lidas"]))

    def test_incidente_planejado_nao_varre_repositorio(self):
        profile = ecologia_local.load_index(ROOT)["perfis"]["galeria_dos_escribas"]
        with (
            mock.patch.object(Path, "glob", side_effect=AssertionError("glob proibido no hot path")),
            mock.patch.object(Path, "rglob", side_effect=AssertionError("rglob proibido no hot path")),
        ):
            result = incidents.plan(
                ROOT,
                scene_id="integracao-incidente-sem-scan",
                local_id="galeria_dos_escribas",
                profile=profile,
                conditions=[],
            )
        self.assertIn(result["publico"]["resultado"], {"rotina", "avaliar_incidente"})

    def test_condicao_persistente_projeta_item_compacto_sem_proveniencia(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / conditions.STATE.parent).mkdir(parents=True, exist_ok=True)
            (repo / conditions.STATE).write_text(
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
            source = repo / "sessoes/001/resumo.md"
            source.parent.mkdir(parents=True, exist_ok=True)
            evidence = "Chuva forte se instalou sobre Ravens Bluff por dois dias."
            source.write_text(evidence + "\n", encoding="utf-8")
            now = mundo.parse_instant("17 Eleasis, 1372 DR", "18:00")
            conditions.register(
                repo,
                kind="clima",
                subject="tempestade costeira",
                intensity="forte",
                description="Chuva forte e vento persistem sobre a cidade.",
                signals=["ruas molhadas", "visibilidade reduzida"],
                markers=["chuva_forte"],
                locals_=[],
                duration_hours=48,
                source="sessoes/001/resumo.md",
                evidence=evidence,
                now=now,
            )
            item = conditions.project(repo, local_id="galeria_dos_escribas", now=now)["ativas"][0]
        limit = load_yaml(CONTRACT)["camadas"]["condicoes_persistentes"]["projecao_publica_item_bytes_max"]
        self.assertLessEqual(len(yaml.safe_dump(item, allow_unicode=True).encode("utf-8")), limit)
        self.assertNotIn("fonte", item)
        self.assertNotIn("evidencia", item)

    def test_canon_principal_sem_pendencia_nao_abre_indice_ou_fragmento(self):
        with mock.patch.object(
            eventos_canonicos,
            "load_catalog",
            side_effect=AssertionError("sem evento devido não deve abrir catálogo"),
        ):
            result = eventos_canonicos.pending_projection(ROOT, [])
        self.assertEqual(result, {"eventos": [], "fontes_lidas": []})

    def test_camadas_integradas_nao_importam_scheduler_ou_rng(self):
        forbidden = {"random", "sched", "schedule", "apscheduler", "threading", "asyncio"}
        modules = (
            "iniciativa_social.py",
            "sidequests_canonicas.py",
            "_sidequests_canonicas_task32.py",
            "condicoes_mundo.py",
            "incidentes_mundo.py",
            "eventos_canonicos.py",
            "resolver_fronteira.py",
            "torneio_clandestino.py",
        )
        for name in modules:
            tree = ast.parse((TOOLS / name).read_text(encoding="utf-8"), filename=name)
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=name):
                self.assertFalse(imported & forbidden, imported & forbidden)


if __name__ == "__main__":
    unittest.main()
