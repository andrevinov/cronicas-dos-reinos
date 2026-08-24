# Task 33 — Secret NPC Quest Catalog

## Objetivo

A Task 32 entregou o motor e entrou em produção com catálogo real vazio por desenho. A Task 33 popula esse motor sem reativar o antigo Side Quest Gate procedural e sem transformar um roteador quente em spoiler.

O conjunto recorrente é o mesmo grupo de doze NPCs que já possuía curadoria de oportunidade antes da Task 31. Os perfis procedurais antigos continuam `inativo` e servem somente como registro histórico/caracterização; nenhuma semente antiga é promovida automaticamente a cânone.

## Cobertura

O catálogo reservado contém:

- 12 quest-givers recorrentes;
- exatamente 3 side quests canônicas por quest-giver;
- 36 side quests no total;
- 3 tipos distintos por NPC;
- cobertura dos 12 tipos de missão já aceitos pelo lifecycle existente.

Esta documentação deliberadamente não lista IDs, títulos, premissas, pedidos, objetivos, consequências ou combinações NPC→quest.

## Roteamento spoiler-light e fragmentado

A primeira implementação colocou as referências opacas diretamente em `narrador/oportunidades/index.yaml`. O catálogo completo faria esse arquivo ultrapassar o teto quente já congelado. A Task 33 portanto **não aumentou o orçamento**: fragmentou o roteamento por NPC.

O índice de oportunidades mantém somente a declaração compacta de que o engine usa:

```yaml
sidequests_canonicas:
  schema_sidequests_canonicas: 1
  engine: canonical_secret_quest_engine_task32
  detalhes_somente_apos_gate: true
  scheduler: proibido
  rng: proibido
  roteamento: fragmentado_por_npc_task33
```

Quando — e somente quando — um quest-giver catalogado entra como NPC explícito da cena, a camada abre um único fragmento dirigido sob:

```text
narrador/sidequests-canonicas/roteadores/<npc_id>.yaml
```

Esse fragmento contém exatamente três refs e cada ref possui somente:

```yaml
- id: qsc-<opaco>
  gate: narrador/sidequests-canonicas/gates/qsc-<opaco>.yaml
  prioridade: <inteiro>
```

NPC fora do catálogo não abre nenhum roteador Task 33. O índice quente não carrega IDs de quests, títulos ou conteúdo narrativo.

Os gates reservados continuam estritamente mecânicos: identidade da quest/NPC, ponteiro para detalhe e condições de elegibilidade. Conteúdo narrativo só existe nos detalhes em `narrador/sidequests-canonicas/segredos/` e só pode ser carregado pelo engine da Task 32 depois que o gate passar.

## Três por NPC, no máximo duas quentes no snapshot de implantação

A terceira quest não possui `hot: false` nem trava artificial equivalente.

No snapshot em que a Task 33 foi implantada — **17 Eleasis, 1372 DR** — cada um dos doze quest-givers possuía exatamente duas possibilidades mecanicamente quentes quando as condições espaciais correspondentes eram satisfeitas. A terceira dependia de uma mudança real e observável, como:

- relação mais forte;
- data futura;
- conhecimento específico;
- combinação adicional de identidade/mundo.

Esse número não é uma regra eterna. A própria campanha pode legitimamente liberar a terceira quest depois. O contrato permanente é que o desbloqueio venha de um gate canônico real e nunca de uma flag `hot`, sorteio ou manutenção manual de fila.

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

Uma quest da Task 33 é conteúdo novo e deliberadamente autorado, com:

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
→ índice compacto identifica que há catálogo para aquele NPC
→ um roteador opaco dirigido
→ gates determinísticos
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

A população do catálogo preserva os tetos existentes:

- 0 scheduler novo;
- 0 RNG novo;
- 0 estado persistente novo;
- 0 scan global;
- índice de oportunidades continua abaixo do teto quente legado;
- NPC catalogado: no máximo 1 leitura adicional para seu roteador opaco;
- NPC fora do catálogo: 0 leituras Task 33 adicionais;
- 3 refs no roteador dirigido, abaixo do teto de 4 da Task 32;
- no máximo 6 gates por cena e 1 detalhe lido continuam sendo tetos da Task 32.

A fragmentação é justamente a razão pela qual 36 quests podem existir sem transformar o catálogo inteiro em contexto quente.

## Compatibilidade com a Task 32

O algoritmo da Task 32 permanece a autoridade. Seu motor original foi preservado como core e o wrapper público aceita dois formatos:

- fixtures/compatibilidade da Task 32 podem continuar usando `por_npc` inline;
- o repositório real da Task 33 usa roteamento fragmentado por NPC.

Os casos sintéticos da Task 32 continuam executados na suíte. A mudança de armazenamento não altera semântica de gate, oferta, recusa, lifecycle ou efeitos.

## Sigilo operacional

O conteúdo é reservado, não criptografado. O dono do repositório sempre pode abrir os arquivos. A proteção aqui é operacional: hot path, documentação, PR e relatórios de manutenção não precisam expor os detalhes antes de a campanha alcançá-los.
