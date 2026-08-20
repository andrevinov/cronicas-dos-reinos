from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("aplicar_fase10", ROOT / "APLICAR-FASE10.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class Fase10PatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "ferramentas").mkdir(parents=True)
        (self.root / "tests").mkdir(parents=True)
        (self.root / "ferramentas/direcoes_destino.py").write_text("# stub\n", encoding="utf-8")
        (self.root / "ferramentas/direcoes.py").write_text(
            '''INDEX_PATH = Path("narrador/direcoes/index.yaml")
    if data.get("nome") != meta.get("nome"):
        raise DirectionError(f"nome de {direction_id} diverge entre índice e fragmento")
def activate(repo: Path, query: str, origin: str, note: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    direction_id, _ = resolve(index, query)
def advance(repo: Path, query: str, origin: str, note: str) -> dict[str, Any]:
    direction_id, meta = resolve(index, query)
    current = state["direcoes"][direction_id]
    if current["estado"] != "ativa":
    if current["marcos_concluidos"] != ordered[:index_current]:
        raise DirectionError(f"progresso inconsistente antes de avançar {direction_id}")

    current["marcos_concluidos"].append(milestone)
        _history(repo, "avancar", origin, note, marco_concluido=milestone, proximo_marco=next_milestone)
    return {
        "ok": True,
        "direcao": direction_id,
        "marco_concluido": milestone,
    show_parser = sub.add_parser("mostrar")
    show_parser.add_argument("direcao")
    sub.add_parser("validar")
    advance_parser.add_argument("--origem", required=True)
    advance_parser.add_argument("--nota", required=True)
        elif args.comando == "ativar":
            result = activate(repo, args.direcao, args.origem, args.nota)
        elif args.comando == "avancar":
            result = advance(repo, args.direcao, args.origem, args.nota)
        else:
''',
            encoding="utf-8",
        )
        (self.root / "ferramentas/direcoes_mundo.py").write_text(
            '''                "tipo": "ativar_direcao",
                "direcao": direction_id,
                "agentes_afetados": [],
                    "tipo": "avaliar_direcao",
                    "direcao": direction_id,
                    "agentes_afetados": [],
''',
            encoding="utf-8",
        )
        (self.root / "tests/test_direcoes.py").write_text(
            '''        result = direcoes.advance(self.repo, "ponte", "Sessão teste", "As pistas se acumularam.")
        self.assertEqual(result["marco_concluido"], "pistas")
        self.assertEqual(result["proximo_marco"], "controle_perdido")
        self.assertEqual(before, digest(public))
        state = direcoes.load_state(self.repo)
        self.assertEqual(state["direcoes"]["ponte"]["marcos_concluidos"], ["pistas"])
        self.assertEqual(state["direcoes"]["ponte"]["historico_recente"][-1]["origem"], "Sessão teste")
''',
            encoding="utf-8",
        )
        (self.root / "AGENTS.md").write_text(
            '''**Gatilho reativo não é rotina.** Em começo de cena, entrada/exploração, encontro ou mudança de elenco, preferir `ferramentas/cena_mundo.py abrir` com `cena_id` estável, local só se entrou/explorou e NPCs cujo encontro começou. Repetir o ID é seguro; NPC novo usa o mesmo ID. Sem gatilho, não consultar recompensa/oportunidade.
''',
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_patch_integra_sem_adivinhar(self):
        mod.patch(self.root)
        direction = (self.root / "ferramentas/direcoes.py").read_text(encoding="utf-8")
        self.assertIn("import direcoes_destino", direction)
        self.assertIn('sub.add_parser("avaliar-destino")', direction)
        self.assertIn('advance_parser.add_argument("--evidencia", required=True', direction)
        self.assertIn("verify_advance_evidence", direction)
        world = (self.root / "ferramentas/direcoes_mundo.py").read_text(encoding="utf-8")
        self.assertEqual(world.count('"papel": "restricao_destino"'), 2)
        self.assertIn("fato-avanco.md", (self.root / "tests/test_direcoes.py").read_text(encoding="utf-8"))
        self.assertIn("Direção canônica é restrição de destino", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_patch_falha_fechado_se_anchor_sumiu(self):
        (self.root / "AGENTS.md").write_text("arquivo mudou\n", encoding="utf-8")
        with self.assertRaises(mod.PatchError):
            mod.patch(self.root)


if __name__ == "__main__":
    unittest.main()
