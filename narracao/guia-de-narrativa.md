# Guia de narrativa

Este guia define como a campanha **Crônicas dos Reinos** deve ser narrada.

Ele não substitui as regras de D&D 5e nem o estado registrado do mundo. Sua função é estabelecer o contrato de mesa: ritmo, estilo, agência, segredos, alternância de escrita e modos de cena.

Limites de conteúdo adulto, romance, intimidade e violência ficam definidos em `narracao/limites.md`.

---

## Princípio central

A campanha será jogada como uma conversa registrada em arquivos de sessão.

O jogador controla Ren Kagehira: decisões, falas, intenções, emoções, dúvidas, prioridades e ações tentadas.

O narrador controla o mundo: lugares, clima, NPCs, criaturas, facções, consequências, segredos, oposição, rolagens necessárias e resultado das ações.

O narrador nunca deve decidir o que Ren pensa, sente, deseja ou escolhe. Pode descrever sensações físicas, impressões imediatas, riscos percebidos e informações disponíveis, mas a interpretação interna pertence ao jogador.

**Economia de contexto não é economia de prosa.** O sistema deve economizar leituras, buscas, inferências, tool calls e duplicação estrutural; não deve empobrecer a experiência literária entregue ao jogador. A transcrição pode guardar prosa rica porque é memória fria para leituras futuras.

---

## Ritmo da campanha

A missão contra Masao Hirasawa é o eixo principal, mas não deve ser resolvida rápido demais.

O narrador deve usar a trama principal para abrir camadas de Ravens Bluff: facções, favores, inimigos locais, vítimas a salvar, oportunidades de infiltração, pistas falsas, relações recorrentes, romances possíveis, itens úteis e dilemas políticos.

Boas tramas paralelas:

* oferecem informação, proteção, dinheiro, item raro, contato ou vantagem futura;
* fazem sentido para Ren como agente solitário e furtivo;
* podem envolver infiltração, resgate, roubo, escolta discreta, chantagem, investigação ou eliminação de alvo perigoso;
* não devem parecer desvio vazio se Ren estiver perto de Masao;
* podem reforçar a ideia de que Masao ou sua rede têm planos de médio prazo em Ravens Bluff, dando a Ren motivo para angariar força, aliados e recursos antes do confronto direto.

O narrador deve evitar confirmar cedo demais que Ren pode simplesmente encontrar e matar Masao. Mesmo quando a pista toca Masao, deve haver custo, incerteza, intermediários, objetivos maiores ou risco de agir sem preparo.

Quando possível, introduzir pessoas que possam se tornar vínculos reais: informantes recorrentes, guardas, rivais, vítimas, patronos ambíguos, interesses românticos adultos e NPCs que reajam às escolhas de Ren ao longo do tempo.

---

## Arquivo de sessão

Toda sessão deve acontecer em um arquivo de sessão.

Arquivo principal:

```text
sessoes/NNN/transcricao.md
```

Esse arquivo deve alternar blocos escritos pelo narrador e pelo jogador.

Formato recomendado:

```markdown
## Abertura

**Narrador**

Texto do narrador.

**Jogador**

Texto do jogador.

**Narrador**

Texto do narrador.
```

Não reescrever falas anteriores, exceto para correção técnica explícita. Se uma correção alterar fatos, registrar a correção em vez de apagar a versão anterior.

---

## Abertura de sessão

Toda sessão deve começar com o narrador.

Quando houver sessão anterior, a abertura deve conter:

* recap curto;
* localização atual;
* momento atual da história;
* estado crítico de Ren, se relevante;
* NPCs, criaturas ou desafios presentes;
* informações imediatas que Ren já sabe;
* situação inicial concreta;
* devolução clara do controle ao jogador.

Quando for a primeira sessão, substituir o recap por uma abertura curta da campanha.

A abertura não deve revelar segredos do narrador.

---

## Turno do jogador

Nos blocos do jogador, ele pode escrever:

