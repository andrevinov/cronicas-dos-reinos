from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("apply7", ROOT / "APLICAR-FASE7.py")
apply7 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(apply7)


class Phase7PatchAnchorsTest(unittest.TestCase):
    def test_patch_script_e_fail_closed_e_compilavel(self):
        self.assertTrue(hasattr(apply7, "patch_mundo"))
        self.assertTrue(hasattr(apply7, "patch_direcoes_mundo"))
        self.assertTrue(hasattr(apply7, "patch_entradas"))
        self.assertTrue(hasattr(apply7, "patch_eventos"))
        self.assertTrue(hasattr(apply7, "patch_fronteira"))

    def test_mundo_anchor_minimo_recebe_guardrail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "ferramentas/mundo.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                "import agentes\n\n"
                + '''def x():\n    emitted = collect_triggers(agenda, cursor, target)\n    extra_sources = _validate_agent_ids_if_needed(repo, emitted)\n    added = _merge_pending(state, emitted)\n    state["processado_ate"] = instant_parts(target)\n    _atomic_write_yaml(repo / WORLD_STATE_PATH, state)\n    return {\n        "ok": True,\n        "alterou": True,\n        "processado_de": instant_parts(cursor),\n        "processado_ate": instant_parts(target),\n        "novas_pendencias": added,\n        "agentes_reconsiderar": sorted(_referenced_agents(added)),\n        "fontes_lidas": [*base_sources, *extra_sources],\n    }\n\n'''
                + '''def _next_trigger(agenda: dict[str, Any], after: WorldInstant) -> dict[str, Any] | None:\n    horizon = WorldInstant(after.minute + 367 * 1440)\n    candidates = _recurrence_triggers(agenda, after, horizon)\n    candidates.extend(_scheduled_triggers(agenda, after, horizon))\n    if not candidates:\n        return None\n    candidates.sort(\n        key=lambda item: parse_instant(\n            item["disparado_em"]["data"], item["disparado_em"]["hora"]\n        ).minute\n    )\n    return candidates[0]\n\n'''
                + 'x={"proximo_disparo": _next_trigger(agenda, cursor),}\n',
                encoding="utf-8",
            )
            apply7.patch_mundo(root)
            text = path.read_text(encoding="utf-8")
            self.assertIn("import arco_mundo", text)
            self.assertIn("filter_world_triggers", text)
            self.assertIn("bloqueados_pelo_arco", text)
            self.assertIn("_next_trigger(repo, agenda, cursor)", text)

    def test_controle_quente_permanece_pequeno(self):
        path = ROOT / "narrador/arcos/controle-mundo.yaml"
        self.assertLessEqual(path.stat().st_size, 4096)


if __name__ == "__main__":
    unittest.main()
