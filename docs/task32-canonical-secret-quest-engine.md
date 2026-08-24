# Task 32 — Canonical Secret Quest Engine

## Problema

A Task 31 aposentou o mecanismo que transformava encontros em tentativas aleatórias de side quest. Isso resolveu o problema de design do antigo `8 nada : 2 oportunidade`, mas deixou uma lacuna intencional: **de onde vem uma nova side quest?**

A Task 32 cria a infraestrutura, sem ainda criar o catálogo de missões.

A resposta passa a ser:

> uma side quest só pode ficar disponível quando uma fonte canônica reservada, previamente escrita, tiver todos os seus gates satisfeitos pelo estado atual da campanha.

Não existe sorteio de “talvez tenha missão”. Não existe geração de pedido em tempo real. Não existe LLM inventando necessidade porque Ren encontrou um NPC simpático.

## Arquitetura: roteador opaco → gate → detalhe

A camada é dividida em três níveis.

### 1. Roteador opaco

O mesmo `narrador/oportunidades/index.yaml` que já precisa ser aberto para resolver encontro contém `sidequests_canonicas.por_npc`.

Cada entrada futura pode conter **somente**:

```yaml
- id: qsc-0123456789ab
  gate: narrador/sidequests-canonicas/gates/qsc-0123456789ab.yaml
  prioridade: 80
```

O roteador não pode conter:

- título;
- premissa;
- pedido;
- objetivo;
- recompensa;
- consequência;
- segredo;
- solução.

Assim um encontro com NPC conhecido consegue saber, sem abrir conteúdo secreto, se há alguma fonte que mereça avaliação.

Na Task 32 o roteador real entra vazio. A Task 33 o popula.

### 2. Gate reservado compacto

O gate fica sob:

```text
narrador/sidequests-canonicas/gates/
```

Ele contém apenas condições operacionais e um ponteiro para o detalhe. O engine suporta:

- `locais`: IDs canônicos de local;
- `janela`: início/fim absolutos no calendário da campanha;
- `relacao`: mínimos/máximos de afinidade, confiança e risco percebido;
- `conhecimento`: arquivo dirigido + termo + presença/ausência exigida;
- `mundo`: arquivo estruturado + caminho + operador + valor;
- `identidade`: persona relacional, suspeitas e confirmações.

A ordem de short-circuit é:

```text
local
→ data
→ lifecycle/orçamento
→ relação
→ conhecimento
→ mundo
→ identidade
→ detalhe
```

Falhar cedo evita leituras posteriores.

### 3. Detalhe secreto

O detalhe fica sob:

```text
narrador/sidequests-canonicas/segredos/
```

Ele só pode ser aberto quando todos os gates anteriores passam.

O schema contém o conteúdo necessário para a oferta e para os efeitos posteriores, mas toda missão exige:

```yaml
oferta:
  recusa_permitida: true
```

O detalhe também passa por um guardrail estrutural que rejeita campos destinados a escrever fala, decisão, ação, intenção, emoção ou crença de Ren.

## Cena normal

A integração usa a porta já existente:

```text
cronica preparar
→ cena_mundo
→ encontro explícito
→ sidequest_gate_v2 (procedural continua morto)
→ refs opacas
→ Canonical Secret Quest Engine
```

O adapter `sidequest_gate_v2.py` continua sem:

- sorteio;
- leitura do estado de oportunidades;
- perfil procedural;
- Adventure Drought Pressure;
- relógio;
- escrita.

Se o NPC não tiver refs canônicas roteadas, a Task 32 faz **zero leituras adicionais**.

Se houver refs, a camada de cena avalia no máximo seis gates e abre no máximo um detalhe.

## Presença incidental não cria quest

A integração canônica é instalada **depois** de Presença Incidental.

Isso é importante porque presença incidental é apenas candidato espacial. Ela não passa pelo encontro explícito e, portanto, não recebe refs de side quest.

Consequência:

> um NPC que aparece plausivelmente no mesmo lugar não vira quest-giver só porque está ali.

A cena precisa realmente estabelecer o encontro/interação com o NPC.

## Relação efetiva

Gates relacionais reutilizam a Task 26.

Afinidade, confiança e risco são lidos do fragmento exato do NPC. Deltas ainda pendentes no ledger transacional são aplicados em memória antes do teste.

Assim uma mudança relacional ocorrida no mesmo checkpoint pode liberar uma missão sem esperar regeneração de runtime e sem criar estado paralelo.

## Conhecimento dirigido

Condição de conhecimento não usa `buscar`, `rglob` nem scan dos fragmentos.

O autor da quest precisa declarar a fonte exata:

```yaml
conhecimento:
- arquivo: personagens/jogador/conhecimento/<fragmento>.md
  termo: <evidencia-operacional>
  presente: true
```

