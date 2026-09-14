# Continuidade e comportamento social de NPCs v2

## Contrato público

`npc_continuity_and_social_behavior.py` é a fachada pública do domínio. Ela
compõe, sem copiar suas fontes de verdade:

- elenco e memória projetada de `memoria_cena`;
- fatos sociais transacionais de `memoria_duravel`;
- afinidade, confiança e risco de `estado_relacional`;
- voz estável de `personalidade_decisoria` e expressão de
  `dialogo_relacional`;
- suspeitas e confirmações de `identidades`;
- reputação por público e persona de `reputacao_publica`;
- política e recibos exactly-once de `iniciativa_social` e
  `iniciativa_elenco`.

Os arquivos anteriores permanecem motores internos, compatibilidade e portas de
manutenção. A fachada não cria cache canônico, estado paralelo, scheduler, RNG,
scan geral de NPCs ou writer.

## Contexto do NPC

Os quatro estados não são intercambiáveis:

```text
presente
→ pertence ao elenco consolidado no local corrente

contactável
→ possui canal já validado para esta janela

mencionado
→ foi selecionado para memória ou citado na preparação

apenas conhecido
→ existe nos índices, mas não está presente, contactável ou mencionado
```

A precedência acima serve somente para classificar uma pessoa dentro da cena.
`--participante` seleciona memória prospectiva; `--interlocutor` solicita uma
decisão social. Nenhum dos dois produz presença. Um NPC mencionado ou apenas
conhecido permanece inelegível para ação física e para abertura incidental sem
canal.

## Projeção e conhecimento

A memória de cena abre índices e fragmentos apenas para os IDs selecionados. Para
cada NPC, ela projeta seu próprio estado, a relação correspondente, sua textura e
os compromissos em que está envolvido. Fontes reservadas do narrador não entram
nessa projeção.

Informação transmitida é registrada no mesmo `cronica concluir` com emissor,
destinatário, canal, estatuto e evidência literal. Só o destinatário explícito
recebe `informacoes_recebidas`; incluir um terceiro em `participantes` não lhe
confere conhecimento. Rumor continua rumor. Memória do narrador nunca é tratada
como memória do NPC.

Retomada fria recompõe o elenco consolidado e volta a projetar os fragmentos
dirigidos. Recibo de contexto permite delta apenas quando a base ainda está
presente; o arquivo de recibo não substitui a base nem o cânone.

## Voz, relação, identidade e reputação

O perfil decisório deriva somente do papel conversacional estruturado. Humor,
tom recente e risco modulam expressão, mas não reescrevem valores, desejos,
receios, métodos ou limites. A avaliação de alternativas é declarativa: ausência
de conhecimento, capacidade, recurso, presença/canal ou autoridade mantém a
opção inviável e nunca executa ação.

Mudança posterior de afinidade ou confiança deve ser declarada como
`memoria.fatos` de tipo `relacao`, com Ren, o NPC e evidência literal no mesmo
concluir. O compilador durável gera tanto o incremento quanto a memória; delta
relacional incremental enviado à parte é recusado. Bootstrap de NPC novo continua
com seu contrato próprio.

Suspeita de identidade guarda evidências sem virar confirmação. Confirmação exige
fato canônico explícito. Reputação pertence ao par `público × persona percebida`;
efeito atribuído a Kage não migra automaticamente para Ren ou Shinta.

## Iniciativa social

Somente NPC presente ou contactável pode ser elegível. O preparo reutiliza a
memória já carregada e registra uma decisão por proposta causal, sem consulta por
NPC. No máximo uma abertura pode ser apresentada por janela. A mesma proposta já
apresentada vira silêncio estrutural; conselho ou censura só reabrem com fato
causal novo.

O resultado é sempre explícito: abertura selecionada, silêncio justificado,
inelegibilidade ou adiamento por pressão superior. Uma abertura apresentada
exige evidência literal e recebe recibo reservado exactly-once depois do writer
canônico concluir. O recibo não cria encontro, segredo, sidequest, presença nem
ação de Ren.

## Telemetria e custo

O ledger v2 separa três subcapacidades:

- `social_initiative`;
- `presence_and_identity`;
- `relationship_memory_reputation`.

Consulta dirigida de NPC conta como continuidade, não como iniciativa. Esta só é
observada quando há `--interlocutor` ou decisão/recibo de `iniciativa_elenco`.
O módulo emite sinais de presença/contactabilidade, silêncio, repetição, efeito
visível e persistência social. Depois de um `concluir` bem-sucedido, o envelope
`continuidade_npc` informa quantidade, evidência e tipos dos fatos persistidos;
ele é telemetria derivada, não uma nova fonte de memória. Qualidade de voz ou
contradição sem marcador estruturado continua sujeita a adjudicação humana, sem
inferência por substring da prosa.

O custo fecha uma vez no módulo pai. Subcapacidades expõem o mesmo turno sem
duplicá-lo. Turno sem NPC não ganha chamada, leitura ou sinal modular novo.

## Manutenção

Check público:

```bash
poetry run python ferramentas/npc_continuity_and_social_behavior.py check
```

O preflight chama essa fachada. Os perfis `cronica`, `mundo` e `runtime` incluem
a regressão modular. Fixtures de voz, memória e conhecimento devem ser
controladas em diretório temporário; prosa viva da campanha não é snapshot de
teste.
