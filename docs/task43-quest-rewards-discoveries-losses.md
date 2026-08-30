# Task 43 — Quest Rewards, Discoveries & Losses

## Propósito

A Task 43 transforma o esqueleto de recompensas e stakes congelado pela Task 41 em um **contrato executável de recompensa da sidequest**. Ela não substitui o loot de exploração da `recompensas.py`: mapas de local continuam pertencendo ao sistema antigo; prêmios de quest pertencem a `recompensas_sidequest.py`.

Cada sidequest emergente materializada deve possuir um fragmento dirigido em `narrador/sidequests-emergentes/recompensas/<quest-id>.yaml`. O `check` falha enquanto uma missão emergente não tiver esse contrato.

## Estrutura

`contrato_recompensa` contém exatamente:

- `recompensa_principal`;
- `recompensas_opcionais`;
- `recompensas_descobríveis`;
- `recompensas_condicionais`;
- `perdas_possiveis`.

O contrato **não pode inventar recompensas novas** depois da materialização. Ele deve classificar exatamente uma vez todas as recompensas já declaradas pela Task 41 e também todas as perdas declaradas em `stakes.perdas_possiveis`.

Tipos suportados incluem dinheiro, item, item mágico, consumível, pergaminho, tesouro, propriedade, direito de uso, serviço, informação, contato, favor, acesso, reputação, recurso e registro de progressão canônica. `progressao_canonica` registra um prêmio/progresso pelo domínio normal de progressão; ele não satisfaz intenção da Task 39 nem substitui o Canon Bridge da Task 42.

## Reward Budget v2

O contrato é validado contra **o mesmo envelope Task40 que originou a quest**; o digest precisa coincidir com o congelado pela Task41.

Recompensas materiais consomem os pontos do Reward Budget v2. Item mágico paga também o custo `especial`, não pode exceder o tier da sidequest e continua sujeito ao teto qualitativo e ao `max_itens`. Dinheiro declara PO concretos e possui teto por tier/valor aproximado para impedir que `moderado` esconda quantia arbitrária.

Ativos narrativos como propriedade, favor ou acesso não são convertidos artificialmente em PO. Propriedade e direito de uso exigem evidência canônica literal de que o concedente possui autoridade para oferecê-los.

## Descoberta

Recompensa descobrível começa `oculta`. Ela só muda por `descoberta` explícita.

O contrato pode declarar teste requerido, perícia/CD, consequência da falha e momento de entrega:

- `permanece_oculta`: uma falha não entrega nada e ainda permite causalmente nova tentativa;
- `perdida_permanentemente`: a oportunidade de obter o tesouro encerra-se;
- `imediata`: sucesso na descoberta pode materializar o prêmio naquele momento;
- `desfecho`: a descoberta apenas reserva o prêmio; a entrega ocorre junto ao sucesso da quest.

Descobrir não significa obter. Um item oculto nunca é concedido apenas porque a sidequest terminou.

## Recompensas de sucesso e condicionais

A recompensa principal fica elegível quando a missão está `concluida`. Opcionais e condicionais exigem evidência literal da condição correspondente. Descobríveis com entrega no desfecho entram somente se o estado já for `descoberta`.

O principal e vários prêmios adicionais podem entrar na **mesma transação**. Isso permite, por exemplo, pagamento em dinheiro + item opcional + favor, sem criar writes independentes por prêmio.

## Perdas

Falha ou expiração não autorizam punição livre. `perdas` só aceita IDs que estavam no contrato e exige evidência canônica literal da condição causal.

Além disso, a coisa perdida precisa existir efetivamente: não se remove dinheiro acima do saldo, item ausente nem ativo narrativo inexistente. Assim a falha não pode simplesmente “tirar 200 PO de Ren” porque parece dramático.

## Persistência transacional

Efeitos reais usam `turno.register_transaction`, portanto seguem o mesmo transcript/buffer/checkpoint/consolidação já testado pelo runtime:

- dinheiro altera `estado.recursos.dinheiro.po`, que o consolidator espelha na ficha;
- item físico entra na ficha e em `equipamento_em_posse`;
- informação usa o domínio de conhecimento;
- propriedade, direito, favor, acesso etc. entram como `estado.ativos_narrativos.<tipo>`;
- progressão usa `progressao registrar`.

O ID da transação deriva deterministicamente da missão, ação e IDs de reward/loss. Se o processo cair depois do writer mas antes do ledger Task43, o retry detecta a transação no buffer ou no ledger de consolidação e apenas repara o estado `obtida/aplicada`. Não soma PO nem anexa propriedade novamente.

## Operação

Depois de Task41 materializar uma missão, registre seu contrato antes de permitir que ela avance operacionalmente:

```text
python ferramentas/recompensas_sidequest.py registrar-contrato <mission-id> < payload.yaml
```

Descoberta usa:

```text
python ferramentas/recompensas_sidequest.py descoberta <mission-id> <reward-id> sucesso|falha < payload.yaml
```

Após conclusão:

```text
python ferramentas/recompensas_sidequest.py sucesso <mission-id> --narracao '...'
```

Após falha/expiração, somente quando houver consequência causal comprovada:

```text
python ferramentas/recompensas_sidequest.py perdas <mission-id> --narracao '...'
```

A Task 46 poderá incorporar essas ações ao fluxo unificado `cronica`; a Task43 não adiciona scheduler nem leitura no turno comum.