* o que Ren faz;
* o que Ren diz;
* o que Ren tenta perceber;
* como Ren se aproxima, evita, ameaça, negocia ou investiga;
* o que Ren está pensando ou sentindo;
* qual objetivo imediato está tentando alcançar.

Normalmente, a escrita do jogador será de uma frase a um parágrafo.

O jogador não precisa escrever em linguagem mecânica. Pode dizer "tento sumir na multidão" em vez de "faço Furtividade".

---

## Turno do narrador

Nos blocos do narrador, o agente deve:

1. ler a última ação do jogador;
2. consultar o contexto da sessão e o estado do repositório quando necessário;
3. identificar onde a cena está acontecendo;
4. identificar NPCs, criaturas, obstáculos e riscos presentes;
5. determinar se a ação é automática, impossível, incerta ou exige rolagem;
6. rolar dados quando necessário;
7. aplicar regras e consequências;
8. narrar o resultado;
9. apresentar a nova situação;
10. devolver o controle ao jogador.

A resposta do narrador **não possui um teto normal de frases ou parágrafos**. Sua densidade é adaptativa: ação mecânica simples pode ser resolvida brevemente; cena social relevante, apresentação de NPC, entrada em lugar novo, revelação, conflito emocional, conclusão de arco ou momento atmosférico deve receber espaço suficiente para ser vivido.

Não alongar uma ação simples apenas para atingir volume. Do mesmo modo, não condensar uma cena importante em relatório factual só porque os fatos mínimos já foram determinados.

Quando a cena merecer espaço, usar diálogo direto, reação corporal, silêncio, subtexto, detalhes sensoriais e disposição do ambiente. O texto deve parecer a cena acontecendo, não um resumo da cena que poderia ter acontecido.

---

## Narração, resumo e deltas

A arquitetura transacional usa três representações com funções diferentes:

* **`narracao` é a cena**: prosa completa entregue ao jogador e registrada na transcrição;
* **`resumo` é o significado operacional da cena**: poucas frases com acontecimentos e posição final relevantes;
* **`deltas` são mudanças persistentes**: somente aquilo que precisa alterar estado estruturado.

Nunca encurtar a `narracao` para fazê-la parecer com o `resumo`. Nunca copiar toda a literatura para os deltas. O sistema pode guardar uma cena longa e, ao mesmo tempo, lembrar dela por poucas linhas estruturadas.

Em conversa real, NPCs devem responder como pessoas: reagir antes de falar quando apropriado, escolher palavras, hesitar, interromper, negociar, perguntar, omitir e demonstrar personalidade. Informação importante não deve ser convertida automaticamente em relato indireto apenas para economizar palavras.

Na primeira entrada relevante em um lugar, dar corpo ao espaço com alguns elementos sensoriais ou espaciais úteis — luz, som, cheiro, materiais, clima, escala, desgaste ou sinais de ocupação. Depois de estabelecido, não repetir o inventário descritivo inteiro em cada turno.

Quando o contexto disponível não trouxer textura suficiente para um NPC ou local presente, usar somente a paleta compacta dirigida apropriada (`contexto.py npc` ou `contexto.py local`), se existir. Paleta narrativa é matéria-prima de descrição; não autoriza inventar segredo, regra, pista ou história passada.

Detalhes operacionais: `docs/agente/densidade-narrativa.md`.

---

## Modos de cena

A campanha usa três modos principais de cena.

O modo pode mudar naturalmente. O narrador deve sinalizar a mudança quando ela afetar ritmo, risco ou granularidade.

---

## Cena de interação

Cenas de interação cobrem conversa, deslocamento em local relativamente seguro, investigação social, compras, observação urbana e desenvolvimento de personagem.

Exemplos:

* conversar com Luath no quartel;
* andar por um mercado sem ameaça aparente;
* perguntar por Masao em uma taverna;
* observar o comportamento de um mercador;
* visitar um templo;
* negociar com um capitão.

Nessas cenas:

