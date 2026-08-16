# Etapa 11 — baseline estrutural da telemetria externa

A Etapa 11 torna a economia de contexto mensurável sem adicionar trabalho ao loop narrativo.

## Contrato

A sessão ao vivo **não escreve telemetria operacional por padrão**.

O fluxo de medição é:

```text
rollout nativo do Codex
→ analisar-rollout.py
→ comparar-rollouts.py
→ relatório em stdout
```

`contexto.py` também deixa o log local desligado por padrão; `--log-local` existe apenas para diagnóstico explícito.

## Baseline pré-refatoração

Fonte derivada de `rollout-2026-08-15T10-13-52-01a0058e-afe1-79e3-a75c-fc7108814a1f.jsonl`:

- 21 turnos totais;
- 254 inferências;
- 358 tool calls;
- 34.011.686 input tokens;
- 32.287.488 cached input tokens;
- 1.724.198 input tokens não-cache aproximados;
- 4 compactações.

Nos 13 avanços narrativos auditados:

- 203 inferências;
- 15,615 inferências por avanço;
- 306 tool calls;
- 23,538 tool calls por avanço;
- 27.908.038 input tokens;
- 26.650.112 cached input tokens;
- 1.257.926 input tokens não-cache aproximados;
- 151 read/search;
- 63 write;
- 51 dice;
- 36 validation;
- 5 other;
- 109 alvos de escrita observados;
- 8,385 alvos de escrita por avanço;
- cerca de 302.484 caracteres de payload de patch.

A representação estruturada está em `baseline/rollout-2026-08-15.json`.

## Metas iniciais

`baseline/metas-rollout-pos-refatoracao.json` estabelece:

- piso de 70% de redução de input bruto por avanço;
- faixa desejada de 75–85%;
- no máximo 5 inferências por avanço;
- no máximo 8 tool calls por avanço;
- no máximo 2 alvos de escrita no turno comum;
- zero escrita em estado canônico durante turno comum;
- transcrição praticamente ausente da leitura normal;
- pelo menos 80% dos avanços resolvidos em L0–L2.

## Métricas nativas versus inferidas

Contadores de token, cache, inferências, tool calls e compactações vêm diretamente do rollout.

Categorias de ferramenta, caminhos, alvos de escrita e níveis de acesso podem depender de classificação observacional dos comandos/tool outputs. O relatório identifica essa distinção.

## Regra de comparação

A comparação principal é **por avanço narrativo**, não por tamanho total do rollout.

Várias sessões novas podem ser passadas juntas ao comparador; os contadores são agregados e as médias são recalculadas sobre o total de avanços.

## Limite epistemológico

O repositório não converte redução de input bruto em economia comercial exata.

Em especial:

- cached input e uncached input são reportados separadamente;
- `input - cached` é aproximação operacional;
- a meta de economia efetiva discutida durante a reforma será avaliada à luz dessas métricas, não tratada como fórmula de faturamento.

## Segurança

Rollouts brutos não são versionados automaticamente. Eles podem conter conversa, prompts, caminhos locais e material reservado.

Esta baseline não altera nenhum fato da campanha.
