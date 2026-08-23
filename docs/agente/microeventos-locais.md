# Local Microevent Deck

A Task 12 transforma a ecologia local da Task 11 em um baralho reativo de pequenas variações cotidianas. O objetivo é dar vida a uma cena local sem pedir ao narrador que invente do zero o que seria plausível ali.

Microevento local continua sendo **candidato operacional**, não cânone automático.

## Porta de uso

Não existe uma segunda ferramenta obrigatória no hot path. A narração continua usando:

```bash
python3 ferramentas/endpoints.py cena ...
```

Quando a preparação possui gatilho local canônico e a camada está configurada, `cena_mundo.py preparar` simula o baralho junto com recompensa, contexto e gates já existentes. A confirmação da cena consome exatamente o sorteio preparado.

Para manutenção existem somente portas read-only:

```bash
python3 ferramentas/microeventos_locais.py simular <local> --cena-id <id>
python3 ferramentas/microeventos_locais.py status [local]
python3 ferramentas/microeventos_locais.py check
```

Não há comando público de `sortear` ou `consumir` fora da confirmação da cena.

## Dois baralhos por local

Cada local mantém estado independente para:

1. **ocorrência** — quatro fichas sem reposição: três `rotina` e uma `microevento`;
2. **cartas** — somente templates compatíveis com a ecologia daquele local.

A ordem é SHA-256 determinística a partir de seed, `local_id`, ciclo e identidade da carta. O estado começa com ciclo 0 e listas vazias; nenhuma visita antiga é inferida retroativamente.

Quando o baralho de ocorrência entrega `rotina`, nenhuma carta de microevento é consumida.

## Compatibilidade ecológica

Uma carta só entra no pool local quando há simultaneamente:

- pelo menos um `canais_microevento` em comum;
- pelo menos uma `tag` em comum.

A interseção é calculada em memória a partir de dois roteadores compactos. Não existe busca semântica ou scan de arquivos.

A validação exige ao menos duas cartas compatíveis para todo local canônico atual.

## Carta candidata, não fato

`avaliar_microevento` significa que o narrador deve considerar a pequena perturbação durante a cena. A carta não estabelece sozinha:

- que um NPC nomeado está presente;
- que houve crime, combate ou dano;
- que surgiu uma pista secreta;
- que nasceu side quest;
- que existe recompensa;
- que o conteúdo da premissa ocorreu exatamente como escrito.

Os `atores_comuns` devolvidos pela ecologia são papéis anônimos possíveis, não pessoas existentes por antecedência.

Se estado canônico, arco, cena já estabelecida ou pendência tornar a carta incompatível, a manifestação pode ser descartada. **Não se sorteia uma substituta.** A carta é consumida mesmo assim; isso impede reroll narrativo até aparecer uma sugestão conveniente.

## Transação

Na preparação:

1. alias local vira `local_id` canônico;
2. ecologia é resolvida;
3. catálogo + estado do baralho são lidos;
4. o próximo resultado é calculado em memória;
5. `atomic()` do baralho está sombreado junto às demais portas de escrita;
6. o estado do baralho entra em `fontes_lidas` e portanto no fingerprint de `preparacao_id`.

A preparação escreve zero bytes.

Na confirmação, a cena é revalidada. Se catálogo ou estado do baralho mudou desde a preparação, o ID fica obsoleto e a cena precisa ser preparada novamente. Se continua válido, a confirmação materializa no máximo uma atualização de `narrador/microeventos-locais/estado.yaml`.

## Idempotência

O histórico reservado guarda no máximo 64 pares recentes `cena_id + local_id`. Reabrir a mesma cena dentro dessa janela reutiliza o mesmo resultado e não consome outra ficha.

O histórico registra apenas qual template foi avaliado. Ele não é histórico canônico do que aconteceu na ficção.

## Relação com as próximas tasks

A Task 12 usa frequência fixa 3:1 e não consulta relógio. `ritmo_baseline` continua sendo escala relativa, não probabilidade embutida.

A Task 13 — Adventure Drought Pressure — poderá pressionar a frequência ou prioridade quando houver seca de aventura sem reescrever o catálogo e sem transformar o baralho em scheduler.

Contrato: `baseline/local-microevent-deck-orcamento.yaml`.
