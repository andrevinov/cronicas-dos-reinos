# Telemetria externa de rollouts

Este documento define como medir o custo operacional de **Crônicas dos Reinos** sem introduzir telemetria no loop narrativo.

## Princípio

A campanha não deve gastar uma interação para medir a própria interação.

Durante narração ao vivo, não criar `runtime/telemetria.jsonl`, não atualizar dashboards, não calcular médias e não executar analisadores de rollout. O registro nativo do Codex já contém os eventos necessários para uma análise posterior.

A telemetria normal é, portanto, **pós-hoc e somente leitura**:

```text
sessão de jogo
→ rollout-*.jsonl nativo do Codex
→ analisar-rollout.py
→ comparar-rollouts.py
→ decisão de engenharia
```

`contexto.py` também não grava mais `runtime/consultas-contexto.jsonl` por padrão. Esse log local existe somente como diagnóstico opt-in com `--log-local`.

## Ferramentas

### Analisar um rollout

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

A ferramenta não altera o repositório. Para guardar um relatório, redirecione explicitamente a saída para um caminho de sua escolha.

### Comparar com a baseline pré-refatoração

```bash
python3 ferramentas/comparar-rollouts.py ~/.codex/sessions/.../rollout-novo.jsonl
```

A baseline padrão é `baseline/rollout-2026-08-15.json` e as metas padrão estão em `baseline/metas-rollout-pos-refatoracao.json`.

Também é possível combinar várias sessões pós-refatoração:

```bash
python3 ferramentas/comparar-rollouts.py \
  rollout-sessao-004.jsonl \
  rollout-sessao-005.jsonl \
  rollout-sessao-006.jsonl
```

Os valores são agregados e normalizados **por avanço narrativo**, evitando que uma sessão maior pareça automaticamente mais cara.

## O que é medido diretamente pelo rollout

São tratados como métricas nativas/exatas dentro do arquivo:

- eventos de inferência (`token_count` / `last_token_usage`);
- input tokens;
- cached input tokens;
- output tokens;
- reasoning output tokens;
- número de tool calls;
- compactações;
- tamanho do `AGENTS.md` observado em `world_state`, quando presente.

O analisador também calcula média, pico e p95 de input por inferência, input não-cache aproximado (`input - cached`) e tool-output bytes anexados ao histórico do modelo.

`input - cached` é uma aproximação operacional. **Não é fórmula de faturamento nem de quota semanal.**

## O que é inferido pelo analisador

Alguns dados não são syscall tracing e precisam ser classificados a partir dos comandos e resultados registrados:

- `read_search`, `write`, `dice`, `validation` e `other` como categorias de **tentativa**;
- consultas roteadas por `contexto.py` / `contexto-buscar-muitos.py`;
- leituras cruas com `rg`, `sed`, `grep`, `cat`, `find`, `ls`, `git show` ou equivalentes;
- descoberta de interface/schema por `--help` ou leitura direta de `ferramentas/*.py`;
- caminhos mencionados em operações de leitura/escrita;
- alvos implícitos de ferramentas conhecidas, por exemplo `turno.py registrar` → transcrição + buffer;
- leitura de transcrição;
- nível L1/L2/L3/L4/L4T quando o comando ou sua saída o identifica.

Desde o schema 3, o analisador também tenta correlacionar **chamada e resultado** pelo `call_id` nativo. Quando o ID não existe em um rollout antigo, usa pareamento FIFO apenas como fallback. Exit code, status explícito e respostas inequívocas (`OK`, `Done!`, `FALHA`) permitem separar:

- escrita tentada;
- escrita concluída;
- escrita falha;
- escrita cujo resultado não pôde ser determinado.

`write_target_touches` e `canonical_write_target_touches` representam agora somente alvos de **escritas concluídas**. `attempted_write_target_touches` preserva a visão das tentativas. O mesmo princípio vale para `transcript_read_calls`, acompanhado por `attempted_transcript_read_calls`.

Esses campos aparecem no relatório como **observational inference**. Servem para engenharia e regressão operacional, não para alegar precisão contábil absoluta.

## Leitura roteada versus leitura crua

Uma consulta L2 não deve esconder leitura direta feita no mesmo turno. Por isso o schema 3 mantém duas dimensões:

```text
contexto roteado = uso da API operacional de contexto
leitura crua     = abertura/busca direta em arquivos
```

Se um turno executa `contexto.py cena` e depois usa `rg` ou `sed`, sua classificação passa a ser, por exemplo, **`L2+RAW`**. Se só há leitura crua sem nível roteado identificável, aparece como `RAW`.

Consequentemente, `fraction_turns_l0_l2` significa agora **L0–L2 limpo**: `L2+RAW` não satisfaz a meta. Isso impede que o acesso direto ao repositório seja mascarado por uma consulta barata feita antes dele.

## Como um avanço narrativo é reconhecido

Há duas rotas complementares:

1. compatibilidade com o prompt legado usado na baseline de 15/08 e uma heurística textual pequena;
2. presença de chamada real a `ferramentas/turno.py registrar`.

`turno.py registrar --help` não é sinal de avanço narrativo nem escrita: é descoberta de interface.

