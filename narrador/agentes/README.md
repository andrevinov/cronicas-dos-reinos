# Agentes autônomos

Camada operacional reservada para NPCs, facções e instituições capazes de agir
fora da presença de Ren.

Ela **não substitui** `narrador/masao/`, `narrador/juppongatana/`, relógios,
relações, sessões ou qualquer outra fonte canônica. Os fragmentos daqui apenas
condensam o estado de agência necessário para responder rapidamente:

- o que o agente quer agora;
- quais recursos importam para esse objetivo;
- quais restrições limitam sua ação;
- o que ele realmente sabe;
- qual plano está ativo;
- qual prazo ou oportunidade pode disparar uma revisão.

## Contrato

Cada agente fica em um YAML próprio. `index.yaml` contém somente metadados de
roteamento para que consultar um agente não carregue os demais.

Campos obrigatórios do fragmento:

```yaml
schema_agente: 1
natureza: reservado
id: exemplo
nome: Exemplo
tipo: npc # npc | faccao | instituicao
estado: ativo # ativo | latente | inativo
objetivo_atual: ...
recursos: [...]
restricoes: [...]
conhecimento:
  - id: fato_estavel
    fato: ...
    fonte: caminho/canonico.md
    evidencia: trecho curto existente na fonte
plano_atual:
  estado: em_execucao
  acao: ...
  prazo_ou_oportunidade: ...
fontes_canonicas:
  - caminho/canonico.md
```

Estados possíveis de `plano_atual.estado`:

- `em_execucao`;
- `aguardando_oportunidade`;
- `requer_reavaliacao`;
- `sem_plano_registrado`.

`sem_plano_registrado` exige `acao: null`. Não inventar um plano apenas para
preencher o campo.

## Proveniência do conhecimento

Todo item em `conhecimento` precisa apontar para uma `fonte` declarada em
`fontes_canonicas` e trazer uma `evidencia` curta localizável nessa fonte.
`ferramentas/agentes.py validar` verifica mecanicamente essas referências.

Isso não prova interpretação semântica perfeita, mas impede que a camada de
agência acumule fatos sem qualquer sustentação no cânone existente.

## Uso econômico

Consulta dirigida:

```bash
python3 ferramentas/agentes.py mostrar shizune
python3 ferramentas/agentes.py mostrar red_sail
```

Essas consultas abrem apenas:

1. `narrador/agentes/index.yaml`;
2. o fragmento solicitado.

Elas não percorrem outros agentes nem abrem as fontes canônicas.

Validação ampla, reservada a manutenção/CI:

```bash
python3 ferramentas/agentes.py validar
```

A validação percorre todos os fragmentos e suas fontes. Não deve ser executada a
cada turno de narração.

## Limite desta etapa

Esta camada registra **agência possível e estado operacional**, mas ainda não
decide quando o mundo deve processar ações. O agendamento temporal e o futuro
motor de mundo pertencem às etapas seguintes.
