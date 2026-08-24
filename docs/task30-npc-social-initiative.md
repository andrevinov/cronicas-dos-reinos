# Task 30 — NPC Social Initiative

## Problema

As Tasks 26 e 27 fizeram duas coisas diferentes:

- Task 26 deu estado operacional uniforme a **afinidade**, **confiança** e risco percebido;
- Task 27 usa esses mesmos medidores para calibrar **como** um NPC fala.

Ainda faltava uma pergunta simples: **quem pode abrir a interação?**

Sem uma regra explícita, NPCs próximos podiam parecer passivos demais, esperando Ren perguntar, procurar ou puxar todo assunto. A solução não deve ser um scheduler social, uma rolagem de “NPC lembra de Ren” nem um sistema paralelo de mensagens.

A Task 30 transforma o mesmo estado relacional em uma **permissão de iniciativa social**.

## Escopo estreito

Iniciativa social significa apenas isto:

> se o NPC já está legitimamente presente, ou já existe um canal canônico de contato, ele pode iniciar a troca sem esperar uma solicitação de Ren?

Ela **não** decide que o NPC apareceu, foi até Ren, enviou recado, encontrou seu esconderijo ou ganhou conhecimento novo.

Portanto a Task 30 não cria:

- presença;
- encontro;
- deslocamento;
- canal de contato;
- conhecimento ou segredo;
- side quest;
- compromisso;
- evento de Mundo Vivo;
- scheduler;
- RNG;
- estado persistente novo.

Presença incidental continua sendo apenas presença candidata da Task 16. Iniciativa social só pode agir depois que presença/canal forem legítimos por outra fonte.

## Mesma consulta L2

`contexto.py npc <nome>` já carrega os medidores e aplica deltas pendentes antes de produzir `dialogo_relacional`.

A Task 30 não adiciona consulta. A projeção `dialogo_relacional` agora inclui um bloco compacto `iniciativa_social`, calculado em memória com os mesmos dados já carregados.

Isso significa que uma melhora relacional pendente pode mudar imediatamente a iniciativa antes do checkpoint, sem reabrir arquivo e sem estado duplicado.

## Modos

A Task 30 usa exatamente os cinco modos relacionais já derivados pela Task 27.

### Alta afinidade + alta confiança → `espontanea`

O NPC pode abrir uma troca cotidiana sem motivo externo adicional, desde que já esteja presente/contatável.

Exemplos permitidos:

- saudação ou check-in;
- convite, oferta ou pedido leve;
- mencionar uma necessidade própria já sustentada pelo cânone.

Isso não significa que o NPC precise falar primeiro em toda cena. É permissão para espontaneidade, não compulsão narrativa.

### Alta afinidade + baixa confiança → `afetiva_cautelosa`

O afeto pode puxar contato, tentativa de proximidade ou reparação de tensão, mas não autoriza o NPC a entregar segredo, plano sensível ou responsabilidade que a confiança ainda não sustenta.

### Baixa afinidade + alta confiança → `funcional`

O NPC pode tomar iniciativa profissional quando existe motivo ligado ao seu domínio: pedir cooperação, oferecer ajuda funcional ou trazer atualização que legitimamente conhece.

Confiança funcional não fabrica intimidade.

### Baixa afinidade + baixa confiança → `somente_motivo_concreto`

Sem conversa casual artificial. O NPC inicia apenas se necessidade, transação, dever, conflito ou limite concreto já estiverem presentes.

### Intermediária/desconhecida → `situacional`

Valor `5`, `null` ou estado sem quadrante forte não vira espontaneidade por inferência. A iniciativa precisa ser sustentada pelo papel, pela cena ou por contexto compartilhado já canônico.

## Identidade relacional

A iniciativa sempre mira a identidade pela qual aquela relação existe.

Sella da Galeria, por exemplo, possui `identidade_relacional: shinta`. Portanto sua iniciativa social é dirigida a **Shinta**, não a Ren. A Task 30 não usa a Task 28 para fundir identidades privadas e não deixa reputação pública da Task 29 atravessar essa fronteira automaticamente.

## Risco percebido

`risco_percebido >= 8` apenas marca `risco_alto: true` no bloco de iniciativa.

Risco alto pode tornar uma abertura legítima mais cautelosa ou urgente; ele não cria contato sozinho. Em uma relação hostil, risco alto pode inclusive justificar evitar contato desnecessário em vez de procurar Ren.

## Conselho continua separado

**Iniciativa social não é iniciativa de conselho.**

Um NPC próximo pode ser o primeiro a dizer “bom dia”, perguntar como Ren está, convidá-lo a comer ou trazer um assunto próprio sem que isso abra automaticamente o gate de sermão da Task 27.

Aconselhamento/censura continuam exigindo os gatilhos já congelados:

1. Ren pediu opinião/conselho;
2. o assunto cai diretamente na responsabilidade do NPC;
3. há risco imediato que torne silêncio artificial.

## Agência de Ren

A iniciativa produz uma **abertura**, não uma conversa inteira. Depois dela, o espaço volta imediatamente ao jogador.

A camada não pode decidir que Ren aceita convite, responde pergunta, revela informação, perdoa, concorda ou muda de plano.

## Exemplos reais esperados

- **Nera** (8/8): `espontanea`; pode iniciar afeto, check-in ou assunto cotidiano quando legitimamente presente, apesar do risco alto.
- **Luath** (4/7): `funcional`; pode iniciar uma abordagem operacional com motivo de guarda, sem intimidade inventada.
- **Sella da Galeria** (6/6): `espontanea`, mas dirigida a **Shinta**.
- **Pell** (3/4): `somente_motivo_concreto`; não ganha sociabilidade gratuita só porque a ferramenta foi consultada.

## Custo

Contrato: `baseline/npc-social-initiative-orcamento.yaml`.

- 0 chamadas extras por `contexto npc`;
- 0 fontes extras;
- 0 leituras extras em `status`/`cena`;
- 0 scheduler;
- 0 RNG;
- 0 estado persistente;
- projeção de iniciativa <= 700 bytes;
- `dialogo_relacional` inteiro, já com iniciativa, continua <= 1,8 KiB.

A Task 30 deve fazer NPCs parecerem **pessoas que também puxam assunto**, sem transformá-los em notificações ambulantes ou em agentes que teleportam até Ren para gerar conteúdo.