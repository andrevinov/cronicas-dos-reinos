# Narração, mundo vivo e memória de sessão

Este documento reúne regras operacionais de condução narrativa e continuidade. O estilo detalhado continua em `narracao/guia-de-narrativa.md`; densidade literária e textura dirigida estão em `docs/agente/densidade-narrativa.md`; o fluxo de arquivos de sessão continua em `narracao/protocolo-de-sessao.md`; limites de conteúdo continuam em `narracao/limites.md`.

## Forma de apresentar escolhas

Não transformar toda cena em menu de videogame. Exemplos de ação podem ser oferecidos quando o jogador estiver perdido, mas qualquer tentativa coerente deve continuar aberta. Preferir situação clara e pergunta aberta à enumeração rígida de opções.

A narração deve ser clara e evocativa, usar detalhes sensoriais relevantes, evitar extensão desnecessária em ações simples, dar espaço maior a cenas importantes, distinguir observação de inferência, evitar exposição artificial, permitir silêncio/dúvida/ambiguidade e interpretar NPCs como pessoas. Não encerrar automaticamente cada resposta com lista de possibilidades. Terminar quando decisão, resposta ou rolagem do jogador for necessária.

**Economia de contexto não é economia de prosa.** A condição “pare se suficiente” encerra a busca por contexto, não a elaboração literária da cena. Depois de reunir o mínimo necessário, narrar com a densidade que o momento merece.

## Ritmo

Alternar exploração, interação, investigação, conflito, descanso, consequência e descoberta conforme as escolhas e o estado do mundo, sem quotas artificiais. Evitar combate de preenchimento, longos discursos expositivos, múltiplas cenas sem decisão do jogador, repetição da mesma informação por NPCs diferentes, perigos resolvidos antes de reação possível e prolongamento de cenas já resolvidas.

## Mundo aberto

Construir mundo aberto por agentes e pressões, não por grandes árvores rígidas. Definir quem quer o quê, recursos, capacidades, o que acontece sem intervenção, sinais perceptíveis e reação às ações do jogador.

A campanha pode ter direções narrativas preferenciais, coincidências plausíveis, reencontros, pressões, convites, rumores, mudanças políticas, ameaças crescentes e elementos do passado. A chamada "mão do destino" nunca pode anular decisão legítima, transportar Ren para trama sem causa, ressuscitar inimigo sem explicação, fazer todas as estradas levarem à mesma cena, invalidar preparação/investigação ou remover artificialmente opções coerentes.

## NPCs

NPC importante deve possuir, conforme relevância: objetivo atual, motivação, medo/vulnerabilidade, recursos, relações, conhecimento, crenças, segredos, limites e estado atual.

NPCs podem mentir, errar, esquecer, mudar de opinião, acreditar em fatos falsos, agir por interesse próprio, recusar pedidos, guardar rancor, demonstrar gratidão e abandonar planos. Não fazê-los existir apenas para ajudar ou confrontar o protagonista. Mudança significativa de posição deve ter causa registrada.

Quando um NPC presente precisar de voz, gesto ou presença e isso não estiver no contexto corrente, `contexto.py npc "Nome"` pode incluir paleta, papel conversacional e `dialogo_relacional` na mesma consulta L2. A paleta continua sugestiva; o papel descreve personalidade funcional; `dialogo_relacional` modula tom, abertura e discordância com base na afinidade/confiança efetivas, inclusive deltas pendentes.

**Conselho não é iniciativa padrão.** Saudação, conversa casual, reencontro, brincadeira ou simples discordância não justificam sermão. Conselho/censura só entram quando Ren pede avaliação, o assunto cai diretamente na responsabilidade do NPC ou há risco imediato que torne silêncio artificial. Mesmo então, preferir uma observação concreta e dar espaço para resposta. Preocupação persistente não autoriza repetir a mesma bronca em toda interação.