O engine testa somente esse arquivo e também considera conhecimento ainda pendente no ledger.

O termo do gate deve ser uma marca operacional suficientemente específica. Não usar o arquivo de conhecimento como busca semântica disfarçada.

## Estado do mundo dirigido

Condições de mundo usam fonte e caminho explícitos:

```yaml
mundo:
- arquivo: estado/<arquivo>.yaml
  caminho: frente.estado
  operador: igual
  valor: ativo
```

Operadores iniciais:

- `igual`;
- `diferente`;
- `maior_igual`;
- `menor_igual`;
- `contem`;
- `em`;
- `existe`;
- `verdadeiro`;
- `falso`.

Não existe scan de estado procurando algo que “pareça relevante”.

`runtime/contexto.yaml` e `runtime/cena.yaml`, quando usados explicitamente como fonte, recebem o overlay transacional antes do teste.

## Identidade

A Task 32 reutiliza a semântica da Task 28.

Um gate pode exigir:

- que o NPC esteja se relacionando com `ren`, `shinta` ou outra persona registrada;
- N evidências numa aresta de suspeita;
- presença ou ausência de uma confirmação.

Suspeita continua sendo suspeita. Três pistas não viram confirmação automaticamente.

Isso permite quests que façam sentido somente para uma persona ou para determinado grau de desconfiança, sem tornar NPCs oniscientes.

## Disponibilidade ≠ oferta

Quando o endpoint de cena encontra uma quest elegível, ele projeta a premissa e o pedido para o narrador.

Isso ainda significa apenas:

> o NPC **pode** formular esse pedido organicamente nesta cena.

Se a conversa não chegar a esse assunto, nada é persistido.

Se o pedido realmente entrar na narração aceita, depois de `cronica concluir` registrar o fato, a oferta é materializada pela porta rara:

```bash
poetry run python ferramentas/sidequests_canonicas.py oferecer qsc-0123456789ab \
  --npc <npc_id> --local <local_id>
```

A porta revalida o mesmo gate antes da primeira escrita.

Ela não usa o cooldown procedural antigo.

## Oferta ≠ aceite

A missão persistida entra em `oferecida`.

A resposta de Ren continua usando o lifecycle existente:

```bash
poetry run python ferramentas/oportunidades.py responder <sqc-id> aceitar
poetry run python ferramentas/oportunidades.py responder <sqc-id> adiar
poetry run python ferramentas/oportunidades.py responder <sqc-id> recusar
```

Toda quest canônica permite recusa.

Retry da mesma oferta é idempotente. Uma missão recusada só pode voltar se o detalhe tiver `pode_reabrir: true` e o gate voltar a passar.

## Efeitos depois do aceite

Conteúdo de efeitos não precisa ficar quente durante a oferta.

Só uma missão canônica em estado `aceita` pode abrir:

```bash
poetry run python ferramentas/sidequests_canonicas.py efeitos <sqc-id>
```

A saída alimenta as primitivas já existentes de efeitos de sidequest em `interacoes_mundo.py`.

Portanto a Task 32 não substitui:

- pressões;
- consequências;
- rastros;
- recompensas;
- Protected Core Network;
- classificação de agentes/NPCs.

Ela apenas fornece a origem canônica e o lifecycle da missão.

## Orçamento

Contrato: `baseline/canonical-secret-quest-engine-orcamento.yaml`.

Principais tetos:

- 4 refs opacas por NPC;
- 6 gates por cena;
- 1 detalhe secreto por cena;
- 0 detalhe se nenhum gate passar;
- 0 leitura Task 32 quando não há ref;
- 1 fragmento de NPC por quest-giver;
- 3 condições dirigidas de conhecimento;
- 4 condições dirigidas de mundo;
- 0 escrita na avaliação/preparação;
- 1 escrita na materialização da oferta;
- 0 scheduler;
- 0 RNG;
- 0 scan global;
- 0 novo arquivo de estado persistente.

O limite de duas sidequests `aceita` simultaneamente continua vindo do lifecycle existente.

## Manutenção

Validação fria:

```bash
poetry run python ferramentas/sidequests_canonicas.py check
```

`check` é exceção deliberada ao lazy loading: em manutenção/CI ele abre gates e detalhes para validar schema e referências. A saída traz somente contadores/erros; nunca despeja o conteúdo secreto.

## Relação com a Task 33

A Task 32 entrega o motor com `por_npc: {}`.

A Task 33 poderá adicionar o catálogo escrevendo apenas:

1. refs opacas no roteador;
2. gates compactos;
3. detalhes reservados.

Não deverá alterar o algoritmo de disponibilidade para “fazer uma quest aparecer”. Se uma missão não fica elegível, corrige-se seu contrato/gate canônico — não se adiciona sorteio, reroll, chance de seca ou improvisação procedural.
