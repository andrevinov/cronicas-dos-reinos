# Operações executadas no rollout

A atividade 3 do reparo separa duas unidades que o detector tratava como se
fossem a mesma coisa:

- **chamada de ferramenta** é o envelope nativo do host, identificado por
  `call_id`;
- **operação executada** é cada invocação interna com comando e resultado
  próprios.

Uma chamada `functions.exec` pode conter várias operações. O detector 4.3.0
mantém essa chamada como uma única ocorrência nas métricas nativas e cria uma
operação ordenada para cada `tools.exec_command(...)`. Consumidores modulares
leem as operações; contadores de `tool_calls`, bytes e custo do host continuam
na unidade nativa.

## Identidade e correlação

O identificador estável de uma operação combina `turn_id`, identidade da
chamada nativa e índice declarado. A correlação segue esta ordem:

1. `call_id` seleciona a chamada nativa;
2. o índice `i` do resultado interno seleciona a operação;
3. na ausência de `i`, a ordem declarada associa resultados e operações;
4. resultado ausente, índice repetido ou índice fora da chamada permanece
   incompleto ou ambíguo.

Um resultado com `call_id` explícito desconhecido não é atribuído por FIFO a
outra chamada. Uma retransmissão de resultado terminal incrementa o diagnóstico
de duplicação e não completa a chamada seguinte. Saída intermediária com
identidade de processo ou célula fica como fragmento até chegar um resultado
terminal.

O detector reconhece os envelopes internos emitidos por `Promise.allSettled`,
incluindo `{i, status, value}` e `{i, result: {status, value}}`. Sucesso, erro,
recibos e sinais de domínio são derivados do resultado da própria operação.
O resultado bem-sucedido de uma leitura não promove outra operação que falhou
ou ficou sem resposta. Quando o script encaminha explicitamente uma única saída,
como `text(resultado.output)`, ela é ligada à variável da operação correspondente.
Uma falha do script anterior à invocação marca a operação como não executada.

A interpretação do resultado é uma camada separada, descrita em
[classificação de resultados](classificacao-resultados-rollout.md). Isso impede
que correlação de transporte seja confundida com sucesso operacional.

## Evidência publicada

`analisar-rollout.py` publica `executed_operations_schema: 1` e o bloco
`executed_operations`. O bloco informa chamadas nativas, chamadas agrupadas,
operações, estados de correlação, fragmentos e retransmissões. Cada item contém
os hashes SHA-256 do comando e da saída; o relatório não replica seu conteúdo.
O contrato estrutural está em
`evaluation/schemas/operacoes-executadas-rollout.schema.json`.

Leituras genéricas continuam sem ativar módulos por palavras encontradas no
arquivo. Consultas pelas portas públicas, como `contexto.py`, podem carregar
recibos estruturados e permanecem observáveis mesmo quando sua categoria nativa
é `read_search`.

## Evidência de regressão

Os casos da atividade 3 levam o corpus de 153 para 222 aprovações, reduzindo as
falhas de 73 para 4 em 226 verificações. O snapshot
`evaluation/regressoes-rollout-v1/resultado-atividade-03.json` preserva esse
estado. As quatro reprovações restantes tratam de semântica de falha sem código
de saída, propagação do bloqueio para agregados e aceite final. Elas pertencem
às atividades 4, 6 e 10 e continuam expostas pelo comando estrito.