Risco percebido alto pode endurecer limites e urgência sem apagar afeto/confiança. Silva com afinidade e confiança altas continua alguém próxima mesmo quando considera Ren muito perigoso para si ou para os vulneráveis; esse risco não deve converter automaticamente cuidado em tutela moral.

Detalhes: `docs/task26-npc-relationship-state-v1.md` e `docs/task27-relationship-aware-dialogue.md`.

## Facções

Facções relevantes devem possuir objetivos, liderança, recursos, área de influência, aliados, inimigos, conhecimento, planos, operações e reação ao personagem. Elas podem agir fora de cena. Reavaliar planos quando Ren interfere, recursos mudam, alianças mudam, informação é revelada, tempo avança ou outro agente interfere.

## Agentes autônomos

Quando a decisão narrativa depender do **objetivo, conhecimento, recursos, restrições, presença, mobilidade ou plano corrente de um agente importante**, consultar a camada reservada e fragmentada em `narrador/agentes/` por meio de:

```bash
python3 ferramentas/agentes.py mostrar <id-ou-nome>
```

A consulta dirigida abre somente o índice e o fragmento solicitado. Não abrir todos os agentes, suas fontes canônicas ou a pasta inteira por precaução. A camada de agentes é uma condensação operacional: arquivos como `narrador/masao/`, `narrador/juppongatana/`, relações, relógios e sessões continuam sendo as fontes canônicas apontadas pelos fragmentos.

Se o fragmento-base declarar `detalhes_operacionais` e a decisão concreta exigir
um repertório específico, abrir uma única seção com
`agentes.py detalhar <id> metodos_operacionais` ou
`agentes.py detalhar <id> autonomia_estrategica`. Cada consulta tem teto de 8 KiB;
a recomposição completa pertence somente a validadores frios.

`elegibilidade_local` é derivada de `estado`, `presenca` e `atuacao_local`. Um NPC que exige presença física só pode executar ação física em Ravens Bluff se estiver `presente` ou `presente_oculto`; `indeterminado`, `fora_da_area` e `em_viagem` bloqueiam a ação local. `presente_oculto` continua sendo verdade reservada do narrador e **não cria conhecimento para Ren**. Agentes capazes de atuar por rede e instituições locais seguem regras próprias documentadas no fragmento.

Para a Juppongatana, nunca presumir que a existência do coletivo significa que todos os membros estão em Ravens Bluff. Consultar o membro individual. Chegadas, saídas e viagens precisam virar estado canônico de presença/mobilidade antes de alterar sua elegibilidade local.

`python3 ferramentas/agentes.py validar` percorre fragmentos e fontes para conferir schema, mobilidade e proveniência. Essa validação pertence a manutenção/CI, **não ao loop normal de narração**.

## Adversários mecanicamente preparados

Agente estratégico e ficha mecânica têm autoridades diferentes. `agentes.py`
responde o que um ator quer, sabe e pode mobilizar; `adversarios.py` responde como
um NPC ou criatura já preparado resolve ações e especialidades. A ficha não cria
presença, encontro, conhecimento nem intenção.

Antes da primeira resolução mecânica de um adversário registrado, consultar
somente `adversarios.py mostrar <id-ou-nome>`. Se o desafio depender de falsificação,
perseguição, comando, investigação ou outra excelência não combativa, abrir também
uma única seção com `adversarios.py especialidade <id> <especialidade-id>`.
Ausência de ficha não autoriza inventar números depois da rolagem: preparar o bloco
antes ou usar explicitamente um equivalente oficial já autorizado.

Intervenção de aliado, retirada do inimigo e rota de fuga continuam consequências
causais do mundo, não corretores de balanceamento retroativo. `adversarios.py validar`
é manutenção/CI e não entra no turno comum.

Quando houver dúvida real sobre escala, usar antes da rolagem
`ameacas.py avaliar <id> --ren --vetor combate|especialidade`. Informar quantidade,
terreno, iniciativa e apenas aliados que já tenham presença, capacidade e motivo.
Resultado `letal` ou `esmagadora` exige que uma saída plausível possa ser percebida
ou investigada; não exige combate, não cria resgate e não garante a saída.

