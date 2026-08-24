# Task 27 — Relationship-Aware Dialogue

## Problema

A campanha já possuía papéis conversacionais para NPCs recorrentes e, desde a Task 26,
um estado relacional tipado. Mesmo assim, a fala podia continuar monotônica: NPCs com
personalidades muito diferentes tendiam a reagir a Ren como se toda conversa pedisse
censura, conselho ou reenquadramento moral.

A Task 27 transforma afinidade/confiança em **modulador de interpretação**, não em novo
motor de diálogo.

## Fontes

A fonte relacional continua sendo a Task 26:

- `medidores.vinculo` = afinidade;
- `medidores.confianca` = confiança;
- `medidores.risco_percebido` = pressão adicional de cautela/limite;
- `estado/relacoes/<id>.yaml` continua guardando nuance em prosa.

O papel conversacional em `cenario/texturas/index.yaml` continua descrevendo a
**personalidade funcional** do NPC. A relação não troca o papel; muda como esse papel é
expresso diante de Ren (ou da identidade pela qual o NPC o conhece).

## Projeção no mesmo L2

`contexto npc <nome>` já carrega medidores, relação e textura dirigida. Depois de aplicar
os deltas pendentes da sessão aos medidores, a consulta chama uma função pura que produz
`dialogo_relacional`.

Não há nova leitura. A projeção usa somente dados que já estão em memória.

Ela contém:

- modo relacional;
- afinidade/confiança atuais;
- risco percebido;
- tom;
- grau de abertura;
- forma recomendada de discordância;
- gate explícito para conselho;
- modulador de risco quando pertinente;
- papel base quando o NPC possui `papel_conversacional`.

## Quatro quadrantes principais

### Baixa afinidade + baixa confiança

Formalidade, contenção ou suspeita. O NPC pode cooperar por necessidade, medo, contrato
ou instituição, mas não presume intimidade. Discordância deve atacar fato/limite/risco,
não virar uma palestra sobre a vida de Ren.

### Alta afinidade + baixa confiança

O NPC pode gostar, amar, proteger ou se importar com Ren e ainda desconfiar de sua palavra
ou julgamento. O diálogo mostra calor e reserva simultaneamente: proximidade pessoal não
vira obediência automática.

### Baixa afinidade + alta confiança

O NPC respeita competência, previsibilidade ou palavra de Ren sem necessariamente gostar
dele. A fala pode ser profissional, eficiente e cooperativa, mas não fabrica amizade ou
vulnerabilidade.

### Alta afinidade + alta confiança

Familiaridade, humor, espontaneidade, vulnerabilidade e franqueza podem aparecer quando
combinam com a personalidade. Discordar continua possível; a diferença é que uma pessoa
próxima não precisa transformar cada discordância numa reprimenda formal.

## Zona intermediária ou desconhecida

Valor `5`, `null` ou combinação sem quadrante forte não é convertido artificialmente em
intimidade ou hostilidade. O papel e a prosa canônica da relação continuam predominantes.

## Guardrail anti-sermão

**Conselho não é a iniciativa padrão de um NPC.** Mesmo um clérigo, cuidador, patrono,
amigo íntimo ou autoridade só deve aconselhar/censurar quando pelo menos um gatilho
concreto estiver presente:

1. Ren pediu opinião, conselho ou avaliação;
2. o assunto cai diretamente na responsabilidade/papel daquele NPC;
3. existe risco imediato que tornaria o silêncio artificial ou irresponsável.

Mesmo nesses casos, preferir uma observação concreta, limite, pedido ou preocupação e
devolver espaço para Ren responder.

Saudação, conversa casual, reencontro, brincadeira, atualização cotidiana ou simples
discordância **não são justificativa automática para sermão**. Uma censura já compreendida
não deve ser repetida em cada nova fala só porque o NPC continua preocupado.

## Risco percebido

`risco_percebido >= 8` pode endurecer limite, urgência e cautela. Ele não substitui os
outros eixos. Silva pode ter afinidade/confiança altas e risco 10: isso significa cuidado
mais protetivo e limites mais fortes, não que ela deva tratar Ren com distância ou lhe dar
uma bronca a cada encontro.

## Papéis revisados

Os perfis opt-in existentes são mantidos, mas sua redação deixa explícito que o papel só
entra em primeiro plano quando o assunto o exige. Exemplo: Maerra continua capaz de
aconselhar pastoralmente, porém conversa casual pode ser apenas conversa; Luath continua
operacional, porém não precisa transformar toda interação em debriefing; Nera pode falar
como pessoa amada, não como dispositivo socrático.

## Custo

Contrato: `baseline/relationship-aware-dialogue-orcamento.yaml`.

- 0 chamadas extras por `contexto npc`;
- 0 fontes extras;
- 0 leitura nova em `status`/`cena`;
- 0 scheduler/RNG/estado persistente;
- projeção pura e compacta;
- deltas pendentes da Task 26 afetam imediatamente o tom antes do checkpoint.

A Task 30 poderá reutilizar o mesmo estado para iniciativa social, mas a Task 27 não cria
qualquer iniciativa automática nem escolhe falas.
