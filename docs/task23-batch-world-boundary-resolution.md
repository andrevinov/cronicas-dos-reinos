# Task 23 — Batch World Boundary Resolution

## Problema observado

Rollouts reais mostraram que uma fronteira temporal podia criar varias pendencias ao
mesmo tempo. A fronteira e a barreira estavam corretas, mas o narrador precisava abrir,
avaliar e concluir cada item por uma sequencia separada de ferramentas. Num caso real,
cinco itens terminaram sem mudanca e somente um exigiu fato novo, mas a orquestracao
consumiu dezenas de inferencias.

## Objetivo

Preservar toda a semantica existente do Mundo Vivo e reduzir apenas a orquestracao:

1. projetar todas as pendencias abertas num unico lote read-only;
2. avaliar os itens juntos na mesma inferencia;
3. concluir todos os `sem_mudanca` aprovados numa unica chamada;
4. devolver somente o subconjunto que ainda exige fato, transacao ou outra resolucao.

A camada nao decide automaticamente que algo e no-op.

## Porta publica

Preparacao:

```bash
poetry run python ferramentas/resolver_fronteira.py preparar
```

A saida fornece um `lote_id`, os itens ordenados, contexto dirigido compacto e um
`token` por pendencia. Cada token assina a pendencia, sua classificacao e o contexto
usado na avaliacao.

Aplicacao:

```bash
poetry run python ferramentas/resolver_fronteira.py aplicar <<'YAML'
lote_id: frn1.<id>
sem_mudanca:
  - id: mundo-...
    token: <token devolvido por preparar>
    nota: Motivo concreto para esta cadencia nao produzir fato novo.
YAML
```

Itens omitidos nao sao concluidos. Permanecem bloqueantes e retornam em
`requer_resolucao`.

## Classificacao

### `avaliar_no_lote`

A pendencia pode ser considerada junto das demais. Se a avaliacao determinar que nada
mudou, ela pode entrar em `sem_mudanca`.

Agente estrategico continua sendo apenas reavaliado; a camada nao escolhe plano ou
acao por ele.

### `avaliar_candidato_autonomo`

A pendencia possui candidato autonomo de pressao de Ravens Bluff. O no-op continua
permitido somente quando existe bloqueio canonico concreto de recurso, conhecimento,
presenca, restricao ou oportunidade. As proibicoes anteriores da barreira continuam
autoritativas.

### `requer_fato_canonico`

Eventos canonicos datados nunca aceitam `sem_mudanca`. O lote somente os separa dos
itens triviais. A materializacao continua exigindo transacao `modo: mundo` e a
conclusao normal pela barreira.

## Agentes leves

`reavaliar_agente_leve` concluido como no-op reutiliza
`agentes_leves.conclude_noop`. Assim a Task 9 continua instalando cache negativo
causal antes de remover a pendencia. A Task 23 nao generaliza esse cache para agentes
estrategicos.

## Staleness e retry

Todas as decisoes sao revalidadas antes da primeira escrita. Se o token de uma
pendencia mudou, o lote falha antes de aplicar qualquer decisao.

O token de agente leve nao inclui o proprio cache negativo. Isso permite recuperar a
queda intencionalmente suportada pela Task 9 entre a escrita do cache e a remocao da
pendencia.

Pendencia ja presente em `concluidas_recentes` e reconhecida como retry idempotente.

## Custo

Contrato: `baseline/batch-world-boundary-resolution-orcamento.yaml`.

- 1 chamada para preparar a fronteira;
- 1 chamada para aplicar todos os no-ops;
- maximo 16 pendencias por lote;
- no maximo um fragmento dirigido por pendencia;
- zero escrita em `preparar`;
- zero scheduler;
- zero estado paralelo;
- zero scan global;
- itens realmente narrativos continuam separados e nao sao comprimidos.

O ganho pretendido e reduzir inferencias e tool calls em fronteiras com varias rotinas,
nao alterar a frequencia nem a criatividade do Mundo Vivo.
