from __future__ import annotations

import csv
import io
import random
import shutil
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "ferramentas") not in sys.path:
    sys.path.insert(0, str(ROOT / "ferramentas"))

import nomes_npcs as names
import npc_continuity_and_social_behavior as continuity
import npc_stubs


class NpcNameCatalogTest(unittest.TestCase):
    """Entradas controladas: nenhuma reserva/escrita alcança a campanha viva."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.rows = [
            self._row("Lorin", "nome", "masculino"),
            self._row("Faren", "nome", "masculino"),
            self._row("Mira", "nome", "feminino"),
            self._row("Stone", "sobrenome", "neutro"),
            self._row("Vell", "sobrenome", "neutro"),
            self._row("Oak", "sobrenome", "neutro"),
            self._row("Skarn", "nome", "masculino", culture="Illuskana"),
            self._row("Wave", "sobrenome", "neutro", culture="Illuskana"),
        ]
        self._catalog(self.rows)
        self._write("estado/npcs/index.yaml", {"schema_npcs": 2, "quantidade": 0, "npcs": {}})
        self._write("estado/relacoes/index.yaml", {"schema_relacoes": 2, "relacoes": {}})

    def _row(self, name: str, kind: str, gender: str, *, culture: str = "Damarana", race: str = "Humano") -> dict:
        return {
            "id": "", "nome": name, "tipo_nome": kind, "genero": gender,
            "raca": race, "cultura_subraca": culture,
            "regiao_primaria": "Damara / Vaasa",
            "regioes_compativeis": "The Vast; Tethyr (diáspora)",
            "status": "gerado_compativel", "fonte_base": "fixture isolada",
            "fonte_url": "", "observacao": "não descreve NPC vivo",
        }

    def _catalog(self, rows: list[dict]) -> None:
        with (self.repo / names.CATALOG).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=names.FIELDS)
            writer.writeheader()
            for index, row in enumerate(rows):
                writer.writerow({**row, "id": f"FIX{index:04d}"})

    def _write(self, path: str, value: dict) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _generate(self, key: str = "pessoa-1", **overrides) -> dict:
        conditions = {
            "reservation": key, "gender": "masculino", "race": "Humano",
            "region": "The Vast", "culture": "Damarana", "rng": random.Random(7),
        }
        conditions.update(overrides)
        return continuity.generate_name(self.repo, **conditions)

    def _bytes(self) -> dict[str, bytes]:
        return {path.relative_to(self.repo).as_posix(): path.read_bytes() for path in self.repo.rglob("*") if path.is_file()}

    def test_filtros_bom_regiao_compativel_e_cultura_coerente(self) -> None:
        result = self._generate(gender="feminino", race="humano", region="the_vast", culture="damarana")
        self.assertEqual(result["selecoes"][0]["nome"], "Mira")
        self.assertEqual({row["cultura_subraca"] for row in result["selecoes"]}, {"Damarana"})
        self.assertTrue(all(row["fonte_base"] == "fixture isolada" for row in result["selecoes"]))
        self.assertFalse(result["cria_npc"])
        self.assertFalse(result["reuso_componentes"])
        self.assertIn("npc_continuity_and_social_behavior|gerar_nome|aplicavel|1", result["cobertura_avaliacao_modular"]["recibos"])

    def test_regiao_primaria_composta_e_diaspora_sem_fallback(self) -> None:
        self.assertTrue(self._generate(region="Vaasa")["ok"])
        self.assertTrue(self._generate("pessoa-2", region="Tethyr")["ok"])
        with self.assertRaisesRegex(names.NpcNameError, "sem candidatos"):
            self._generate("pessoa-3", region="Ravens Bluff")

    def test_nome_e_sobrenome_nunca_misturam_culturas(self) -> None:
        self._catalog([self.rows[0], self.rows[-1]])
        with self.assertRaisesRegex(names.NpcNameError, "pool"):
            self._generate(culture=None)

    def test_genero_raca_e_cultura_nao_sao_ampliados_silenciosamente(self) -> None:
        for overrides in ({"gender": "neutro"}, {"race": "Elfo"}, {"culture": "Shou"}):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(names.NpcNameError, "sem candidatos"):
                    self._generate(**overrides)
        self.assertFalse((self.repo / names.RESERVATIONS).exists())

    def test_raca_acentuada_e_nome_neutro_de_virtude(self) -> None:
        self._catalog([self._row("Grâce", "virtude", "neutro", race="Anão")])
        result = self._generate(race="ANAO", surname_type=None)
        self.assertEqual(result["nome_completo"], "Grâce")
        self.assertEqual(len(result["selecoes"]), 1)

    def test_nome_presente_em_dois_generos_nao_perde_candidato_feminino(self) -> None:
        self._catalog([self._row("Alex", "nome", "masculino"), self._row("Alex", "nome", "feminino")])
        result = self._generate(gender="feminino", surname_type=None)
        self.assertEqual(result["selecoes"][0]["genero"], "feminino")

    def test_cla_so_com_tipo_explicito(self) -> None:
        self._catalog([self.rows[0], self._row("Iron", "clã", "neutro")])
        with self.assertRaisesRegex(names.NpcNameError, "sem candidatos"):
            self._generate()
        self.assertEqual(self._generate(surname_type="clã")["selecoes"][1]["tipo_nome"], "clã")

    def test_retry_reutiliza_reserva_e_bytes_sem_reroll(self) -> None:
        first = self._generate()
        before = self._bytes()
        second = self._generate(rng=random.Random(987))
        self.assertEqual(first["nome_completo"], second["nome_completo"])
        self.assertTrue(second["reutilizado"])
        self.assertEqual(before, self._bytes())
        with self.assertRaisesRegex(names.NpcNameError, "mesmos filtros"):
            self._generate(gender="feminino")
        self.assertEqual(before, self._bytes())

    def test_componentes_pendentes_sao_unicos_pool_esgota_e_reuso_e_minimo(self) -> None:
        first, second = self._generate(), self._generate("pessoa-2")
        self.assertTrue(all(left["nome"] != right["nome"] for left, right in zip(first["selecoes"], second["selecoes"])))
        with self.assertRaisesRegex(names.NpcNameError, "pool"):
            self._generate("pessoa-3")
        third = self._generate("pessoa-3", allow_reuse=True)
        self.assertTrue(third["reuso_componentes"])
        self.assertEqual([row["total"] for row in third["usos_antes"]], [1, 0])
        self.assertNotIn(third["nome_completo"], {first["nome_completo"], second["nome_completo"]})

    def test_nome_completo_duplicado_bloqueia_mesmo_com_reuso(self) -> None:
        self._catalog([self.rows[0], self.rows[4]])
        self._write("estado/npcs/index.yaml", {"schema_npcs": 2, "npcs": {"lorin_vell": {"nome": "Lorin Vell"}}})
        with self.assertRaisesRegex(names.NpcNameError, "pool"):
            self._generate(allow_reuse=True)

    def test_contador_canonico_deduplica_ids_indices_e_aliases(self) -> None:
        person = {"nome": "Lorin Vell", "aliases": ["Lorin", "Lorin Vell"]}
        self._write("estado/npcs/index.yaml", {"schema_npcs": 2, "npcs": {"lorin_vell": person}})
        self._write("estado/relacoes/index.yaml", {"relacoes": {"lorin_vell": person}})
        self._catalog([self.rows[0], self.rows[3]])
        result = self._generate(allow_reuse=True)
        self.assertEqual(result["usos_antes"][0], {"canonicos": 1, "reservas_pendentes": 0, "total": 1})
        self.assertEqual(result["usos_antes"][1]["total"], 0)

    def test_reserva_materializada_nao_conta_duas_vezes_nem_libera_nome(self) -> None:
        self._catalog([self.rows[0], self.rows[3], self.rows[4]])
        first = self._generate()
        identity = npc_stubs.resolve_or_propose(self.repo, first["nome_completo"])["identidade_stub"]
        self.assertEqual(identity["reserva_nome"], "pessoa-1")
        npc_stubs.ensure_stub(self.repo, identity, scene_id="cena-fixture")
        fragment = yaml.safe_load((self.repo / f"estado/npcs/{identity['npc_id']}.yaml").read_text(encoding="utf-8"))
        self.assertEqual(fragment["npc"]["nomeacao"]["entradas"], [row["id"] for row in first["selecoes"]])
        second = self._generate("pessoa-2", allow_reuse=True)
        self.assertEqual(second["usos_antes"][0], {"canonicos": 1, "reservas_pendentes": 0, "total": 1})
        self.assertEqual(self._generate()["estado"], "materializado")
        with self.assertRaisesRegex(names.NpcNameError, "materializado"):
            names.cancel(self.repo, "pessoa-1")
        self.assertFalse(npc_stubs.ensure_stub(self.repo, identity, scene_id="cena-fixture")["criado"])

    def test_cancelamento_libera_proposta_mas_nao_reutiliza_chave(self) -> None:
        self._catalog([self.rows[0], self.rows[3]])
        first = self._generate()
        names.cancel(self.repo, "pessoa-1")
        with self.assertRaisesRegex(names.NpcNameError, "cancelada"):
            self._generate()
        second = self._generate("pessoa-2")
        self.assertEqual(first["nome_completo"], second["nome_completo"])
        self.assertEqual(second["usos_antes"][0]["total"], 0)

    def test_stub_sem_reserva_falha_sem_escrever_canonico(self) -> None:
        before = self._bytes()
        with self.assertRaisesRegex(npc_stubs.NpcStubError, "reserva nominal"):
            npc_stubs.resolve_or_propose(self.repo, "Tomas Rell")
        with self.assertRaisesRegex(npc_stubs.NpcStubError, "reserva nominal"):
            npc_stubs.ensure_stub(self.repo, {"npc_id": "tomas_rell", "nome": "Tomas Rell", "stub_automatico": True}, scene_id="fixture")
        self.assertEqual(before, self._bytes())

    def test_lote_revalida_todas_reservas_antes_de_criar_primeiro_stub(self) -> None:
        first = self._generate()
        identity = npc_stubs.resolve_or_propose(self.repo, first["nome_completo"])["identidade_stub"]
        before = self._bytes()
        with self.assertRaisesRegex(npc_stubs.NpcStubError, "reserva nominal"):
            npc_stubs.ensure_many(self.repo, [identity, {"npc_id": "zavros_vane", "nome": "Zavros Vane", "stub_automatico": True}], scene_id="fixture")
        self.assertEqual(before, self._bytes())

    def test_excecao_exige_autoridade_e_evidencia_preserva_nome(self) -> None:
        with self.assertRaises(names.NpcNameError):
            continuity.register_authoritative_name(self.repo, reservation="fonte-1", name="NPC Oficial", origin="estetica", evidence="gostei")
        with self.assertRaisesRegex(names.NpcNameError, "evidência"):
            continuity.register_authoritative_name(self.repo, reservation="fonte-1", name="NPC Oficial", origin="fonte_autorizada", evidence="")
        result = continuity.register_authoritative_name(self.repo, reservation="fonte-1", name="NPC Oficial", origin="fonte_autorizada", evidence="fixture: livro autorizado, p. 10")
        self.assertEqual(result["nome_completo"], "NPC Oficial")
        self.assertEqual(npc_stubs.resolve_or_propose(self.repo, "NPC Oficial")["identidade_stub"]["reserva_nome"], "fonte-1")
        with self.assertRaisesRegex(names.NpcNameError, "já pertence"):
            continuity.register_authoritative_name(self.repo, reservation="fonte-2", name="npc oficial", origin="escolha_jogador", evidence="fixture: escolha literal")

    def test_ticket_de_reserva_cancelada_nao_materializa_reserva_posterior(self) -> None:
        self._catalog([self.rows[0], self.rows[3]])
        first = self._generate()
        identity = npc_stubs.resolve_or_propose(self.repo, first["nome_completo"])["identidade_stub"]
        names.cancel(self.repo, "pessoa-1")
        self._generate("pessoa-2")
        before = self._bytes()
        with self.assertRaisesRegex(npc_stubs.NpcStubError, "reserva nominal mudou"):
            npc_stubs.ensure_stub(self.repo, identity, scene_id="fixture")
        self.assertEqual(before, self._bytes())

    def test_reservas_concorrentes_nao_repetem_componentes(self) -> None:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self._generate, ["concorrente-1", "concorrente-2"]))
        self.assertEqual(len({row["nome_completo"] for row in results}), 2)
        self.assertTrue(all(left["nome"] != right["nome"] for left, right in zip(results[0]["selecoes"], results[1]["selecoes"])))

    def test_retry_concorrente_retira_um_so_nome(self) -> None:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self._generate, ["mesma-chave", "mesma-chave"]))
        self.assertEqual(len({row["nome_completo"] for row in results}), 1)
        self.assertEqual(sum(row["reutilizado"] for row in results), 1)

    def test_csv_ausente_corrompido_ou_id_duplicado_falha_fechado(self) -> None:
        (self.repo / names.CATALOG).unlink()
        with self.assertRaisesRegex(names.NpcNameError, "não foi possível ler"):
            self._generate()
        self.assertFalse(names.check(self.repo)["ok"])
        (self.repo / names.CATALOG).write_text("nome,raca\nTomas,Humano\n", encoding="utf-8")
        with self.assertRaisesRegex(names.NpcNameError, "cabeçalho"):
            self._generate()
        self._catalog(self.rows)
        text = (self.repo / names.CATALOG).read_text(encoding="utf-8-sig").replace("FIX0001", "FIX0000")
        (self.repo / names.CATALOG).write_text(text, encoding="utf-8-sig")
        with self.assertRaisesRegex(names.NpcNameError, "ID duplicado"):
            self._generate()
        self.assertFalse((self.repo / names.RESERVATIONS).exists())

    def test_cli_publica_nome_cobertura_e_erro_controlado(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = continuity.main(["catalogo-nomes", "--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertTrue(yaml.safe_load(output.getvalue())["ok"])
        output = io.StringIO()
        with redirect_stdout(output):
            code = continuity.main(["--repo", str(self.repo), "gerar-nome", "--reserva", "cli-1", "--genero", "masculino", "--raca", "Humano", "--regiao", "The Vast", "--cultura", "Damarana"])
        self.assertEqual(code, 0)
        self.assertTrue(yaml.safe_load(output.getvalue())["ok"])
        output = io.StringIO()
        with redirect_stdout(output):
            code = continuity.main(["--repo", str(self.repo), "gerar-nome", "--reserva", "cli-2", "--genero", "masculino", "--raca", "Elfo", "--regiao", "The Vast"])
        self.assertEqual(code, 1)
        self.assertFalse(yaml.safe_load(output.getvalue())["ok"])

    def test_catalogo_real_e_compativel_sem_reservar_na_campanha(self) -> None:
        # Integração estrutural com o CSV fornecido; não congela quantidade/nome.
        rows = names.load_catalog(ROOT)
        self.assertGreater(len(rows), 0)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        shutil.copyfile(ROOT / names.CATALOG, self.repo / names.CATALOG)
        result = self._generate(culture=None)
        self.assertEqual({row["raca"] for row in result["selecoes"]}, {"Humano"})
        self.assertEqual(len({row["cultura_subraca"] for row in result["selecoes"]}), 1)
        self.assertEqual(npc_stubs.resolve_or_propose(self.repo, result["nome_completo"])["resolucao"], "stub_persistente_proposto")


if __name__ == "__main__":
    unittest.main()
