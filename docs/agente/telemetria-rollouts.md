# Telemetria externa de rollouts

Este documento define como medir o custo operacional de **Crônicas dos Reinos** sem introduzir telemetria no loop narrativo.

## Princípio

A campanha não deve gastar uma interação para medir a própria interação. Durante narração ao vivo, não criar `runtime/telemetria.jsonl`, não atualizar dashboards, não calcular médias e não executar analisadores de rollout.

A telemetria normal é **pós-hoc e somente leitura**:

```text
sessão de jogo
→ rollout-*.jsonl nativo do Codex
→ analisar-rollout.py
→ comparar-rollouts.py
→ decisão de engenharia
```

`contexto.py` também não grava `runtime/consultas-contexto.jsonl` por padrão. O log local, quando disponível, é apenas diagnóstico opt-in.

## Ferramentas

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
python3 ferramentas/comparar-rollouts.py ~/.codex/sessions/.../rollout-novo.jsonl
```

A baseline padrão é `baseline/rollout-2026-08-15.json` e as metas ficam em `baseline/metas-rollout-pos-refatoracao.json`. O comparador também aceita vários rollouts e normaliza os resultados por avanço narrativo.

## Schema público e extensão Task 38

O relatório principal continua em **`schema_version: 3`**. A Task 38 não força consumidores existentes a migrar apenas para receber observabilidade adicional.

Quando a extensão está presente, o relatório também contém:

```text
narrative_systems_schema: 1
```

Ela acrescenta métricas de orquestração e atribuição de sistemas narrativos sem remover ou reinterpretar as métricas do schema 3.

### Orquestração

A extensão reconhece as fases `cronica preparar`, `cronica concluir`, `cronica registrar` e `cronica confirmar` e expõe:

- `orchestration_calls`;
- `avg_orchestration_calls_per_turn`;
- `orchestration_phases`;
- `cronica_pair_turns`;
- `fraction_turns_with_cronica_pair`.

Um turno conta como a dupla preferencial quando possui exatamente um `preparar` e um `concluir` como chamadas de orquestração. Rolagens materialmente necessárias entre as duas não deixam de ser válidas: elas são tools de mecânica, não uma terceira fase de orquestração.

### Sistemas narrativos observados

A extensão atribui chamadas/turnos a sete famílias:

- `npc_social_initiative`;
- `world_local_incidents`;
- `canonical_secret_quests`;
- `secret_canon`;
- `batch_world_boundary`;
- `persistent_world_conditions`;
- `underground_tournament`.

A atribuição usa o comando e marcadores do output da própria ferramenta. Isso permite que uma única chamada de `cronica preparar` seja marcada, por exemplo, como incidente + condição persistente + sidequest canônica **sem contar três tool calls**.

Essa classificação é **inferência observacional**. Um marcador de `canonical_secret_quests` significa que aquela camada apareceu no fluxo observado; não significa que a quest foi oferecida, aceita ou canonizada. O mesmo vale para incidente, cânone futuro, torneio e demais sistemas.

`narrative_system_calls` pode somar mais que `tool_calls` porque uma mesma chamada pode carregar mais de uma família. `narrative_system_turns` conta cada família no máximo uma vez por turno.

## Compatibilidade operacional atualizada

A Task 38 também fecha três lacunas da telemetria anterior:

- `cronica concluir` e `cronica registrar` são sinais de avanço narrativo moderno, além do writer legado `turno.py registrar`;
- `poetry run dados` e `poetry run dados-lote` são classificados como `dice`, mantendo compatibilidade com `rolar-dados.py` / `rolar-lote.py` antigos;
- `contexto.py reputacao` é reconhecido como consulta L2.

## O que é medido diretamente pelo rollout

São métricas nativas/exatas dentro do arquivo:

- eventos de inferência (`token_count` / `last_token_usage`);
- input tokens e cached input tokens;
- output tokens e reasoning output tokens;
- número de tool calls;
- compactações;
- tamanho do `AGENTS.md` observado em `world_state`, quando presente.

O analisador calcula ainda média, pico e p95 de input por inferência, input não-cache aproximado (`input - cached`) e tool-output bytes anexados ao histórico do modelo.

`input - cached` é aproximação operacional. **Não é fórmula de faturamento nem de quota semanal.**

## O que é inferido pelo analisador

Além da extensão Task 38, continuam sendo inferências observacionais:

- categorias `read_search`, `write`, `dice`, `validation` e `other`;
- consultas roteadas por `contexto.py` / `contexto-buscar-muitos.py`;
- leituras cruas com `rg`, `sed`, `grep`, `cat`, `find`, `ls`, `git show` ou equivalentes;
- descoberta de interface/schema por `--help` ou leitura direta de `ferramentas/*.py`;
- caminhos mencionados em operações de leitura/escrita;
- alvos implícitos de writers conhecidos;
- leitura de transcrição;
- nível L1/L2/L3/L4/L4T;
- fases de `cronica` e famílias narrativas da extensão.

Desde o schema 3, chamada e resultado são correlacionados pelo `call_id` nativo quando possível, com FIFO apenas como fallback para rollouts antigos. Exit code, status explícito e respostas inequívocas permitem separar escrita tentada, concluída, falha e desconhecida.

`write_target_touches` e `canonical_write_target_touches` contam apenas alvos de escritas concluídas. `attempted_write_target_touches` preserva as tentativas. O mesmo princípio vale para leitura de transcrição.

## Leitura roteada versus leitura crua

Uma consulta L2 não esconde leitura direta no mesmo turno:

```text
contexto roteado = API operacional de contexto
leitura crua     = abertura/busca direta em arquivos
```

Se houver `contexto.py cena` seguido de `rg`/`sed`, o nível pode aparecer como `L2+RAW`. `fraction_turns_l0_l2` significa L0–L2 **limpo**; variantes `+RAW` não satisfazem a meta.

## Como um avanço narrativo é reconhecido

Há três rotas complementares:

1. prompt legado da baseline + heurística textual pequena;
2. writer legado `turno.py registrar`;
3. writers modernos `cronica concluir` / `cronica registrar`.

Chamadas com `--help` não contam como avanço nem escrita. Se a forma de pedir avanço mudar radicalmente, use `--narration-regex` no analisador/comparador.

## Métricas principais

### Input bruto por avanço

Meta técnica: redução de **75–85%**, com piso inicial de aprovação de **70%**.

### Inferências por avanço

Baseline antiga: aproximadamente 15,6. Meta: **até 5**.

### Tool calls por avanço

Baseline antiga: aproximadamente 23,5. Meta inicial: **até 8** sem sacrificar regra, agência ou continuidade.

### Orquestração por avanço

Contrato preferencial da Task 21/38: **2 chamadas de orquestração** (`preparar + concluir`) no turno comum. Esse número é diferente de tool calls totais: uma rolagem necessária continua sendo uma chamada adicional legítima.

### Leitura roteada, crua e descoberta de schema

`routed_context_calls`, `raw_read_calls` e `schema_discovery_calls` localizam custo evitável sem confundir API operacional com investigação da infraestrutura.

### Alvos de escrita

O avanço comum pretende persistir apenas:

```text
sessoes/NNN/transcricao.md
runtime/eventos-pendentes.jsonl
```

Meta: **até 2 alvos concluídos** e zero escrita canônica concluída durante o turno comum.

### Leitura de transcrição

Transcrição é L4T/evidência bruta, não memória operacional. Meta comum: praticamente zero; a regra agregada tolera até 0,05 leitura concluída por avanço.

### Distribuição L0–L2 limpa

Meta: **ao menos 80%** dos avanços em L0–L2 limpo.

## Baseline pré-refatoração

`baseline/rollout-2026-08-15.json` combina contadores nativos com auditoria manual dos 13 avanços narrativos. Campos antigos sem precisão suficiente permanecem `n/d`; o comparador não inventa valores históricos.

A meta informal de economia efetiva não é convertida automaticamente em faturamento/quota. O comparador mostra separadamente input bruto, não-cache aproximado, inferências, tools e escrita.

## Momento recomendado para medir

Depois que a campanha estiver rodando:

1. jogar uma sessão real;
2. localizar o rollout correspondente;
3. executar analisador e comparador;
4. investigar outliers antes de alterar a arquitetura;
5. preferir 2–3 sessões para média mais estável.

Não medir depois de cada ação.

## Privacidade e versionamento

Rollouts podem conter conversa, caminhos locais, prompts e outputs. O bruto não deve ser copiado automaticamente ao repo. Versione apenas relatórios derivados quando isso for deliberado e seguro. Nunca incluir credenciais, tokens ou arquivos de autenticação.

## Invariantes

- telemetria normal é pós-hoc;
- nenhuma tool call extra é necessária durante avanço apenas para medir;
- métricas ausentes permanecem ausentes;
- falha de writer não vira escrita efetiva;
- leitura crua não é mascarada por L1/L2 roteado;
- atribuição de sistema não equivale a fato canônico;
- uma chamada pode pertencer a múltiplos sistemas sem multiplicar `tool_calls`;
- token traffic não é faturamento;
- rollout bruto permanece fora do repo por padrão;
- observabilidade nunca altera o cânone da campanha.