Se a forma de pedir avanço mudar radicalmente e `turno.py` não aparecer, use:

```bash
python3 ferramentas/analisar-rollout.py rollout.jsonl \
  --narration-regex 'regex que identifica os turnos desejados'
```

O comparador aceita a mesma opção.

## Métricas mais importantes

### 1. Input bruto por avanço

É a soma de input tokens de todas as inferências pertencentes ao avanço, dividida pela quantidade de avanços.

Meta técnica: redução de **75–85%**; piso inicial de aprovação: **70%**.

### 2. Inferências por avanço

É o melhor indicador simples de round-trip amplification.

Baseline pré-refatoração: aproximadamente 15,6 por avanço narrativo. Meta: **até 5**.

### 3. Tool calls por avanço

Baseline: aproximadamente 23,5. Meta inicial: **até 8**, sem sacrificar regra, agência ou continuidade.

### 4. Leitura roteada, crua e descoberta de schema

`routed_context_calls` mede uso das portas de contexto; `raw_read_calls` mede acesso direto aos arquivos; `schema_discovery_calls` mede o custo de a IA precisar descobrir como usar as próprias ferramentas.

Não existe número pré-refatoração confiável para essas três métricas, portanto a baseline aparece como `n/d`. No pós-refatoração, elas servem para localizar o próximo gargalo sem confundir API operacional com investigação da infraestrutura.

### 5. Alvos de escrita por avanço

A arquitetura transacional pretende manter o avanço comum em:

```text
sessoes/NNN/transcricao.md
runtime/eventos-pendentes.jsonl
```

Meta: **até 2 alvos concluídos**, com **zero escrita canônica concluída** durante o turno comum. Uma tentativa que falhou permanece visível nos contadores de tentativa/falha, mas não é fingida como alteração persistida.

### 6. Leitura de transcrição

Transcrição é L4T/evidência bruta, não memória operacional.

Meta de narração comum: praticamente zero; a regra automática aceita no máximo 0,05 leitura concluída por avanço para não transformar uma investigação histórica legítima isolada em falso alarme quando várias sessões forem agregadas.

### 7. Distribuição L0–L2 limpa

O analisador calcula o nível máximo observado por avanço. L0 é inferido quando não há read/search observado naquele turno.

Meta: **ao menos 80% dos avanços em L0–L2 limpo**.

`L1+RAW`, `L2+RAW` etc. são deliberadamente excluídos desse percentual. Consultas antigas que não permitem determinar o nível nem caracterizar leitura crua aparecem como `UNCLASSIFIED`.

## Baseline pré-refatoração

`baseline/rollout-2026-08-15.json` preserva dois tipos de medição:

- contadores nativos exatos do rollout;
- auditoria manual já realizada sobre os 13 avanços narrativos.

A auditoria manual registra, entre outros, 203 inferências, 306 tool calls, 151 read/search, 63 write, 51 dice, 36 validation, 5 other, 109 alvos de escrita observados e aproximadamente 302.484 caracteres em payloads de patch.

Campos que não foram preservados com precisão suficiente na baseline antiga — inclusive sucesso de writer, leitura crua separada e distribuição formal L0–L4T — ficam como `n/d` na comparação. **O comparador não inventa um número antigo.**

## Metas e interpretação

`baseline/metas-rollout-pos-refatoracao.json` contém os gates operacionais iniciais.

O comparador exibe `OK`, `FALHA` ou `N/D` para cada regra. Uma falha não significa automaticamente regressão de campanha: serve como pista para abrir o rollout e entender o motivo.

A meta de aproximadamente 65% de economia efetiva discutida durante a reforma **não é calculada automaticamente** porque a relação entre input bruto, cache e limites comerciais não é uma fórmula pública inferida pelo repositório. O comparador mostra separadamente redução de input bruto, input não-cache aproximado, rounds, tools e escrita.

## Momento recomendado para medir

Não medir depois de cada ação.

Depois que a campanha voltar:

1. jogar uma sessão real com a arquitetura nova;
2. localizar o rollout correspondente;
3. executar o analisador e o comparador;
4. não modificar a campanha por causa de um único outlier sem investigar o turno;
5. após 2–3 sessões, comparar os rollouts em conjunto para obter uma média mais estável.

## Privacidade e versionamento

Rollouts podem conter conversa, caminhos locais, prompts, tool outputs e outros detalhes da sessão. O rollout bruto **não deve ser automaticamente copiado para o repositório**.

Versione apenas baselines/relatórios derivados quando isso for deliberado e não expuser material que deva permanecer local.

Nunca incluir `~/.codex/.env`, credenciais, tokens ou arquivos de autenticação.

## Invariantes

- telemetria normal é pós-hoc;
- nenhuma tool call extra é necessária durante um avanço apenas para medir o avanço;
- `contexto.py` não grava log local por padrão;
- baseline e rollout novo são comparados por turno narrativo;
- métricas ausentes ficam ausentes;
- falha de writer não vira escrita efetiva por inferência;
- leitura crua não pode ser escondida por um nível L1/L2 roteado;
- token traffic não é apresentado como faturamento;
- o rollout bruto permanece fora do repo por padrão;
- observabilidade nunca deve alterar o cânone da campanha.
