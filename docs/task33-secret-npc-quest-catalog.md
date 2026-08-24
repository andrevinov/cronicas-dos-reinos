# Task 33 — Secret NPC Quest Catalog

## Objetivo

A Task 32 entregou o motor e entrou em produção com catálogo real vazio por desenho. A Task 33 popula esse motor sem reativar o antigo Side Quest Gate procedural e sem transformar o roteador quente em spoiler.

O conjunto recorrente é o mesmo grupo de doze NPCs que já possuía curadoria de oportunidade antes da Task 31. Os perfis procedurais antigos continuam `inativo` e servem somente como registro histórico/caracterização; nenhuma semente antiga é promovida automaticamente a cânone.

## Cobertura

O catálogo reservado contém:

- 12 quest-givers recorrentes;
- exatamente 3 side quests canônicas por quest-giver;
- 36 side quests no total;
- 3 tipos distintos por NPC;
- cobertura dos 12 tipos de missão já aceitos pelo lifecycle existente.

Esta documentação deliberadamente não lista IDs, títulos, premissas, pedidos, objetivos, consequências ou combinações NPC→quest.

## Roteador spoiler-light

`narrador/oportunidades/index.yaml` continua sendo a única porta quente. Sob `sidequests_canonicas.por_npc`, cada entrada contém somente:

```yaml
- id: qsc-<opaco>
  gate: narrador/sidequests-canonicas/gates/qsc-<opaco>.yaml
  prioridade: <inteiro>
```

O roteador não contém título, tipo, premissa, pedido, objetivo, consequência ou efeito.

Os gates reservados continuam estritamente mecânicos: identidade da quest/NPC, ponteiro para detalhe e condições de elegibilidade. Conteúdo narrativo só existe nos detalhes em `narrador/sidequests-canonicas/segredos/` e só pode ser carregado pelo engine da Task 32 depois que o gate passar.

## Três por NPC, no máximo duas quentes

A terceira quest não possui `hot: false` nem trava artificial equivalente.

No checkpoint atual da campanha, cada um dos doze quest-givers possui exatamente duas possibilidades mecanicamente quentes quando as condições de cena correspondentes são satisfeitas. A terceira permanece fria porque exige uma mudança real e observável, como:

- relação mais forte;
- data futura;
- conhecimento específico;
- combinação adicional de identidade/mundo.

Assim, a campanha pode desbloquear conteúdo organicamente sem scan, sorteio ou manutenção manual de uma fila de quests.

`hot` é uma propriedade **derivada** do estado corrente. Nunca é persistida.

## Variedade

O catálogo usa os tipos já conhecidos por `oportunidades.py` e cobre todos eles ao menos uma vez:

- busca;
- proteção;
- investigação;
- resgate;
- entrega;
- aquisição;
- exploração;
- mediação;
- favor;
- problema cotidiano;
- segredo pessoal;
- trabalho profissional.

Cada NPC recebe três tipos diferentes. Isso evita que todo quest-giver se comporte como distribuidor de entrega ou investigação genérica.

## Curadoria, não promoção procedural

Os antigos `narrador/oportunidades/perfis/*.yaml` ajudaram somente a preservar voz, profissão e classe de problemas plausíveis para cada NPC. Eles continuam com estatuto de sementes não canônicas e seus registros no índice permanecem inativos.

Uma quest da Task 33 é um conteúdo novo e deliberadamente autorado, com:

- gate canônico explícito;
- detalhe reservado próprio;
- recusa sempre permitida;
- consequência sem Ren que não força participação;
- guardrails de agência e de não-escalada gratuita.

Nenhuma quest é criada por copiar mecanicamente uma necessidade do sistema aposentado.

## Agência e lifecycle

Todos os detalhes declaram `recusa_permitida: true`.

A sequência continua sendo a da Task 32:

```text
NPC explícito
→ refs opacas
→ gate determinístico
→ no máximo um detalhe reservado
→ disponibilidade
→ NPC pode ou não fazer o pedido na ficção
→ oferta só é registrada após o pedido realmente narrado
→ Ren decide aceitar, adiar ou recusar
```

Aceite, adiamento, recusa, conclusão, falha e expiração continuam no lifecycle de `oportunidades.py`. Limite de duas side quests aceitas permanece inalterado.

## Efeitos e recompensas

A Task 33 não cria um segundo sistema de efeitos ou recompensa. O schema reservado continua capaz de apontar efeitos que, depois do aceite, passam pelo pipeline já existente da Task 32/`interacoes_mundo.py`.

O catálogo inicial não precisa fabricar recompensa mecânica para justificar cada história: recompensa, pista, relação, consequência ou efeito só devem existir quando o conteúdo concreto exigir e pelos sistemas já autorizados.

## Custo

Contrato: `baseline/secret-npc-quest-catalog-orcamento.yaml`.

A população do catálogo altera conteúdo frio, não a arquitetura:

- 0 scheduler novo;
- 0 RNG novo;
- 0 estado persistente novo;
- 0 scan global;
- 3 refs por quest-giver, abaixo do teto de 4 da Task 32;
- no máximo 6 gates por cena e 1 detalhe lido continuam sendo tetos da Task 32;
- encontro com NPC sem refs continua com zero leituras Task 32 adicionais.

## Sigilo operacional

O conteúdo é reservado, não criptografado. O dono do repositório sempre pode abrir os arquivos. A proteção aqui é operacional: hot path, documentação, PR e relatórios de manutenção não precisam expor os detalhes antes de a campanha alcançá-los.
