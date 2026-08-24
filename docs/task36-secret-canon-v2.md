# Task 36 — Secret Canon v2

## Objetivo

Fortalecer a espinha canônica futura da Parte 1 sem transformar a campanha em trilho.
A data obriga **uma situação do mundo** a entrar em jogo; ela não escolhe a resposta de
Ren, não escreve emoção, não garante vitória/derrota e não concede conhecimento,
reputação, relação ou progressão automaticamente.

O passado já materializado na instalação da Task 36 é imutável e fica protegido por
digest. Somente material futuro foi reautorado.

## Arquitetura

O catálogo reservado deixou de ser um monólito quente.

```text
narrador/arcos/parte_1/eventos-canonicos.yaml
        ↓ índice compacto
narrador/arcos/parte_1/eventos/<evento>.yaml
        ↓ um fragmento reservado por batida
```

O índice contém identidade operacional, agendamento e ponteiro para fragmento. Prosa,
guardrails, categorias e adaptações permanecem frios.

Um turno sem evento devido lê **zero fragmentos** da Task 36. Quando uma pendência
canônica vence, o resolvedor abre o índice e somente o fragmento daquele evento. A
validação completa pode percorrer todos os fragmentos, mas isso pertence a manutenção/CI.

## Autoria futura

Cada batida futura declara categorias controladas. A cobertura da Parte 1 inclui:

- crises que alteram o cotidiano e as instituições;
- entrada orgânica de aliados;
- oportunidades reais envolvendo Juppongatana sem neutralização automática;
- oportunidades heroicas com custo e risco;
- jogo de identidade compatível com suspeita ≠ confirmação;
- escalada estratégica de Masao;
- Golden Lily e consequências urbanas;
- progressão material rumo à Ponte/Kozakura.

Os detalhes, datas, atores, ordem e títulos futuros permanecem reservados. Este
documento não os enumera.

## Elasticidade causal

Cada evento futuro possui `adaptacao`. Se um personagem já morreu, foi preso, saiu da
área, uma instituição mudou ou uma descoberta ocorreu antes da data, o narrador adapta
a **forma**. Ele não ressuscita personagens, desfaz consequências, entrega informação
gratuita ou força uma decisão de Ren.

Quando o próprio núcleo está temporariamente impossível, a pendência continua aberta.
Evento canônico continua não aceitando no-op.

## Integração com sistemas existentes

A Task 36 reutiliza a mesma agenda, Mundo Vivo, barreira e transação da espinha datada.
Não existe scheduler novo nem segundo relógio.

Identidade continua sob a Task 28; reputação pública sob a Task 29; relação sob as
Tasks 26–27; neutralização durável de Juppongatana sob a Task 54. A Task 35 pode
satisfazer uma crise compatível já materializada, evitando duplicar violência só para
cumprir roteiro.

A Task 37 permanece separada e não é implementada aqui.

## Orçamento

Contrato: `baseline/secret-canon-v2-orcamento.yaml`.

- 21 eventos no catálogo, sendo 1 passado congelado e 20 futuros;
- índice <= 12 KiB;
- cada fragmento <= 6 KiB;
- no máximo 1 fragmento narrativo aberto por evento devido;
- 0 fragmentos em turno sem evento;
- 0 scheduler novo;
- 0 estado paralelo;
- 0 RNG;
- 0 scan global no hot path.

## Resultado

A Parte 1 passa a ter uma coluna vertebral autoral mais forte, espaçada e variada, mas
o sistema continua distinguindo **o que o mundo faz acontecer** de **o que Ren decide
fazer com isso**.
