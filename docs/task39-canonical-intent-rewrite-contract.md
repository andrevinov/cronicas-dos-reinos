# Task 39 — Canonical Intent & Rewrite Contract

## Problema

A Secret Canon v2 separa situação do mundo de decisão de Ren e já permite adaptar a forma de uma batida futura quando
a causalidade muda. Ainda assim, o contrato anterior trata o `nucleo_obrigatorio` como a própria coisa que precisa
acontecer. Isso é forte o bastante para impedir deriva, mas mistura duas ideias diferentes:

1. **por que a batida existe na história**;
2. **qual forma foi escrita originalmente para cumprir essa função**.

A reforma de side quests precisa alterar essa relação sem apagar a espinha da Parte 1. Uma side quest futura poderá
conduzir Ren naturalmente para uma batida, antecipar uma função narrativa, trocar atores inviáveis, reancorar lugar
ou adiar uma realização dentro de limites. Ela não poderá simplesmente remover aquilo que o cânone precisava produzir.

## Regra central

> A intenção canônica é obrigatória; a realização padrão é substituível somente por rewrite causal autorizado.

Task 39 **não implementa esse rewrite**. Ela apenas instala e valida o contrato que as tasks posteriores poderão usar.
Até existir uma transação de rewrite autorizada, a Task 36 continua sendo a única realização operacional e materializa
seu `nucleo_obrigatorio`/`forma_preferencial` exatamente pelo pipeline atual.

Consequências:

- não existe comando Task 39 para satisfazer, transformar, adiar ou reancorar;
- side quests ainda não recebem autoridade sobre o cânone;
- nenhum evento atual muda de data, ator, local ou conteúdo por causa desta task;
- nenhum scheduler, relógio, estado paralelo ou RNG é criado.

## Camada reservada

O contrato fica separado dos fragmentos narrativos da Task 36:

```text
narrador/arcos/parte_1/eventos-canonicos.yaml
        ↓ catálogo e realização padrão já existentes

narrador/arcos/parte_1/intencoes-canonicas.yaml
        ↓ fronteira Task 39 + passado congelado + regras globais

narrador/arcos/parte_1/intencoes/<evento>.yaml
        ↓ uma intenção compacta por batida futura real
```

A separação é deliberada. Um turno normal continua sem tocar na Task 39. Uma consulta dirigida de intenção abre apenas
o índice Task 39, o catálogo Task 36 e um fragmento compacto de intenção; ela não abre o fragmento narrativo da
realização padrão.

## Intenção canônica

Cada batida futura real declara:

- `id` estável de intenção;
- `funcao`: o papel narrativo que a batida precisa cumprir;
- `criterios_satisfacao`: fatos observáveis suficientes para considerar essa função cumprida.

Critério de satisfação descreve **estado do mundo**, nunca decisão, emoção, crença, vitória ou ação voluntária de Ren.

Uma futura ferramenta de rewrite poderá dizer que a intenção já foi satisfeita por outra causalidade somente se houver
evidência canônica compatível com esses critérios. A existência do modo `satisfazer` no contrato não materializa
satisfação por si só.

## Realização padrão

A realização padrão continua sendo a Task 36:

- `nucleo_obrigatorio`;
- `forma_preferencial`;
- `guardrails`;
- `adaptacao`.

O fragmento Task 39 aponta para esses campos em vez de duplicar a prosa. Isso mantém uma única fonte para a realização
atual e evita custo/contexto duplicado.

Sem rewrite:

```text
intenção
    ↓
realização padrão Task 36
    ↓
agenda → barreira → transação → mundo
```

## Contrato de rewrite

Task 39 reconhece somente quatro modos futuros:

- `satisfazer` — fatos anteriores ou laterais já cumprem a intenção;
- `transformar` — preserva a intenção, mas muda a realização;
- `adiar` — desloca a realização dentro do limite explícito;
- `reancorar` — preserva a intenção e muda sua ancoragem causal, por exemplo local ou contexto.

`cancelar` não é modo válido.

Cada intenção declara ainda:

- se pode integrar uma side quest;
- se admite satisfação antecipada;
- se admite reancoragem local;
- se atores podem ser trocados causalmente;
- atraso máximo permitido.

O teto global inicial é de sete dias. Fragmentos concretos podem impor limites menores. Isso existe para que flexibilidade
não vire adiamento infinito da espinha canônica.

## Passado materializado

Task 39 possui sua própria fronteira de instalação.

Tudo que já havia materializado até essa fronteira é registrado por digest sem alterar os fragmentos da Task 36.
A camada nova não retroage para converter passado em intenção regravável.

Isso também cobre batidas que eram futuras quando a Secret Canon v2 foi escrita, mas já entraram em jogo antes da
instalação da Task 39.

## Economia

Contrato: `baseline/canonical-intent-rewrite-contract-orcamento.yaml`.

Metas:

- 0 leituras Task 39 em turno normal;
- 0 fragmentos Task 39 no `cronica preparar` atual;
- consulta explícita de uma intenção: 2 índices compactos + 1 fragmento de intenção;
- 0 fragmento narrativo Task 36 aberto pela consulta de intenção;
- fragmento de intenção <= 2 KiB;
- índice Task 39 <= 2 KiB;
- 0 scheduler;
- 0 estado persistente;
- 0 RNG;
- 0 scan global no hot path.

O `check` de manutenção pode validar todas as intenções e abrir as realizações padrão. Essa varredura é fria e não
pertence à narração ao vivo.

## Relação com as próximas tasks

Task 40 poderá usar a consulta dirigida para decidir se uma oportunidade emergente merece autoria de side quest.
Task 41 poderá registrar o mini-arco. Task 42 será a primeira camada autorizada a propor e materializar rewrite.

Até lá, Task 39 é deliberadamente incapaz de escrever qualquer alteração no cânone.
