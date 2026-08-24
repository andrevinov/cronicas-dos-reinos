# Task 38 — Narrative Systems Integration & Budget Regression

## Objetivo

A Task 38 não acrescenta um novo motor narrativo. Ela fecha a sequência de
engenharia das Tasks 23–37 provando que as camadas já existentes continuam
componíveis sem transformar o turno comum em uma sequência crescente de chamadas,
scans ou ativações de NPCs.

O contrato executável está em
`baseline/narrative-systems-integration-budget-regression-orcamento.yaml`.

## Regra principal

O turno neutro continua tendo a mesma dupla de orquestração:

```text
cronica preparar
→ narração / rolagens materialmente necessárias
→ cronica concluir
```

Isso significa **duas chamadas de orquestração**, não duas ferramentas totais. Uma
rolagem realmente necessária continua podendo ocorrer entre elas. O que a Task 38
proíbe é uma terceira chamada ritualística criada apenas para alimentar um sistema
narrativo novo.

## Matriz de integração

### Relação, diálogo e iniciativa social

`contexto.py npc` continua sendo a única consulta dirigida necessária. O estado da
Task 26 é sobreposto primeiro; diálogo e iniciativa são projeções puras sobre os
dados já carregados. Uma consulta não abre fichas de outros NPCs nem acrescenta
uma fonte própria para `iniciativa_social.py`.

Uma cena espacial sem NPC explícito não executa iniciativa social. Coincidências
locais continuam responsabilidade da Presença Incidental: no máximo um candidato,
sem diálogo, ação, conhecimento, encontro ou side quest automáticos.

### Side quests canônicas

O roteador por NPC pode abrir gates mecânicos compactos, mas um gate bloqueado
continua abrindo **zero detalhes secretos**. Um detalhe só entra quando a quest
realmente é elegível, e ainda assim disponibilidade não significa oferta ou aceite.

### Condições persistentes e incidentes

Condição persistente é contexto compacto. Incidente sério reutiliza a projeção da
condição, mas continua com seu próprio baralho determinístico. A Task 38 congela:

- uma leitura de estado ambiental em cena espacial;
- duas leituras próprias da Task 35 em cena espacial;
- zero scans globais;
- no máximo um incidente sério por cena.

Nenhuma condição ou incidente passa a acordar NPCs ou criar side quest.

### Cânone secreto principal

Sem pendência canônica datada, `eventos_canonicos.pending_projection()` retorna
vazio antes de abrir até mesmo o índice reservado. Quando existe um alvo devido,
a Task 36 continua permitindo no máximo um fragmento frio por evento.

### Fronteira do Mundo Vivo

A Task 23 continua sendo a operação de lote: até 16 pendências são preparadas em
uma chamada e todos os no-ops aprovados são aplicados por uma única chamada de
`aplicar`. A Task 38 não cria outro batch, scheduler ou estado paralelo.

### Torneio clandestino

A Task 37 permanece um mini-arco opcional. Fora dele não há chamada extra; uma
consulta de rodada abre no máximo um fragmento e sua agenda não vira pendência de
Mundo Vivo.

## Telemetria pós-hoc

`ferramentas/analisar-rollout.py` preserva o relatório público `schema_version: 3`
e acrescenta a extensão `narrative_systems_schema: 1`.

A extensão mede, por observação do rollout:

- chamadas e fases de orquestração `cronica`;
- turnos que usam exatamente a dupla `preparar + concluir`;
- presença dos sistemas `npc_social_initiative`, `world_local_incidents`,
  `canonical_secret_quests`, `secret_canon`, `batch_world_boundary`,
  `persistent_world_conditions` e `underground_tournament`;
- atribuição por comando e por marcadores presentes no output da própria ferramenta.

Uma única chamada de `cronica preparar` pode carregar mais de um sistema e, por
isso, aparecer em várias categorias sem aumentar `tool_calls`. Essa atribuição é
**observacional**: dizer que o output continha `sidequest_canonica`, por exemplo,
não afirma que Ren a aceitou ou que o fato foi canonizado.

O analisador também passa a reconhecer `cronica concluir`/`cronica registrar` como
sinais modernos de avanço narrativo, `poetry run dados`/`dados-lote` como rolagens
e `contexto.py reputacao` como L2.

A telemetria continua exclusivamente pós-hoc. Nenhuma chamada ao analisador ou ao
comparador entra no loop de jogo.

## Regressões executáveis

`tests/test_task38_narrative_systems_integration.py` cobre a composição dos
sistemas e confere os limites contra os contratos originais. O objetivo é impedir
que uma mudança futura torne silenciosamente mais caro um sistema antigo apenas
porque outro foi adicionado depois.

`tests/test_analisar_rollout_task38.py` cobre a extensão de telemetria sem alterar
o schema público anterior.

## Invariantes finais

- nenhum motor narrativo novo;
- nenhum estado persistente novo da Task 38;
- nenhum scheduler;
- nenhum endpoint;
- nenhum scan global;
- nenhuma chamada de telemetria durante jogo;
- duas orquestrações no turno neutro;
- iniciativa social não é wake-all;
- detalhe secreto permanece frio até gate;
- condição permanece contexto compacto;
- incidente continua dirigido e raro;
- cânone principal permanece lazy;
- no-ops do Mundo Vivo continuam em lote;
- nenhuma dessas camadas decide por Ren.
