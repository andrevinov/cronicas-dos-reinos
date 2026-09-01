from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml


MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "adversarios.py"
SPEC = importlib.util.spec_from_file_location("adversarios", MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

REPO = Path(__file__).parents[1]


class AdversariosRepositoryTest(unittest.TestCase):
    def test_registro_real_valida_as_dez_fichas_populadas(self):
        result = mod.validate_repo(REPO)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade"], len(mod.load_index(REPO)["adversarios"]))
        self.assertGreaterEqual(result["quantidade"], 10)

    def test_contrato_congela_ruleset_orcamento_e_invariantes(self):
        contract = mod.load_contract(REPO)
        self.assertEqual(contract["ruleset_obrigatorio"], "dnd_5_5e")
        self.assertEqual(contract["orcamento"]["consulta_dirigida_max_bytes"], 8192)
        self.assertTrue(all(contract["invariantes"].values()))


class JuppongatanaAdversaryPopulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = mod.load_contract(REPO)
        cls.index = mod.load_index(REPO, cls.contract)
        cls.roster = yaml.safe_load(
            (REPO / "narrador/juppongatana/index.yaml").read_text(encoding="utf-8")
        )["membros"]

    def test_registro_mecanico_cobre_todo_o_elenco_canonico(self):
        self.assertLessEqual(set(self.roster), set(self.index["adversarios"]))
        for adversary_id, roster_meta in self.roster.items():
            self.assertEqual(
                self.index["adversarios"][adversary_id]["nome"],
                roster_meta["nome"],
            )

    def test_escala_mecanica_acompanha_os_tres_circulos(self):
        expected_scale = {
            "externo": "elite",
            "meio": "chefe",
            "interno": "lendario",
        }
        for adversary_id, roster_meta in self.roster.items():
            sheet = mod.load_adversary(REPO, adversary_id)["resultado"]
            self.assertEqual(
                sheet["escala"]["categoria"],
                expected_scale[roster_meta["circulo"]],
                adversary_id,
            )

    def test_todos_possuem_repertorio_executavel_e_especialidade_dirigida(self):
        for adversary_id in self.roster:
            base = mod.load_adversary(REPO, adversary_id)
            sheet = base["resultado"]
            repertoire = sum(
                len(sheet[group])
                for group in ("acoes", "acoes_bonus", "reacoes", "acoes_lendarias")
            )
            self.assertGreaterEqual(repertoire, 6, adversary_id)
            self.assertTrue(sheet["acoes_bonus"], adversary_id)
            self.assertTrue(sheet["reacoes"], adversary_id)
            self.assertIn(
                "narrador/juppongatana/membros.md",
                sheet["proveniencia"]["referencia"],
                adversary_id,
            )
            for specialty_id in sheet["especialidades"]["ids"]:
                detail = mod.load_specialty(REPO, adversary_id, specialty_id)
                self.assertTrue(detail["resultado"]["procedimentos"], adversary_id)

    def test_consultas_de_todo_elenco_respeitam_l2_sem_leitura_cruzada(self):
        ceiling = self.contract["orcamento"]["consulta_dirigida_max_bytes"]
        for adversary_id in self.roster:
            result = mod.load_adversary(REPO, adversary_id)
            self.assertLessEqual(len(mod._dump(result).encode("utf-8")), ceiling)
            self.assertEqual(len(result["fontes_lidas"]), 4)
            self.assertEqual(
                result["fontes_lidas"][-1],
                self.index["adversarios"][adversary_id]["arquivo"],
            )


class AdversariosContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/adversarios/fichas").mkdir(parents=True)
        (self.repo / "narrador/adversarios/especialidades").mkdir(parents=True)
        shutil.copy(
            REPO / mod.CONTRACT_PATH,
            self.repo / mod.CONTRACT_PATH,
        )
        self._write_yaml(
            "campanha.yaml",
            {"sistema": {"ruleset": {"atual": "dnd_5_5e"}}},
        )
        self.meta = {
            "nome": "Mestra da Ponte",
            "tipo": "npc",
            "funcao": "hibrido",
            "arquivo": "narrador/adversarios/fichas/mestra_ponte.yaml",
            "especialidades_arquivo": "narrador/adversarios/especialidades/mestra_ponte.yaml",
        }
        self.base = {
            "schema_adversario": 1,
            "natureza": "reservado",
            "id": "mestra_ponte",
            "nome": "Mestra da Ponte",
            "tipo": "npc",
            "funcao": "hibrido",
            "ruleset": "dnd_5_5e",
            "proveniencia": {
                "origem": "original_campanha",
                "referencia": "fixture mecânica isolada",
                "decisao": None,
                "adaptacao": None,
            },
            "perfil": {
                "tamanho": "Médio",
                "tipo_criatura": "Humanoide",
                "alinhamento": "Neutro",
            },
            "escala": {"categoria": "elite", "referencia": "especialista individual"},
            "defesas": {"ca": 17, "pv": 68, "dados_vida": "8d8+32"},
            "movimento": {"terrestre": 30},
            "atributos": {"for": 14, "des": 18, "con": 18, "int": 13, "sab": 16, "car": 12},
            "bonus_proficiencia": 3,
            "iniciativa": 7,
            "salvaguardas": {"des": 7, "sab": 6},
            "pericias": {"acrobacia": 7, "percepcao": 6},
            "vulnerabilidades": [],
            "resistencias": [],
            "imunidades_dano": [],
            "imunidades_condicao": [],
            "sentidos": {"percepcao_passiva": 16, "especiais": []},
            "idiomas": ["Comum"],
            "recursos": [
                {
                    "id": "foco_tatico",
                    "nome": "Foco tático",
                    "maximo": 3,
                    "recuperacao": "descanso_curto",
                    "condicao_recuperacao": None,
                }
            ],
            "tracos": [
                {
                    "id": "base_firme",
                    "nome": "Base firme",
                    "regra": "Tem vantagem para resistir a empurrões enquanto estiver sobre pedra.",
                    "contrajogo": ["Retirá-la do piso de pedra antes de tentar deslocá-la."],
                }
            ],
            "acoes": [
                {
                    "id": "golpe_longo",
                    "nome": "Golpe longo",
                    "ativacao": "acao",
                    "gatilho": None,
                    "alcance": "corpo a corpo, 10 pés",
                    "alvos": "uma criatura",
                    "resolucao": {"tipo": "ataque", "bonus": 7, "defesa": "ca", "modo": "corpo_a_corpo"},
                    "efeitos": [
                        {
                            "quando": "acerto",
                            "regra": "O alvo sofre o dano da arma.",
                            "dano": {"formula": "1d10+4", "tipo": "cortante"},
                        }
                    ],
                    "custo": None,
                    "limite": {"tipo": "ilimitado", "valor": None},
                    "contrajogo": ["Sair do alcance da arma ou usar cobertura total."],
                }
            ],
            "acoes_bonus": [
                {
                    "id": "passo_dominante",
                    "nome": "Passo dominante",
                    "ativacao": "acao_bonus",
                    "gatilho": None,
                    "alcance": "pessoal",
                    "alvos": "a própria adversária",
                    "resolucao": {"tipo": "automatica", "condicao": "possuir ao menos 1 foco tático"},
                    "efeitos": [
                        {
                            "quando": "uso",
                            "regra": "Move até 15 pés sem provocar ataque de oportunidade.",
                            "dano": None,
                        }
                    ],
                    "custo": {"recurso": "foco_tatico", "quantidade": 1},
                    "limite": {"tipo": "ilimitado", "valor": None},
                    "contrajogo": ["Bloquear fisicamente os espaços de destino."],
                }
            ],
            "reacoes": [
                {
                    "id": "aparar",
                    "nome": "Aparar",
                    "ativacao": "reacao",
                    "gatilho": "ser atingida por ataque corpo a corpo que possa ver",
                    "alcance": "pessoal",
                    "alvos": "o ataque desencadeador",
                    "resolucao": {"tipo": "automatica", "condicao": "o ataque desencadeador causa dano"},
                    "efeitos": [
                        {
                            "quando": "reação",
                            "regra": "Reduz o dano em 1d8+4.",
                            "dano": None,
                        }
                    ],
                    "custo": None,
                    "limite": {"tipo": "ilimitado", "valor": None},
                    "contrajogo": ["Consumir a reação antes do ataque mais importante."],
                }
            ],
            "acoes_lendarias": [],
            "taticas": {
                "abertura": ["Ocupa a passagem estreita antes de atacar."],
                "prioridades": ["Impede travessia antes de perseguir dano."],
                "adaptacoes": ["Muda para terreno aberto se for cercada."],
                "uso_terreno": ["Usa o alcance da arma sobre a ponte."],
                "evita": ["Não abandona a passagem por provocação verbal."],
            },
            "retirada": {
                "postura": "recua",
                "gatilhos": ["A ponte deixa de ter valor estratégico."],
                "metodo": "Recua pela margem preparada sem atravessar inimigos.",
                "custo_ou_risco": "Abandona a carga que estava protegendo.",
                "sinais_observaveis": ["Olha repetidamente para a margem e encurta a guarda."],
            },
            "especialidades": {
                "arquivo": "narrador/adversarios/especialidades/mestra_ponte.yaml",
                "ids": ["controle_de_passagem"],
            },
        }
        self.specialties = {
            "schema_especialidades_adversario": 1,
            "natureza": "reservado",
            "adversario_id": "mestra_ponte",
            "especialidades": {
                "controle_de_passagem": {
                    "nome": "Controle de passagem",
                    "dominio": "vigilância e bloqueio de rotas",
                    "objetivo": "Detectar travessias e manter o ponto sem depender de combate.",
                    "procedimentos": [
                        {
                            "id": "ler_aproximacao",
                            "gatilho": "uma criatura tenta cruzar sem chamar atenção",
                            "resolucao": {
                                "tipo": "teste_oposto",
                                "atributo_ou_pericia": "Percepção",
                                "bonus": 6,
                                "oposicao": "Furtividade da criatura",
                            },
                            "resultado_sucesso": "A aproximação é percebida antes da travessia.",
                            "resultado_falha": "A criatura alcança a passagem sem ser percebida.",
                            "custo": None,
                            "limite": {"tipo": "ilimitado", "valor": None},
                        }
                    ],
                    "contrajogo": ["Criar distração fora da ponte ou escolher outra rota."],
                }
            },
        }
        self._install()

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, relative: str, data: object) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _install(self, *, second_unavailable: bool = False) -> None:
        entries = {"mestra_ponte": self.meta}
        if second_unavailable:
            entries["outro_adversario"] = {
                "nome": "Outro Adversário",
                "tipo": "npc",
                "funcao": "combatente",
                "arquivo": "narrador/adversarios/fichas/outro_adversario.yaml",
                "especialidades_arquivo": "narrador/adversarios/especialidades/outro_adversario.yaml",
            }
        self._write_yaml(
            mod.INDEX_PATH.as_posix(),
            {
                "schema_indice_adversarios": 1,
                "natureza": "reservado",
                "contrato": mod.CONTRACT_PATH.as_posix(),
                "adversarios": entries,
            },
        )
        self._write_yaml(self.meta["arquivo"], self.base)
        self._write_yaml(self.meta["especialidades_arquivo"], self.specialties)

    def test_ficha_completa_e_especialidade_dirigida_passam(self):
        result = mod.validate_repo(self.repo)
        self.assertTrue(result["ok"], result["erros"])
        base = mod.load_adversary(self.repo, "Mestra da Ponte")
        detail = mod.load_specialty(self.repo, "mestra_ponte", "controle_de_passagem")
        self.assertLessEqual(len(mod._dump(base).encode("utf-8")), 8192)
        self.assertLessEqual(len(mod._dump(detail).encode("utf-8")), 8192)

    def test_consulta_nao_abre_outro_adversario(self):
        self._install(second_unavailable=True)
        (self.repo / self.meta["especialidades_arquivo"]).unlink()
        result = mod.load_adversary(self.repo, "mestra_ponte")
        self.assertNotIn("outro_adversario.yaml", " ".join(result["fontes_lidas"]))
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/adversarios/contrato.yaml",
                "narrador/adversarios/index.yaml",
                "campanha.yaml",
                "narrador/adversarios/fichas/mestra_ponte.yaml",
            ],
        )
        with self.assertRaises(mod.AdversaryValidationError):
            mod.load_specialty(self.repo, "mestra_ponte", "controle_de_passagem")

    def test_ficha_sem_acao_falha(self):
        self.base["acoes"] = []
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("ao menos uma ação", result["erros"][0])

    def test_custo_precisa_referenciar_recurso_declarado(self):
        self.base["acoes_bonus"][0]["custo"]["recurso"] = "recurso_inventado"
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("recurso não declarado", result["erros"][0])

    def test_salvaguarda_sem_cd_falha(self):
        self.base["acoes"][0]["resolucao"] = {"tipo": "salvaguarda", "atributo": "des"}
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("atributo e cd", result["erros"][0])

    def test_formula_de_dano_invalida_falha(self):
        self.base["acoes"][0]["efeitos"][0]["dano"]["formula"] = "mais ou menos muito"
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("dano.formula inválida", result["erros"][0])

    def test_escala_lendaria_sem_acao_lendaria_falha(self):
        self.base["escala"]["categoria"] = "lendario"
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("escala lendária exige", result["erros"][0])

    def test_reacao_sem_gatilho_falha(self):
        self.base["reacoes"][0]["gatilho"] = None
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("reação exige gatilho", result["erros"][0])

    def test_especialidade_sem_procedimento_falha(self):
        self.specialties["especialidades"]["controle_de_passagem"]["procedimentos"] = []
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("procedimentos não pode ser vazio", result["erros"][0])

    def test_campo_de_ajuste_pos_rolagem_e_rejeitado(self):
        self.base["ajuste_pos_rolagem"] = True
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("estrutura inesperada", result["erros"][0])

    def test_ruleset_divergente_falha(self):
        self.base["ruleset"] = "dnd_5e_2014"
        self._install()
        result = mod.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("diverge do ruleset ativo", result["erros"][0])


if __name__ == "__main__":
    unittest.main()
