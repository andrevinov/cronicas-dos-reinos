# RM-07 — Contexto e memória

## Status e dependências

**Implementada; gates próprios verdes.** Depende das RM-01–RM-02.

## Problema

Economia de contexto e fidelidade de memória são determinantes para custo,
latência e continuidade, mas hoje aparecem apenas como métricas globais ou
ferramentas isoladas. Nenhum módulo assume o resultado de ponta a ponta.

## Objetivo

Criar `context_and_memory`, responsável por entregar o menor contexto suficiente
e persistir fatos novos na camada correta, sem misturar leitura, conhecimento e
autoridade.

## Escopo

- escada L0–L5 e justificativas de aprofundamento;
- contexto e memória de cena;
- retomada fria;
- consultas dirigidas de NPC, local, relação, conhecimento e continuidade;
- memória durável criada no concluir;
- separação entre narrador, facção, NPC, Ren e jogador;
- detecção de contexto obsoleto, leitura redundante e fato não persistido.

## Contrato

O módulo recebe uma necessidade concreta e produz:

- contexto suficiente com fontes e nível de acesso;
- lacunas ainda indeterminadas;
- evidência de que não houve leitura acima do necessário;
- no concluir, recibo dos fatos duráveis efetivamente persistidos.

Leitura e escrita permanecem subcapacidades distintas. Uma não prova a correção
da outra.

## Indicadores

- proporção de turnos resolvidos em L0–L2;
- leituras RAW e L4T por oportunidade válida;
- tokens de contexto total e não-cache;
- precisão e cobertura de recuperação;
- contexto obsoleto ou redundante;
- fatos duráveis esperados versus registrados;
- duplicação e vazamento entre camadas de conhecimento;
- completude de retomada fria.

## Testes

- consultas sobem a escada somente após lacuna demonstrada;
- transcrição não é aberta para retomada quando L4 basta;
- memória de cena evita nova leitura equivalente;
- fato novo persistente é registrado exatamente uma vez;
- rumor, possibilidade e segredo não viram fato de Ren;
- operação read-only não altera fontes ou runtime.

## Definition of done

- módulo aparece em todo turno com demanda de contexto, inclusive quando resolve
  economicamente em L0;
- custo de leitura e qualidade de memória têm métricas separadas;
- não há scan global novo;
- memória canônica continua nas fontes atuais;
- perfis de contexto, memória e retomada ficam verdes.
