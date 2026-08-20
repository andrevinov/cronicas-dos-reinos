from __future__ import annotations
import sys, unittest, yaml
from pathlib import Path
ROOT=Path(__file__).parents[1]; TOOLS=ROOT/'ferramentas'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
import arcos, metodos_agentes, autonomia_juppongatana, pressao_ravens_bluff, contexto_cena, arco_mundo

class Phase11PopulationTest(unittest.TestCase):
    def test_parte1_tem_exatamente_quatro_juppongatana_e_dois_aliados(self):
        arc=arcos.load_contract(ROOT,'parte_1_uma_ponte_para_kozakura')
        self.assertEqual(set(arc['habilitacoes']['antagonistas']),{'kurobane_jinzaburo','kajiwara_shizune','pan_chu','sawagejo_cho'})
        self.assertEqual(set(arc['habilitacoes']['aliados']),{'shen_meihua','tsukishiro_joen'})
        self.assertTrue({'yukyuzan_anji','uonuma_usui','kureha_shiranui','amagiri_seishiro','wetuji','fuji'}.isdisjoint(arc['habilitacoes']['antagonistas']))

    def test_arco_tem_duas_direcoes_e_golden_lily_e_destino_nao_operacao(self):
        arc=arcos.load_contract(ROOT,'parte_1_uma_ponte_para_kozakura')
        self.assertEqual(set(arc['habilitacoes']['direcoes']),{'ponte_de_kozakura','golden_lily_em_ravens_bluff'})
        self.assertNotIn('golden_lily_em_ravens_bluff',arc['linhas_operacionais'])

    def test_onze_linhas_cobrem_pressao_urbana_marcial_e_maritima(self):
        arc=arcos.load_contract(ROOT,'parte_1_uma_ponte_para_kozakura')
        self.assertEqual(len(arc['linhas_operacionais']),11)
        for line in ('expandir_presenca_de_masao','ocupar_espaco_urbano','desgastar_autoridade_de_ravens_bluff','pressionar_ren_por_vinculos','pressionar_identidade_marcial_de_ren','sustentar_cobertura_maritima'):
            self.assertIn(line,arc['linhas_operacionais'])

    def test_todo_executor_tem_metodo_sem_acao_concreta_schema(self):
        arc=arcos.load_contract(ROOT,'parte_1_uma_ponte_para_kozakura')
        for lid,line in arc['linhas_operacionais'].items():
            for aid in line['executores']:
                data=yaml.safe_load((ROOT/f'narrador/agentes/{aid}.yaml').read_text(encoding='utf-8'))
                methods=metodos_agentes.for_line(data,lid,expected_agent_id=aid)
                self.assertGreaterEqual(len(methods),1,(lid,aid))

    def test_cho_e_pressao_pessoal_condicionada_a_conhecimento(self):
        cho=yaml.safe_load((ROOT/'narrador/agentes/sawagejo_cho.yaml').read_text(encoding='utf-8'))
        prof=autonomia_juppongatana.normalize_profile(cho['autonomia_estrategica'],'sawagejo_cho')
        self.assertEqual(prof['regra_conhecimento_vinculos'],'exige_conhecimento_canonico')
        methods=metodos_agentes.for_line(cho,'pressionar_ren_por_vinculos')
        self.assertTrue(any('sequestrar' in m['id'].lower() or 'capturar' in m['abordagem'].lower() for m in methods))
        self.assertTrue(all('vinculo_conhecido' in m['tags'] for m in methods))

    def test_cho_tem_capricho_mas_nao_pode_sabotar_masao(self):
        cho=yaml.safe_load((ROOT/'narrador/agentes/sawagejo_cho.yaml').read_text(encoding='utf-8'))
        prof=autonomia_juppongatana.normalize_profile(cho['autonomia_estrategica'],'sawagejo_cho')
        self.assertEqual(prof['regra_masao'],'nao_sabotar_plano_mestre')
        methods=metodos_agentes.for_line(cho,'desgastar_autoridade_de_ravens_bluff')
        self.assertTrue(any('capricho' in m['id'].lower() or 'impulso' in m['abordagem'].lower() for m in methods))

    def test_shizune_tem_exemplo_lendario_do_documento_restaurado_sem_canoniza_lo(self):
        sh=yaml.safe_load((ROOT/'narrador/agentes/kajiwara_shizune.yaml').read_text(encoding='utf-8'))
        prof=autonomia_juppongatana.normalize_profile(sh['autonomia_estrategica'],'kajiwara_shizune')
        blob=' '.join(prof['feito_lendario']['exemplos_nao_obrigatorios']).lower()
        self.assertIn('restaurado',blob)
        disc=yaml.safe_load((ROOT/'narrador/arcos/parte_1/descoberta-e-consequencias.yaml').read_text(encoding='utf-8'))
        self.assertEqual(disc['exemplo_shizune_nao_obrigatorio']['estatuto'],'exemplo_de_escala_lendaria_nao_evento_canonico')

    def test_pan_chu_pode_resistir_expulsao_e_cormyr_permanece_opcional(self):
        pan=yaml.safe_load((ROOT/'narrador/agentes/pan_chu.yaml').read_text(encoding='utf-8'))
        ms=metodos_agentes.for_line(pan,'desgastar_autoridade_de_ravens_bluff')
        self.assertTrue(any('armamento naval' in m['abordagem'].lower() for m in ms))
        src=(ROOT/'narrador/arcos/parte_1/golden-lily.md').read_text(encoding='utf-8')
        self.assertIn('pode ser chamada',src)
        self.assertIn('não é convocado automaticamente',src)

    def test_pan_chu_tem_relogio_canonico_sem_presenca_antecipada(self):
        state=yaml.safe_load((ROOT/'narrador/arcos/estado-marcos-aparicao.yaml').read_text(encoding='utf-8'))
        pan=yaml.safe_load((ROOT/'narrador/agentes/pan_chu.yaml').read_text(encoding='utf-8'))
        self.assertEqual(state['marcos']['pan_chu']['estado'],'elegivel')
        self.assertEqual(pan['estado'],'latente')
        self.assertIn('27 Eleasis',pan['plano_atual']['prazo_ou_oportunidade'])

    def test_contexto_conhece_cho_pan_golden_lily_sem_forcar_evento(self):
        router=contexto_cena.load_router(ROOT)
        self.assertIn('presenca_sawagejo_cho',router['candidatos'])
        self.assertIn('presenca_pan_chu',router['candidatos'])
        self.assertIn('direcao_golden_lily',router['candidatos'])
        self.assertEqual(router['candidatos']['direcao_golden_lily']['tipo'],'direcao')

    def test_shen_e_joen_foram_curados_para_derrota_grave_sem_deus_ex_machina(self):
        sh=yaml.safe_load((ROOT/'narrador/entradas/shen_meihua.yaml').read_text(encoding='utf-8'))
        jo=yaml.safe_load((ROOT/'narrador/entradas/tsukishiro_joen.yaml').read_text(encoding='utf-8'))
        self.assertTrue(any('surra' in x.lower() or 'quase-morte' in x.lower() for x in sh['gatilhos_fortes']))
        self.assertIn('não apaga a derrota',sh['forma_preferencial'])
        self.assertIn('jamais aparece do nada',jo['forma_preferencial'])

    def test_vida_civil_cobre_dojo_night_watch_kage_e_relacoes_sem_automatismo(self):
        d=yaml.safe_load((ROOT/'narrador/arcos/parte_1/vida-civil.yaml').read_text(encoding='utf-8'))
        self.assertFalse(d['dojo']['night_watch']['automatico'])
        self.assertTrue(d['circo_e_kage']['continua_disponivel'])
        self.assertTrue(d['relacoes']['romance_possivel_com_outros_npcs'])
        self.assertFalse(d['relacoes']['automatico'])
        self.assertTrue(d['relacoes']['nao_transformar_em_harem_por_padrao'])

    def test_descoberta_nao_e_concedida_ao_ren(self):
        d=yaml.safe_load((ROOT/'narrador/arcos/parte_1/descoberta-e-consequencias.yaml').read_text(encoding='utf-8'))
        self.assertTrue(d['regras']['ren_nao_e_notificado_automaticamente'])
        self.assertTrue(d['regras']['consequencia_pode_chegar_antes_da_causa'])
        self.assertGreaterEqual(d['regras']['min_canais_para_acao_relevante'],1)

    def test_pressao_urbana_tem_cinco_frentes_e_nao_avanca_por_tempo(self):
        r=pressao_ravens_bluff.validate(ROOT)
        self.assertTrue(r['ok'],r['erros']); self.assertEqual(r['frentes'],5)
        p=pressao_ravens_bluff.load_profile(ROOT)
        self.assertFalse(p['regras']['avanco_automatico'])
        self.assertIn('desgaste_da_autoridade',p['frentes'])
        self.assertIn('ocupacao_imobiliaria',p['frentes'])

    def test_pressao_inclui_precos_despejo_milicia_nobres_e_ajuda_externa(self):
        p=pressao_ravens_bluff.load_profile(ROOT)
        blob=yaml.safe_dump(p,allow_unicode=True).lower()
        for term in ('aluguel','despejo','milícias','night watch','nobres','ajuda externa'):
            self.assertIn(term,blob)

class Phase11ArcWorldStateTest(unittest.TestCase):
    def test_controle_real_exige_estado_ativo_para_cho_e_pan(self):
        d=yaml.safe_load((ROOT/'narrador/arcos/controle-mundo.yaml').read_text(encoding='utf-8'))
        self.assertTrue(d['agentes_estrategicos']['sawagejo_cho']['requer_estado_ativo_para_acao'])
        self.assertTrue(d['agentes_estrategicos']['pan_chu']['requer_estado_ativo_para_acao'])

if __name__=='__main__': unittest.main()
