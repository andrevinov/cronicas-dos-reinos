# Classificação de resultados do rollout

A atividade 4 do reparo define o resultado de cada operação antes de qualquer
cobrança de recibo ou nota modular. O detector 4.4.0 publica
`operation_outcomes_schema: 1` e não usa a conclusão do envelope
`functions.exec` como prova de sucesso das operações internas.

## Estados da operação

| Estado | Evidência necessária |
| --- | --- |
| `sucesso` | Código zero, flag/status explícito, prefixo terminal de sucesso ou estado terminal reconhecido |
| `falha_operacional` | Código não zero, flag/status de erro ou marcador terminal de erro, falha ou recusa |
| `nao_executada` | Falha do script demonstravelmente anterior à invocação |
| `resultado_ausente` | Operação observada sem resultado correlacionável |
| `resultado_ambiguo` | Resultado duplicado, índice inválido ou correlação não unívoca |
| `evidencia_insuficiente` | Saída existente sem sinal terminal que autorize sucesso ou falha |
| `erro_detector` | Combinação interna impossível, como sucesso sem execução ou resultado |

`Promise.allSettled` com `status: fulfilled` prova apenas que a promessa entregou
um valor. Se esse valor contém `erro: lote recusado`, a operação é uma falha
operacional mesmo sem `exit_code`. O sucesso de outra operação no mesmo envelope
não altera essa classificação.

Cada ocorrência aponta para `operation_id`, `call_id` pai, turno e índice. A
evidência registra fonte, marcador determinístico e SHA-256 da saída. O conteúdo
bruto não é duplicado no relatório. O contrato público fica em
`evaluation/schemas/resultados-operacoes-rollout.schema.json`.

## Resultado operacional e cobertura modular

Somente uma operação classificada como sucesso pode criar uma atividade modular
esperada. A cobertura da atividade recebe um dos estados abaixo:

- `aplicavel`;
- `nao_aplicavel`, exigindo recibo explícito;
- `evidencia_insuficiente`, para recibo completo `indeterminado`;
- `falha_instrumentacao_recibo_ausente`;
- `falha_instrumentacao_recibo_incompleto`;
- `falha_instrumentacao_recibo_duplicado`.

Uma falha operacional não vira ausência de recibo. Uma operação bem-sucedida
que deveria emitir recibo e não o faz continua sendo falha de instrumentação.
Erro do detector permanece numa categoria própria e não é atribuído ao módulo
executado.

## Evidência de regressão

O snapshot `evaluation/regressoes-rollout-v1/resultado-atividade-04.json`
registra 224 aprovações e 2 reprovações em 226 verificações. A atividade 4
removeu as duas falhas de classificação sem código de saída. As reprovações
restantes são a propagação do bloqueio para o agregado e o aceite final,
reservadas às atividades 6 e 10.

