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
  `iniciativa_elenco`;
- nomeação explícita em `nomes_npcs` e bootstrap mínimo em `npc_stubs`.

Os arquivos anteriores permanecem motores internos, compatibilidade e portas de
manutenção. A fachada não cria cache canônico, estado paralelo, scheduler,
scan geral de NPCs ou writer canônico. O RNG auxiliar de nomeação só roda sob
pedido explícito para NPC novo, nunca no preparo de NPC já conhecido.

## NPC novo: identidade e nomeação obrigatória

O domínio dono é `npc_continuity_and_social_behavior`, implementação `1.1.0`.
`npc_stubs` materializa a identidade mínima somente após a confirmação canônica
da cena. O módulo não decide que um NPC deve existir: essa necessidade vem da
ficção causal, não do sorteio de nome.

Antes de nomear qualquer NPC original novo, consultar o catálogo do jogador
`nomes_npcs_forgotten_realms.csv` pela fachada, nunca inventar uma alternativa por
memória do modelo nem ler o CSV inteiro no contexto. Selecionar os filtros reais:
gênero, raça e região **de origem/tradição nominal**, não presumir que residência
define cultura. `--cultura` é opcional, mas nome e sobrenome sempre pertencem à
mesma cultura/sub-raça. A normalização ignora caixa/acentos; região aceita os
valores primários e os itens compatíveis separados por `;` ou ` / ` no CSV, sem
fuzzy matching, traduções geográficas presumidas ou fallback silencioso.

```bash
poetry run python ferramentas/npc_continuity_and_social_behavior.py gerar-nome --reserva <chave-estavel-do-novo-npc> --genero masculino --raca Humano --regiao 'The Vast'
```

A chave identifica a intenção estável de criar **essa pessoa**, não uma tentativa
de sorteio. A saída entrega `nome_completo`, entradas escolhidas, cultura, status e
proveniência do CSV, além de `usos_antes` por componente. Usar o nome retornado
verbatim na proposta da cena. Retry usa a mesma chave/filtros e recebe o mesmo
nome; mudar os filtros sob a mesma reserva falha.

Política padrão:

- impedir tanto nome quanto sobrenome já usados, incluindo reservas pendentes;
- contar pessoas únicas dos índices compactos `estado/npcs/index.yaml` e
  `estado/relacoes/index.yaml`, sem escanear fragmentos, histórico ou transcrições;
- não contar duas vezes o mesmo ID presente nos dois índices, nem a reserva cujo
  nome já foi materializado; aliases normalizados também protegem identidade;
- não reutilizar nome completo existente ou reservado, mesmo com permissão;
- pool esgotado ou filtros sem candidatos falham: ampliar origem/cultura só por
  razão ficcional explícita, ou pedir autorização ao jogador para `--permitir-reuso`;
- com reuso autorizado, sortear apenas entre as combinações de menor uso total;
  o resultado sinaliza `reuso_componentes`, não fabrica parentesco.

`--sem-sobrenome` exige intenção explícita de nome único. Tipos `clã`, `tribo`,
`dinástico` e `alcunha` só são usados com `--tipo-sobrenome <tipo>`: nunca converter
um clã em família automaticamente. Nome de virtude neutro pode servir de nome
pessoal quando compatível com os filtros. O catálogo oferece nomes, não prova
que a pessoa existe no cenário oficial nem valida raça/região para a época da
campanha; esse julgamento continua sob as fontes autorizadas.

Exceções estritamente documentadas:

- NPC canônico já existente: preservar ID/nome; não sortear nem renomear;
- personagem de fonte autorizada ainda não cadastrado, nome explicitamente
  escolhido pelo jogador ou parentesco já estabelecido: `registrar-nome` exige
  `--reserva`, `--nome`, `--origem fonte_autorizada|escolha_jogador|parentesco_canonico`
  e `--evidencia` literal/referência autorizada. A exceção não é licença estética
  para inventar nomes, parentesco ou contornar o pool; duplicata completa falha.

No repositório com catálogo instalado, `npc_stubs` recusa um nome novo sem reserva
na preparação e revalida antes de materializar. Lotes validam todas as reservas
antes da primeira escrita; ticket cuja reserva mudou exige novo preparo. A
origem nominal (IDs do CSV ou exceção evidenciada) acompanha fragmento/histórico
na confirmação. Fixtures legadas sem catálogo/reservas preservam o
contrato anterior, sem acesso ao repo vivo. O check público exige o catálogo e
valida reservas, de modo que fonte ausente/corrompida aparece no preflight.

Reservas vivem em `runtime/reservas-nomes-npcs.yaml`: são controle operacional
não canônico, não NPCs nem um segundo contador de cânone. Os usos são derivados
dos índices atuais a cada nomeação. A seleção é protegida por lock e instalação
atômica. Reserva não cria presença, relações, medidores, agenda, quest ou
conhecimento; a confirmação de cena mantém seu writer e seus gates habituais.
Nome materializado não pode ser liberado. Proposta abandonada antes da narração:
`cancelar-nome --reserva <chave>`; chave cancelada não volta a sortear. Pessoa já
nomeada na ficção exige persistência/correção explícita, nunca cancelamento para
apagar histórico. `catalogo-nomes` lista filtros disponíveis sem escrever dados.

A régua avaliativa permanece `4.0.0`: esta é uma capacidade operacional aditiva
de identidade, não uma alteração na semântica das notas. O recibo modular cobre
as novas portas, mas não converte reserva de nome em NPC materializado.

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
