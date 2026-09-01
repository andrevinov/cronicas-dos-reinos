# Agentes leves

Camada reservada para NPCs recorrentes que têm trabalho, rotina, relações e vida
própria, mas não justificam o custo de um agente estratégico.

A regra é **rotina como padrão**. Uma reavaliação só pergunta se apareceu causa
concreta para alguma iniciativa fora da rotina. Se não apareceu, concluir a
pendência com "nenhuma mudança extraordinária".

## Economia

- a camada normal só roda quando um checkpoint atravessa um amanhecer;
- checkpoints durante o dia não leem índice/estado de agentes leves;
- no máximo **1 nova** pendência leve por checkpoint;
- no máximo **2 pendências leves abertas** simultaneamente;
- se houver mais vencidos, a ordem é: mais atrasado → maior prioridade → ID;
- vencidos adiados permanecem vencidos, portanto não são esquecidos;
- intervalos perdidos são condensados em uma única reavaliação;
- fragmentos não são abertos para selecionar candidatos.

## Comandos

```bash
python3 ferramentas/agentes_leves.py status
python3 ferramentas/agentes_leves.py mostrar luath
python3 ferramentas/agentes_leves.py validar
python3 ferramentas/populacao.py status
python3 ferramentas/populacao.py validar
```

`processar` existe para teste/manutenção; o fluxo normal passa pelo checkpoint.
`populacao.py` é somente manutenção/CI e nunca participa do hot path.

## População canônica

O passo 11 parte de `estado/npcs/index.yaml`, usando relações apenas como camada
adicional de consistência. O inventário frio `narrador/populacao-canonica.yaml`
classifica todos os NPCs canônicos atuais em quatro grupos: agentes estratégicos,
agentes leves, personagens cobertos por um agente-pai e personagens persistentes
sem agenda.

Agentes leves atuais, com primeira reavaliação escalonada:

- 11 Eleasis — Kethra Dunn, a cada 3 dias;
- 12 Eleasis — Bram Vask, a cada 3 dias;
- 13 Eleasis — Luath, a cada 3 dias;
- 14 Eleasis — Silva Elkwood, a cada 4 dias;
- 15 Eleasis — Maerra Thandrel, a cada 5 dias;
- 16 Eleasis — Halessa Vorn, a cada 4 dias;
- 17 Eleasis — Jack Mooney, a cada 5 dias;
- 18 Eleasis — Pell, a cada 4 dias.

O escalonamento evita rajada inicial. Colisões futuras são normais e continuam
submetidas ao orçamento rígido de 1 nova pendência por checkpoint.

Brass, Rusk e o homem capturado não ganham agenda separada da Red Sail; Sirrus é
coberto pela Casa de Tyr; Noll pela agenda de Bram; Tobb pela de Jack. Isso evita
que uma mesma operação seja acordada duas vezes por nomes diferentes.

Personagens como Nera, Colm, Corven, Peta, Iria e outros continuam plenamente
canônicos e podem agir quando uma cena ou evento os alcançar. **Persistente sem
agenda não significa passivo nem sem agência**; significa apenas que ainda não há
base canônica suficiente para justificar um despertador periódico.

Uma pendência `reavaliar_agente_leve` não significa que o NPC fez algo. Só depois
dela o narrador abre o fragmento indicado e decide, com base nos fatos atuais, se
houve iniciativa. Emprego, rotina e obrigações ordinárias continuam acontecendo
sem narração e sem custo de contexto.
