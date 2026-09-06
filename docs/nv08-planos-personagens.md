# NV-08 — Continuidade executável de planos de personagens

## Responsabilidade e autoridade

`planos_personagens.py` conecta a intenção estabelecida no perfil à agenda, à fila
e às transações do Mundo Vivo. O narrador ainda escolhe a conduta e registra o que
aconteceu; o motor não chama IA, não escolhe ações nem sorteia sucessos. Um plano
pode continuar sem contato com Ren. Ausência de Ren não justifica apagá-lo.

O perfil conserva a intenção; o controle `planos_personagens` no **estado do mundo
existente** registra sua execução. Não é uma segunda ficha, nem uma cópia de todos
os recursos/conhecimentos. O passo aponta os requisitos; seus valores atuais
continuam nos domínios canônicos de origem. O resultado guarda a referência à
transação; o histórico completo permanece no ledger da sessão, append-only.

Não há migração automática dos planos em prosa. Objetivo deve corresponder
literalmente a objetivo/ação/iniciativa já estabelecidos no perfil. Informação
faltante não é inventada: falta de presença, conhecimento ou recurso impede a
tentativa. A adoção acontece por registro explícito; este PR não reescreve o save
nem apresenta fixtures como acontecimentos de Silva, Nera, Luath ou Ren.

## Portas existentes, não um novo ritual

1. No `cronica concluir` da cena pertinente, incluir o delta `definir` junto dos
   acontecimentos narrados. O writer força checkpoint na mesma chamada.
2. Quando a condição temporal chegar, a agenda existente produz a pendência.
   A barreira dentro de `cronica preparar` encaminha à resolução de fronteira.
3. `resolver_fronteira.py preparar` projeta os planos devidos; uma única avaliação
   decide os eventos; `resolver_fronteira.py aplicar` recebe todos em `planos`.
   Não fazer uma chamada de IA/consulta por NPC.
4. `tentar` compromete a tentativa e consome os custos uma vez. Após a duração,
   `resolver` registra resultado e a próxima escolha. O próximo prazo volta à
   mesma agenda. Não avançar o relógio dentro de uma decisão do plano: usar o
   fluxo temporal normal e respeitar a fronteira antes de narrar espera/viagem.

Preparações são somente leitura. IDs, revisões e tokens detectam decisões
obsoletas. Repetir o mesmo lote é idempotente; mudar uma decisão já aplicada é
erro. Um journal interrompido precisa ser recuperado antes de continuar.

## Definição — exemplo sintético, não dados da campanha

O exemplo supõe perfil e fontes já estabelecidos para `escriba_fixture`. `fato`
precisa aparecer literalmente em `narracao` da transação original. Incluir o
objeto abaixo em `deltas`, não escrever o controle/agenda diretamente.

```yaml
alvo: plano:documentos
op: registrar
visibilidade: narrador
valor:
  evento: definir
  revisao: 0
  fato: A escriba decidiu preparar os documentos.
  agente: {tipo: leve, id: escriba_fixture}
  objetivo: Rotina documental.
  passo:
    id: preparar
    acao: Preparar os documentos para entrega.
    em: {data: '7 Eleasis, 1372 DR', hora: '08:03'}
    duracao_minutos: 5
    local: Circo
    condicoes: []
    recursos: [{caminho: recursos.moedas, quantidade: 1}]
    conhecimento: [documentos]
    resolucao:
      tipo: factual
      sem_oposicao:
        arquivo: estado/npcs/escriba_fixture.yaml
        caminho: npc.oportunidade.sem_oposicao
        valor: true
```

Tipos de responsável: `leve` ou `estrategico`; nunca Ren. Uma definição cria
`pretende`, não `tentou` nem `concluido`. Plano ativo não pode ser sobrescrito por
outra definição. Reutilizar ID terminal exige sua revisão atual; o ledger antigo
é preservado. Não criar objetivos retroativos para encaixar este contrato.

## Condições, conhecimento, recursos e deslocamento

Referência factual exige exatamente `arquivo`, `caminho` e `valor` esperado,
com igualdade tipada e caminho YAML dentro de `estado/` ou `narrador/`.
São permitidas até quatro condições, quatro custos e seis IDs de conhecimento.
Fontes ausentes/obsoletas bloqueiam; não tornam a condição verdadeira.

Para ação simples, o estado indexado do próprio NPC contém pools numéricos em
`npc.recursos.<nome>`. O compilador agrega custos de todos os planos do lote e
emite deltas `inc` no mesmo registro. Não cobra no preparo, na intenção, no retry
ou outra vez na resolução. Não aceita sobrescrever/compensar o custo por `set`.

Agente leve exige `npc.presenca` com `local`, `estado: presente` e
`em_deslocamento: false`. Agente estratégico reutiliza presença, mobilidade,
elegibilidade local e gates de arco existentes. Conhecimento vem do próprio
perfil/NPC, com ID, fonte e evidência literal ainda localizável; o conhecimento de
Ren ou do narrador não supre a ausência. Rumores continuam sendo rumores: o
contrato confirma disponibilidade da informação, não sua veracidade.

