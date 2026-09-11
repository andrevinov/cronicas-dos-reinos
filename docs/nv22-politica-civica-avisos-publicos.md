# NV-22 — Política cívica e avisos públicos

## Objetivo

A NV-22 dá às instituições de Ravens Bluff um pipeline cívico explícito sem
transformar o governo em uma sonda global de conteúdo. Uma medida só existe
quando uma instituição autorizada a propõe com motivo, causa institucional e
escopo. A ausência de agenda institucional continua sendo um resultado normal.

O estado é compacto e vive na raiz `politica_civica` de
`estado/estado-atual.yaml`, usando o writer transacional e o journal já
existentes. Não há scheduler, fila ou RNG paralelo.

## Registro institucional

`cenario/regioes/ravens-bluff/instituicoes-civicas.yaml` parte da estrutura
social já canônica em `faccoes.md` e registra, para fins operacionais da NV-22:

- Lord Mayor e gabinete;
- Council of Lords;
- Courts / Chancelaria;
- City Guard;
- Harbor Administration.

Advisory Council e Night Watch permanecem no registro como não autorizados a
originar medidas. Isso evita promover influência, patrulha ou canal de entrega a
poder legislativo por conveniência narrativa.

A competência modelada é deliberadamente conservadora. Ela não pretende
reconstruir toda a teoria constitucional de Ravens Bluff; apenas impede autoria
sem autoridade e restringe tipos/canais plausíveis.

## Ciclo de vida

Uma medida possui histórico append-only e uma fase atual. Transições aceitas:

```text
proposta -> em_avaliacao -> aprovada -> vigente -> publicada
     \-----------------> aprovada

publicada -> expirada | revogada | substituida
```

A fase `publicada` não pode ser criada por uma transição vazia: a primeira
passagem de `vigente` para `publicada` ocorre no mesmo delta que cria uma
publicação concreta. Uma substituição referencia outra medida já registrada.

Campos centrais de uma medida — instituição, tipo, título, motivo, causa
institucional, escopo, instante de criação e eventual entrada de catálogo — são
imutáveis depois da proposta.

## Agenda institucional

`politica_civica.propose_plan()` adiciona no máximo um plano pendente por medida.
Cada plano tem ação, prazo e motivo. O plano é determinístico por
`medida + ação + prazo`.

`politica_civica.due_plans()` é a única consulta de agenda prevista pela NV-22.
Ela percorre apenas o pequeno ledger de planos institucionais e retorna apenas os
pendentes cujo prazo já venceu. O hot path da crônica e a permanência espacial
**não chamam** essa consulta.

Assim:

- plano vencido pode motivar processamento institucional dirigido;
- plano futuro não é sondado como pressão narrativa;
- nenhuma agenda significa nenhuma nova lei automática.

## Catálogo de medidas menores

`catalogo-medidas-civicas.yaml` contém um conjunto pequeno e fechado de classes
de medidas menores. O catálogo não contém eventos prontos e não possui seleção
aleatória.

Usá-lo exige, ainda assim:

1. escolher explicitamente uma entrada;
2. indicar uma instituição autorizada pela entrada;
3. fornecer motivo;
4. fornecer causa institucional;
5. definir escopo e conteúdo concretos.

Portanto não existe “lei aleatória para movimentar o dia”.

## Publicações e deduplicação

Uma publicação possui ID determinístico por:

```text
medida + localidade + período
```

O mesmo trio não pode produzir duas proclamações diferentes. Retries da mesma
publicação retornam `ja_publicada` e não criam novo delta.

Canais suportados:

- `arauto`;
- `quadro_avisos`;
- `guarda`;
- `templo`;
- `mensageiro`;
- `edital_publico`.

`quadro_avisos` e `edital_publico` são canais persistentes. Os demais são
ativos: um arauto ou mensageiro não ganha permanência fictícia só porque sua
fala foi registrada.

O período `persistente` só é permitido para canal persistente. Publicações
ativas usam uma janela causal explícita, por exemplo
`21 Eleasis, 1372 DR|tarde`.

