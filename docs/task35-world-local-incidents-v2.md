# Task 35 — World & Local Incidents v2

## Objetivo

Criar situações sérias e imediatas em Ravens Bluff sem depender de side quest e sem transformar microeventos cotidianos em combate por acidente.

A camada cobre, entre outros, **briga, roubo, perseguição, acidente, incêndio, desabamento, criança em perigo, extorsão, problema com guarda, tumulto e ferimento**.

Um incidente é uma situação que pode exigir decisão agora. Ele pode terminar naquela mesma cena. Não nasce com lifecycle de quest.

## Duas escalas

A Task 35 mantém dois baralhos de ocorrência independentes:

- **municipal/global** — situações que podem atravessar ou repercutir no ponto da cidade onde Ren está;
- **local** — situações produzidas pela ecologia específica do local atual.

A avaliação ocorre somente quando a cena já possui contexto espacial canônico. O baralho municipal é tentado primeiro. Se ele não materializa candidato, o baralho local pode ser avaliado. **No máximo um incidente** aparece por cena.

Frequência-base:

- global: `11 rotina : 1 incidente`;
- local: `7 rotina : 1 incidente`.

Os baralhos são determinísticos e sem reposição dentro do ciclo. Não existe `random`, scheduler ou relógio de incidentes.

## Incidente não é microevento

O Local Microevent Deck continua responsável por textura cotidiana: entrega, serviço, fluxo, manutenção, pequenos movimentos e ambiente.

A Task 35 é outra camada porque aceita risco real e urgência concreta. Ela não relaxa os guardrails do microevento. Um microevento continua sem combate/quest/recompensa automáticos, mesmo depois desta task.

As duas camadas podem ser avaliadas na mesma cena, mas o narrador deve privilegiar coerência: se um incidente sério entra em primeiro plano, textura banal não precisa disputar foco narrativo.

## Ecologia local

As cartas usam o perfil ecológico já carregado pela cena:

- `acesso`;
- `tags`;
- `canais_microevento`;
- `atores_comuns`.

Participantes automáticos são apenas **papéis anônimos plausíveis** (`trabalhador`, `guarda`, `cliente`, `vizinho` etc.). A Task 35 nunca escolhe NPC nomeado. Um NPC conhecido só participa se outra camada/cânone já o colocou ali.

## Condições persistentes

A Task 35 é instalada **depois** da Task 34 e reutiliza `condicoes_mundo` já projetadas na cena. Portanto não abre um segundo estado ambiental.

Condições não alteram a frequência de incidentes. Elas somente podem habilitar cartas cujo contexto depende de marcadores, por exemplo:

- `chuva_forte` → acidente agravado por piso/visibilidade;
- `multidao` → pressão perigosa de multidão;
- `precos_tensionados` → conflito de abastecimento;
- `patrulha_reforcada` → abordagem sob regime excepcional.

Sem o marcador, a carta fica fora do pool. Com o marcador, ela entra no pool normal — ainda depende do baralho de ocorrência.

## Intervenção imediata ≠ side quest

Cada incidente fornece uma premissa e várias `rotas_observaveis`.

Exemplos de respostas possíveis incluem:

- intervir fisicamente;
- proteger terceiro;
- negociar;
- chamar ajuda/autoridade;
- observar;
- seguir suspeito;
- retirar-se;
- não intervir.

Essas rotas não são escolhas fechadas nem menu para o jogador; servem para impedir que o narrador trate a primeira solução imaginada como obrigatória.

Resolver a situação pode encerrar tudo ali. Criar uma side quest exige continuar usando o Canonical Secret Quest Engine das Tasks 32–33, com fonte canônica própria. Task 35 nunca registra uma missão automaticamente.

## Combate

Incidente pode produzir combate se a ficção e a resposta de Ren levarem a isso. Ele **não nasce como combate obrigatório**.

Guardrail:

> se a oposição for deliberadamente esmagadora, a cena precisa mostrar pelo menos uma saída plausível — fuga, cobertura, negociação, ajuda, esconderijo ou outra rota observável.

Isso não garante vitória e não reduz automaticamente todo inimigo ao nível de Ren.

## Preparação transacional

A integração reutiliza `cena_mundo.py`:

```text
presença / sidequests
→ condições persistentes
→ Task 35
   → sem contexto espacial: zero leitura
   → com local: ler index.yaml + estado.yaml
      → tentar baralho global
      → se não houver candidato, tentar baralho local
      → no máximo um incidente
```

Durante `preparar`, a escrita do estado Task35 é sombreada junto das demais mutações reativas. A confirmação refaz a preparação e só então consome as fichas.

A mesma `cena_id + local_id` já registrada reutiliza o resultado, impedindo consumo duplicado em retry.

## Cânone

O sorteio é apenas candidato operacional. O incidente só se torna fato quando é realmente narrado/aceito pela cena e registrado pelo pipeline transacional normal.

A Task 35 não concede automaticamente:

- conhecimento;
- reputação;
- relação;
- recompensa;
- item;
- side quest;
- segredo;
- presença de NPC nomeado.

Essas consequências continuam nas respectivas camadas existentes.

## Estado

Arquivos:

```text
narrador/incidentes-v2/index.yaml
narrador/incidentes-v2/estado.yaml
```

O estado guarda somente posição dos baralhos e histórico recente compacto. Não é fonte narrativa independente.

## Custo

Contrato: `baseline/world-local-incidents-v2-orcamento.yaml`.

- 0 tool calls extras;
- cena sem local: 0 leituras Task35;
- cena espacial: 2 leituras pequenas (`index` + `estado`);
- no máximo 1 incidente por cena;
- índice <= 24 KiB;
- estado <= 16 KiB;
- histórico recente <= 48;
- 0 scheduler;
- 0 scan global.

A Task 35 foi deliberadamente implementada sobre o `main` pós-Task 34. A Task 36 deve ser atualizada/revalidada depois do merge desta task, e pode tratar uma crise Task35 já materializada como satisfação causal de um núcleo equivalente em vez de duplicar artificialmente o mesmo desastre.