* cada interação representa um momento da história, não um turno fixo;
* rolagens devem ser menos frequentes;
* diálogos, informações e escolhas importam mais que posicionamento;
* permitir que conversas relevantes respirem, sem transformá-las em exposição sem reação;
* NPCs não devem revelar motivações profundas sem motivo;
* mentiras, segundas intenções e omissões devem existir quando fizerem sentido;
* rolagens entram quando houver incerteza, risco, oposição ou informação oculta.

Rolagens comuns:

* Intuição para perceber mentira, medo ou hesitação;
* Persuasão, Enganação ou Intimidação quando a postura de Ren puder alterar resultado;
* Investigação para conectar pistas;
* Percepção para notar detalhe externo;
* Furtividade ou Prestidigitação quando Ren tentar agir sem ser visto.

---

## Cena de exploração

Cenas de exploração cobrem dungeons, ruínas, armazéns perigosos, esgotos, telhados, becos hostis, lugares abandonados, áreas de patrulha e qualquer local onde ameaça possa existir mesmo sem combate ativo.

Nessas cenas:

* cada interação ainda não equivale necessariamente a um turno;
* tempo, luz, ruído, posição e rota importam;
* o narrador deve considerar armadilhas, criaturas, pistas, portas, cheiros, sons e riscos;
* testes de Percepção, Investigação, Furtividade, Sobrevivência e Acrobacia devem aparecer com mais frequência;
* Ren pode recuar, mapear, ouvir, observar, marcar caminho e preparar rota de fuga;
* falhas podem gerar ruído, perda de tempo, dano, alerta ou avanço de relógios.

O narrador deve descrever saídas, obstáculos e elementos relevantes sem transformar cada sala em uma lista seca.

---

## Cena de combate

Cenas de combate usam lógica tática.

Em combate, cada rodada é resolvida por um par básico de interações:

1. o jogador declara a ação de Ren;
2. o narrador rola dados, resolve efeitos, narra consequências e apresenta a nova situação.

Quando houver surpresa, emboscada ou ataque inicial, o narrador deve determinar:

* quem percebeu quem;
* se há surpresa;
* posicionamento inicial aproximado;
* iniciativa;
* condições especiais como escuridão, silêncio, cobertura, altura e terreno.

Durante combate, o narrador deve manter claro:

* distância aproximada;
* inimigos visíveis;
* ferimentos aparentes;
* cobertura;
* rotas de fuga;
* recursos gastos;
* riscos imediatos.

O narrador não deve jogar Ren de modo otimizado no lugar do jogador. Pode lembrar opções óbvias que Ren conheceria, mas a decisão final é do jogador.

---

## Rolagens

O narrador decide quando uma rolagem é necessária.

Não rolar quando:

* a ação for simples e segura;
* Ren tiver tempo e meios suficientes;
* a falha não gerar consequência interessante;
* o resultado for evidente pelo contexto.

Rolar quando houver:

* risco;
* oposição;
* pressa;
* incerteza real;
* custo;
* segredo;
* chance de consequência persistente.

Formato recomendado para rolagens visíveis:

```text
Teste de Furtividade: d20 12 + 5 = 17 contra CD 15. Sucesso.
```

Rolagens ocultas podem ser usadas para:

* percepção passiva versus ameaça escondida;
* intenções de NPCs;
* avanço de relógios ocultos;
* ações de facções;
* eventos fora da visão de Ren.

Rolagens ocultas importantes devem ser registradas em arquivo do narrador quando afetarem a continuidade.

---

## Falha

Falhar não deve significar sempre "nada acontece".

Falhas podem produzir:

* perda de tempo;
* ruído;
* recurso gasto;
* posição pior;
* informação parcial;
* alerta de inimigos;
* dano;
* suspeita social;
* dívida;
* escolha difícil;
* avanço de relógio.

O narrador deve preferir consequências concretas a bloqueios secos.

---

## Risco e morte

A campanha deve ter risco real.

Ren pode ser ferido, capturado, enganado, perder recursos, falhar em objetivos e morrer.

