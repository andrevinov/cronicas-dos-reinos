# AMV-02 — Uma classificação operacional e métricas coerentes

**Data:** 2026-10-04. **Status:** concluída em 2026-10-04; G0 pendente.
**Dependência:** AMV-01.

## Entrega executada

`resultados_operacoes.py` é o dono da decisão terminal, compartilhada pelo ledger
moderno e pelo adaptador histórico. Os contadores de leitura/escrita, alvos,
proporções e linhas por turno são derivados das mesmas operações normalizadas.
Comparador e geração das linhas do dashboard usam categorias de operação;
chamadas nativas, tokens e custo observado conservam sua unidade original.
Detector atualizado para 4.7.0 e gerador para 4.5.0.

Resultados de lotes são correlacionados por índice; `wait`, `write_stdin` e
fragmentos atualizam a operação original, inclusive em outro turno. Resultado
terminal repetido não cria uma operação. Replay explícito conta como execução
bem-sucedida, com contador próprio e sem novos alvos escritos. IDs de sessão/célula
desconhecidos e subprocessos ainda abertos não recebem sucesso presumido.

YAML/JSON terminal válido é reconhecido; erro explícito prevalece sobre sinal de
sucesso contraditório. Saída truncada não comprova sucesso. Citação de conclusão
em documentação e `fulfilled` do envelope não são prova de commit. Resultado
ficcional de dado permanece separado do sucesso da execução da ferramenta.
Alvos continuam inferências identificadas por comando, não prova de cada byte
alterado no save. Código JavaScript não é executado para descobrir operações:
correlação depende das identidades e dos comandos observáveis.

O ledger identifica categoria, módulos dependentes e escrita canônica. Uma
inspeção auxiliar inconclusiva produz limitação; uma preparação, rolagem ou
escrita canônica inconclusiva bloqueia sua conclusão dependente. Pacotes antigos
sem metadados de escopo conservam o bloqueio prudente. A nova decisão participa
dos hashes obrigatórios de proveniência do gerador.

## Evidência da entrega

- [Resultado AMV-02](../../../evaluation/aceite-avaliacao-v1/resultado-amv02.json):
  a regressão YAML passou; restam seis divergências das AMV-03–05. Expectativas
  e resultado inicial da AMV-01 permanecem preservados.
- [Reanálise operacional da 024](../../../evaluation/aceite-avaliacao-v1/operacoes-s024-amv02.json):
  as 15 escritas anteriormente desconhecidas agora são **11 sucessos, 2 falhas
  e 2 resultados desconhecidos**. As contagens fecham com o ledger. As 62 chamadas
  nativas e os tokens registrados permanecem iguais; o pacote histórico não foi
  reescrito. Corte e sete âncoras da fonte foram novamente verificados.
- [Verificação](../../../evaluation/aceite-avaliacao-v1/verificacao-amv02.json):
  **163 testes focados passaram**, incluindo formatos históricos, lotes,
  assíncronos, retries, contradições, escopo e consumidores. As **226 comparações**
  do corpus anterior passaram. Hash da árvore protegida da campanha preservado.

As verificações de versão do detector passaram a exigir coerência com a versão
instalada, sem fixá-la para sempre em 4.6.0. A regressão de correlação ambígua usa
uma preparação dependente, mantendo o bloqueio exigido; leituras auxiliares
receberam um controle separado que preserva conclusões independentes.

**Limite:** correção operacional demonstrada; associação de recibos, avaliação
semântica e apresentação completa da 024 permanecem nas AMV-03–05. G0 pendente.
Esta etapa verificou os domínios afetados; a última suíte integral, registrada na
AMV-01, contém cinco casos preexistentes em falha. Nenhum gate foi aposentado.

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
