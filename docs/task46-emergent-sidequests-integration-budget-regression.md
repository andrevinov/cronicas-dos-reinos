# Task 46 — Emergent Sidequests Integration & Budget Regression

## Objetivo

Integrar as Tasks 40–45 ao fluxo operacional real sem transformar sidequests num
custo permanente. A origem operacional de novas sidequests passa a ser a âncora
causal emergente da Task40; Task32/33 permanecem somente como legado frio durante
a migração.

## Fluxo preferencial

### Turno comum

Desde a Task47, o turno comum declara explicitamente a decisão negativa:

1. `cronica preparar --cena-id <id> --sem-oportunidade-sidequest`
2. narração
3. `cronica concluir`

`--sem-oportunidade-sidequest` significa que o narrador avaliou a cena e não viu
âncora causal concreta para **nova** sidequest. Essa decisão não chama Task40,
não autora Task41/43/44/45, não lê horizonte canônico adicional e não acrescenta
chamada de orquestração. Desde a Task48, missões já aceitas continuam projetadas
read-only por seus fragmentos Task45. Omitir tanto a decisão positiva quanto a
negativa é inválido pela Task47.

### Turno com oportunidade causal

O narrador só usa `--oportunidade-sidequest` quando a própria cena já produziu
material concreto: pedido, necessidade, risco, pista, dependência, ameaça,
consequência, proposta ou oportunidade. Presença incidental e ausência de quests
não são âncoras suficientes.

A mesma chamada `cronica preparar` devolve o pacote Task40, limitado a 8 KiB e a
três intenções canônicas candidatas. O ticket guarda apenas a âncora + digest; o
pacote secreto não é transportado inteiro no ticket.

Na mesma inferência, o narrador pode autorar:

- quest Task41;
- contrato de recompensa Task43;
- contrato adversarial Task44;
- contrato de progressão Task45.

Se a oferta realmente aparece na narração, a transação enviada a `cronica
concluir` inclui um bloco reservado `sidequest_emergente`. Antes de qualquer
escrita, Task46 recomputa Task40 pelo instante congelado no ticket, exige o mesmo
digest e valida Task41/43/44/45. Sem oferta literal, o bloco deve ser omitido e
nenhuma missão nasce.

## Materialização transacional

Após todas as validações, Task46 cria um journal técnico de recovery, registra o
turno pelo writer normal e instala a sidequest em uma única transação lógica:

1. fragmento Task41;
2. contrato Task43;
3. contrato Task44;
4. contrato Task45;
5. `narrador/oportunidades/estado.yaml` por último.

O estado de oportunidades é o commit point. Crash antes dele pode deixar somente
fragmentos reservados idênticos e recuperáveis; a missão ainda não existe. Retry do
mesmo `cronica concluir` reapresenta o mesmo turno e repara somente os alvos
faltantes.

## Cânone

Task46 não ganha autoridade nova sobre o cânone. A relação autorada na Task41
continua sendo candidatura. Somente o aceite no lifecycle pode criar reserva pela
Task42; somente evidência suficiente pode satisfazer uma intenção. Falha/expiração
libera ou transforma a forma futura segundo Task42/45, nunca apaga a intenção.

## Task32/33

O catálogo pré-escrito e seus roteadores ficam disponíveis como legado frio para
compatibilidade e auditoria, mas deixam de ser `fonte_nova_sidequest`. O hot path
não abre Task33 para descobrir uma missão. A fonte operacional é
`emergente_causal_task40`.

## Orçamento congelado

- turno comum: 2 chamadas de orquestração;
- sem sidequest aceita: leituras Task40–45 no turno comum = 0;
- com sidequest aceita: no máximo 2 fragmentos Task45 read-only pela Task48;
- na conclusão: uma decisão Task49 por missão, até quatro fatos por missão e um único writer de turno;
- fragmentos emergentes no turno comum: 0;
- horizonte canônico adicional no turno comum: 0;
- pacote autoral Task40: <= 8 KiB;
- intenções candidatas: <= 3;
- transcrição lida para planejar: 0;
- scans globais: 0;
- instalação de oferta: 1 transação lógica Task46;
- scheduler novo: 0;
- relógio novo: 0;
- RNG novo: 0.

O CI mede esses contratos por baseline e regressões de rollout. A meta continua
sendo a dupla `cronica preparar` + `cronica concluir`; chamadas adicionais só
existem quando outro sistema já as exige materialmente, nunca porque sidequest
emergente virou polling.

## Regressão integrada posterior — Task 53

O snapshot histórico isolado de “Sete Nomes” prova o caminho completo: oferta e
aceite preexistentes, preparação negativa para oportunidade nova com projeção da
missão ativa, progresso Task49 por Luath, terminal exatamente uma vez, recompensa
Task43 e reação Task50 separada. O orçamento medido está em
`baseline/seven-names-migration-integration-orcamento.yaml`; a regressão pertence
aos perfis `sidequests`, `cronica`, `mundo` e `sessoes`, além de `test-full`.
