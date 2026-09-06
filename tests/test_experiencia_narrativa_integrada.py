"""Experiência narrativa completa em save temporário, com prosa avaliada."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "tests"))

import cronica
import consolidar
import contexto
import experiencia_integrada
import memoria_cena
import memoria_duravel
import personalidade_decisoria
import test_memoria_duravel_integracao as fixtures


PILOT_CAST = ["silva_elkwood", "nera_vell", "luath"]


def protected_digest(repo: Path) -> str:
    """Digest de fontes canônicas; artefatos de ferramentas ficam fora."""
    digest = hashlib.sha256()
    roots = ["campanha.yaml", "estado", "historico", "personagens", "sessoes", "runtime"]
    paths: list[Path] = []
    for relative in roots:
        path = repo / relative
        paths.extend([path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file()))
    for path in paths:
        digest.update(path.relative_to(repo).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class IntegratedNarrativeExperienceTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DurableMemoryIntegrationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo = self.fixture.repo
        self._install_controlled_cast()

    def _install_controlled_cast(self) -> None:
        names = {
            "silva_elkwood": "Silva Elkwood",
            "nera_vell": "Nera Vell",
            "luath": "Luath",
        }
        meters = {
            "silva_elkwood": {"vinculo": 8, "confianca": 7, "risco_percebido": 1},
            "nera_vell": {"vinculo": 8, "confianca": 8, "risco_percebido": 1},
            "luath": {"vinculo": 3, "confianca": 8, "risco_percebido": 2},
        }
        npc_index, relation_index = {}, {}
        for identity in PILOT_CAST:
            name = names[identity]
            npc_path = f"estado/npcs/{identity}.yaml"
            relation_path = f"estado/relacoes/{identity}.yaml"
            npc_index[identity] = {"nome": name, "arquivo": npc_path}
            relation_index[identity] = {"nome": name, "arquivo": relation_path}
            self.fixture.write(
                npc_path,
                {"id": identity, "schema_npc": 2,
                 "npc": {"nome": name, "medidores": meters[identity]}},
            )
            self.fixture.write(
                relation_path,
                {"id": identity, "schema_relacao": 2,
                 "relacao": {"nome": name, "vinculo": "Relação estabelecida no cenário isolado."}},
            )
        self.fixture.write("estado/npcs/index.yaml", {"npcs": npc_index, "quantidade": 3})
        self.fixture.write("estado/relacoes/index.yaml", {"relacoes": relation_index, "quantidade": 3})
        roles = yaml.safe_load(
            (ROOT / "tests/fixtures/personalidade-papeis.yaml").read_text(encoding="utf-8")
        )["npcs"]
        self.fixture.write(
            "cenario/texturas/index.yaml",
            {"npcs": {identity: roles[identity] for identity in PILOT_CAST}, "locais": {}},
        )

    def prepare(self, scene: str, participants: list[str] | None = None) -> dict:
        # Se a composição regredir para a consulta esquecível antiga, o teste falha.
        with patch.object(
            contexto,
            "command_npc",
            side_effect=AssertionError("cronica preparar não deve exigir contexto.py npc"),
        ):
            return cronica.prepare(
                self.repo,
                scene_id=scene,
                sidequest_signal=None,
                memory_participants=participants,
            )

    @staticmethod
    def transaction(
        identity: str,
        player: str,
        narration: str,
        summary: str,
        *,
        deltas: list[dict] | None = None,
        facts: list[dict] | None = None,
    ) -> dict:
        value = {
            "id": identity,
            "jogador": player,
            "narracao": narration,
            "resumo": summary,
            "modo": "interação",
            "deltas": deltas or [],
        }
        if facts is not None:
            value["memoria"] = {"versao": 1, "fatos": facts}
        return value

    @staticmethod
    def narrative_evidence(identity: str, system: str, turn: str, excerpt: str, reason: str) -> dict:
        return {
            "id": identity,
            "sistema": system,
            "turno": turn,
            "trecho": excerpt,
            "avaliador": "revisão humana anotada",
            "justificativa": reason,
        }

    def test_episodio_multicena_reune_memoria_personalidade_iniciativa_e_consequencia(self):
        live_before = protected_digest(ROOT)
        transcript_path = self.repo / "sessoes/003/transcricao.md"
        transcript_before = transcript_path.read_text(encoding="utf-8")
        ids_before = sorted(yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text())["npcs"])
        turns: list[dict] = []

        opening = self.prepare("reencontro-na-estrada", ["silva_elkwood"])
        silva = opening[memoria_cena.KEY]["itens"]["silva_elkwood"]
        profile = silva[personalidade_decisoria.KEY]
        initiative = silva["dialogo_relacional"]["iniciativa_social"]
        choice = personalidade_decisoria.evaluate_options(
            profile,
            [
                {
                    "id": "cuidado_concreto",
                    "conduta": "Receber Ren e resolver uma necessidade imediata.",
                    "favorece": {"cuidado_concreto": "Transforma afeto em ajuda possível agora."},
                    "contraria": {},
                    "viabilidade": {key: True for key in personalidade_decisoria.GATES},
                },
                {
                    "id": "sermao_generico",
                    "conduta": "Usar o reencontro para repreender Ren sem risco novo.",
                    "favorece": {},
                    "contraria": {"sem_tutela_moral": "Converte proteção em tutela sem gatilho."},
                    "viabilidade": {key: True for key in personalidade_decisoria.GATES},
                },
            ],
        )
        self.assertEqual(choice["preferiveis"], ["cuidado_concreto"])
        self.assertTrue(initiative["pode_iniciar"])
        initiative_excerpt = "Silva se aproxima de Ren antes que ele precise chamá-la."
        personality_excerpt = "Ela troca qualquer sermão por cuidado concreto e aponta a carroça livre."
        promise_excerpt = "Silva promete manter a carroça reservada para Ren até o reencontro."
        narration = f"{initiative_excerpt} {personality_excerpt} {promise_excerpt}"
        promise_summary = "Silva manterá uma carroça reservada para Ren."
        promise = {
            "id": "reserva_carroca",
            "tipo": "promessa",
            "participantes": ["ren", "silva_elkwood"],
            "evidencia": {"campo": "narracao", "trecho": promise_excerpt},
            "operacao": "registrar",
            "compromisso": {"tipo": "compromisso", "resumo": promise_summary},
        }
        first = self.transaction(
            "experiencia-promessa",
            "Ren pergunta se pode contar com uma carroça mais tarde.",
            narration,
            "Silva toma a iniciativa e reserva uma carroça.",
            facts=[promise],
        )
        cronica.conclude(self.repo, opening["ticket"], first)
        turns.append({"id": "turno-1", "marcos": ["reencontro"], "jogador": first["jogador"],
                      "narracao": narration, "resumo": first["resumo"]})

        continuation = self.prepare("reencontro-na-estrada")
        memory_bundle = continuation[memoria_cena.KEY]
        self.assertIn("silva_elkwood", memory_bundle["itens"])
        self.assertIn("@compromissos", memory_bundle["itens"])
        self.assertIn(promise_summary, memoria_cena.canonical(memory_bundle))
        memory_excerpt = "A carroça continua reservada, como prometi, diz Silva sem pedir que Ren reconte o acordo."
        second = self.transaction(
            "experiencia-continuidade",
            "Ren confirma apenas o horário em que pretende voltar.",
            memory_excerpt,
            "Silva mantém o acordo sem exigir reexposição.",
        )
        cronica.conclude(self.repo, continuation["ticket"], second)
        turns.append({"id": "turno-2", "marcos": ["continuidade_sem_recontar"],
                      "jogador": second["jogador"], "narracao": memory_excerpt,
                      "resumo": second["resumo"]})

        departure = self.prepare("caminho-do-porto", [])
        travel_narration = (
            "Ren deixa a cerca por decisão própria; o relógio avança enquanto o caminho o leva até o porto."
        )
        third = self.transaction(
            "experiencia-passagem",
            "Ren decide seguir a pé até o porto.",
            travel_narration,
            "Ren chega ao porto depois da passagem de tempo.",
            deltas=[
                {"alvo": "tempo", "op": "instante",
                 "valor": {"data": "7 Eleasis, 1372 DR", "hora": "09:10"}},
                {"alvo": "estado", "op": "set", "caminho": "localizacao.area", "valor": "porto"},
                {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "cais"},
            ],
        )
        cronica.conclude(self.repo, departure["ticket"], third)
        turns.append({"id": "turno-3", "marcos": ["passagem_tempo", "mudanca_cena"],
                      "jogador": third["jogador"], "narracao": travel_narration,
                      "resumo": third["resumo"]})

        meeting = self.prepare("conversa-no-cais", ["nera_vell"])
        nera = meeting[memoria_cena.KEY]["itens"]["nera_vell"]
        self.assertEqual(nera[personalidade_decisoria.KEY]["estavel"]["metodos_preferidos"]["id"],
                         "franqueza_pessoal")
        self.assertTrue(nera["dialogo_relacional"]["iniciativa_social"]["pode_iniciar"])
        nera_excerpt = (
            "Nera puxa conversa por vontade própria e fala do que quer, sem transformar o encontro em instrução moral."
        )
        fourth = self.transaction(
            "experiencia-nera",
            "Ren para no cais e escuta Nera.",
            nera_excerpt,
            "Nera age de modo coerente com seu vínculo e perfil.",
        )
        cronica.conclude(self.repo, meeting["ticket"], fourth)
        turns.append({"id": "turno-4", "marcos": [], "jogador": fourth["jogador"],
                      "narracao": nera_excerpt, "resumo": fourth["resumo"]})

        consolidar.consolidate(self.repo, "cena")
        cold_script = (
            "import json,sys; from pathlib import Path; import retomada_cronica; "
            "print(json.dumps(retomada_cronica.current_snapshot(Path(sys.argv[1])),ensure_ascii=False))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0,sys.argv.pop(1)); " + cold_script,
             str(TOOLS), str(self.repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        cold = json.loads(completed.stdout)
        self.assertFalse(cold["transcricao_lida"])
        self.assertIn("nera_vell", cold[memoria_cena.KEY]["itens"])
        self.assertNotIn("transcricao.md", cold["fontes_lidas"])

        consequence_scene = self.prepare("retorno-a-carroca", ["silva_elkwood"])
        self.assertIn(promise_summary, memoria_cena.canonical(consequence_scene[memoria_cena.KEY]))
        fulfillment_excerpt = "Silva entrega as rédeas da carroça que guardou e declara cumprida a promessa."
        consequence_excerpt = "Como consequência do acordo lembrado, Ren agora tem transporte disponível no cais."
        final_narration = f"{fulfillment_excerpt} {consequence_excerpt}"
        commitment_id = memoria_duravel.event_id("experiencia-promessa", "reserva_carroca", 3)
        close = {
            "id": "reserva_cumprida",
            "tipo": "promessa",
            "participantes": ["ren", "silva_elkwood"],
            "evidencia": {"campo": "narracao", "trecho": fulfillment_excerpt},
            "operacao": "cumprir",
            "compromisso_id": commitment_id,
            "anterior": {
                "tipo": "compromisso",
                "resumo": promise_summary,
                "envolvidos": ["ren", "silva_elkwood"],
            },
        }
        fifth = self.transaction(
            "experiencia-consequencia",
            "Ren retorna ao ponto combinado e aceita as rédeas.",
            final_narration,
            "A promessa lembrada produz transporte e é encerrada.",
            deltas=[
                {"alvo": "consequencia", "op": "registrar",
                 "valor": {"titulo": "Carroça reservada",
                           "descricao": "A promessa de Silva garantiu transporte a Ren no cais."}},
            ],
            facts=[close],
        )
        cronica.conclude(self.repo, consequence_scene["ticket"], fifth)
        turns.append({"id": "turno-5", "marcos": ["retomada_fria", "consequencia"],
                      "jogador": fifth["jogador"], "narracao": final_narration,
                      "resumo": fifth["resumo"]})
        consolidar.consolidate(self.repo, "cena")

        ids_after = sorted(yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text())["npcs"])
        transcript_after = transcript_path.read_text(encoding="utf-8")
        self.assertTrue(transcript_after.startswith(transcript_before))
        for turn in turns:
            self.assertIn(turn["narracao"], transcript_after)
        self.assertIn("Carroça reservada", (self.repo / "sessoes/003/consequencias.md").read_text())
        history = (self.repo / "historico/relacoes/silva_elkwood.yaml").read_text(encoding="utf-8")
        self.assertIn("registrar", history)
        self.assertIn("cumprir", history)
        self.assertEqual(live_before, protected_digest(ROOT))

        episode = {
            "schema_episodio_integrado": 1,
            "cenario_id": "reencontro-promessa-cais",
            "elenco": ["silva_elkwood", "nera_vell"],
            "turnos": turns,
            "evidencias_narrativas": [
                self.narrative_evidence(
                    "memoria-acordo", "memoria", "turno-2", memory_excerpt,
                    "A fala retoma o conteúdo específico da promessa sem pedir nova exposição ao jogador.",
                ),
                self.narrative_evidence(
                    "personalidade-escolha", "personalidade", "turno-1", personality_excerpt,
                    "A conduta narrada corresponde à alternativa favorecida pelo perfil decisório projetado.",
                ),
                self.narrative_evidence(
                    "iniciativa-contato", "iniciativa", "turno-1", initiative_excerpt,
                    "A NPC presente abre o contato dentro da permissão social e sem decidir qualquer ação de Ren.",
                ),
                self.narrative_evidence(
                    "consequencia-promessa", "consequencia", "turno-5", consequence_excerpt,
                    "A narração explicita um resultado causado pelo compromisso lembrado e persistido pelo writer.",
                ),
            ],
            "retomada_fria": {
                "processo_novo": True,
                "contexto_anterior_fornecido": False,
                "transcricao_lida": False,
            },
            "consultas_manuais": [],
            "preservacao": {
                "ids_antes": ids_before,
                "ids_depois": ids_after,
                "historico_append_only": transcript_after.startswith(transcript_before),
                "save_original_inalterado": live_before == protected_digest(ROOT),
            },
        }
        report = experiencia_integrada.evaluate_episode(
            episode,
            experiencia_integrada.load_contract(ROOT),
        )
        self.assertTrue(report["ok"])
        self.assertEqual(report["sistemas_com_evidencia_narrativa"],
                         ["consequencia", "iniciativa", "memoria", "personalidade"])
        self.assertEqual(report["consultas_manuais"], 0)

    def test_campos_estruturados_nao_substituem_evidencia_na_narracao(self):
        contract = experiencia_integrada.load_contract(ROOT)
        turns = [
            {"id": f"turno-{number}",
             "marcos": (["reencontro", "continuidade_sem_recontar"] if number == 1 else
                        ["passagem_tempo", "mudanca_cena"] if number == 2 else
                        ["retomada_fria"] if number == 3 else
                        ["consequencia"] if number == 4 else []),
             "jogador": "Ren toma uma decisão explícita dentro do cenário controlado.",
             "narracao": "A cena progride com uma narração longa o bastante para a avaliação integrada.",
             "resumo": "A cena progride no cenário."}
            for number in range(1, 6)
        ]
        evidence = [
            self.narrative_evidence(f"ev-{system}", system, "turno-1", "só existe no YAML",
                                    "O teste injeta metadado sem correspondência literal na prosa produzida.")
            for system in sorted(experiencia_integrada.REQUIRED_SYSTEMS)
        ]
        episode = {
            "schema_episodio_integrado": 1,
            "cenario_id": "metadado-nao-e-narracao",
            "elenco": ["silva_elkwood"],
            "turnos": turns,
            "evidencias_narrativas": evidence,
            "retomada_fria": {"processo_novo": True, "contexto_anterior_fornecido": False,
                               "transcricao_lida": False},
            "consultas_manuais": [],
            "preservacao": {"ids_antes": ["silva_elkwood"], "ids_depois": ["silva_elkwood"],
                            "historico_append_only": True, "save_original_inalterado": True},
        }
        with self.assertRaisesRegex(
            experiencia_integrada.IntegratedExperienceError,
            "não aparece literalmente na narração produzida",
        ):
            experiencia_integrada.evaluate_episode(episode, contract)

    def test_contrato_instalado_valida_piloto_sem_escrever_no_save(self):
        before = protected_digest(ROOT)
        report = experiencia_integrada.check(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual([item["id"] for item in report["adocao_controlada"]["elenco"]], PILOT_CAST)
        self.assertFalse(report["adocao_controlada"]["save_alterado"])
        self.assertEqual(before, protected_digest(ROOT))


if __name__ == "__main__":
    unittest.main()
