from __future__ import annotations

from pathlib import Path
import textwrap
import yaml

ROOT = Path('.')

migration = {
    'schema_migracao_ren_5_5e': 1,
    'personagem': 'Ren Kagehira',
    'base_canonica': 'personagens/jogador/ficha.yaml',
    'ruleset_origem': 'dnd_5e_2014',
    'ruleset_alvo': 'dnd_5_5e',
    'status': 'pronto_para_ativacao',
    'ativacao': {
        'gate': 'task_8_auditoria_final',
        'aplica_antes_do_gate': False,
        'modo': 'promocao_prospectiva',
    },
    'preservacao': {
        'sessoes_concluidas': 'imutaveis',
        'atributos_canonizados': 'preservar_sem_rebuild',
        'pontos_de_vida': 'preservar_estado_efetivo_no_momento_da_ativacao',
        'ki_para_focus': 'mapear_1_para_1_o_valor_efetivo_no_momento_da_ativacao',
        'inventario_e_canon_narrativo': 'preservar',
    },
    'classe_alvo': {
        'classe': 'Monge',
        'nivel': 7,
        'subclasse': 'Guerreiro das Sombras',
        'dado_artes_marciais': '1d8',
        'bonus_movimento_sem_armadura_pes': 15,
        'pontos_focus_maximos': 7,
        'cd_focus': 14,
    },
    'ataques_alvo': {
        'golpe_desarmado': {
            'usar_dado_artes_marciais': True,
            'dano_tipo_padrao': 'contundente',
            'dano_tipo_alternativo': 'forca',
        },
        'wakizashi': {
            'mecanica': 'espada curta',
            'arma_monge_5_5e': True,
            'usar_dado_artes_marciais': True,
        },
        'shuriken': {
            'mecanica': 'dardo',
            'arma_monge_5_5e': False,
            'preservar_dado_da_arma': True,
        },
    },
    'focus': {
        'pontos_atuais': {'derivar_de': 'recursos_de_classe.ki.pontos_atuais'},
        'pontos_maximos': 7,
        'cd': 14,
        'recarga': 'descanso curto ou longo',
        'usos': {
            'flurry_of_blows': {
                'custo': 1,
                'acao': 'acao_bonus',
                'requer_acao_atacar_antes': False,
                'golpes_desarmados': 2,
            },
            'patient_defense': {
                'gratuito': 'Desengajar como ação bônus',
                'com_focus': '1 Focus: Desengajar e Esquivar como a mesma ação bônus',
            },
            'step_of_the_wind': {
                'gratuito': 'Disparada como ação bônus',
                'com_focus': '1 Focus: Desengajar e Disparada como a mesma ação bônus; salto dobrado no turno',
            },
        },
    },
    'capacidades_nivel_7': {
        'unarmored_defense': {
            'formula': '10 + Destreza + Sabedoria',
        },
        'uncanny_metabolism': {
            'nivel': 2,
            'gatilho': 'ao rolar iniciativa',
            'recupera_focus': 'todos os Focus Points gastos',
            'cura': 'nível de Monge + 1 dado de Artes Marciais',
            'cura_ren_nivel_7': '7 + 1d8',
            'recarga': '1 uso por descanso longo',
        },
        'deflect_attacks': {
            'nivel': 3,
            'reacao': True,
            'tipos_iniciais': ['contundente', 'perfurante', 'cortante'],
            'reducao_ren_nivel_7': '1d10 + 11',
            'redirecionar_se_reduzir_a_zero': {
                'custo_focus': 1,
                'cd_destreza': 14,
                'dano_falha': '2d8 + 4',
                'tipo': 'mesmo tipo do ataque original',
            },
        },
        'slow_fall': {
            'nivel': 4,
            'reacao': True,
            'reducao_ren_nivel_7': 35,
        },
        'extra_attack': {
            'nivel': 5,
            'ataques_na_acao_atacar': 2,
        },
        'stunning_strike': {
            'nivel': 5,
            'custo_focus': 1,
            'limite': 'uma vez por turno',
            'gatilho': 'acerto com arma de Monge ou Golpe Desarmado',
            'cd_constituicao': 14,
            'falha': 'Atordoado até o início do próximo turno de Ren',
            'sucesso': 'deslocamento pela metade até o início do próximo turno de Ren; próximo ataque contra o alvo antes disso tem vantagem',
        },
        'empowered_strikes': {
            'nivel': 6,
            'efeito': 'Golpe Desarmado pode causar dano de Força ou o tipo normal',
        },
        'evasion': {
            'nivel': 7,
            'sucesso': 'nenhum dano quando o efeito normalmente causaria metade em salvaguarda de Destreza',
            'falha': 'metade do dano',
            'restricao': 'não funciona enquanto Incapacitado',
        },
    },
    'guerreiro_das_sombras': {
        'shadow_arts': {
            'nivel': 3,
            'darkvision_pes': 60,
            'minor_illusion': {
                'conhece': True,
                'habilidade_conjuracao': 'Sabedoria',
            },
            'darkness': {
                'custo_focus': 1,
                'componentes': 'nenhum',
                'acao': 'Magia',
                'concentracao': True,
                've_dentro_da_propria_escuridao': True,
                'mover_area_no_inicio_do_turno_pes': 60,
            },
            'removidas_da_versao_2014': [
                'Passos sem Pegadas',
                'Silêncio',
                'Visão no Escuro como magia gasta por ki',
            ],
        },
        'shadow_step': {
            'nivel': 6,
            'custo_focus': 0,
            'acao': 'ação bônus',
            'alcance_pes': 60,
            'origem_e_destino': 'luz baixa ou escuridão',
            'destino': 'espaço desocupado que Ren consiga ver',
            'efeito_pos_teleporte': 'vantagem no próximo ataque corpo a corpo antes do fim do turno',
        },
    },
    'remocoes_de_classe_2014': {
        'quietude_da_mente_nivel_7': 'não existe no Monge 5.5e nível 7; Self-Restoration chega no nível 10',
        'aparar_projeteis': 'substituído por Deflect Attacks',
        'golpes_potencializados_por_ki': 'substituído por Empowered Strikes',
        'ki': 'renomeado/reestruturado como Focus',
    },
    'beneficios_de_criacao_preservados': {
        'natureza': 'beneficios_canonizados_da_campanha',
        'nao_sao_fallback_ruleset_2014': True,
        'nao_reconstroem_origem_5_5e': True,
        'nao_concedem_novos_origin_feats': True,
        'nao_recalculam_atributos': True,
        'humano_variante': {
            'preservado_como': 'origem histórica de Ren; não converter em novo pacote de Humano 5.5e nem adicionar benefícios retroativos',
        },
        'movel': {
            'preservar_texto_funcional_existente': True,
            'motivo': 'talento inicial canonizado do Humano Variante; não reprecificar como Speedy nem conceder novo +1 de atributo',
        },
        'actor': {
            'preservar_texto_funcional_existente': True,
            'motivo': 'talento bônus retroativo canonizado; Actor 5.5e tem pré-requisito incompatível com Carisma 11 de Ren e não justifica rebuild',
        },
        'observant': {
            'preservar_texto_funcional_existente': True,
            'motivo': 'talento bônus retroativo canonizado; manter a escolha Inteligência e os passivos já estabelecidos em vez de refazer a criação',
        },
        'passivos_preservados': {
            'percepcao': 21,
            'investigacao': 20,
            'intuicao': 16,
        },
    },
}

