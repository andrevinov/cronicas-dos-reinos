# Task 24 — Pending Gate inside `cronica preparar`

## Problema observado

Depois da Task 21, o turno normal passou a preferir `cronica preparar` + `cronica concluir`,
mas a barreira do Mundo Vivo ainda precisava ser consultada separadamente antes da
primeira chamada. Isso mantinha uma tool call ritualística no hot path e deixava um modo
de falha simples: o narrador podia esquecer a leitura, preparar/narrar uma cena e só
então o writer rejeitar o turno por pendências abertas.

A Task 23 já tornou a resolução de uma fila bloqueante barata em termos de orquestração.
A Task 24 não duplica essa resolução; apenas move a **detecção** para a porta que todo
turno já usa.

## Regra

`cronica preparar` começa pelo Pending Gate.

### Caminho livre

O gate lê somente `runtime/mundo-pendencias.yaml`. Se o marcador estiver livre ou não
configurado, a preparação existente segue sem alteração. A resposta/ticket da Task 21
permanece byte-logicamente igual; a leitura do marcador não é incorporada ao ticket nem
à lista de fontes da cena.

Isso substitui a leitura manual do arquivo no protocolo do narrador sem adicionar uma
terceira chamada operacional.

### Caminho bloqueado

Se o marcador disser `bloqueado: true`, o gate confirma `narrador/mundo/estado.yaml`
read-only antes de bloquear. Com pendências reais, `cronica preparar` retorna:

- `fase: bloqueada_pendencias_mundo`;
- `ticket_emitido: false`;
- quantidade e disparo mais antigo da fila;
- `disponibilidade.narracao: false` e `conclusao: false`;
- próxima ação: `resolver_fronteira.py preparar` (Task 23).

Nenhuma preparação neutra/reativa é construída, nenhum trânsito é planejado, nenhum
endpoint de cena é chamado e nenhum `contrato_conclusao` é emitido. O jogador ainda não
recebe narração nova.

Depois de resolver a fila pela Task 23 e materializar os itens que realmente exigem
fato, o narrador repete **o mesmo** `cronica preparar` pretendido originalmente.

## Marcador stale

O marcador é derivado; a fonte autoritativa continua sendo `narrador/mundo/estado.yaml`.
Por isso somente o caminho que já parece bloqueado paga uma segunda leitura.

Se o marcador disser bloqueado mas a fila autoritativa já estiver vazia, a Task 24 não
escreve reparo durante `preparar`: considera o gate livre e permite a preparação normal.
O writer/checkpoint existente continua responsável por reparar o marcador persistido.
Isso evita deadlock sem violar `preparar_e_read_only`.

O caminho livre não abre o estado autoritativo por precaução. A sincronização do
checkpoint e a barreira repetida no writer permanecem a defesa contra um marcador livre
que venha a envelhecer depois da preparação.

## Relação com a Task 23

A separação é proposital:

1. Task 24 detecta que **não pode haver turno novo**;
2. Task 23 projeta/avalia a fila e aplica no-ops em lote;
3. fatos restantes são materializados pelas autoridades já existentes;
4. `cronica preparar` é repetido e só então emite o ticket do turno.

Task 24 nunca decide que uma pendência é no-op, nunca chama `resolver_fronteira.aplicar`
e nunca conclui o Mundo Vivo por conta própria.

## `cronica concluir`

Não há mudança de responsabilidade. `cronica concluir` continua confirmando cena quando
reativa e registrando o turno. A barreira do writer continua obrigatória porque uma
pendência pode surgir depois da preparação ou o estado pode mudar entre as duas chamadas.
A Task 24 é uma prevenção antecipada; não substitui a trava transacional final.

## Custo

Contrato: `baseline/pending-gate-cronica-preparar-orcamento.yaml`.

- caminho livre: 1 leitura do marcador minúsculo;
- caminho bloqueado: no máximo marcador + estado autoritativo;
- 0 escritas em `cronica preparar`;
- 0 chamada ao hot path de cena quando bloqueado;
- 0 ticket quando bloqueado;
- saída bloqueada <= 2 KiB;
- 0 endpoint, scheduler, estado ou scan novo.

O ganho operacional é remover a consulta manual obrigatória do marcador e impedir
narração que seria rejeitada tardiamente, sem mover semântica da Task 21, Task 23 ou do
writer transacional.
