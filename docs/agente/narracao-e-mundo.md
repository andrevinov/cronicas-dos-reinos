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

## Durante a sessão

Acompanhar mudanças importantes de localização, tempo, recursos, dano/cura, condições, magias/habilidades, itens, promessas, relações, descobertas, relógios e consequências. Não interromper a narração para exibir atualização interna.

O registro pode ser consolidado ao fim da cena ou sessão. Durante a atual refatoração, esta regra é especialmente importante: **não duplicar preventivamente a mesma mudança em vários arquivos apenas porque ela ocorreu.** A arquitetura transacional completa será implantada em etapa posterior.

## Encerramento de sessão

Historicamente a sessão consolida, conforme aplicável:

- `sessoes/NNN/transcricao.md`;
- `sessoes/NNN/resumo.md`;
- `sessoes/NNN/alteracoes-de-estado.yaml`;
- `sessoes/NNN/experiencia.md`;
- `sessoes/NNN/consequencias.md`.

Registrar ponto inicial/final, tempo transcorrido, acontecimentos, decisões, rolagens decisivas, combates, XP/marcos, recursos, ferimentos/condições, relações, promessas/favores/dívidas, descobertas, mistérios, consequências, mudanças do mundo, relógios e pendências quando existirem. Depois consolidar o estado necessário para retomada. Uma sessão não está encerrada se a próxima exigir reconstrução manual substancial.

## Memória por finalidade

- `sessoes/`: memória histórica — **o que aconteceu?**
- `estado/`: estado atual — **como está agora?**
- `registros/`, quando existir: memória crônica — **o que pode voltar a importar?**
- `narrador/`: verdade secreta — **o que é verdadeiro sem ser necessariamente conhecido?**

Evitar duplicar a mesma informação em muitos lugares. Quando duplicação for útil, deixar clara a fonte autoritativa.

## Consequências persistentes

Decisões capazes de afetar sessões futuras devem permanecer rastreáveis: promessas quebradas, vidas salvas/abandonadas, favores a facções, segredos expostos, crimes, recursos destruídos, dívidas, humilhações, ameaças que escaparam etc.

Uma consequência persistente deve ter origem identificável, estado e entidades relacionadas. Efeitos possíveis não são cenas obrigatórias. Consequências podem permanecer dormentes por muitas sessões e devem ser consultadas quando realmente relacionadas à preparação corrente.

## Relações

Não reduzir necessariamente relações a um número único. Quando útil registrar confiança, respeito, medo, gratidão, lealdade, suspeita, ressentimento, dívida, interesse e rivalidade. Mudança significativa precisa de causa.

## Camadas de conhecimento

Distinguir:

1. verdade objetiva do mundo;
2. crença de NPC;
3. conhecimento de facção;
4. conhecimento do personagem;
5. conhecimento do jogador;
6. informação ainda não definida.

Antes de NPC usar uma informação, verificar como a obteve quando isso for relevante. Antes de revelar algo, verificar como Ren poderia percebê-lo. Rumor continua rumor até confirmação; evitar onisciência acidental.