migration_path = ROOT / 'personagens/jogador/migracao-5-5e.yaml'
migration_path.write_text(
    yaml.safe_dump(migration, allow_unicode=True, sort_keys=False, width=110),
    encoding='utf-8',
)

adapter = r'''"""Visão mecânica alvo de Ren para a migração D&D 5.5e.

A ficha operacional continua sendo ``personagens/jogador/ficha.yaml`` até a Task 8.
Este adaptador é puro: combina a ficha canônica atual com o contrato de migração e
produz a visão que deverá ser promovida quando o gate final for aberto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import ficha_ren

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHEET_PATH = ROOT / "personagens/jogador/ficha.yaml"
DEFAULT_MIGRATION_PATH = ROOT / "personagens/jogador/migracao-5-5e.yaml"
DAMAGE_RE = re.compile(r"^(\d*d\d+)([+-]\d+)?$")
SPEED_RE = re.compile(r"^\s*(\d+)\s*pés\s*$", re.IGNORECASE)


class Ren55MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class TargetAttack:
    label: str
    attack_bonus: int
    damage: str
    damage_type: str


@dataclass(frozen=True)
class Ren55Mechanics:
    ruleset: str
    level: int
    subclass: str
    abilities: dict[str, int]
    skills: dict[str, int]
    passives: dict[str, int]
    saves: dict[str, int]
    proficiency_bonus: int
    attacks: dict[str, TargetAttack]
    armor_class: int
    initiative: int
    speed: int
    hit_points: dict[str, Any]
    focus: dict[str, Any]
    features: dict[str, Any]
    shadow: dict[str, Any]
    legacy_creation: dict[str, Any]


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Ren55MigrationError(f"{path} precisa ser um mapa")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Ren55MigrationError(f"não foi possível ler {path}") from exc
    return _mapping(data, str(path))


def _damage_with_die(damage: str, die: str) -> str:
    match = DAMAGE_RE.match(damage)
    if match is None:
        raise Ren55MigrationError(f"dano base inesperado: {damage!r}")
    modifier = match.group(2) or ""
    return f"{die}{modifier}"


def _speed_feet(raw: object) -> int:
    if not isinstance(raw, str):
        raise Ren55MigrationError("combate.deslocamento.total precisa ser texto em pés")
    match = SPEED_RE.match(raw)
    if match is None:
        raise Ren55MigrationError(f"deslocamento total inválido: {raw!r}")
    return int(match.group(1))


def load(
    sheet_path: Path = DEFAULT_SHEET_PATH,
    migration_path: Path = DEFAULT_MIGRATION_PATH,
) -> Ren55Mechanics:
    base_path = Path(sheet_path)
    migration_file = Path(migration_path)
    raw = _load_yaml(base_path)
    migration = _load_yaml(migration_file)
    active = ficha_ren.load(base_path)

    if migration.get("personagem") != "Ren Kagehira":
        raise Ren55MigrationError("contrato de migração não pertence a Ren Kagehira")
    if migration.get("ruleset_alvo") != "dnd_5_5e":
        raise Ren55MigrationError("ruleset alvo da migração precisa ser dnd_5_5e")
    activation = _mapping(migration.get("ativacao"), "ativacao")
    if activation.get("aplica_antes_do_gate") is not False:
        raise Ren55MigrationError("migração de Ren não pode ativar antes da Task 8")

    identity = _mapping(raw.get("identidade"), "identidade")
    if identity.get("nivel") != 7 or identity.get("classe") != "Monge":
        raise Ren55MigrationError("Task 5 exige Ren Monge nível 7 como base")

    target_class = _mapping(migration.get("classe_alvo"), "classe_alvo")
    martial_die = target_class.get("dado_artes_marciais")
    if martial_die != "1d8":
        raise Ren55MigrationError("Monge 5.5e nível 7 precisa usar Artes Marciais 1d8")

    target_attacks: dict[str, TargetAttack] = {}
    for key, attack in active.attacks.items():
        damage = attack.damage
        if key in {"golpe_desarmado", "wakizashi"}:
            damage = _damage_with_die(damage, martial_die)
        target_attacks[key] = TargetAttack(
            label=attack.label,
            attack_bonus=attack.attack_bonus,
            damage=damage,
            damage_type=attack.damage_type,
        )

    active_ki = _mapping(active.resources.get("ki"), "recursos ativos.ki")
    focus = {
        "pontos_atuais": active_ki["pontos_atuais"],
        "pontos_maximos": target_class["pontos_focus_maximos"],
        "cd": target_class["cd_focus"],
        "recarga": migration["focus"]["recarga"],
    }
    if focus["pontos_atuais"] < 0 or focus["pontos_atuais"] > focus["pontos_maximos"]:
        raise Ren55MigrationError("mapeamento Ki→Focus produziria valor fora da faixa")

    combat = _mapping(raw.get("combate"), "combate")
    movement = _mapping(combat.get("deslocamento"), "combate.deslocamento")
    speed = _speed_feet(movement.get("total"))

    return Ren55Mechanics(
        ruleset="dnd_5_5e",
        level=7,
        subclass="Guerreiro das Sombras",
        abilities=dict(active.abilities),
        skills=dict(active.skills),
        passives=dict(active.passives),
        saves=dict(active.saves),
        proficiency_bonus=active.resources["proficiencia"]["bonus"],
        attacks=target_attacks,
        armor_class=active.armor_class,
        initiative=active.initiative,
        speed=speed,
        hit_points=dict(active.resources["pontos_de_vida"]),
        focus=focus,
        features=dict(migration["capacidades_nivel_7"]),
        shadow=dict(migration["guerreiro_das_sombras"]),
        legacy_creation=dict(migration["beneficios_de_criacao_preservados"]),
    )
'''
(ROOT / 'ferramentas/ficha_ren_5_5e.py').write_text(textwrap.dedent(adapter).lstrip(), encoding='utf-8')

