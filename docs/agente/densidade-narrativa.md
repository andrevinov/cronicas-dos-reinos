# Densidade narrativa e textura dirigida

Este documento define como preservar a experiência literária da campanha **sem desfazer a economia de contexto**.

## Invariante principal

**Economia de contexto não é economia de prosa.**

A arquitetura deve economizar leituras, buscas, inferências, tool calls, arquivos quentes, duplicação estrutural e reescritas canônicas. Ela **não** deve reduzir por reflexo a qualidade, a presença ou o tamanho da narração que o jogador recebe.

O texto entregue ao jogador pode e deve respirar quando a cena pede. A transcrição é fria para leitura futura; portanto, prosa rica pode crescer em `sessoes/NNN/transcricao.md` sem ser carregada automaticamente em cada avanço posterior.

## Três camadas diferentes

Nunca tratar os três campos abaixo como versões quase iguais do mesmo texto.

### 1. `narracao` — a cena

É a experiência do jogador. Deve conter, conforme relevância:

- ação e consequência dramatizadas;
- fala direta de NPCs quando houver conversa real;
- reação corporal, silêncio, hesitação e subtexto;
- espaço, luz, clima, ruído, cheiro e textura quando ajudam a cena;
- presença e voz dos personagens;
- informação mecânica apenas na medida em que mantém a situação jogável.

A `narracao` pode ser longa. Seu tamanho é decidido pela importância dramática, não pelo tamanho desejado do JSONL.

### 2. `resumo` — compressão operacional

É a lembrança curta do que aconteceu. Deve responder, em poucas frases:

- o que mudou;
- o que foi descoberto;
- qual decisão ou resultado passou a importar;
- onde a cena ficou.

Não copiar floreio, diálogo completo, descrição sensorial ou sequência detalhada de golpes para o resumo quando isso não for estruturalmente necessário.

### 3. `deltas` — mudanças persistentes

São somente as alterações de estado que precisam sobreviver de forma estruturada: recurso, hora, localização, relação, conhecimento, consequência, relógio etc.

Não transformar descrição literária em delta. Não transformar todo detalhe sensorial em cânone estruturado.

Em fórmula:

```text
narracao = a cena
resumo   = o significado da cena
­deltas   = o que mudou no estado persistente
```

## Densidade adaptativa

Não há meta fixa de palavras ou parágrafos. A pergunta correta é: **quanto espaço esta cena merece para ser vivida, sem enchimento?**

### Pode ser breve

- ação mecânica simples;
- deslocamento já conhecido sem novidade;
- ataque ou teste isolado que não muda o tom da cena;
- confirmação administrativa;
- repetição de informação que o jogador já domina.

Uma resolução dessas pode ter um ou poucos parágrafos.

### Deve ganhar espaço

- entrada em lugar novo ou significativamente transformado;
- apresentação ou reencontro importante com NPC;
- conversa com conteúdo emocional, político, moral ou investigativo;
- revelação relevante;
- mudança de relação;
- conclusão de conflito;
- cena de descanso/intimidade/personagem que exista justamente pela experiência;
- passagem em que ambiente, silêncio ou ritmo são parte do significado.

Nesses casos, usar quantos parágrafos forem necessários para criar presença. Não comprimir diálogo em relatório indireto apenas para ser curto.

## Conversa precisa parecer conversa

Quando Ren conversa com alguém, permitir que o NPC tenha voz própria. Sempre que fizer sentido:

- apresentar a reação antes da resposta;
- usar fala direta para informação importante;
- deixar a pessoa perguntar, interromper, hesitar, negociar, desconfiar ou escolher palavras;
- evitar transformar uma interação social inteira em `NPC explica que X, Y e Z`;
- não terminar todo diálogo imediatamente após transmitir a informação mecânica necessária.

Isso não significa criar monólogos longos. Significa dramatizar a interação em vez de apenas relatá-la.

## Lugar novo precisa existir antes de virar coordenada

Na primeira entrada relevante em um lugar, oferecer ao menos alguns elementos que deem corpo ao espaço, escolhidos conforme a situação:

- impressão visual e escala;
- luz;
- som;
- cheiro;
- temperatura/ar;
- materiais e desgaste;
- disposição espacial útil;
- sinais de quem vive ou trabalha ali.

Depois que o lugar já estiver estabelecido na conversa corrente, não repetir a descrição inteira a cada turno.

## NPC novo precisa ter presença antes de virar ficha

Na primeira interação relevante, quando houver material suficiente, usar alguns elementos de presença:

- aparência ou silhueta perceptível;
- voz e ritmo de fala;
- gesto ou hábito;
- maneira de ocupar o espaço;
- atitude atual diante de Ren.

Não inventar segredo, competência mecânica ou história passada apenas para colorir. A textura é descritiva, não licença para criar fatos de enredo.

## Textura narrativa dirigida

`cenario/texturas/` contém **paletas pequenas e opcionais**, não uma nova enciclopédia.

Regras:

- cada fragmento deve permanecer pequeno (alvo: até 2 KiB);
- carregar apenas para NPC/local presente e relevante;
- `contexto.py npc "Nome"` pode acrescentar a paleta de NPC à consulta dirigida já necessária;
- `contexto.py local "Nome do lugar"` consulta uma paleta de lugar em L2;
- normalmente consultar uma vez ao apresentar o elemento ou após ausência longa, não a cada fala;
- paleta não é fonte de segredo, regra, estatística ou evento histórico;
- campos marcados como sugestivos são **matéria-prima de descrição**, não cânone até aparecerem na ficção;
- âncoras canônicas continuam vindo de estado, relação, cenário e eventos pendentes.

Se relação/estado já bastarem e nenhuma descrição adicional for necessária, não consultar textura apenas por ritual.

## Mecânica não deve engolir a prosa

Rolagens e números precisam continuar claros, especialmente em combate. Mas uma cena não deve virar relatório de testes.

Preferir:

1. narrar o acontecimento;
2. mostrar o resultado mecânico de forma curta quando ele for útil ao jogador;
3. continuar a consequência ficcional;
4. devolver o controle no ponto natural.

Não repetir CA, PV, Ki, dinheiro, hora e localização por hábito quando não mudaram nem são necessários para a decisão.

## Relação com a economia de tokens

A principal economia vem de não reler material frio, não abrir arquivos enormes, reduzir round-trips e evitar write amplification. Prosa adicional aumenta output e o contexto corrente da conversa, mas vai para uma transcrição que permanece fria depois.

Portanto, quando houver conflito entre **cortar uma leitura inútil** e **cortar uma descrição que torna a cena viva**, corte a leitura inútil.

## Critério de parada

A política de acesso continua valendo: pare de **buscar** quando o contexto for suficiente.

Isso não significa parar de **narrar** assim que os fatos mínimos forem conhecidos.

Primeiro obtenha apenas os fatos/texturas necessários. Depois use esse material para contar a cena com a densidade que ela merece.