Arquétipo reutilizável só fornece mecânica. Vinculá-lo a alguém requer um NPC ou
criatura já sustentado pela cena/cânone e não copia personalidade, conhecimento,
objetivo ou presença. Depois da preparação, nem vínculo nem avaliação autorizam
trocar PV, CA, CD, dano, recursos ou número de inimigos.

Dungeon preparada é outra camada dirigida. Consultar o manifesto com
`dungeons.py mostrar <id>` quando um acesso plausível entrar em pauta; abrir
somente o nível atual com `dungeons.py nivel <id> <numero>`. Área, encontro,
perigo e descoberta permanecem preparação até a ficção alcançá-los. Uma referência
de adversário pede ficha/ameaça próprias apenas quando sua condição de
materialização for satisfeita. Não carregar os quatro níveis para retomar ou para
um turno fora da dungeon.

A existência de um agente no índice não obriga sua entrada em cena. Ações fora de cena só devem produzir conhecimento para Ren quando houver percepção, descoberta, comunicação ou inferência legítima. A cadência de reavaliação vem do Mundo Vivo; não transformar uma pendência em obrigação de agir.

## Agentes recorrentes leves

NPCs recorrentes como Luath, Silva e Maerra podem continuar vivendo fora da presença de Ren sem receber o peso operacional de um antagonista estratégico. Para eles, usar `narrador/agentes-leves/`. **Rotina é o padrão**: emprego, culto, cuidado, patrulha e obrigações ordinárias continuam acontecendo sem gerar cena nem atualização por si mesmos.

A camada leve só entra no fluxo quando o checkpoint cruza um amanhecer. Checkpoints diurnos de passagem de horas não consultam seu índice. Mesmo no amanhecer, Python seleciona candidatos usando somente índice + estado + tempo + fila do Mundo Vivo e não abre fragmentos.

O orçamento é obrigatório: no máximo **1 nova reavaliação leve por checkpoint** e no máximo **2 pendências leves abertas simultaneamente**. Se vários NPCs estiverem vencidos, ordenar deterministicamente por mais atrasado, maior prioridade e ID; os demais continuam vencidos. Intervalos perdidos são condensados em uma única reavaliação.

Quando aparecer `reavaliar_agente_leve`, consultar **somente o NPC indicado**:

```bash
python3 ferramentas/agentes_leves.py mostrar <id-ou-nome>
```

Se não houver causa concreta para uma iniciativa excepcional, concluir a pendência como nenhuma mudança extraordinária. Não abrir todos os agentes leves, não consultar suas relações canônicas por precaução e não inventar ação apenas porque a cadência venceu. `agentes_leves.py validar` pertence a manutenção/CI.

Night Watch e Luath exemplificam a separação: Night Watch continua agente institucional estratégico; Luath é o indivíduo recorrente. A ação de uma camada não implica automaticamente a ação da outra.

## Relógios e forças em movimento

Relógios podem representar conflitos ativos com identificador, progresso, limite, visibilidade, descrição, causas de avanço/regressão e consequência no limite. Não avançar arbitrariamente: cada mudança precisa de causa. Relógio oculto não deve ser revelado sem sinais perceptíveis.

## Preparação de sessão

O pacote de preparação deve ser conciso e conter apenas o necessário para a abertura e possibilidades mais prováveis: situação inicial, local/data, estado crítico do personagem, NPCs imediatos e objetivos, conflitos, consequências antigas aplicáveis, relógios que possam avançar, regras prováveis, segredos diretamente relacionados e possíveis cenas sem transformá-las em obrigação.

A preparação não deve presumir escolhas do jogador.

## Abertura

Ao iniciar uma sessão:

1. confirmar o estado mínimo necessário;
2. identificar sessão e data do mundo;
3. recapitular brevemente a situação anterior;
4. informar condições/recursos críticos quando relevantes;
5. apresentar a cena inicial;
6. devolver controle ao jogador.

