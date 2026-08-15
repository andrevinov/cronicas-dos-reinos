# Narração, mundo vivo e memória de sessão

Este documento reúne regras operacionais de condução narrativa e continuidade. O estilo detalhado continua em `narracao/guia-de-narrativa.md`; o fluxo de arquivos de sessão continua em `narracao/protocolo-de-sessao.md`; limites de conteúdo continuam em `narracao/limites.md`.

## Forma de apresentar escolhas

Não transformar toda cena em menu de videogame. Exemplos de ação podem ser oferecidos quando o jogador estiver perdido, mas qualquer tentativa coerente deve continuar aberta. Preferir situação clara e pergunta aberta à enumeração rígida de opções.

A narração deve ser clara e evocativa, usar detalhes sensoriais relevantes, evitar extensão desnecessária em ações simples, dar espaço maior a cenas importantes, distinguir observação de inferência, evitar exposição artificial, permitir silêncio/dúvida/ambiguidade e interpretar NPCs como pessoas. Não encerrar automaticamente cada resposta com lista de possibilidades. Terminar quando decisão, resposta ou rolagem do jogador for necessária.

## Ritmo

Alternar exploração, interação, investigação, conflito, descanso, consequência e descoberta conforme as escolhas e o estado do mundo, sem quotas artificiais. Evitar combate de preenchimento, longos discursos expositivos, múltiplas cenas sem decisão do jogador, repetição da mesma informação por NPCs diferentes, perigos resolvidos antes de reação possível e prolongamento de cenas já resolvidas.

## Mundo aberto

Construir mundo aberto por agentes e pressões, não por grandes árvores rígidas. Definir quem quer o quê, recursos, capacidades, o que acontece sem intervenção, sinais perceptíveis e reação às ações do jogador.

A campanha pode ter direções narrativas preferenciais, coincidências plausíveis, reencontros, pressões, convites, rumores, mudanças políticas, ameaças crescentes e elementos do passado. A chamada "mão do destino" nunca pode anular decisão legítima, transportar Ren para trama sem causa, ressuscitar inimigo sem explicação, fazer todas as estradas levarem à mesma cena, invalidar preparação/investigação ou remover artificialmente opções coerentes.

## NPCs

NPC importante deve possuir, conforme relevância: objetivo atual, motivação, medo/vulnerabilidade, recursos, relações, conhecimento, crenças, segredos, limites e estado atual.

NPCs podem mentir, errar, esquecer, mudar de opinião, acreditar em fatos falsos, agir por interesse próprio, recusar pedidos, guardar rancor, demonstrar gratidão e abandonar planos. Não fazê-los existir apenas para ajudar ou confrontar o protagonista. Mudança significativa de posição deve ter causa registrada.

## Facções

Facções relevantes devem possuir objetivos, liderança, recursos, área de influência, aliados, inimigos, conhecimento, planos, operações e reação ao personagem. Elas podem agir fora de cena. Reavaliar planos quando Ren interfere, recursos mudam, alianças mudam, informação é revelada, tempo avança ou outro agente interfere.

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

O registro pendente contém resumo curto e apenas deltas realmente ocorridos. Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04 de 7 Eleasis"}
{"alvo":"relacao:kethra_dunn","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"balança velha","texto":"marca violeta sob a unha"}}
```

Não registrar um delta quando nada persistente mudou. Um turno pode ter `deltas: []` e ainda assim permanecer rastreável na transcrição.

`ferramentas/contexto.py` combina snapshot-base + eventos pendentes quando responde `status`, `cena`, `npc`, `relacao`, `conhecimento` e `buscar`. Portanto o narrador deve consultar o estado efetivo por essa ferramenta, e não tentar manter manualmente múltiplos arquivos sincronizados durante a cena.

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
python3 ferramentas/consolidar.py cena
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

Na arquitetura transacional, `runtime/eventos-pendentes.jsonl` é a lista explícita de mudanças ainda não incorporadas. Antes de encerrar a sessão, executar `python3 ferramentas/consolidar.py sessao`; o ledger impede reaplicação e o buffer só é limpo depois da instalação verificada do lote.

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

Não reduzir necessariamente relações a um número único. Quando útil registrar confiança, respeito, medo, gratidão, lealdade, suspeita, ressentimento, dívida, interesse e rivalidade. Mudança significativa precisa de causa.

Durante a sessão, registrar apenas o delta significativo (`relacao:<id>`), não recontar o histórico da relação. O histórico próprio é atualizado em consolidação.

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