summary = r'''# Resumo de poderes de Ren — alvo D&D 5.5e

> **STAGED / NÃO OPERACIONAL:** esta é a visão alvo da Task 5. Enquanto `campanha.yaml` mantiver `ruleset.atual: dnd_5e_2014`, a narração ao vivo continua usando `personagens/jogador/ficha.yaml` e `resumo-de-poderes.md`. A promoção desta visão só ocorre na Task 8.

Ren permanece **Monge 7**, agora convertido como **Guerreiro das Sombras** para D&D 5.5e. A conversão preserva atributos, PV, inventário, histórico e benefícios de criação canonizados; ela não reconstrói o personagem nem reescreve sessões passadas.

## Números alvo

- CA 17;
- PV máximos 52; PV atuais são preservados do estado efetivo no momento da ativação;
- deslocamento 55 pés;
- bônus de proficiência +3;
- iniciativa +4;
- Focus máximo 7; Focus atual será o valor efetivo de Ki convertido 1:1 no momento da ativação;
- CD de Focus 14;
- Artes Marciais `1d8` no nível 7;
- Golpe desarmado +7, `1d8+4` contundente (ou Força por Empowered Strikes);
- Wakizashi +7, `1d8+4` perfurante;
- Shuriken +7, `1d4+4` perfurante.

## Focus

**Flurry of Blows:** 1 Focus, ação bônus, dois Golpes Desarmados; não exige usar a ação Atacar antes.

**Patient Defense:** Desengajar como ação bônus é gratuito. Com 1 Focus, Ren faz Desengajar e Esquivar na mesma ação bônus.

**Step of the Wind:** Disparada como ação bônus é gratuita. Com 1 Focus, Ren faz Desengajar e Disparada na mesma ação bônus e dobra a distância de salto no turno.

## Capacidades de Monge até o nível 7

**Uncanny Metabolism:** ao rolar iniciativa, uma vez por descanso longo, pode recuperar todos os Focus gastos e curar `7 + 1d8` PV.

**Deflect Attacks:** reação contra ataque que inclua dano contundente, perfurante ou cortante; Ren reduz `1d10+11`. Se reduzir a zero, pode gastar 1 Focus para redirecionar: salvaguarda de Destreza CD 14; em falha, `2d8+4` do mesmo tipo do ataque original.

**Slow Fall:** reação; reduz dano de queda em 35.

**Extra Attack:** dois ataques ao usar a ação Atacar.

**Stunning Strike:** uma vez por turno, depois de acertar com arma de Monge ou Golpe Desarmado, 1 Focus; Constituição CD 14. Em falha, Atordoado até o início do próximo turno de Ren. Em sucesso, deslocamento pela metade até então e o próximo ataque contra o alvo antes disso tem vantagem.

**Empowered Strikes:** Golpes Desarmados podem causar dano de Força ou o tipo normal.

**Evasion:** em efeito de Destreza que daria metade no sucesso, Ren sofre zero no sucesso e metade na falha; não funciona enquanto Incapacitado.

**Quietude da Mente deixa de existir no nível 7.** A função revisada equivalente só aparece mais tarde como Self-Restoration, no nível 10.

## Guerreiro das Sombras

**Shadow Arts — nível 3:**

- Darkvision 60 pés;
- Minor Illusion, usando Sabedoria;
- Darkness por 1 Focus, sem componentes; Ren enxerga dentro da própria área criada por esta característica;
- no início de cada turno, enquanto a magia persistir, Ren pode mover sua área para um espaço a até 60 pés;
- a versão 5.5e não mantém Passos sem Pegadas nem Silêncio nas Shadow Arts, e Visão no Escuro deixa de ser uma magia comprada com recurso.

**Shadow Step — nível 6:** ação bônus, custo 0; em luz baixa/escuridão, teleporta até 60 pés para espaço desocupado visível também em luz baixa/escuridão e recebe vantagem no próximo ataque corpo a corpo antes do fim do turno.

## Benefícios de criação preservados pela DEC-0008

Humano Variante, Móvel, Actor e Observant não serão “recomprados” pela criação 5.5e. Eles são preservados como benefícios canonizados da campanha, sem novos Origin Feats, sem novo ASI e sem reconstrução de atributos.

Isso mantém:

- deslocamento total de 55 pés e o comportamento canonizado de Móvel;
- Actor com o gatilho já usado pela campanha para outra identidade, incluindo Enganação/Atuação e mimetismo separado;
- Observant com escolha Inteligência e passivos atuais: Percepção 21, Investigação 20 e Intuição 16;
- o ASI do nível 4 `+1 Destreza, +1 Sabedoria`;
- todo o histórico anterior exatamente como foi jogado.
'''
(ROOT / 'personagens/jogador/resumo-de-poderes-5-5e.md').write_text(textwrap.dedent(summary).lstrip(), encoding='utf-8')

