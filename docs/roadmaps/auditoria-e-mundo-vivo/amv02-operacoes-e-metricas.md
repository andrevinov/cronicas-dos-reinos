# AMV-02 — Uma classificação operacional e métricas coerentes

**Data:** 2026-10-04. **Status:** proposta. **Dependência:** AMV-01.

## O que implementar

Criar uma representação normalizada de operação observada no analisador existente.
Correlacionar chamada, subprocesso, resultado e saída por identidade estável,
incluindo operações aninhadas em `functions.exec`, lotes, execução assíncrona,
`wait` e resultados parciais. Distinguir chamada nativa da operação de domínio
para evitar multiplicar escritas porque um envelope contém vários resultados.

Aplicar uma única decisão de resultado: sucesso, falha operacional, evidência
insuficiente ou resultado ausente. Usar saída terminal reconhecida pelo contrato,
código de saída e resultado estruturado, com regra explícita para contradições.
YAML `estado: concluido` válido deve ser reconhecido. Envelope `fulfilled`, texto
que menciona sucesso ou uma rolagem bem executada não comprovam commit canônico.

Derivar desse ledger os contadores de leitura, escrita tentada/bem-sucedida/falha,
alvos tocados, retries e proporções. Remover a decisão paralela do classificador
herdado, mantendo adaptadores de leitura necessários para formatos históricos.

Associar incerteza ao domínio afetado e à conclusão que depende dele. Um comando
de inspeção sem resultado de domínio não deve inutilizar arbitrariamente todos
os módulos; uma escrita sem resultado deve bloquear sua conclusão dependente.

## Por que corrige a causa

Hoje a operação pode ser sucesso num relatório e escrita desconhecida em outro.
Quando ambos usam a mesma decisão normalizada, essa divergência desaparece por
construção. Preservar estados desconhecidos impede substituir falta de prova por
zero falhas ou sucesso presumido.

## Prova de correção e aceite

- A reprodução de `cronica concluir` com YAML terminal passa a produzir uma
  operação bem-sucedida e a escrita correspondente, de modo consistente.
- Casos de erro, timeout, saída truncada, resultado ausente e contradição não
  recebem sucesso inferido pelo envelope.
- Sucesso mecânico de ferramenta e sucesso ficcional da rolagem são separados.
- Casos diretos, aninhados, assíncronos, lotes e retries produzem as unidades
  esperadas e nunca duplicam commit ou custo.
- Todas as métricas derivadas fecham com os resultados do ledger; ausência de
  resultado continua contável e identificável.
- Uma consulta desconhecida não apaga uma avaliação independente válida; uma
  dependência canônica desconhecida mantém o bloqueio necessário.

## Onde mudar e o que poderá sair

`_analisar_rollout_core.py`, `analisar-rollout.py`, comparador e consumidores das
métricas. Após prova de compatibilidade, a regra de sucesso duplicada pode sair;
o parser de formato histórico continua se ainda houver consumidor legítimo.
Não retirar os casos históricos: mudar o dono da decisão, preservando cobertura.
