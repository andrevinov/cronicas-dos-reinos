from pathlib import Path
import sys, yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / 'ferramentas'
sys.path.insert(0, str(TOOLS))

import arcos
import autonomia_juppongatana
import eventos_canonicos
import pressao_ravens_bluff

arc = arcos.load_contract(ROOT, 'parte_1_uma_ponte_para_kozakura')
assert set(arc['habilitacoes']['antagonistas']) == {
    'kurobane_jinzaburo', 'kajiwara_shizune', 'sawagejo_cho', 'pan_chu'
}
assert set(arc['habilitacoes']['aliados']) == {'shen_meihua', 'tsukishiro_joen'}
assert set(arc['habilitacoes']['direcoes']) == {'ponte_de_kozakura', 'golden_lily_em_ravens_bluff'}
assert len(arc['linhas_operacionais']) == 11

for agent_id in arc['habilitacoes']['antagonistas']:
    data = yaml.safe_load((ROOT / f'narrador/agentes/{agent_id}.yaml').read_text(encoding='utf-8'))
    profile = autonomia_juppongatana.normalize_profile(data['autonomia_estrategica'], agent_id)
    assert profile['regra_masao'] == 'nao_sabotar_plano_mestre'
    assert profile['regra_conhecimento_vinculos'] == 'exige_conhecimento_canonico'

pressure = pressao_ravens_bluff.validate(ROOT)
assert pressure['ok'] and pressure['frentes'] == 5, pressure

canonical = eventos_canonicos.validate(ROOT)
assert canonical['ok'] and canonical['eventos'] == 17, canonical

pan = yaml.safe_load((ROOT / 'narrador/agentes/pan_chu.yaml').read_text(encoding='utf-8'))
assert pan['estado'] == 'latente'
assert '27 Eleasis' in pan['plano_atual']['prazo_ou_oportunidade']

golden = (ROOT / 'narrador/arcos/parte_1/golden-lily.md').read_text(encoding='utf-8')
assert '27 Eleasis' in golden and '10:00' in golden
assert '29 Eleasis' in golden and 'não atacam' in golden

catalog = eventos_canonicos.load_catalog(ROOT)['eventos']
assert catalog['sequestro_de_kethra']['ativacao']['data'] == '1 Eleint, 1372 DR'
assert 'descida_a_ponte_e_masao' in catalog

print('smoke população Parte 1: OK')
