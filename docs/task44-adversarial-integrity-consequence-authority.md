# Task 44 — Adversarial Integrity & Consequence Authority

## Objetivo

Garantir que antagonistas continuem perigosos quando a causalidade justificar, sem transformá-los em homicidas aleatórios e sem conceder onisciência, capacidades novas ou plot armor oculto aos aliados de Ren.

A regra de interpretação é dupla:

1. antagonistas perseguem seus objetivos conforme personalidade, conhecimento, recursos e restrições canônicas; eles não preservam Ren ou NPCs por conveniência narrativa;
2. uma consequência causalmente apropriada não pode ser substituída por outra artificialmente mais branda apenas para preservar personagem, relacionamento ou conforto do jogador.

Gravidade, porém, não é sinônimo de competência. Um antagonista competente prefere o meio que melhor atende ao objetivo dentro de seus custos, riscos, conhecimento e limitações.

## Contrato adversarial da sidequest

A Task 41 continua sendo a autora do mini-arco. Antes de a oferta virar uma missão aceitável, a Task 44 prepara um contrato reservado complementar com:

- `objetivos_antagonistas`;
- `capacidades_disponiveis`;
- `conhecimentos_disponiveis`;
- `estado_se_ren_nao_intervier`;
- `escaladas_possiveis`;
- `consequencias_de_falha`;
- `consequencias_de_inacao`;
- `alvos_em_risco`;
- `gravidade_maxima_causal`.

O contrato não executa nada. Ele congela o espaço de consequência antes do aceite, para que o narrador não decida depois do resultado que um inimigo foi milagrosamente mais gentil — ou mais cruel — do que a situação permitia.

Reações causadas por sucesso ou progresso excepcional pertencem à Task50. Elas
ganham contrato novo somente depois do fato canônico e guardam o caminho e o
SHA-256 do contrato Task44 original; não acrescentam bytes, stakes ou capacidades
retroativamente a ele. Toda alternativa volta a passar por esta autoridade e
pela rede protegida no preparo e no compromisso.

### Capacidades e conhecimento

Para um agente estratégico existente, `capacidade_id` precisa ser um método operacional que já exista no fragmento canônico do agente. A quest não pode adicionar uma capacidade nova a Masao, Pan Chu ou um Juppongatana apenas porque seria conveniente.

Do mesmo modo, fatos marcados como conhecimento do agente precisam já existir em `conhecimento` no fragmento canônico. Um Juppongatana brutal continua incapaz de agir sobre um segredo que não conhece.

Antagonistas autorais novos podem receber capacidades e fatos próprios da quest, mas esses fatos precisam estar ancorados literalmente no próprio mini-arco.

## Escaladas

Cada escalada liga:

- antagonista;
- condição causal;
- capacidade real;
- conhecimento necessário;
- alvos declarados;
- gravidade, reversibilidade e classe de impacto;
- consequência possível;
- prioridade;
- bloqueios causais conhecidos.

Prioridades:

- `possivel`: uma opção causal entre outras;
- `preferencial`: tende a servir melhor ao objetivo, sem obrigar resultado;
- `obrigatoria_se_condicao`: se a condição for demonstrada canonicamente, não pode ser trocada por uma consequência mais branda apenas por conveniência narrativa. Para escolher outra rota, é preciso demonstrar também um bloqueio causal previamente declarado.

Isso não obriga um antagonista a escolher sempre a consequência mais violenta. Ao contrário: a escalada obrigatória deve representar aquilo que o próprio contrato decidiu ser estruturalmente necessário para aquele objetivo.

## Protected Core e autoridade da consequência

A Task 44 acrescenta seis classes de autoridade:

- `procedural`;
- `sidequest_lateral`;
- `sidequest_canonica`;
- `evento_canonico`;
- `acao_de_ren`;
- `combate_resolvido`.

### Procedural e sidequest lateral

Continuam sob `rede_protegida.py`. Nera, Tavin, Silva, Maerra e Luath não podem receber morte, sequestro irreversível ou outra consequência grave apenas porque uma camada procedural ou uma sidequest lateral quis aumentar drama.

NPCs fora do núcleo não recebem esse plot armor: uma consequência grave é permitida quando já estava causalmente contratada.

### Sidequest canônica

Uma sidequest não lateral só ganha esta autoridade depois que o aceite criou exatamente uma reserva Task 42 ativa para a intenção canônica correspondente. A reserva não inventa risco: alvo, gravidade, capacidade, conhecimento e condição ainda precisam estar congelados no contrato Task 44 e a condição precisa ser demonstrada por evidência canônica literal.

Assim, uma sidequest realmente conectada à espinha canônica pode colocar um membro do Protected Core em risco sério sem transformar qualquer aventura lateral em licença para matar aliados.

### Evento canônico, ação de Ren e combate resolvido

Essas autoridades não recebem correção protetiva escondida. Se uma consequência grave estiver estabelecida por fonte canônica, ação efetiva do jogador ou resultado de combate, o Protected Core não faz o atacante errar, a prisão desaparecer ou o golpe perder gravidade por conveniência.

A evidência literal continua obrigatória: ausência de plot armor não é licença para inventar o fato.

## Competência adversarial

`integridade_adversarial.py` expõe gates dirigidos para capacidades, conhecimento e escaladas condicionais.

Exemplos de contrato:

- Pan Chu sob uma ordem administrativa simples não ganha autorização para bombardeio; sua escalada naval só entra no espaço de opções quando coerção/apreensão séria é demonstrada.
- se a apreensão do Golden Lily realmente ocorrer, a força naval destrutiva declarada no próprio agente passa a ser opção legítima.
- Shizune não recebe automaticamente capacidade física ou conhecimento que não possui; seus métodos documentais continuam preferenciais enquanto forem estruturalmente adequados.
- Masao não precisa matar quando chantagem, desaparecimento ou desgaste servem melhor ao plano; mas uma escalada previamente marcada `obrigatoria_se_condicao` não pode virar mera carta ameaçadora porque a vítima ficou querida pelo jogador.

## Evidência

Planejamento reservado não prova condição causal. Fontes sob sidequests emergentes ou eventos/intencões futuras não servem como evidência de que a consequência já ocorreu.

A autorização de consequência exige fonte canônica existente e trecho literal localizável.

## Economia

- contrato por quest: no máximo 24 KiB;
- preparação: no máximo 8 KiB;
- zero RNG;
- zero scheduler;
- zero scan global;
- nenhuma leitura Task 44 em turno comum;
- execução terminal continua na Task45; reações pós-sucesso pertencem à Task50;
- integração automática no fluxo `cronica` continua na Task 46.
