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
```

`processar` existe para teste/manutenção; o fluxo normal passa pelo checkpoint.

## Primeira população

- Luath: a cada 3 dias;
- Silva Elkwood: a cada 4 dias;
- Maerra Thandrel: a cada 5 dias.

As primeiras datas foram escalonadas a partir do estado atual para não gerar uma
rajada retroativa de NPCs no primeiro amanhecer do Mundo Vivo.

Uma pendência `reavaliar_agente_leve` não significa que o NPC fez algo. Só depois
dela o narrador abre o fragmento indicado e decide, com base nos fatos atuais, se
houve iniciativa. Emprego, rotina e obrigações ordinárias continuam acontecendo
sem narração e sem custo de contexto.