Duração do passo é um requisito declarado antes da tentativa, não um calculador
de rotas. O narrador deve usar as regras de deslocamento/resolução existentes;
local incompatível impede iniciar e o resultado não pode anteceder o término.
Ações sobre outros atores, combate e consequências adversariais não usam o atalho
factual: permanecem nos motores próprios, incluindo Task44/50/51 e Protected Core.

## Eventos do lote

Todos têm `evento`, `revisao` atual e `fato` literal. A lista `planos` usa os mesmos
`id` e `token` devolvidos pelo preparar; itens omitidos continuam abertos.

```yaml
lote_id: frn1.<recebido>
planos:
  - id: mundo-<recebido>
    token: <recebido>
    evento:
      evento: tentar
      revisao: 1
      fato: A escriba começou a preparar os documentos.
```

`bloquear` acrescenta `motivo` e `retomar_em` (instante futuro obrigatório).
`replanejar` acrescenta `motivo` e novo `passo`. `desistir` acrescenta `motivo`.
Tentativa em curso não pode ser apagada por essas operações: primeiro registrar
seu resultado. Não usar `sem_mudanca`, `mundo concluir` ou `barreira concluir`
para remover uma pendência de plano.

`resolver` exige todos estes campos adicionais, inclusive os nulos:

```yaml
resultado: sucesso  # sucesso | falha | parcial
seguimento: concluir  # prosseguir | mudar_estrategia | bloquear | desistir | concluir
motivo: Os documentos foram preparados e o objetivo desta etapa foi alcançado.
passo: null
retomar_em: null
rolagem: null
prova:
  arquivo: estado/npcs/escriba_fixture.yaml
  caminho: npc.documentos
  valor: prontos
```

No resultado factual, a mesma decisão inclui `deltas` normais que materializam a
prova no próprio NPC, por exemplo `set documentos=prontos`. Prova antiga que não
mudou não conta como resultado novo. `prosseguir` e `mudar_estrategia` exigem novo
passo com ID distinto; mudar estratégia também muda a conduta. `bloquear` exige
reavaliação futura. Falha/parcial não podem virar `concluir`: prosseguir, mudar,
bloquear ou desistir continuam possíveis. Nenhum desses eventos decide por Ren.

## Mecânica e operações

`resolucao: {tipo: teste, bonus: <referência>, cd: <referência>}` fixa ambos antes
da tentativa; bônus deve pertencer ao responsável. A primeira versão suporta
**teste simples de d20 normal**, não combate nem vantagem/desvantagem. Usar as
ferramentas de dados existentes com rótulo
`plano:<id>:<transacao_da_tentativa>` e incluir sua saída literal em
`rolagens_ocultas` da decisão. `rolagem` contém o valor natural e `prova` é nula.
O validador recompõe a conta contra a CD comprometida. Isso verifica consistência
do recibo, não autentica entropia: continua proibido escolher/inventar os dados.

`resolucao: {tipo: operacao, operacao_id: <id>}` referencia operação Task51 do
mesmo responsável/local. Não repetir custos: recursos, oposição, composição,
rolagens e efeitos pertencem ao motor existente. O plano só registra tentativa
após compromisso válido e só recebe resultado depois da resolução canônica.
A CLI existente `operacoes_concorrentes.py resolver` aceita agora
`--desfecho sucesso|falha|parcial`, além da prova e do texto já exigidos.
O desfecho e o texto devem coincidir com o evento de resultado do plano.
Operações antigas sem desfecho estruturado **não são reinterpretadas como sucesso**.

## Persistência, recuperação e orçamento

Os deltas reservados passam pelo mesmo registro e journal de consolidação; estado
do NPC, controle do plano, agenda, barreira e ledger são instalados juntos.
O fingerprint do registro protege retries depois da consolidação. NV-07 continua
usando exclusivamente `acionamentos_leves`; a alteração causada pela própria
execução não produz uma segunda avaliação falsa do mesmo NPC, sem silenciar
outros afetados. Grupos de operações de um lote misto são pré-validados sem
escrita antes de materializar os planos.

Tetos: oito slots de planos no controle, 24 KiB para o controle, 2.400 bytes por
passo, 4 KiB por projeção de plano, referências dirigidas de até 32 KiB. O lote
mantém o teto existente de 16 pendências; a fila de agentes leves mantém seu teto
de duas. Excesso falha explicitamente: não truncar fatos indispensáveis. Não há
varredura de perfis; um perfil é carregado por plano devido, com as fontes
dirigidas dos requisitos. Uma lista vazia não acrescenta dados ao preparo legado.

Medição reproduzível em `test_planos_personagens.py`, fixture isolada: lote neutro
885 bytes YAML, preparar com um plano 3.188, argumentos da tentativa 209, retorno
do aplicar 1.085 e contexto do plano 1.166. Não são tokens nem medida do episódio
narrado. O caminho com plano acrescenta informação/trabalho; o turno comum não
ganha nova chamada de IA. Não se declara economia global nem melhoria literária
sem a avaliação de episódios prevista no plano NV-02/NV-12.

Os testes cobrem jornadas fora de cena, duas tentativas em uma transação, custos
compartilhados, prazo, bloqueios, sucesso/falha, mudança de estratégia, operações
reais, CLI em outro processo, inconsistências, retries e recuperação interrompida.
As expectativas usam fixtures, não valores mutáveis do save da campanha.
