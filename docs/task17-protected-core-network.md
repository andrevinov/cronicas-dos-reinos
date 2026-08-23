# Task 17 — Protected Core Network

A rede protegida impede apenas **escalada procedural indevida**. Ela não torna NPCs imortais e não cancela consequências vindas de combate resolvido, decisões de Ren ou ações canônicas dirigidas pelo arco.

O núcleo inicial é declarativo e contém cinco relações já centrais no estado atual: Nera Vell, Tavin Vell, Silva Elkwood, Irmã Maerra Thandrel e Luath. Jack Mooney, Kethra Dunn e Irmã Halessa Vorn continuam importantes em seus papéis atuais, mas não são promovidos silenciosamente ao núcleo por esta task.

## Eventos mundiais

O ranking continua exatamente o mesmo e mantém o mesmo teto. Se o único agente leve selecionado pelo ranking pertence ao núcleo, ele deixa de aparecer como `agentes_leves_afetados` e passa para `nucleo_protegido_reconsiderar`. Não há busca de substituto: isso impediria que a proteção aumentasse a quantidade de peças despertadas pelo evento.

O NPC protegido pode reagir à situação, prestar ajuda, mudar rotina ou entrar em cena por causa do fato já resolvido. O sorteio, porém, não pode impor diretamente morte, sequestro, perda permanente de liberdade ou outra consequência grave/irreversível.

## Sidequests

Consequências procedurais de sidequest, quando a política está configurada, precisam declarar `gravidade`, `reversibilidade`, `classe_impacto` e `alvos_npc`. Para um alvo protegido, o máximo é `moderada + reversivel`; classes `vida` e `liberdade` são bloqueadas.

Consequências graves contra NPCs fora do núcleo continuam possíveis. Isso é deliberado: a Task 17 não cria plot armor global.

## Custo

A política é uma única fonte compacta. Ela só entra no hot path quando há consequência de sidequest ou quando uma carta mundial já foi sorteada e precisa de roteamento. Rotina, microeventos e presença incidental não recebem leitura adicional. Não há scheduler, estado novo, escrita, scan ou fragmento narrativo adicional.
