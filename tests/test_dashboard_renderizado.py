"""Navegador real sobre cenário temporário e pacote histórico imutável da 024.

O histórico reproduz o defeito original. As revisões sintéticas isolam validade,
prova pública/reservada, qualidade zero e comparabilidade, sem tocar no save.
"""
import copy
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("google-chrome"), "Chrome necessário para DOM renderizado")
class RenderedDashboardTest(unittest.TestCase):
    def test_s024_derivada_exibe_contagens_e_diagnostico_real(self):
        # Snapshot de engenharia AMV-05, datado e derivado do mesmo histórico.
        with tempfile.TemporaryDirectory(prefix="dashboard-s024-") as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "evaluation/dashboard", root / "evaluation/dashboard")
            shutil.copy(ROOT / "evaluation/module-releases.json", root / "evaluation/module-releases.json")
            package = root / "evaluation/sessions/024"
            package.mkdir(parents=True)
            for revision in ("", "revisoes/amv05", "revisoes/amv14a-final"):
                target = package / revision
                target.mkdir(parents=True, exist_ok=True)
                for name in ("manifest.json", "scorecard.json", "resumo-modulos.json", "interacoes.json",
                             "manifestacoes-jogador.json", "avaliacoes-qualidade.json", "proveniencia-medicao.json"):
                    shutil.copy(ROOT / "evaluation/sessions/024" / revision / name, target / name)
            shutil.copy(ROOT / "evaluation/sessions/index.json", package.parent / "index.json")
            prior = package.parent / "023"
            prior.mkdir()
            for name in ("manifest.json", "scorecard.json", "resumo-modulos.json", "interacoes.json", "manifestacoes-jogador.json"):
                shutil.copy(ROOT / "evaluation/sessions/023" / name, prior / name)
            driver = """
<script>window.addEventListener('load',async()=>{try{
 const until=async p=>{for(let i=0;i<200;i++){if(p())return;await new Promise(r=>setTimeout(r,50));}throw Error('timeout');};
 await until(()=>document.querySelector('#overallBand').textContent==='Medição incompleta');
 const sel=document.querySelector('#revisionSelect');sel.value='amv05';sel.dispatchEvent(new Event('change'));
 await until(()=>document.querySelector('#overallBand').textContent==='Violação crítica');
 const link=document.querySelector('#criticalFindings a');link.click();
 await until(()=>document.querySelector('#parecer-amv04-espera-nao-autorizada').open);
 const metrics=Object.fromEntries([...document.querySelectorAll('#metricsGrid .metric-card')].map(c=>[c.querySelector('span').textContent,c.querySelector('strong').textContent]));
 const value={title:document.querySelector('#sessionTitle').textContent,metrics,coverage:document.querySelector('#coverageSummary').textContent,
 proof:document.querySelector('#parecer-amv04-espera-nao-autorizada').textContent, provenance:document.querySelector('#provenanceSummary').textContent,
 reviews:document.querySelectorAll('.review-card').length, feedback:document.querySelector('#interactionFeedbackSection').textContent,
 insights:document.querySelector('#insights').textContent};
 sel.value='amv14a-final';sel.dispatchEvent(new Event('change'));
 await until(()=>document.querySelector('#validitySummary').textContent.includes('13/13 unidades decididas'));
 value.workflow=document.querySelector('#validitySummary').textContent;
 value.currentInsights=document.querySelector('#insights').textContent;
 value.priorities=[...document.querySelectorAll('.insight')].filter(x=>x.textContent.includes('Problema confirmado da experiência')).map(x=>x.textContent);
 const session=document.querySelector('#sessionSelect');session.value='023';session.dispatchEvent(new Event('change'));
 await until(()=>document.querySelector('#sessionTitle').textContent==='Sessão 023');
 value.historicalCompatible=document.querySelector('#reviewGrid').textContent.includes('Nenhum parecer');
 document.body.append(Object.assign(document.createElement('pre'),{id:'native-result',textContent:JSON.stringify(value)}));
}catch(e){document.body.append(Object.assign(document.createElement('pre'),{id:'native-result',textContent:JSON.stringify({error:String(e)})}));}});</script>
"""
            html = root / "evaluation/dashboard/index.html"
            html.write_text(html.read_text().replace("</body>", driver + "</body>"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                result = subprocess.run([shutil.which("google-chrome"), "--headless=new", "--no-sandbox", "--disable-gpu",
                    f"--user-data-dir={root / 'chrome'}", "--virtual-time-budget=22000", "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/evaluation/dashboard/"], capture_output=True, text=True, timeout=35, check=True)
            finally:
                server.shutdown(); server.server_close(); thread.join()
            import html as html_parser
            match = re.search(r'<pre id="native-result">(.*?)</pre>', result.stdout, re.S)
            self.assertIsNotNone(match, result.stdout[-1200:])
            observed = json.loads(html_parser.unescape(match.group(1)))
            self.assertNotIn("error", observed)
            self.assertEqual(observed["title"], "Sessão 024")
            self.assertEqual(observed["reviews"], 13)
            for label, value in (("Chamadas nativas · recorte completo", "62"), ("Escritas tentadas", "15"),
                ("Escritas com sucesso", "11"), ("Escritas com falha", "2"), ("Escritas sem resultado comprovado", "2")):
                self.assertEqual(observed["metrics"][label], value)
            self.assertIn("408", observed["coverage"])
            self.assertIn("395", observed["coverage"])
            self.assertIn("Correção proposta:", observed["proof"])
            self.assertIn("Narração acrescentou decisão voluntária de Ren sem autorização", observed["proof"])
            self.assertIn("avaliação registrada no jogo 4.0.0", observed["provenance"])
            self.assertIn("sem novo jogo", observed["provenance"])
            self.assertIn("parcial", observed["feedback"])
            self.assertTrue(observed["historicalCompatible"])
            self.assertIn("Maior nota operacional parcial", observed["insights"])
            self.assertNotIn("Melhor nota", observed["insights"])
            self.assertIn("13/13 unidades decididas", observed["workflow"])
            self.assertIn("parcial_declarado", observed["workflow"])
            self.assertIn("Narrative Delivery", observed["priorities"][0])
            self.assertIn("crítico", observed["priorities"][0])
            self.assertNotIn("Context And Memory", observed["priorities"][0])

    def test_revisoes_validade_provas_series_e_reserva_no_dom_real(self):
        with tempfile.TemporaryDirectory(prefix="dashboard-renderizado-") as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "evaluation/dashboard", root / "evaluation/dashboard")
            shutil.copy(ROOT / "evaluation/module-releases.json", root / "evaluation/module-releases.json")
            package = root / "evaluation/sessions/024"
            package.mkdir(parents=True)
            # Somente arquivos efetivamente consumidos pela página, sem fonte bruta.
            files = ("manifest.json", "scorecard.json", "resumo-modulos.json", "interacoes.json",
                     "manifestacoes-jogador.json", "avaliacoes-qualidade.json", "proveniencia-medicao.json")
            for name in files:
                shutil.copy(ROOT / "evaluation/sessions/024" / name, package / name)
            card = json.loads((package / "scorecard.json").read_text())
            rows = json.loads((package / "resumo-modulos.json").read_text())["modulos"]
            entry = {"sessao_id": "024", "caminho": "024", "serie_avaliacao": "modules-v2",
                     "nota_geral_0a100": 85.1, "conclusao_medicao": {"permitida": False},
                     "agregacao_modular": {"conclusao_permitida": False}, "chave_comparabilidade": ["modules-v2", "test"]}
            derived = package / "revisoes/teste"
            shutil.copytree(package, derived, ignore=shutil.ignore_patterns("revisoes"))
            states = ["inadequada_no_criterio", "negativa_valida", "fontes_insuficientes", "nao_avaliada",
                      "amostra_insuficiente_para_generalizar"]
            for index, row in enumerate(rows):
                row["nota_desempenho_provisoria_0a100"] = 100
                row["nota_qualidade_interacao_0a100"] = 0 if index == 0 else None
                row["leitura_experiencia"] = {"estado": states[index % len(states)], "unidades": 10,
                                             "confirmadas_verificadas": 1, "pendencias": 9,
                                             "elegiveis": 1, "atendidas": 1, "omitidas": 0,
                                             "negativas_validas": 0, "indeterminadas": 9,
                                             "assessment_ids": ["publica"]}
                row["comparabilidade"] = {"qualidade": row["modulo"], "custo": row["modulo"]}
            card["apresentacao"] = {"qualidade": "violacao_critica", "conclusao_global_permitida": False,
                                    "cobertura": {"unidades_interacao_criterio": 120, "com_parecer": 2,
                                                 "confirmadas_verificadas": 2, "sem_parecer": 118}}
            card["nota_operacional_parcial_0a100"] = 100
            card["violacoes_criticas"] = [{"guardrail": "player_agency", "assessment_id": "publica",
                                          "interaction_ref": "S024-I0011", "module_id": rows[0]["modulo"]}]
            (derived / "scorecard.json").write_text(json.dumps(card))
            (derived / "resumo-modulos.json").write_text(json.dumps({"modulos": rows}))
            manifest = json.loads((derived / "manifest.json").read_text())
            manifest["revisao"] = {"rotulo": "Revisão de teste", "manifest_original_sha256": "a" * 64}
            (derived / "manifest.json").write_text(json.dumps(manifest))
            evidence = {"visibility": "publica", "literal": "Citação pública de teste.", "locator": "S024-I0011/response",
                        "source_sha256": "b" * 64, "literal_sha256": "c" * 64, "start": 1, "end": 25}
            public = {"assessment_id": "publica", "interaction_ref": "S024-I0011", "criterion_id": "voice",
                      "quality": "inadequada", "eligibility": "sim", "activation": "presente",
                      "adjudication": {"state": "confirmada"}, "review": {"verification": "verificada",
                      "diagnosis": {"category": "instrucao_dado", "finding": "Achado público", "correction": "Correção pública", "test": "Teste público"}}, "evidence": [evidence]}
            secret = copy.deepcopy(public)
            secret["assessment_id"] = "reservada"
            secret["evidence"][0].update(visibility="reservada", literal="SEGREDO_NAO_EXPORTAR", observation="SEGREDO_NAO_EXPORTAR")
            secret["review"]["diagnosis"]["finding"] = "SEGREDO_NAO_EXPORTAR"
            (derived / "avaliacoes-qualidade.json").write_text(json.dumps({"assessments": [public, secret]}))
            revision = {**entry, "caminho": "024/revisoes/teste", "revisao_id": "teste",
                        "revisao": manifest["revisao"], "series_modulos": [{"module_id": row["modulo"],
                          "comparabilidade": row["comparabilidade"], "estado": row["leitura_experiencia"]["estado"],
                          "qualidade": 0, "guardrail": False} for row in rows]}
            entry["revisoes"] = [revision]
            prior = {**entry, "sessao_id": "023", "caminho": "023", "revisoes": [],
                     "series_modulos": [{**revision["series_modulos"][0], "comparabilidade": {"qualidade": "incompativel"}}]}
            (package.parent / "index.json").write_text(json.dumps({"sessoes": [prior, entry]}))
            driver = """
<script>
const until = async predicate => {for(let i=0;i<200;i++){if(predicate())return; await new Promise(r=>setTimeout(r,50));}throw Error('interface não carregou');};
window.addEventListener('load', async () => {try {
 await until(()=>document.querySelector('#overallBand').textContent==='Medição incompleta');
 const original = {band:document.querySelector('#overallBand').textContent, score:document.querySelector('#overallScore').textContent,
 trend:document.querySelector('#trendChart').textContent, revisions:document.querySelector('#revisionSelect').options.length};
 const select=document.querySelector('#revisionSelect');select.value='teste';select.dispatchEvent(new Event('change'));
 await until(()=>document.querySelector('#overallBand').textContent==='Violação crítica');
 const proof=document.querySelector('#parecer-publica');proof.open=true;
 const trend=document.querySelector('#trendMetric');trend.value='modulo:context_and_memory:qualidade';trend.dispatchEvent(new Event('change'));
 const revised={band:document.querySelector('#overallBand').textContent, score:document.querySelector('#overallScore').textContent,
 text:document.querySelector('#topo').textContent, trend:document.querySelector('#trendChart').textContent,
 points:document.querySelectorAll('.series-points li').length, proof:proof.textContent};
 select.value='original';select.dispatchEvent(new Event('change'));
 await until(()=>document.querySelector('#overallBand').textContent==='Medição incompleta');
 document.body.append(Object.assign(document.createElement('pre'),{id:'browser-result',textContent:JSON.stringify({original,revised,returned:true})}));
}catch(e){document.body.append(Object.assign(document.createElement('pre'),{id:'browser-result',textContent:JSON.stringify({error:String(e)})}));}});
</script>
"""
            html = root / "evaluation/dashboard/index.html"
            html.write_text(html.read_text().replace("</body>", driver + "</body>"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run([shutil.which("google-chrome"), "--headless=new", "--no-sandbox", "--disable-gpu",
                                         f"--user-data-dir={root / 'chrome'}", "--virtual-time-budget=22000", "--dump-dom",
                                         f"http://127.0.0.1:{server.server_port}/evaluation/dashboard/"],
                                        capture_output=True, text=True, timeout=35, check=True)
            finally:
                server.shutdown(); server.server_close(); thread.join()
            match = re.search(r'<pre id="browser-result">(.*?)</pre>', result.stdout, re.S)
            self.assertIsNotNone(match, result.stdout[-1200:])
            import html as html_parser
            observed = json.loads(html_parser.unescape(match.group(1)))
            self.assertNotIn("error", observed)
            self.assertEqual(observed["original"]["band"], "Medição incompleta")
            self.assertEqual(observed["original"]["score"], "—")
            self.assertEqual(observed["original"]["revisions"], 2)
            self.assertIn("Sem pontos válidos", observed["original"]["trend"])
            self.assertEqual(observed["revised"]["band"], "Violação crítica")
            self.assertEqual(observed["revised"]["score"], "!")
            self.assertIn("Experiência inadequada no critério", observed["revised"]["text"])
            self.assertIn("Negativa válida", observed["revised"]["text"])
            self.assertIn("Fontes insuficientes", observed["revised"]["text"])
            self.assertIn("Qualidade não avaliada", observed["revised"]["text"])
            self.assertIn("amostra insuficiente", observed["revised"]["text"])
            self.assertIn("Citação pública de teste.", observed["revised"]["proof"])
            self.assertIn("Achado público", observed["revised"]["proof"])
            self.assertNotIn("SEGREDO_NAO_EXPORTAR", observed["revised"]["text"])
            self.assertEqual(observed["revised"]["points"], 1)
            self.assertNotIn("Sessão 023:", observed["revised"]["trend"])
            self.assertTrue(observed["returned"])
