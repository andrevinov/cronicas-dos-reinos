# Task 40 — Emergent Sidequest Opportunity Boundary

## Propósito

A Task 40 cria uma porta **somente de planejamento** para uma mudança de postura autoral: o narrador pode reconhecer que uma cena acabou de produzir material suficiente para talvez nascer uma aventura, mesmo quando essa sidequest não existia previamente no catálogo da Task 33.

A liberdade nova começa somente depois de uma **âncora causal concreta da cena**. Conversar com um NPC simpático, encontrar alguém incidentalmente ou simplesmente desejar mais conteúdo não basta.

## O que pode ser âncora

A origem pode ser uma conversa explícita com NPC, carta, mensagem, consequência de NPC, evento canônico ou outro fato concreto da cena. A âncora precisa nomear o material que surgiu: pedido, necessidade, problema, pista, ameaça, consequência, mudança, mensagem, carta ou conflito.

Uma presença incidental nunca aciona a boundary. Quando o Codex olha a cena e conclui que não há oportunidade, ele simplesmente não chama a porta — ou usa `recusar`, que faz zero leituras e zero escritas.

## O que a boundary devolve

Depois do sinal explícito, `ferramentas/oportunidade_sidequest.py planejar` monta um pacote reservado com teto rígido de 8 KiB:

- origem e âncora causal;
- relação efetiva do NPC de origem, quando houver, incluindo overlay transacional pendente;
- sidequests atualmente abertas/aceitas e o orçamento restante;
- instante atual e condições persistentes do mundo relevantes;
- no máximo três intenções canônicas futuras cronologicamente próximas da Task 39, mantendo apenas as que aceitam integração com sidequest;
- atores estratégicos que o arco/estado já permitem considerar agora;
- Juppongatana habilitados nesta parte do arco, separados por disponibilidade causal atual;
- envelope de recompensa derivado do Reward Budget v2, sem sorteio nem criação de item.

O pacote não contém uma sidequest pronta. Ele existe para a próxima decisão autoral do narrador.

## Fail-fast de orçamento

A primeira leitura de uma oportunidade sinalizada é somente o índice/estado de oportunidades. Se já existirem duas missões aceitas, a resposta é `limite_ativas`. Se o orçamento de missões abertas estiver cheio, a resposta é `limite_abertas`.

Nesses casos a boundary termina ali: não lê relação, mundo, Task 39, atores, Juppongatana, recompensas nem catálogo secreto.

## Segredos e economia de contexto

A Task 40 não varre NPCs e não abre o catálogo de 36 sidequests da Task 33. Ela também não abre fragmentos narrativos da Task 36. O horizonte canônico usa somente o índice da Task 39, o catálogo compacto da Task 36 e até três fragmentos de intenção dirigidos.

São proibidos scan global, `rglob`, `glob`, transcript e busca histórica para “achar uma aventura”. Se as três intenções próximas não oferecerem compatibilidade, a ausência de match não autoriza continuar procurando.

## Recompensa

`narrador/recompensas/envelope-sidequest.yaml` é um roteador derivado e pequeno do Reward Budget v2. Ele contém somente limites de tier, risco e família ecológica necessários ao planejamento. O `check` da Task 40 compara esse roteador com a tabela autoritativa em manutenção fria.

A boundary nunca chama o gerador de recompensas, não cria mapa, não sorteia item e não estabelece que Ren receberá qualquer prêmio.

## Autoridade que NÃO existe nesta Task

A Task 40 não pode:

- criar ou oferecer missão;
- aceitar missão em nome de Ren;
- escrever estado;
- criar scheduler ou pendência;
- marcar intenção da Task 39 como satisfeita;
- transformar, adiar ou reancorar evento canônico;
- escolher automaticamente ator, antagonista, Juppongatana ou recompensa.

Ela responde apenas: **há material causal suficiente; aqui está o pequeno conjunto de restrições e possibilidades que você precisa para pensar a aventura.**

## Uso operacional

Sem oportunidade:

```text
poetry run python ferramentas/oportunidade_sidequest.py recusar
```

Com oportunidade concreta:

```text
poetry run python ferramentas/oportunidade_sidequest.py planejar \
  --origem-tipo mensagem \
  --origem-id mensagem-iria-001 \
  --ancora-tipo problema \
  --ancora 'A mensagem relata que um contato desapareceu depois de transportar uma prova concreta.' \
  --npc iria_doss \
  --local casa_iria_doss \
  --periculosidade media
```

O exemplo ilustra a forma da chamada; não canoniza o conteúdo do exemplo.