# DEC-0008
path = ROOT / 'regras/decisoes.md'
text = path.read_text(encoding='utf-8')
if '## DEC-0008 — Migração de Ren para Monge/Guerreiro das Sombras 5.5e' not in text:
    dec = r'''

## DEC-0008 — Migração de Ren para Monge/Guerreiro das Sombras 5.5e

- Sessão de origem: preparação de migração entre rulesets, antes da ativação 5.5e.
- Contexto: a campanha está migrando de D&D 5e 2014 para D&D 5.5e. Ren já possui sete níveis jogados, atributos, PV, recursos consumidos, Humano Variante, background customizado e os benefícios canonizados Móvel, Actor e Observant. Recriar o personagem pela ordem de criação 5.5e mudaria retrospectivamente escolhas que já produziram dezenas de cenas.
- Regra oficial alvo: o Monge 5.5e usa Focus Points, Artes Marciais `1d8` no nível 7, Uncanny Metabolism, Deflect Attacks, Stunning Strike revisado, Empowered Strikes e Evasion; o Guerreiro das Sombras revisa Shadow Arts para Darkness/Minor Illusion/Darkvision e preserva Shadow Step no nível 6. Pass Without Trace e Silence deixam de fazer parte da subclasse revisada.
- Decisão de classe: na ativação da 5.5e, Ren é promovido prospectivamente para **Monge 7 / Guerreiro das Sombras**. Ki vira Focus 1:1 preservando os pontos atualmente disponíveis no instante da ativação; PV atuais/máximos, atributos, proficiências, inventário e estado narrativo não são recalculados. O dado de Artes Marciais passa a `1d8`; Golpe Desarmado e wakizashi usam esse dado, enquanto shuriken/dardo preserva `1d4`.
- Decisão de criação: **não reconstruir a origem de Ren**. Humano Variante, Móvel, Actor e Observant passam a ser tratados, para fins de migração, como benefícios de criação canonizados da campanha e de autoridade superior ao ruleset pelo contrato de `campanha.yaml`. Eles não são fallback genérico de regra 2014, não consomem novos slots de feat 5.5e e não concedem novos Origin Feats, ASIs ou benefícios de Humano/background retroativos.
- Móvel: preservar a funcionalidade já canonizada e o +10 pés, sem convertê-lo em Speedy nem acrescentar o +1 de atributo do feat novo.
- Actor: preservar a funcionalidade canonizada da DEC-0007, inclusive o gatilho de outra identidade para Enganação/Atuação e o mimetismo separado. Não refazer atributos para satisfazer pré-requisitos do Actor 5.5e; Carisma permanece 11.
- Observant: preservar a escolha Inteligência, o +1 já incorporado e os passivos canonizados (Percepção 21, Investigação 20), em vez de trocar retroativamente por uma nova escolha de Expertise/Quick Search.
- Capacidades removidas/substituídas: Quietude da Mente não permanece como característica de nível 7; Aparar Projéteis é substituído por Deflect Attacks; Golpes Potencializados por Ki é substituído por Empowered Strikes; as antigas Shadow Arts que concediam Passos sem Pegadas, Silêncio e Visão no Escuro por ki deixam de existir no perfil 5.5e.
- Continuidade: esta decisão **não reescreve sessões concluídas, rolagens, recursos gastos, descobertas, falhas, consequências ou descrições históricas**. Até o gate `task_8_auditoria_final`, a ficha 2014 continua operacional. O perfil 5.5e existe apenas como alvo materializado de migração; seus efeitos começam no primeiro estado canônico explicitamente promovido após a ativação.
- Estado: permanente para a migração; staged e não operacional até a Task 8.
'''
    path.write_text(text.rstrip() + textwrap.dedent(dec) + '\n', encoding='utf-8')

