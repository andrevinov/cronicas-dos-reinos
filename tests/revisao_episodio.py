"""Monta fontes para decisões humanas já registradas; não julga prosa.

A entrega usou leitura nova. Os testes reaplicam os pareceres daquele dia,
explicitamente como regressão do vínculo e da publicação.
"""
import json
from pathlib import Path
import subprocess
import sys
from episodio_integrado import ROOT, TOOLS, revisao_sessao as workflow

VERDICTS = ROOT / 'tests/fixtures/revisao-episodio-integrado.json'

def request_for(root, variant):
    root = Path(root)
    bundle = workflow.load(root / 'entrada.json')
    frames = workflow.prepare(root / 'rollout.jsonl', bundle,
                              criterion_ids=['context_and_memory.scene_and_durable_memory'])['frames']
    refs = {frame['turn_id']: frame['evaluation_ref'] for frame in frames}
    decisions = workflow.load(VERDICTS)['cases'][variant]
    return workflow.prepare(root / 'rollout.jsonl', bundle,
                            units=[(refs[item['turn_id']], item['criterion_id']) for item in decisions])

def bind_recorded_decisions(request, variant):
    decisions = workflow.load(VERDICTS)['cases'][variant]
    frames = {frame['turn_id']: frame for frame in request['frames']}
    bound = []
    for recipe in decisions:
        frame = frames[recipe['turn_id']]
        sources = [s for s in frame['sources']
                   if s['kind'] in {'input', 'response', 'native_tool_output'}
                   and s.get('available_before_response') is not False]
        if recipe['state'] == 'fontes_insuficientes':
            sources += [s for s in frame['sources'] if s['kind'] == 'causal_coverage']
        bound.append({**{k: v for k, v in recipe.items() if k != 'turn_id'},
                      'interaction_ref': frame['evaluation_ref'],
                      'evidence': [{'locator': s['locator'], 'quote': request['texts'][s['sha256']]}
                                   for s in sources]})
    return {'request_id': request['request_id'],
            'reviewer': {'identity': 'Codex/revisao-integrada/2026-10-06', 'role': 'revisor_poshoc',
                         'configuration': {'mode': 'leitura_semantica_das_fontes',
                                           'casos_conhecidos': True, 'mesmo_autor_e_revisor': True}},
            'decisions': bound}

def publish_recorded(root, variant, *, fresh=False):
    root = Path(root)
    request = request_for(root, variant)
    work = root / 'trabalho-final'
    cmd = [sys.executable, str(TOOLS / 'revisao_sessao.py'), 'preparar',
           '--rollout', str(root / 'rollout.jsonl'), '--entrada-medicao', str(root / 'entrada.json'),
           '--trabalho', str(work)]
    for ref, criterion in request['required_units']:
        cmd += ['--unidade', ref + ':' + criterion]
    prepared = subprocess.run(cmd, capture_output=True, text=True, check=True)
    submission = bind_recorded_decisions(request, variant)
    submission['reviewer']['configuration']['execucao'] = 'nova_leitura_registrada' if fresh else 'replay_regressao'
    path = work / 'pareceres.json'
    path.write_text(json.dumps(submission, ensure_ascii=False, indent=2)); path.chmod(0o600)
    completed = subprocess.run([sys.executable, str(TOOLS / 'revisao_sessao.py'), 'concluir',
                               '--trabalho', str(work), '--pareceres', str(path),
                               '--saida', str(root / 'publicado'), '--revisao', 'episodio-integrado',
                               '--data-revisao', '2026-10-06'], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)
