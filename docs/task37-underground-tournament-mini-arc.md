# Task 37 — Underground Tournament Mini-Arc

## Objetivo

Adicionar um mini-arco marcial opcional em Ravens Bluff sem colocá-lo dentro da espinha obrigatória da Task 36.

O conceito público é deliberadamente limitado: existe um **torneio clandestino multi-noite**, distribuído por aproximadamente duas semanas, com lutadores de tradições de Faerûn e Kara-Tur. O convite pode chegar por Luath quando relação, nível e tempo sustentarem a oportunidade. O quadro detalhado, identidades dos oponentes, estilos específicos e informação final permanecem reservados.

## Convite não é missão obrigatória

O torneio começa em `latente`.

Somente um encontro **explicitamente resolvido como Luath** pode consultar o gate. Presença incidental, coincidência de local, tag ou turno neutro não abrem o catálogo.

O gate exige:

- janela temporal mínima;
- nível mínimo de Ren;
- confiança mínima de Luath.

Se passar, a mesma preparação de cena pode projetar o pedido de Luath. Isso é somente permissão para ele fazer o convite. Ren pode recusar sem penalidade automática.

Se o convite realmente for narrado, a ferramenta `torneio_clandestino.py oferecer` registra o fato usando fonte e evidência canônicas. A resposta é registrada separadamente.

## Identidade de inscrição

Ao aceitar, **Ren escolhe** sob qual identidade entra. A camada aceita Ren, Kage, Shinta ou outra identidade explicitamente nomeada pelo jogador.

O torneio não funde personas. Actor continua funcionando apenas nos casos previstos pelo talento; estilo marcial, corpo, equipamento, conhecimento contextual e outras pistas podem continuar alimentando a Task 28 quando forem realmente observados.

## Agenda relativa, sem scheduler

O aceite ancora cinco noites relativas ao instante canônico da inscrição. A última fica aproximadamente catorze dias depois.

A agenda não entra em `narrador/mundo/agenda.yaml` e não cria pendência de Mundo Vivo, porque comparecer ou faltar é ação do jogador. Em vez disso, a consulta **já existente** de fronteira temporal considera a próxima noite enquanto o mini-arco estiver ativo.

Assim, uma intenção de dormir, esperar ou comprimir vários dias para antes da luta. Parar o relógio naquela data não decide que Ren compareceu.

## Rodadas frias e dirigidas

Cada noite possui um fragmento reservado próprio. A consulta:

```bash
poetry run python ferramentas/torneio_clandestino.py rodada
```

abre apenas a próxima rodada devida. Nenhuma consulta comum percorre o quadro inteiro.

O quadro mistura tradições marciais de Faerûn e Kara-Tur. As lutas são desenhadas como desafios reais e apropriados à faixa do mini-arco, mas:

- vitória nunca é garantida;
- estatísticas/dificuldade devem ser fixadas antes da primeira rolagem;
- derrota não pode ser reescrita depois;
- ausência tem consequência classificatória;
- retirada é sempre possível;
- combate é não letal por padrão, embora clandestinidade não transforme o local em espaço perfeitamente seguro.

Duas derrotas nas três primeiras noites eliminam Ren. A semifinal exige vitória para chegar à final.

## Final

A final é reservada para um **artista marcial kozakuriano já causalmente ligado à campanha**. O nome não é congelado no fragmento da luta: ele só é resolvido quando a final está realmente devida.

A resolução respeita o estado vivo. Ela não pode ressuscitar, teleportar ou liberar artificialmente um personagem bloqueado. Se um candidato vier da camada de aliados futuros, sua aparição continua respeitando nível e Contrato de Arco e precisa ser canonizada pelo mecanismo normal de entrada depois de acontecer.

Se nenhum candidato adequado estiver causalmente disponível, a final fica temporariamente impossível até adaptação coerente; o sistema não substitui por um desconhecido arbitrário apenas para preencher chave.

Uma vitória sobre membro da Juppongatana em contexto de torneio **não é neutralização durável por si só**. A Task 54 continua sendo a única autoridade dos milestones 8–17.

## Recompensa informacional

Chegar profundamente ao torneio pode liberar uma pista parcial; vencer a final pode liberar a versão mais forte. A recompensa é informação relacionada à logística da rede de Masao/Juppongatana.

Mesmo quando disponível, abrir o fragmento não concede conhecimento a Ren. A informação precisa ser efetivamente entregue, narrada e registrada pelo pipeline normal. Nenhuma recompensa cria automaticamente side quest, reputação, relação ou neutralização.

## Relação com outros sistemas

- Task 26: confiança de Luath participa do gate do convite;
- Task 27/30: Luath pode tomar iniciativa funcional, mas isso não força aceite;
- Task 28: suspeita/reconhecimento de identidade continua separada;
- Task 29: fama ou reação do público não viram reputação automaticamente;
- Tasks 31–33: o torneio não usa lifecycle de side quest;
- Tasks 34–35: condições/incidentes podem coexistir com as noites, sem substituir o quadro;
- Task 36: o mini-arco é opcional e separado da espinha canônica obrigatória;
- Task 54: somente neutralização durável conta para progressão Juppongatana.

## Custo

Contrato: `baseline/underground-tournament-mini-arc-orcamento.yaml`.

- 0 chamadas extras em turno comum;
- 0 leituras Task 37 em cena sem Luath explícito;
- nenhuma pendência nova de Mundo Vivo;
- nenhum scheduler;
- nenhum RNG de progressão;
- fronteira temporal ganha apenas leitura compacta do estado do mini-arco, e o índice somente quando ele está ativo;
- cada consulta de rodada abre no máximo um fragmento reservado;
- índice e estado <= 12 KiB;
- fragmento individual <= 6 KiB.

O resultado é um mini-arco que pode ocupar várias sessões e produzir técnica, risco, rivalidade e informação sem tomar o volante do jogador nem transformar o torneio em coluna obrigatória da Parte 1.
