"""Contrato da saída pública de retomada, incluindo erros do subprocesso."""
from pathlib import Path
import subprocess
import sys
import unittest

import yaml
import test_memoria_cena_integracao as fixtures


TRACE_SCRIPT = r'''
import ast, hashlib, pathlib, runpy, sys
program = pathlib.Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(program.parent))
source = program.read_bytes()
print("SOURCE", str(program), hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest(), file=sys.stderr)
tree = ast.parse(source)
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"main", "render_resume", "command_resume"}:
        print("DEFINITION", node.name, node.lineno, ast.get_source_segment(source.decode(), node), file=sys.stderr)
names = {"main", "render_resume", "command_resume", "resume", "load_scene", "fit_budget", "decorate"}
def profile(frame, event, value):
    if event not in {"call", "return"} or frame.f_code.co_name not in names:
        return
    if "ferramentas" not in frame.f_code.co_filename:
        return
    info = ""
    if event == "return":
        if isinstance(value, dict):
            info = " keys=" + repr(list(value))
        elif isinstance(value, tuple):
            info = " tuple=" + repr([list(v) if isinstance(v, dict) else type(v).__name__ for v in value])
    else:
        info = " args=" + repr({k: str(v) for k, v in frame.f_locals.items() if k in {"repo", "include_memory", "as_json", "max_bytes"}})
    print("TRACE", event, frame.f_code.co_name, frame.f_code.co_filename, frame.f_code.co_firstlineno, info, file=sys.stderr)
sys.setprofile(profile)
runpy.run_path(str(program), run_name="__main__")
'''


class SceneMemoryCliTest(unittest.TestCase):
    def test_cli_retomada_preserva_memoria_em_ambos_formatos(self):
        fixture = fixtures.SceneMemoryIntegrationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixtures.checkpoint.refresh_memory(fixture.repo, "cena")
        fixture.establish()
        program = Path(__file__).resolve().parents[1] / "ferramentas" / "contexto.py"
        for options in (["--json"], []):
            with self.subTest(formato=options or "yaml"):
                argv = [str(program), "--repo", str(fixture.repo), *options, "retomada"]
                process = subprocess.run([sys.executable, *argv], capture_output=True, text=True, check=False)
                diagnostics = f"program={program}\nSTDERR:\n{process.stderr}\nSTDOUT:\n{process.stdout}"
                output = yaml.safe_load(process.stdout) if process.returncode == 0 else {}
                if process.returncode or not isinstance(output, dict) or "memoria_cena" not in output:
                    trace = subprocess.run([sys.executable, "-c", TRACE_SCRIPT, *argv],
                                           capture_output=True, text=True, check=False)
                    diagnostics += "\nTRACE DIAGNOSTIC:\n" + trace.stderr + "\nTRACE STDOUT:\n" + trace.stdout
                self.assertEqual(process.returncode, 0, diagnostics)
                self.assertIn("memoria_cena", output, diagnostics)
                self.assertEqual(output["memoria_cena"]["modo"], "completa")
                self.assertIn("silva_fixture", output["memoria_cena"]["itens"])
                self.assertLessEqual(len(process.stdout.encode("utf-8")), 8192)