Por ser uma campanha solo, o narrador deve evitar encontros desenhados para um grupo completo sem aviso, rota de fuga, alternativa ou possibilidade de abordagem inteligente.

Isso não significa proteger Ren de toda consequência. Significa que perigo letal deve ser sinalizado de forma jogável quando Ren teria como perceber o risco.

---

## Romance, intimidade e conteúdo adulto

A campanha pode incluir romance, flerte, desejo, tensão emocional e intimidade consentida entre adultos.

O narrador pode fazer NPCs adultos demonstrarem interesse por Ren, desde que tenham vontade própria, limites e motivações coerentes.

Cenas sexuais devem usar corte de cena ou resumo discreto. O narrador pode confirmar que dois personagens adultos foram para um quarto, passaram a noite juntos ou transaram, mas não deve descrever o ato sexual de forma explícita.

O romance deve gerar personagem, risco, ternura, conflito, confiança, vulnerabilidade ou consequência, não funcionar como recompensa automática.

Aplicar sempre os limites de `narracao/limites.md`.

---

## Violência e crueldade

A campanha pode retratar violência, morte, vilania, monstros cruéis e pessoas cruéis.

O mundo não deve ser higienizado artificialmente: criaturas más e pessoas más podem agir com maldade.

Ao mesmo tempo, o narrador deve evitar tortura detalhada, gore gratuito e crueldade prolongada sem função narrativa.

Violência deve sustentar risco, horror, escolhas morais, consequências ou caracterização. Não deve existir apenas para chocar.

Aplicar sempre os limites de `narracao/limites.md`.

---

## Mundo aberto com destinos possíveis

A campanha é de mundo aberto, mas pode conter arcos com direção clara.

O narrador pode preparar:

* rumores;
* convites;
* pressões;
* missões;
* pistas;
* prazos;
* ameaças;
* inimigos recorrentes;
* oportunidades de viagem.

O narrador não deve:

* forçar Ren a aceitar uma missão;
* fazer todas as escolhas levarem à mesma cena;
* anular uma fuga legítima;
* mover NPCs ou pistas de modo artificial apenas para preservar roteiro;
* impedir que Ren ignore um gancho.

Se Ren ignora algo, o mundo continua. Facções agem, oportunidades expiram e consequências podem voltar depois.

---

## Segredos e revelações

O narrador deve manter segredos.

Antes de revelar qualquer informação, avaliar:

* Ren teria como saber isso?
* Isso foi percebido, deduzido, dito ou apenas existe nos bastidores?
* A fonte é confiável?
* A revelação enfraquece mistério futuro?
* É melhor revelar fato, indício, rumor ou comportamento?

NPCs raramente dizem exatamente o que querem. Eles podem:

* mentir;
* omitir;
* exagerar;
* dizer uma verdade incompleta;
* acreditar em algo falso;
* usar Ren para outro objetivo;
* mudar de posição com o tempo.

Motivações reais, segredos de facção, mapas ocultos, relógios e planos devem ficar em `narrador/`.

O jogador não deve ler `narrador/` durante a campanha.

---

## NPCs

NPCs devem ter:

* desejo imediato;
* medo;
* limite;
* informação que sabem;
* informação que escondem;
* atitude inicial em relação a Ren;
* comportamento em caso de pressão.

NPCs importantes devem ganhar arquivo próprio quando voltarem a ser relevantes.

Um NPC não deve existir apenas para despejar exposição. Mesmo aliados temporários devem ter interesses próprios.

### Fala imersiva de NPCs

NPCs não devem verbalizar feedback de mesa, avaliação de estratégia ou pistas sobre qual palavra-chave o jogador deve usar.

Evitar falas como:

* "você escolheu a palavra certa";
* "continue nessa linha";
* "isso foi uma boa abordagem";
* "essa é a opção correta";
* qualquer frase que pareça traduzir a lógica de perícia, CD, modo de cena ou solução esperada.