# campanha.yaml
path = ROOT / 'campanha.yaml'
text = path.read_text(encoding='utf-8')
old = '          task_5_conversao_ren: false\n'
if old not in text and '          task_5_conversao_ren: true\n' not in text:
    raise SystemExit('task_5 marker not found')
text = text.replace(old, '          task_5_conversao_ren: true\n', 1)
anchor = '    adaptador_ficha_ren: "ferramentas/ficha_ren.py"\n'
refs = (
    anchor
    + '    migracao_ficha_ren_5_5e: "personagens/jogador/migracao-5-5e.yaml"\n'
    + '    adaptador_ficha_ren_5_5e: "ferramentas/ficha_ren_5_5e.py"\n'
    + '    personagem_resumo_poderes_5_5e: "personagens/jogador/resumo-de-poderes-5-5e.md"\n'
)
if 'migracao_ficha_ren_5_5e:' not in text:
    if anchor not in text:
        raise SystemExit('campaign adapter anchor not found')
    text = text.replace(anchor, refs, 1)
path.write_text(text, encoding='utf-8')

# docs/agente/regras-e-rolagens.md
path = ROOT / 'docs/agente/regras-e-rolagens.md'
text = path.read_text(encoding='utf-8')
if '## Perfil alvo 5.5e de Ren' not in text:
    marker = '## Filosofia de fidelidade: aproximadamente 70%\n'
    if marker not in text:
        raise SystemExit('docs marker not found')
    section = r'''## Perfil alvo 5.5e de Ren

A Task 5 materializa a conversão de Ren sem furar o gate da Task 1. `personagens/jogador/migracao-5-5e.yaml` descreve a promoção prospectiva e `ferramentas/ficha_ren_5_5e.py` deriva uma visão mecânica completa a partir da ficha canônica **sem alterar a ficha ativa**. `personagens/jogador/resumo-de-poderes-5-5e.md` é documentação alvo e deve ser ignorado em narração ao vivo enquanto `ruleset.atual` continuar `dnd_5e_2014`.

O adaptador alvo deve sempre derivar PV atuais e a quantidade atual de Focus do estado efetivo: no gate final, Ki é mapeado 1:1 para Focus em vez de restaurar ou gastar recurso por efeito da migração. Os benefícios de criação preservados pela DEC-0008 são decisões de campanha canonizadas, não fallback silencioso de regras 2014.

'''
    path.write_text(text.replace(marker, textwrap.dedent(section) + marker, 1), encoding='utf-8')

