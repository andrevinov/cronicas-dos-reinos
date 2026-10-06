"""CLI integrada e replay explícito da revisão humana de 2026-10-06.

Não há juiz literário automático: expectativas confrontam publicação de
pareceres registrados após leitura nova. Todo estado é temporário.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from episodio_integrado import Episode, ROOT, revisao_sessao as workflow
from revisao_episodio import publish_recorded, request_for
import cronica
import permanencia_espacial_idempotencia as stay

class IntegratedEpisodeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(prefix='cronicas-episodio-integrado-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.episodes = {}
        for variant in ('correta', 'memoria_omitida', 'espera_passiva', 'fronteira_ignorada'):
            episode = Episode(Path(cls.temp.name) / variant, variant)
            try:
                episode.run()
                publish_recorded(episode.root, variant)
                cls.episodes[variant] = episode
            finally:
                episode.close()

    def positive(self):
        episode = self.episodes['correta']
        return episode, {s['id']: s for s in episode.steps}

    def test_intention_presence_promise_and_cold_recovery_survive_composition(self):
        episode, steps = self.positive()
        absent = steps['prospecto']['prepare']['iniciativa_elenco']['itens'][0]
        self.assertEqual(absent['presenca'], 'ausente')
        self.assertIsNone(steps['prospecto']['prepare']['iniciativa_elenco']['selecionada'])
        self.assertTrue(steps['conversa']['prepare']['iniciativa_elenco']['selecionada'])
        self.assertEqual(steps['promessa']['conclude']['memoria_contexto']['fatos_persistidos_novos'], 1)
        before = steps['nova_interacao']['prepare']['memoria_cena']['itens']['@compromissos']
        after = steps['retomada_fria']['prepare']['memoria_cena']['itens']['@compromissos']
        identifiers = [key for key in before if key != 'memoria_relevante']
        self.assertEqual(len(identifiers), 1)
        self.assertEqual(after[identifiers[0]]['janela']['fim']['hora'], '11:50')
        self.assertEqual(after[identifiers[0]]['situacao_temporal'], 'janela_encerrada')
        state = episode.read('estado/estado-atual.yaml')
        self.assertEqual(state['localizacao']['area'], 'abrigo_fixture')
        self.assertEqual(state['estado_narrativo']['elenco_cena']['participantes'], ['silva_fixture'])
        self.assertEqual(state['tempo']['hora_aproximada'], '12:14')

    def test_wait_limits_and_completed_pressure_release_the_actor_without_reroll(self):
        episode, steps = self.positive()
        wait = steps['espera_limite']; resumed = steps['continuacao']
        self.assertEqual(wait['transaction']['deltas'][0]['valor']['hora'], '11:50')
        self.assertEqual(resumed['transaction']['deltas'][0]['valor']['hora'], '12:14')
        first = wait['prepare']['permanencia_espacial']; later = resumed['prepare']['permanencia_espacial']
        self.assertEqual(first['avaliacao_id'], later['avaliacao_id'])
        self.assertTrue(first['exige_decisao_conclusao'])
        self.assertFalse(later['exige_decisao_conclusao'])
        self.assertNotIn('permanencia_espacial', resumed['transaction'])
        self.assertEqual(wait['prepare']['iniciativa_elenco']['itens'][0]['resultado_automatico'], 'adiada_por_pressao_superior')
        initiative = resumed['prepare']['iniciativa_elenco']
        self.assertTrue(initiative['selecionada'])
        self.assertIsNone(initiative['itens'][0]['pressao_superior'])
        self.assertEqual(resumed['transaction']['iniciativa_elenco']['resultado'], 'apresentada')
        self.assertEqual(episode.read('narrador/mundo/estado.yaml')['pendencias'], [])

    def test_original_retry_and_new_ticket_have_distinct_literal_obligations(self):
        episode, steps = self.positive()
        old = cronica.decode_ticket(steps['espera_limite']['prepare']['ticket'])['permanencia_espacial']
        new = cronica.decode_ticket(steps['continuacao']['prepare']['ticket'])['permanencia_espacial']
        self.assertNotIn('pressao_ja_concluida', old)
        self.assertTrue(new['pressao_ja_concluida'])
        block = steps['espera_limite']['transaction']['permanencia_espacial']
        with self.assertRaises(stay.SpatialPermanenceError):
            stay.prepare_conclusion(episode.repo, old, {})
        self.assertEqual(stay.prepare_conclusion(episode.repo, old, {'permanencia_espacial': block}), block)
        self.assertIsNone(stay.prepare_conclusion(episode.repo, new, {}))
        with self.assertRaises(stay.SpatialPermanenceError):
            stay.prepare_conclusion(episode.repo, new, {'permanencia_espacial': block})
        invalid = deepcopy(new); invalid['pressao_ja_concluida'] = False
        with self.assertRaises(stay.SpatialPermanenceError):
            stay.validate_ticket(invalid)

    def test_actual_cli_budget_cut_closed_capture_and_public_secrecy(self):
        for variant, episode in self.episodes.items():
            with self.subTest(variant=variant):
                for outputs in episode.outputs.values():
                    for output in outputs:
                        self.assertEqual(output['exit_code'], 0)
                        if output['tool'] == 'cronica.py' and output['args'][0] == 'preparar':
                            self.assertLessEqual(output['stdout_bytes'], 8192)
                bundle = workflow.load(episode.root / 'entrada.json')
                self.assertTrue(bundle['evidencias_sessao']['conteudo']['encerrada'])
                request = request_for(episode.root, variant)
                # Recorte integral contém encerramento; revisão exata escolhe os ON.
                full = workflow.prepare(episode.root / 'rollout.jsonl', bundle,
                                        criterion_ids=['context_and_memory.scene_and_durable_memory'])
                self.assertEqual(len(full['frames']), 12)
                self.assertEqual(full['frames'][-1]['turn_id'], 'encerramento')
                self.assertTrue(all(f['complete'] for f in full['frames']))
                for path in (episode.root / 'publicado').rglob('*'):
                    if path.is_file():
                        self.assertNotIn(b'SEGREDO_RESERVADO_DO_EPISODIO', path.read_bytes())
                self.assertTrue(request['required_units'])

    def test_recorded_review_publication_distinguishes_defects_absence_and_abstention(self):
        expectations = workflow.load(ROOT / 'tests/fixtures/expectativas-episodio-integrado.json')['cases']
        for variant, episode in self.episodes.items():
            with self.subTest(variant=variant):
                result = workflow.load(episode.root / 'publicado/adjudicacoes-modulares.json')
                request = request_for(episode.root, variant)
                names = {f['evaluation_ref']: f['turn_id'] for f in request['frames']}
                failures = sorted(names[a['interaction_ref']] + ':' + a['criterion_id']
                                  for a in result['quality_assessments']
                                  if a['quality'] == 'inadequada' or 'violado' in a['review']['guardrails'].values())
                self.assertEqual(failures, sorted(expectations[variant]['failures']))
                summary = result['review_workflow']
                self.assertEqual(summary['units_reviewed'], 18)
                self.assertEqual(summary['blocked_reviews'], 0)
                self.assertEqual(summary['not_applicable'], expectations[variant]['not_applicable'])
                self.assertEqual(summary['insufficient_sources'], expectations[variant]['insufficient_sources'])
                self.assertEqual(summary['reviewer']['configuration']['execucao'], 'replay_regressao')
                for assessment in result['quality_assessments']:
                    self.assertEqual(assessment['review']['verification'], 'verificada')

if __name__ == '__main__':
    unittest.main()