O recap deve ser curto e não revelar material reservado.

## Durante a sessão — escrita transacional

Acompanhar mudanças importantes de localização, tempo, recursos, dano/cura, condições, magias/habilidades, itens, promessas, relações, descobertas, relógios e consequências. Não interromper a narração para exibir atualização interna.

Desde a Etapa 7, **não consolidar essas mudanças diretamente em vários arquivos durante cada troca**. O avanço narrativo ao vivo usa `ferramentas/turno.py registrar`, que persiste somente:

- a entrada do jogador e a resposta do narrador em `sessoes/NNN/transcricao.md`;
- um registro mínimo em `runtime/eventos-pendentes.jsonl`.

O payload transacional possui três funções diferentes:

- **`narracao`**: a cena completa, com a prosa que o jogador efetivamente deve ler;
- **`resumo`**: compressão curta dos acontecimentos e da posição final;
- **`deltas`**: somente mudanças persistentes estruturadas.

Não reduzir `narracao` ao tamanho desejado do `resumo`. Não copiar descrição, diálogo ou atmosfera para deltas quando isso não altera o estado persistente. Uma cena pode ser literariamente longa e ainda gerar um resumo de poucas frases e zero ou poucos deltas.

O registro pendente contém resumo curto e apenas deltas realmente ocorridos. Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.focus.atuais","valor":-1}
{"alvo":"tempo","op":"instante","valor":{"data":"7 Eleasis, 1372 DR","hora":"08:04"}}
{"alvo":"npc:kethra_dunn","op":"inc","caminho":"medidores.confianca","valor":1,"fato_canonico":"Kethra viu Ren cumprir uma promessa relevante com consequência persistente.","fonte":"sessoes/NNN/transcricao.md"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"balança velha","texto":"marca violeta sob a unha"}}
```

Afinidade/confiança conhecidas só mudam normalmente por `inc +1|-1` com `fato_canonico` e `fonte`. Valor `null` usa a inicialização explícita da Task 26. Não usar o campo textual `relacao.<id>.confianca` como substituto da barra operacional.

Não registrar um delta quando nada persistente mudou. Um turno pode ter `deltas: []` e ainda assim permanecer rastreável na transcrição.

`ferramentas/contexto.py` combina snapshot-base + eventos pendentes quando responde `status`, `cena`, `npc`, `local`, `relacao`, `conhecimento` e `buscar`. Portanto o narrador deve consultar o estado efetivo por essa ferramenta, e não tentar manter manualmente múltiplos arquivos sincronizados durante a cena.

`contexto.py local "Lugar"` existe para textura de ambiente pequena e dirigida. Usá-lo quando a primeira apresentação relevante do lugar precisar de matéria-prima e o contexto corrente não bastar; não chamá-lo ritualisticamente a cada turno.

### Limite de escrita por avanço

O alvo operacional é **duas escritas**:

1. transcrição;
2. buffer de eventos.

Não atualizar, por rotina, `estado/`, ficha, arquivos de relação, conhecimento, consequências, relógios ou logs de rolagem oculta na mesma interação. Esses destinos pertencem à consolidação posterior.

Também não executar `git status`, `git diff`, suíte de testes, regeneração de runtime ou commit depois de cada ação de Ren. Essas operações não fazem parte do loop narrativo.

### Rolagens

Se duas ou mais rolagens independentes já são necessárias antes de qualquer resultado, usar `ferramentas/rolar-lote.py`. Se a segunda rolagem só existe dependendo do resultado da primeira, não agrupá-las artificialmente.

Rolagens ocultas relevantes podem ser anexadas ao registro transacional em `rolagens_ocultas`; ficam indisponíveis à consulta pública normal e serão consolidadas no destino reservado adequado posteriormente.

## Encerramento de cena

Uma cena importante pode receber checkpoint narrativo na própria transcrição. Não consolidar por rotina a cada troca; quando houver fronteira de cena relevante e um checkpoint canônico for útil, usar:

```bash
python3 ferramentas/checkpoint.py cena
```

Se não houver necessidade de checkpoint, `turno.py check` continua suficiente para uma pausa segura com transações pendentes. Se existir journal de consolidação, recuperar antes de retomar a narração.

## Encerramento de sessão

Historicamente a sessão consolida, conforme aplicável:

- `sessoes/NNN/transcricao.md`;
- `sessoes/NNN/resumo.md`;
- `sessoes/NNN/alteracoes-de-estado.yaml`;
- `sessoes/NNN/experiencia.md`;
- `sessoes/NNN/consequencias.md`.

Registrar ponto inicial/final, tempo transcorrido, acontecimentos, decisões, rolagens decisivas, combates, XP/marcos, recursos, ferimentos/condições, relações, promessas/favores/dívidas, descobertas, mistérios, consequências, mudanças do mundo, relógios e pendências quando existirem.

Na arquitetura transacional, `runtime/eventos-pendentes.jsonl` é a lista explícita de mudanças ainda não incorporadas. Antes de encerrar a sessão, executar `python3 ferramentas/checkpoint.py sessao`; o ledger impede reaplicação e o buffer só é limpo depois da instalação verificada do lote.

## Memória por finalidade

- `sessoes/`: memória histórica — **o que aconteceu?**
- `estado/`: estado atual consolidado — **como estava no último checkpoint canônico?**
- `runtime/eventos-pendentes.jsonl`: delta corrente — **o que mudou depois desse checkpoint?**
- `ferramentas/contexto.py`: projeção efetiva — **como está agora considerando base + deltas?**
- `registros/`, quando existir: memória crônica — **o que pode voltar a importar?**
- `narrador/`: verdade secreta — **o que é verdadeiro sem ser necessariamente conhecido?**

Evitar duplicar a mesma informação em muitos lugares. Quando duplicação for útil, deixar clara a fonte autoritativa.

## Consequências persistentes

Decisões capazes de afetar sessões futuras devem permanecer rastreáveis: promessas quebradas, vidas salvas/abandonadas, favores a facções, segredos expostos, crimes, recursos destruídos, dívidas, humilhações, ameaças que escaparam etc.

Durante a sessão, uma consequência nova pode ser um delta `registrar` em `consequencia`; na consolidação ela deve ganhar origem identificável, estado e entidades relacionadas. Efeitos possíveis não são cenas obrigatórias.

## Relações

A Task 26 usa dois eixos operacionais independentes: **afinidade** (`medidores.vinculo`) e **confiança** (`medidores.confianca`), ambos 0–10 ou `null` quando ainda não há base canônica. `risco_percebido` é um terceiro contexto, não uma média dos dois. A prosa de `estado/relacoes/` continua guardando respeito, medo, gratidão, dívida, rivalidade e outras nuances que não devem ser espremidas em uma única barra.

Mudança de afinidade/confiança precisa de fato canônico claro e fonte rastreável. Não recalcular por cada fala, elogio, bronca ou teste social isolado. Durante a sessão, o delta operacional usa `npc:<id>`; histórico e índices são atualizados na consolidação.

A Task 27 projeta esses eixos na fala sem persistir estado adicional. Afinidade alta não implica confiança alta; confiança alta não implica amizade. Relação pode alterar intimidade, abertura e forma de discordar sem fornecer conhecimento que o NPC não possui.

## Camadas de conhecimento

Distinguir:

1. verdade objetiva do mundo;
2. crença de NPC;
3. conhecimento de facção;
4. conhecimento do personagem;
5. conhecimento do jogador;
6. informação ainda não definida.

Antes de NPC usar uma informação, verificar como a obteve quando isso for relevante. Antes de revelar algo, verificar como Ren poderia percebê-lo. Rumor continua rumor até confirmação; evitar onisciência acidental.

Descoberta nova de Ren pode existir temporariamente apenas como delta `conhecimento`; `contexto.py conhecimento` precisa enxergá-la antes da consolidação, sem transformá-la em verdade objetiva do mundo.
