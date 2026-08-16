from __future__ import annotations

import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas" / "migrar-estado-atual.py"
spec = importlib.util.spec_from_file_location("migrar_estado_atual", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


class EstadoHistoricoTest(unittest.TestCase):
    def test_migracao_real_esta_integra(self):
        self.assertEqual(mod.validate(ROOT), [])

    def test_legado_foi_preservado_byte_a_byte(self):
        self.assertEqual(
            git_blob_sha(ROOT / mod.ARCHIVE_STATE),
            mod.LEGACY_STATE_BLOB,
        )
        self.assertEqual(
            git_blob_sha(ROOT / mod.ARCHIVE_TIME),
            mod.LEGACY_TIME_BLOB,
        )

    def test_estado_corrente_permanece_pequeno(self):
        self.assertLessEqual(
            (ROOT / mod.STATE_PATH).stat().st_size,
            mod.MAX_CURRENT_STATE_BYTES,
        )
        self.assertLessEqual(
            (ROOT / mod.TIME_PATH).stat().st_size,
            mod.MAX_CURRENT_TIME_BYTES,
        )

    def test_tempo_corrente_nao_reincorpora_cronologia(self):
        tempo = mod.load_yaml(ROOT / mod.TIME_PATH)
        self.assertEqual(tempo["natureza"], "tempo_atual")
        self.assertNotIn("marcos_de_tempo", tempo)
        self.assertNotIn("referencias_calendario", tempo)

    def test_condicoes_nao_sao_diario_de_rolagens(self):
        estado = mod.load_yaml(ROOT / mod.STATE_PATH)
        self.assertEqual(estado["natureza"], "estado_atual")
        condicoes = ((estado.get("recursos") or {}).get("condicoes")) or []
        self.assertLessEqual(len(condicoes), 16)
        texto = "\n".join(str(item) for item in condicoes)
        self.assertNotIn("Rolagem para", texto)
        self.assertNotIn("contra CD", texto)


if __name__ == "__main__":
    unittest.main()