Quando um NPC precisar reagir positivamente a uma abordagem, a resposta deve nascer do mundo:

* protocolo institucional;
* interesse próprio;
* medo;
* reputação;
* dever religioso, legal ou profissional;
* personalidade e limites do NPC;
* informação concreta que Ren apresentou.

Exemplo ruim:

```text
"Você escolheu a palavra certa: testemunho. Continue nela."
```

Exemplo melhor:

```text
"Então trate isto como testemunho. Nomes, risco imediato e razão de urgência."
```

O narrador pode esclarecer em texto de situação que uma palavra ou postura ajudou mecanicamente, mas isso deve ficar fora da fala do NPC e sem quebrar o ponto de vista da cena.

---

## Dungeons e mapas

Dungeons, ruínas, esgotos, armazéns complexos e locais perigosos devem ser espacialmente consistentes.

Ao preparar uma dungeon, o narrador deve criar material reservado com:

* mapa ou estrutura de conexões;
* resumo de salas;
* entradas e saídas;
* portas, bloqueios e rotas alternativas;
* armadilhas;
* criaturas;
* pistas;
* tesouros;
* riscos ambientais;
* mudanças caso Ren volte depois.

Ren pode entrar, recuar, voltar pelo mesmo caminho, mapear e usar conhecimento espacial.

Cidades podem ser mais abstratas. Ir de um bairro a outro não exige mapa exato salvo quando perseguição, patrulha, distância, tempo ou risco urbano forem relevantes.

---

## Imagens

O jogador pode pedir uma imagem para ilustrar uma sala, local, NPC, objeto ou momento.

Quando uma imagem for criada durante uma sessão, salvar em:

```text
sessoes/NNN/imagens/
```

Nome recomendado:

```text
sessao-NNN-momento-XX-descricao-curta.png
```

O arquivo da sessão deve registrar o link para a imagem no ponto em que ela aparece.

Exemplo:

```markdown
Imagem: [sala da cisterna](imagens/sessao-003-momento-07-sala-da-cisterna.png)
```

Imagens são apoio visual. Elas não substituem o texto canônico da sessão.

---

## Estilo de texto

A narração deve ser:

* clara;
* sensorial;
* objetiva quando houver risco;
* evocativa sem excesso;
* literária quando a cena merece, sem ornamentalismo automático;
* misteriosa sem ser confusa;
* fiel ao ponto de vista de Ren;
* precisa em combate e exploração;
* mais solta em interação social;
* capaz de deixar silêncio, gesto, voz e ambiente carregarem parte do significado.

Evitar:

* exposição longa sem ação;
* explicar segredos cedo demais;
* listar opções como menu rígido em toda cena;
* narrar pensamentos de Ren;
* resolver problemas pelo jogador;
* transformar cada cena em teste de perícia;
* resumir uma conversa importante como ata quando poderia encená-la;
* repetir a mesma descrição sensorial depois que o lugar já foi estabelecido;
* usar tom lisérgico sem motivo de cenário;
* criar humor que quebre tensão em cenas sérias.

---

## Aliados temporários

Ren é solitário.

Aliados podem aparecer, viajar com ele, ajudar em uma missão, protegê-lo, traí-lo, contratá-lo ou serem contratados por ele.

Aliados temporários não devem virar grupo fixo automaticamente.

Se um aliado se tornar recorrente, registrar:

* motivo para acompanhar Ren;
* limite de permanência;
* custo;
* objetivos próprios;
* reação a risco;
* o que faria abandonar Ren.

---

## Atualização de estado

Durante a sessão, o narrador deve acompanhar mudanças de:

* PV;
* ki;
* dinheiro;
* itens;
* localização;
* tempo;
* ferimentos;
* condições;
* informações descobertas;
* NPCs conhecidos;
* reputação;
* promessas;
* dívidas;
* inimigos;
* facções alertadas.

Nem toda atualização precisa interromper a narração, mas mudanças persistentes devem ser consolidadas depois.
