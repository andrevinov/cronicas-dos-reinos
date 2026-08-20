from __future__ import annotations

import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location("apply9", ROOT/"APLICAR-FASE9.py")
apply9=importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader; SPEC.loader.exec_module(apply9)


class Phase9PatchTest(unittest.TestCase):
    def test_patch_exige_fase7_e_e_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); p=root/"ferramentas/entradas.py"; p.parent.mkdir(parents=True)
            p.write_text("import mundo\n\ndef process_checkpoint(repo):\n    pass\n\ndef check_world(repo):\n    pass\n",encoding="utf-8")
            with self.assertRaises(apply9.PatchError): apply9.patch_entradas(root)

    def test_patch_troca_pendencia_por_janela_contextual(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); p=root/"ferramentas/entradas.py"; p.parent.mkdir(parents=True)
            p.write_text(
                "import mundo\nimport arco_mundo\n\n"
                "def process_checkpoint(repo):\n    old=True\n\n"
                "def check_world(repo):\n    return True\n",
                encoding="utf-8",
            )
            apply9.patch_entradas(root)
            text=p.read_text(encoding="utf-8")
            self.assertIn('"janela_contextual_aberta":cid',text)
            self.assertIn('record("abrir_janela_contextual"',text)
            self.assertNotIn('tipo":"avaliar_entrada"',text)
            self.assertIn('pendencias_legadas_removidas',text)

    def test_process_checkpoint_realmente_abre_janela_sem_pendencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); tools=root/"ferramentas"; tools.mkdir(parents=True)
            (tools/"mundo.py").write_text(
                "class WorldInstant:\n"
                "    def __init__(self, minute): self.minute=minute\n"
                "    def __lt__(self,o): return self.minute<o.minute\n"
                "    def __le__(self,o): return self.minute<=o.minute\n"
                "    def __gt__(self,o): return self.minute>o.minute\n"
                "def load_world_state(repo): return {'pendencias': []}\n"
                "def load_canonical_time(repo): return WorldInstant(100), {}\n"
                "def instant_parts(x): return {'data':'12 Eleasis, 1372 DR','hora':'06:00'}\n"
                "def _atomic_write_yaml(path,data): pass\n"
                "WORLD_STATE_PATH='world.yaml'\nTIME_PATH='time.yaml'\n",
                encoding="utf-8",
            )
            (tools/"arco_mundo.py").write_text(
                "class ArcWorldError(ValueError): pass\n"
                "def entry_gate(repo,cid): return {'permitido':True,'fontes_lidas':['arco']}\n",
                encoding="utf-8",
            )
            (tools/"entradas.py").write_text(
                "import mundo\nimport arco_mundo\n"
                "INDEX='idx'; STATE='state'; RUNTIME='runtime'\n"
                "IDX={'cadencia_padrao_dias':3,'candidatos':{'shen':{'nome':'Shen','nivel_minimo_normal':6}}}\n"
                "ST={'candidatos':{'shen':{'estado':'latente','antecipado':False,'proxima_avaliacao':mundo.WorldInstant(90),'historico_recente':[]}}}\n"
                "def load_index(repo): return IDX\n"
                "def load_state(repo,index): return ST\n"
                "def focus(index,state): return 'shen'\n"
                "def level(repo): return 6\n"
                "def parse_due(v,label): return v\n"
                "def atomic(path,data): pass\n"
                "def record(action,origin,note,when): return {'acao':action,'origem':origin,'nota':note}\n"
                "def process_checkpoint(repo):\n    old=True\n\n"
                "def check_world(repo): return {'ok':True}\n",
                encoding="utf-8",
            )
            apply9.patch_entradas(root)
            sys.path.insert(0,str(tools))
            try:
                for name in ("entradas","mundo","arco_mundo"): sys.modules.pop(name,None)
                mod=importlib.import_module("entradas")
                result=mod.process_checkpoint(root)
                self.assertEqual(result["janela_contextual_aberta"],"shen")
                self.assertEqual(result["novas_pendencias"],[])
                self.assertIsNone(mod.ST["candidatos"]["shen"]["proxima_avaliacao"])
                self.assertEqual(mod.ST["candidatos"]["shen"]["historico_recente"][-1]["acao"],"abrir_janela_contextual")
            finally:
                sys.path.remove(str(tools))
                for name in ("entradas","mundo","arco_mundo"): sys.modules.pop(name,None)

    def test_direcoes_mundo_expoe_janelas_abertas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); p=root/"ferramentas/direcoes_mundo.py"; p.parent.mkdir(parents=True)
            p.write_text('x={\n        "entradas_reconsiderar": entry.get("entradas_reconsiderar") or [],\n}\n',encoding="utf-8")
            apply9.patch_direcoes_mundo(root)
            self.assertIn("entradas_contextuais_abertas",p.read_text(encoding="utf-8"))


if __name__=="__main__": unittest.main()
