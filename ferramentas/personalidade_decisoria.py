"""Personalidade como critério de escolha, não como fala pronta ou plano executado.

Adaptador puro dos papéis já existentes. Recortes só permanecem válidos enquanto
sua frase de origem inteira coincidir; mudança exige recuração, não inferência.
Humor, leitura recente e medidores ficam no estado efetivo, fora do perfil estável.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

VERSION = 1
KEY = "personalidade_decisoria"
AXES = ("valores", "desejos", "receios", "metodos_preferidos", "limites", "relacionamento")
MAX_PROFILE_BYTES = 2048
GATES = ("conhecimento", "capacidade", "recursos", "presenca_ou_canal", "autoridade")

# (ID do critério, campo/índice no papel, frase integral esperada, recorte literal).
# Isto é uma seleção interpretativa, não um segundo registro de fatos do NPC.
PILOTS = {
    "silva_elkwood": ("guardia_pragmatica", {
        "valores": ("verdade_verificavel", "prioriza", 1,
                    "verdade verificável antes de conclusões ou escalada",
                    "verdade verificável antes de conclusões ou escalada"),
        "desejos": ("rotina_segura", "prioriza", 0,
                    "vidas, rotina segura e exposição dos vulneráveis quando a cena toca esses riscos",
                    "rotina segura"),
        "metodos_preferidos": ("cuidado_concreto", "prioriza", 2,
                    "cuidado concreto que possa ser feito agora",
                    "cuidado concreto que possa ser feito agora"),
        "limites": ("sem_tutela_moral", "limite_de_autoridade", None,
                    "orienta segurança e cuidado a partir do que Silva recebeu ou observou; proteção não a torna tutora moral permanente de Ren",
                    "proteção não a torna tutora moral permanente de Ren"),
        "relacionamento": ("acolher_antes_de_corrigir", "forma_de_responder", 0,
                    "acolher, informar ou agir primeiro; corrigir Ren só quando houver risco ou limite concreto em pauta",
                    "acolher, informar ou agir primeiro"),
    }),
    "nera_vell": ("espelho_afetivo", {
        "valores": ("reciprocidade", "prioriza", 1,
                    "verdade e reciprocidade dentro da relação entre os dois",
                    "verdade e reciprocidade dentro da relação entre os dois"),
        "desejos": ("vida_comum", "prioriza", 2,
                    "a possibilidade de vida comum, humor, desejo e futuro para além da crise",
                    "vida comum, humor, desejo e futuro para além da crise"),
        "metodos_preferidos": ("franqueza_pessoal", "forma_de_responder", 1,
                    "quando discordar, dizer o que sente, quer ou não aceita antes de tentar ensinar alguma coisa",
                    "quando discordar, dizer o que sente, quer ou não aceita"),
        "limites": ("sem_controle_de_ren", "limite_de_autoridade", None,
                    "fala a partir do que viveu, escolheu e sabe; intimidade não lhe concede segredos ou autoridade sobre decisões de Ren",
                    "intimidade não lhe concede segredos ou autoridade sobre decisões de Ren"),
        "relacionamento": ("envolvimento_pessoal", "forma_de_responder", 0,
                    "responder primeiro como pessoa emocionalmente envolvida, não como consciência moral de Ren",
                    "responder primeiro como pessoa emocionalmente envolvida"),
    }),
    "luath": ("operacional_civico", {
        "valores": ("prova_utilizavel", "prioriza", 0,
                    "prova utilizável, preparação e risco público quando existe operação ou assunto da Guarda",
                    "prova utilizável, preparação e risco público"),
        "metodos_preferidos": ("perguntas_decisivas", "forma_de_responder", 1,
                    "em operação, fazer apenas as perguntas decisivas e distinguir vigilância, investigação e captura",
                    "fazer apenas as perguntas decisivas e distinguir vigilância, investigação e captura"),
        "limites": ("sem_preconceito", "evita", 0,
                    "suspeita indiscriminada contra estrangeiros ou grupos inteiros",
                    "suspeita indiscriminada contra estrangeiros ou grupos inteiros"),
        "relacionamento": ("colega_sem_debriefing", "forma_de_responder", 0,
                    "fora de assunto operacional, conversar como colega conhecido sem transformar tudo em debriefing",
                    "conversar como colega conhecido sem transformar tudo em debriefing"),
    }),
}


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def project(person: str, role: Any) -> dict | None:
    """Retorna somente critérios ancorados; receio não é inferido de risco atual."""
    if person not in PILOTS:
        return None
    expected_role, selections = PILOTS[person]
    role = role if isinstance(role, dict) else {}
    stable, gaps = {}, {}
    for axis in AXES:
        selection = selections.get(axis)
        stable[axis] = None
        if selection is None:
            gaps[axis] = "nao_estabelecido_nas_fontes_selecionadas"
            continue
        criterion, field, index, expected, excerpt = selection
        value = role.get(field)
        if index is not None:
            value = value[index] if isinstance(value, list) and len(value) > index else None
        if role.get("papel") != expected_role or _text(value) != expected:
            gaps[axis] = "fonte_ausente_ou_alterada_requer_recuracao"
            continue
        if excerpt not in expected:
            raise ValueError("recorte de personalidade não pertence à frase de origem")
        # Preserva também condicionantes (em operação, fora dela, risco concreto).
        # Palavras isoladas não podem transformar preferência contextual em regra geral.
        stable[axis] = {"id": criterion, "texto": expected,
                        "origem": "/" + field + (f"/{index}" if index is not None else "")}
        if axis == "limites" and field == "evita":
            stable[axis]["sentido"] = "evitar"
    return {"versao": VERSION, "natureza": "orientacao_interpretativa_nao_autorizacao",
            "origem": "/textura_narrativa/papel_conversacional", "estavel": stable,
            "lacunas": gaps, "situacao_em": "/medidores/dados",
            "disciplina": "Humor, tom, leitura recente e risco não redefinem valores. Preferência não é ação nem sucesso."}


def enrich(data: dict) -> dict:
    """Enriquece a projeção já sobreposta, sem I/O ou correspondência aproximada."""
    out = deepcopy(data)
    result = out.get("resultado")
    if not isinstance(result, dict) or out.get("consulta", {}).get("comando") != "npc":
        return out
    ids = {v["id"] for key in ("medidores", "relacao", "textura_narrativa")
           if isinstance(v := result.get(key), dict) and isinstance(v.get("id"), str)}
    if len(ids) != 1:
        if ids & PILOTS.keys():
            raise ValueError("fontes de personalidade apontam para NPCs distintos")
        return out
    person = next(iter(ids))
    texture = result.get("textura_narrativa") or {}
    profile = project(person, texture.get("papel_conversacional") if isinstance(texture, dict) else None)
    if profile is not None:
        result[KEY] = profile
    return out


def evaluate_options(profile: dict, options: list[dict]) -> dict:
    """Compara afinidades DECLARADAS, sem entender prosa ou validar o mundo.

    Ferramenta pura e opcional para deliberação/testes; não acrescenta chamada de
    IA nem é um planner. Os gates são declarações do chamador. A execução continua
    exigindo os validadores, tickets e writers reais. Não há escore psicológico:
    retorna a fronteira de alternativas não dominadas, conservando empates.
    """
    if (not isinstance(profile, dict) or type(profile.get("versao")) is not int
            or profile["versao"] != VERSION or not isinstance(profile.get("estavel"), dict)
            or set(profile["estavel"]) != set(AXES)):
        raise ValueError("perfil decisório inválido")
    traits, limits = {}, set()
    for axis, value in profile["estavel"].items():
        if value is None:
            continue
        if (not isinstance(value, dict) or not _text(value.get("id")) or not _text(value.get("texto"))
                or value["id"] in traits):
            raise ValueError("critério inválido ou duplicado")
        traits[value["id"]] = value
        if axis == "limites":
            limits.add(value["id"])
    if not isinstance(options, list) or not 1 <= len(options) <= 6:
        raise ValueError("deliberação exige uma a seis alternativas")
    rows, seen = [], set()
    for option in options:
        if (not isinstance(option, dict) or set(option) != {"id", "conduta", "favorece", "contraria", "viabilidade"}
                or not _text(option.get("id")) or len(option["id"]) > 80
                or not _text(option.get("conduta")) or len(option["conduta"]) > 500
                or option["id"] in seen):
            raise ValueError("alternativa inválida ou duplicada")
        seen.add(option["id"])
        for name in ("favorece", "contraria"):
            links = option[name]
            if (not isinstance(links, dict) or len(links) > 12
                    or any(not isinstance(k, str) or not _text(v) or len(v) > 250 for k, v in links.items())):
                raise ValueError("afinidade exige critério e justificativa explícita")
        if set(option["favorece"]) & set(option["contraria"]):
            raise ValueError("um critério não pode ser favorecido e contrariado simultaneamente")
        gates = option["viabilidade"]
        if (not isinstance(gates, dict) or set(gates) != set(GATES)
                or any(v is not None and type(v) is not bool for v in gates.values())):
            raise ValueError("viabilidade exige todos os gates booleanos ou desconhecidos")
        positive = sorted(traits.keys() & option["favorece"].keys())
        negative = sorted(traits.keys() & option["contraria"].keys())
        blocked = sorted(k for k, v in gates.items() if v is False)
        unknown = sorted(k for k, v in gates.items() if v is None)
        status = ("inviavel_declarada" if blocked else "aguarda_base" if unknown
                  else "contraria_limite" if limits.intersection(negative)
                  else "contraria_sem_apoio" if negative and not positive
                  else "sem_fundamento_no_perfil" if not positive else "avaliavel")
        justification = [{"criterio": key, "texto_fonte": traits[key]["texto"],
                          "efeito": name, "justificativa_declarada": option[name][key]}
                         for name, keys in (("favorece", positive), ("contraria", negative)) for key in keys]
        rows.append({"id": option["id"], "conduta": option["conduta"], "status": status,
                     "favorece": positive, "contraria": negative, "bloqueios": blocked,
                     "lacunas_viabilidade": unknown, "justificativas": justification,
                     "criterios_nao_presentes": sorted((option["favorece"].keys() | option["contraria"].keys()) - traits.keys())})
    eligible = [row for row in rows if row["status"] == "avaliavel"]

    def dominates(a: dict, b: dict) -> bool:
        ap, an, bp, bn = set(a["favorece"]), set(a["contraria"]), set(b["favorece"]), set(b["contraria"])
        return ap >= bp and an <= bn and (ap != bp or an != bn)

    preferred = sorted(row["id"] for row in eligible if not any(dominates(other, row) for other in eligible))
    return {"alternativas": sorted(rows, key=lambda row: row["id"]), "preferiveis": preferred,
            "lacunas_perfil": sorted(axis for axis, value in profile["estavel"].items() if value is None),
            "natureza": "afinidades_e_viabilidade_declaradas_nao_verificadas",
            "executa_acao": False, "sucesso_garantido": False,
            "disciplina": "O narrador pondera custos e escolhe; os gates canônicos continuam obrigatórios."}
