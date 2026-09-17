# Filas de decisão e atribuição contábil de custo

A atividade 8 remove o ranking global que combinava déficit de desempenho com
tokens rateados. O gerador 4.3.0 publica três filas independentes no contrato
de avaliação 5.0.0. Uma fila responde a uma decisão específica; seus valores
não alteram as outras duas.

## Reparo do medidor

`fila_reparo_medidor_rank` contém somente módulos bloqueados por falha de
instrumentação. A severidade é a proporção entre recibos obrigatórios afetados
— ausentes, incompletos ou duplicados — e unidades avaliativas obrigatórias,
limitada a 100. Uma linha histórica que declare a falha sem contadores conserva
uma unidade afetada para não desaparecer da fila.

O desempate usa, nesta ordem, severidade, quantidade de unidades afetadas e
`module_id`. Tokens e qualidade não participam. Módulos sem falha recebem rank e
pontuação de reparo nulos.

## Problemas da experiência

`fila_experiencia_rank` exige ao menos uma avaliação de qualidade pontuável e
uma `nota_experiencia_interacao_0a100`. A prioridade é `100 - nota`, portanto
uma experiência pior aparece primeiro. O desempate usa o maior denominador
adjudicado e depois `module_id`.

Conformidade operacional, confiança do detector, falha do instrumento e custo
não fabricam posição nessa fila. Sem adjudicação explícita, o módulo permanece
fora dela em vez de receber um valor neutro ou provisório.

## Investigação de custo

`fila_investigacao_custo_rank` ordena módulos com tokens atribuídos maiores que
zero. Cada linha contém `custo_atribuicao_contabil`, com método, tokens, parcela
da sessão, uso permitido e `causalidade_inferida: false`.

O método divide por inteiros o custo de cada turno entre os módulos-pai
observados naquele turno, mantendo a classe de controle separada. A soma fecha
contabilmente com a telemetria narrativa, mas não mede custo marginal e não
prova que um módulo causou os tokens do turno. A fila serve para escolher onde
investigar o custo com evidência adicional.

## Contrato do pacote

`scorecard.filas_prioridade`, schema 1, registra as três sequências e declara
`ranking_global_existe: false` e `custo_e_experiencia_misturados: false`. Os
ranks são contíguos dentro de cada fila. Um módulo pode aparecer em mais de uma
fila porque as decisões são independentes.

As linhas de `resumo-modulos.json` preservam a ordem do catálogo. Os campos
legados `prioridade_rank` e `pontuacao_prioridade_0a100` ficam nulos, com
`prioridade_legada_descontinuada: true`, para que leitores antigos não
interpretem um dos novos ranks como substituto do ranking misto.

O contrato estrutural está em
`evaluation/schemas/filas-prioridade-v2.schema.json`. O painel e o relatório
mostram as três filas e identificam tokens como custo contábil não causal.

## Regressão

Os testes metamórficos alteram somente os tokens e exigem que as filas de
reparo e experiência permaneçam iguais. Também verificam adjudicação obrigatória
para a fila de experiência, ordem estável do catálogo, descontinuação do ranking
global, ranks contíguos e a declaração explícita de não causalidade.

O snapshot `evaluation/regressoes-rollout-v1/resultado-atividade-08.json`
preserva o corpus de desenvolvimento. O aceite final continua reservado à
atividade 10.