## Integração com NV-15

`permanencia_espacial.prepare()` consulta a NV-22 somente quando a própria
permanência local já foi acionada explicitamente. A consulta lê exclusivamente
publicações já produzidas no local:

- não abre agenda institucional;
- não consulta instituições;
- não cria medida;
- não cria publicação;
- não transforma presença no local em conhecimento.

Um quadro de avisos ou edital persistente ainda ativo pode, por isso, aparecer
no circo quando Ren realmente permanece naquele local. O `avaliacao_id` da
NV-15 é devolvido como evidência sugerida para a entrega posterior.

## Integração com NV-13

A projeção espacial não torna Ren automaticamente conhecedor da medida.
`politica_civica.propose_delivery()` cria no mesmo writer:

1. um registro append-only em `politica_civica.entregas`;
2. um recibo reservado NV-13 em `relogio:entrega_<id>`.

O recibo aponta a publicação como causa, conserva o conteúdo anunciado e exige
o mesmo canal da publicação. O contrato transacional rejeita:

- recibo cívico sem entrega NV-22;
- entrega NV-22 sem recibo NV-13;
- recibo cujo conteúdo, canal, destinatário ou causa divergem da publicação.

Esse pareamento é o gate de ciência de Ren dentro da NV-22.

## Canais ativos

Arauto, guarda, templo e mensageiro não são projetados automaticamente pela
permanência. A entrega precisa de evidência causal explícita do encontro/canal.
Isso permite que um decreto chegue ao circo por um guarda ou arauto sem fingir
que todo guarda ou templo transmite toda medida existente.

## Atomicidade

A NV-22 reutiliza `estado/estado-atual.yaml` como alvo `estado/set` da raiz
inteira. O consolidator existente aplica esse arquivo e o relógio NV-13 no mesmo
journal multi-arquivo. Não existe segundo writer.

`transacoes.py` valida a forma e o pareamento no registro pendente.
`consolidar.py` revalida a sequência real de transições contra o estado canônico
e depois valida a raiz staged.

## Economia e limites

Orçamentos principais:

- até 32 medidas;
- até 48 planos;
- até 64 publicações;
- até 96 entregas;
- até 16 marcos por histórico de medida;
- raiz cívica de até 64 KiB;
- até 6 avisos projetados por permanência.

A consulta de permanência percorre apenas o ledger limitado de publicações já
produzidas. A consulta de agenda percorre apenas o ledger limitado de planos e
só ocorre quando chamada explicitamente.

## Idempotência

IDs determinísticos:

- plano: medida + ação + prazo;
- publicação: medida + localidade + período;
- entrega: publicação + destinatário Ren;
- recibo NV-13: entrega cívica.

Publicações e entregas são append-only. Medidas mantêm núcleo imutável e
histórico append-only. Planos só passam de `pendente` para `concluido` ou
`cancelado`.

## Estado vivo e migração

A NV-22 não cria lei retroativa e não migra uma agenda inventada para o estado
vivo. Se `politica_civica` estiver ausente, o estado válido é simplesmente um
ledger vazio. Isso preserva o critério de aceitação de que não haver nova lei é
normal quando não há causa/agenda institucional.

## Limitações deliberadas

- A NV-22 não tenta modelar todas as dependências constitucionais entre Mayor,
  Council e Courts. Cada medida permanece sob a instituição que a originou;
  acordos interinstitucionais exigiriam um contrato posterior específico.
- Expiração, revogação e substituição encerram a medida, mas não geram por si
  próprias uma nova proclamação. Se o encerramento precisar ser comunicado,
  deve existir uma publicação/medida apropriada, em vez de conhecimento mágico.
- Canais ativos dependem de evidência narrativa/canônica explícita; a NV-22 não
  seleciona automaticamente arautos, guardas, templos ou mensageiros.
- O catálogo é intencionalmente pequeno e não é um gerador procedural.
