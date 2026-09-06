# Acionamentos causais dos agentes leves — NV-07

## O que muda

A cadência rotineira continua no amanhecer: uma nova reavaliação por checkpoint,
no máximo duas pendências leves ativas, reaproveitando decisões negativas quando
as fontes declaradas e a versão do perfil continuam iguais. Ela deixa de ser o
único caminho. Uma mudança efetiva em dependência declarada ou uma janela de
compromisso alcançada encaminha uma avaliação ao agente afetado, mesmo de dia.

O acionamento não executa um plano. Não significa que o NPC compareceu, aceitou,
cumpriu uma promessa, venceu oposição ou recebeu conhecimento. A interpretação
e a decisão continuam no lote de Mundo Vivo; ações e consequências continuam
pelos writers e gates existentes. Execução de planos e contato efetivo pertencem
às etapas seguintes do plano, não a esta instalação.

## Dependências e condições

São usados os IDs e as fontes já existentes: `fontes_causais` no índice leve,
o fragmento `npc:<id>` correspondente ao agente e os `envolvidos` de compromissos
em `estado/estado-atual.yaml`. Caminhos de fragmentos são resolvidos pelos índices,
não pelo nome presumido do arquivo. A comparação usa o conteúdo efetivo antes e
depois dos deltas; um `set` que não muda o valor não aciona ninguém.

A dependência é estrutural e explícita. A ferramenta não afirma compreender a
importância semântica de toda alteração, não interpreta qualquer frase como
prazo e não inspeciona todos os perfis. Mudanças fora desses vínculos continuam
seguindo os mecanismos anteriores. Informação registrada para alguém não se
transfere automaticamente aos demais envolvidos em uma cena.

Prazos usam somente `janela.inicio` e `janela.fim` estruturados. Atingir o fim pede
avaliação, não declara descumprimento automático. Uma descrição como “algum dia”
continua sem instante inferido. O início e o fim de uma mesma versão de compromisso
têm recibos independentes por agente; o recibo não depende de o ID ainda caber na
lista de conclusões recentes. Cancelamento, substituição e inativação revogam as
condições que deixaram de existir, sem inventar cumprimento ou resultado narrado.

## Caminho operacional

O narrador continua usando `cronica preparar` e `cronica concluir`. No concluir,
o detector identifica mudanças relevantes e reutiliza o checkpoint de cena já
existente. O registro inicial continua transcrição + buffer; o checkpoint
adicional tem custo de leitura e consolidação e pode ocorrer antes do amanhecer.
Não há terceira chamada ritual de ferramenta nem avaliador de IA por NPC.

Na consolidação, a alteração canônica, o sinal reservado e o marcador da barreira
entram no **mesmo journal e staging**. Recuperar uma instalação interrompida
reaplica os mesmos bytes, não recalcula uma nova decisão nem perde o acionamento.
Um journal aberto impede a avaliação da mistura parcial de arquivos.

Antes de comprimir tempo, a consulta de fronteira existente também considera
compromissos. Um encontro cinco minutos adiante interrompe uma espera mesmo que
as duas vagas rotineiras estejam ocupadas. Ao chegar à fronteira, o próprio
concluir promove o checkpoint, e o preparar seguinte observa a barreira.

Resolver a barreira continua em lote:

```sh
poetry run python ferramentas/resolver_fronteira.py preparar
poetry run python ferramentas/resolver_fronteira.py aplicar <<'JSON'
{"lote_id":"<lote recebido>","sem_mudanca":[
  {"id":"<pendência>","token":"<token recebido>","nota":"<motivo concreto>"}
]}
JSON
```

As duas chamadas acima pertencem à resolução de uma fronteira que efetivamente
existe, não ao turno comum. O jogador não precisa executá-las. Avaliar os itens
juntos e enviar somente os que realmente não produzem fato; os demais permanecem
abertos para resolução pelos mecanismos existentes. Os tokens incluem causas e
assinatura integral da fonte consultada, inclusive fatos omitidos da projeção;
planos obsoletos são recusados antes de aplicar as decisões do lote.

Ausência de ação de Ren ou “nenhum fato novo” não justifica descartar uma condição
que acabou de chegar. Uma decisão sem mudança exige motivo concreto e reutiliza
o cache negativo existente. A validação é estrutural: não é prova automática da
verdade do motivo escrito pelo narrador.

## Prioridades sem apagar trabalho

Causas novas do mesmo agente são reunidas na pendência já aberta. Prazos têm
precedência sobre mudanças de fonte na admissão de novos acionamentos; avaliações
leves puramente rotineiras ficam depois de condições causais no lote. Eventos e
operações canônicos não são reclassificados como rotinas nem passam a aceitar no-op.

Se as duas vagas estiverem ocupadas por rotinas, uma rotina é suspensa com seu
registro e ID originais. Depois de concluir o acionamento, ela retorna com o mesmo
ID. Se as vagas já tiverem causas reais, o trabalho restante permanece reservado
em espera e é promovido quando uma vaga abre, sem esperar outro amanhecer. A
conclusão direta por `agentes_leves.py concluir-noop` e os retries também repõem
as vagas e sincronizam a barreira. A cadência não cria uma duplicata da rotina
suspensa. Resolver uma alteração própria não inicia um ciclo de autoavaliações;
outros agentes explicitamente afetados continuam sendo notificados.

`acionamentos_leves` é metadado de entrega dentro de
`narrador/mundo/estado.yaml`, não outro arquivo de cânone. O teto continua duas
pendências leves **ativas**; a espera não é apresentada como aumento gratuito da
capacidade. Há limites adicionais explícitos: oito causas por agente, 32 sinais
no controle e 16 KiB para o controle causal. Excedê-los falha, em vez de descartar
trabalho silenciosamente. O buffer/recuperação transacional permanecem autoridades.

## Contexto e orçamento

Uma pendência causal carrega no máximo **um fragmento dirigido**, em vez de somar
perfil estático, relação e medidor inteiros. A projeção usa a seleção NV-03/NV-05,
as informações já disponíveis nos índices e os compromissos pertinentes do
estado. A base integral consultada é assinada; seleção não enfraquece revalidação.
O contexto causal tem teto de **2.560 bytes**, compartilhado por causas e memória,
sem multiplicar o teto por causa. Fatos que não couberem e perfis adicionais só
são recuperados por aprofundamento dirigido quando necessários. A consulta do
perfil permanece apontada na própria resposta.

Não há varredura de transcrições, histórico, diretórios de NPCs ou todos os perfis.
O turno sem relação, medidor, compromisso ou tempo alterados não faz leitura causal.
Mudanças e consultas temporais têm custo explícito de índices/estado; uma condição
relevante pode promover uma consolidação mais cedo. A economia pretendida vem de
não avaliar personagens não afetados, reunir causas, manter cache negativo válido
e resolver em lote. Nenhuma dessas propriedades comprova economia de tokens
nativos ou qualidade da narração sem episódios comparáveis do benchmark NV-02.

## Validação e instalação

Os cenários de regressão são temporários: promessa NV-04, prazo curto, fontes
renomeadas, rotina suspensa, retomada das vagas, cache, cancelamento/substituição,
repetição, token obsoleto e recuperação do journal. Não se altera o save para
popular fixtures nem se infere retroativamente quem deveria ter agido. O código
passa a operar sobre dependências e compromissos canônicos quando o fluxo existente
processar uma mudança ou sincronização de mundo. Não há backfill de ações.