# tests
tests = r'''from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren
import ficha_ren_5_5e


class Ren55MigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.active_path = ROOT / "personagens/jogador/ficha.yaml"
        cls.migration_path = ROOT / "personagens/jogador/migracao-5-5e.yaml"
        cls.active_raw = yaml.safe_load(cls.active_path.read_text(encoding="utf-8"))
        cls.migration = yaml.safe_load(cls.migration_path.read_text(encoding="utf-8"))
        cls.active = ficha_ren.load(cls.active_path)
        cls.target = ficha_ren_5_5e.load(cls.active_path, cls.migration_path)

    def test_task5_nao_ativa_5_5e_antes_da_task8(self) -> None:
        campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        ruleset = campaign["sistema"]["ruleset"]
        self.assertEqual(ruleset["atual"], "dnd_5e_2014")
        self.assertEqual(ruleset["alvo"], "dnd_5_5e")
        self.assertFalse(ruleset["migracao"]["ativacao"]["permitida"])
        self.assertTrue(ruleset["migracao"]["ativacao"]["requisitos"]["task_5_conversao_ren"])
        self.assertEqual(self.active_raw["personagem"]["sistema"], "Dungeons & Dragons 5e")
        self.assertIn("ki", self.active_raw["recursos_de_classe"])
        self.assertNotIn("focus", self.active_raw["recursos_de_classe"])
        self.assertFalse(self.migration["ativacao"]["aplica_antes_do_gate"])

    def test_identidade_nivel_e_numeros_centrais_sao_preservados(self) -> None:
        self.assertEqual((self.target.ruleset, self.target.level, self.target.subclass), ("dnd_5_5e", 7, "Guerreiro das Sombras"))
        self.assertEqual(self.target.armor_class, 17)
        self.assertEqual(self.target.hit_points, {"atuais": 45, "maximos": 52, "dados_de_vida": "7d8"})
        self.assertEqual(self.target.initiative, 4)
        self.assertEqual(self.target.proficiency_bonus, 3)
        self.assertEqual(self.target.speed, 55)
        self.assertEqual(self.target.abilities, self.active.abilities)
        self.assertEqual(self.target.saves, self.active.saves)

    def test_focus_substitui_ki_sem_restaurar_recurso(self) -> None:
        self.assertEqual(self.target.focus, {"pontos_atuais": 1, "pontos_maximos": 7, "cd": 14, "recarga": "descanso curto ou longo"})
        self.assertEqual(self.target.focus["pontos_atuais"], self.active.resources["ki"]["pontos_atuais"])

    def test_focus_atual_deriva_do_estado_efetivo_e_nao_de_constante(self) -> None:
        changed = copy.deepcopy(self.active_raw)
        changed["recursos_de_classe"]["ki"]["pontos_atuais"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ficha.yaml"
            path.write_text(yaml.safe_dump(changed, allow_unicode=True, sort_keys=False), encoding="utf-8")
            target = ficha_ren_5_5e.load(path, self.migration_path)
        self.assertEqual(target.focus["pontos_atuais"], 3)

    def test_ataques_usam_artes_marciais_1d8_sem_transformar_dardo_em_arma_de_monge(self) -> None:
        attacks = self.target.attacks
        self.assertEqual((attacks["golpe_desarmado"].attack_bonus, attacks["golpe_desarmado"].damage), (7, "1d8+4"))
        self.assertEqual((attacks["wakizashi"].attack_bonus, attacks["wakizashi"].damage), (7, "1d8+4"))
        self.assertEqual((attacks["shuriken"].attack_bonus, attacks["shuriken"].damage), (7, "1d4+4"))
        self.assertEqual(self.migration["classe_alvo"]["dado_artes_marciais"], "1d8")
        self.assertFalse(self.migration["ataques_alvo"]["shuriken"]["arma_monge_5_5e"])

    def test_capacidades_de_monge_nivel_7_foram_convertidas(self) -> None:
        features = self.target.features
        metabolism = features["uncanny_metabolism"]
        self.assertEqual(metabolism["cura_ren_nivel_7"], "7 + 1d8")
        self.assertEqual(metabolism["recarga"], "1 uso por descanso longo")
        deflect = features["deflect_attacks"]
        self.assertEqual(deflect["reducao_ren_nivel_7"], "1d10 + 11")
        self.assertEqual(deflect["redirecionar_se_reduzir_a_zero"]["dano_falha"], "2d8 + 4")
        self.assertEqual(features["slow_fall"]["reducao_ren_nivel_7"], 35)
        stunning = features["stunning_strike"]
        self.assertEqual(stunning["limite"], "uma vez por turno")
        self.assertIn("deslocamento pela metade", stunning["sucesso"])
        self.assertIn("Força", features["empowered_strikes"]["efeito"])
        self.assertIn("Incapacitado", features["evasion"]["restricao"])

    def test_focus_basico_reflete_as_acoes_revisadas(self) -> None:
        uses = self.migration["focus"]["usos"]
        self.assertFalse(uses["flurry_of_blows"]["requer_acao_atacar_antes"])
        self.assertIn("gratuito", uses["patient_defense"])
        self.assertIn("gratuito", uses["step_of_the_wind"])
        self.assertIn("Esquivar", uses["patient_defense"]["com_focus"])
        self.assertIn("salto dobrado", uses["step_of_the_wind"]["com_focus"])

    def test_guerreiro_das_sombras_perde_magias_2014_e_ganha_darkness_revisada(self) -> None:
        arts = self.target.shadow["shadow_arts"]
        self.assertEqual(arts["darkvision_pes"], 60)
        darkness = arts["darkness"]
        self.assertEqual(darkness["custo_focus"], 1)
        self.assertTrue(darkness["ve_dentro_da_propria_escuridao"])
        self.assertEqual(darkness["mover_area_no_inicio_do_turno_pes"], 60)
        removed = set(arts["removidas_da_versao_2014"])
        self.assertIn("Passos sem Pegadas", removed)
        self.assertIn("Silêncio", removed)
        shadow_step = self.target.shadow["shadow_step"]
        self.assertEqual(shadow_step["alcance_pes"], 60)
        self.assertEqual(shadow_step["custo_focus"], 0)
        self.assertIn("vantagem", shadow_step["efeito_pos_teleporte"])

    def test_beneficios_de_criacao_e_passivos_permanecem_canonizados(self) -> None:
        legacy = self.target.legacy_creation
        self.assertTrue(legacy["nao_sao_fallback_ruleset_2014"])
        self.assertTrue(legacy["nao_reconstroem_origem_5_5e"])
        self.assertTrue(legacy["nao_concedem_novos_origin_feats"])
        self.assertTrue(legacy["movel"]["preservar_texto_funcional_existente"])
        self.assertTrue(legacy["actor"]["preservar_texto_funcional_existente"])
        self.assertTrue(legacy["observant"]["preservar_texto_funcional_existente"])
        self.assertEqual(self.target.passives, {"percepcao": 21, "investigacao": 20, "intuicao": 16})
        self.assertEqual(self.target.skills, self.active.skills)

    def test_decisao_proibe_rebuild_e_retroatividade(self) -> None:
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0008", text)
        self.assertIn("não reconstruir a origem de Ren", text)
        self.assertIn("não reescreve sessões concluídas, rolagens, recursos gastos", text)
        self.assertIn("staged e não operacional até a Task 8", text)
        self.assertIn("Ki vira Focus 1:1", text)


if __name__ == "__main__":
    unittest.main()
'''
(ROOT / 'tests/test_migracao_ren_5_5e.py').write_text(textwrap.dedent(tests).lstrip(), encoding='utf-8')
