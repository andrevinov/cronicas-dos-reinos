# Revisão integral da sessão 024 — 2026-10-06

## Conclusão

Esta é uma **revisão semântica nova**, feita pelo agente sobre entradas, respostas,
preparos, conclusões e contexto realmente registrado. Não é replay dos 13
pareceres anteriores, nem execução de uma nova sessão.

Há iniciativa própria na ficção: Mori resiste, exige prova, contrapõe uma
alternativa e rompe a perseguição; Aiko exige informações para proteger seu
negócio e decide abrir. Portanto, esta sessão **não demonstra passividade geral
dos NPCs**. Demonstra uma ruptura entre essa ficção e partes da representação
operacional que deveriam sustentar presença, memória e projeção do mundo.

A avaliação encontra problemas concretos e propostas verificáveis de correção.
Ela ainda não aprova o sistema nem comprova todos os problemas relatados pelo
jogador: contratos históricos e bases causais de vários módulos não foram
preservados no recorte.

## Cobertura e interpretação

| Resultado da revisão | Unidades interação × critério |
|---|---:|
| Avaliadas como adequadas | 85 |
| Avaliadas com falha | 22 |
| Não aplicáveis, com motivo | 164 |
| Fontes insuficientes, com lacuna identificada | 137 |
| Sem parecer | 0 |
| **Total decidido** | **408** |

São 34 critérios em 12 observações, incluindo nove entradas ON e três OFF.
Uma entrada composta contém dois commits; número de observações não é número de
transações. Há 107 avaliações da experiência e 164 negativas de aplicabilidade;
**271 decisões confirmadas não significam 271 resultados positivos**.

As 22 unidades com falha incluem o mesmo problema visto em diferentes critérios
e interações. Não são 22 bugs independentes. A espera não autorizada viola dois
critérios, mas corresponde a um acontecimento. Guardrail crítico continua fora
das médias; não há nota global publicável.

“Integral” significa que cada combinação recebeu uma decisão. Não significa que
o avaliador conhece todo o estado histórico do mundo. A revisão registra
abstenção onde falta fonte, mesmo quando seria conveniente produzir uma nota.

## Achados prioritários

### 1. Agência de Ren: decisão voluntária acrescentada

**Evidência pública, S024-I0011:** a entrada pede “Ele irá voltar para o circo
normalmente, andando na rua como senhor Tanaka.” A resposta começa com “Ren
espera alguns minutos antes de deixar o telhado.” Não há ordem do jogador nem
impedimento externo que autorize essa decisão adicional.

**Estágio:** narração. **Conclusão:** violação confirmada; a causa específica no
processo de geração permanece hipótese.

**Correção proposta:** distinguir deslocamento autorizado, consequência externa
e decisão nova do personagem. Frustração declarada pode acompanhar a prosa;
não autoriza escolher uma espera.

**Verificação:** comparar retorno normal, espera explicitamente ordenada e
interrupção externa com causa. Só os dois últimos autorizam narrar a espera.

### 2. Aiko presente na ficção, ausente na decisão social

**Episódios:** pedido de desculpas às 12:24
(`OBS-fcc2ca79463482f4e6f2`) e despedida em S024-I0009. Entrada, resposta anterior
e narração colocam Aiko no balcão. Os preparos com interlocutora classificam sua
presença como ausente e dispensam decisão por ausência. A prosa ainda lhe dá
iniciativa, mas isso não valida a negativa do módulo.

**Estágio:** elegibilidade/contexto. **Mecanismo identificado:**
`memoria_cena_iniciativa.attach` recupera presença salva quando o identificador
da cena é o mesmo, ou quando uma permanência válida conserva a janela. O
narrador usa identificadores novos para sucessivas falas no mesmo restaurante.
Assim, a identidade técnica da interação pode romper a presença física.

**Reprodução isolada na implementação instalada:**

| Entrada controlada | Presença devolvida | Decisão social |
|---|---|---|
| Mesmo identificador, mesmo local, elenco confirmado | presente | requerida |
| Identificador novo, mesmo local e elenco anterior | ausente | dispensada |
| Identificador novo, permanência válida no mesmo local | presente | requerida |

A reprodução usa fixture de perfil social e memória; não reproduz toda a ficha
histórica de Aiko nem prova qual fala seria escolhida. Ela confirma o mecanismo
de perda de presença. A atribuição histórica completa permanece hipótese
respaldada pelas chamadas e pelo resultado observado.

**Correção proposta:** separar identidade da cena física de identidade de cada
interação; preservar presença confirmada enquanto local e continuidade forem
válidos, revalidando saída, deslocamento e contato. Selecionar um participante
continua sem provar presença por si só.

**Verificação:** nova fala no mesmo local deve conservar presença; saída e
mudança real de local devem invalidá-la. O controle deve impedir encontros
fabricados quando só existe menção ou seleção prospectiva.

### 3. Promessas e informação ficam no histórico, com recuperação estruturada incompleta

**Episódios:** bilhete (S024-I0005), palavra de Mori (S024-I0006), exigência de
Aiko e promessa de Tanaka (S024-I0009).

O conteúdo enviado ao writer mostra resumos/consequências, mas o commit final
não traz memória tipada para esses fatos. Na promessa de Tanaka, houve uma
tentativa com `memoria`, participantes e evidência. Após erro de ticket e erro
de ID relacional não indexado, o narrador retirou esse bloco e concluiu com
consequência genérica.

**O histórico não foi apagado:** prosa, resumos e consequências conservam os
acontecimentos. A falha é perder o caminho normal de compromisso/memória com
participantes e recuperação dirigida. Não há prova nesta sessão de que um NPC
já tenha esquecido a promessa numa cena posterior.

**Estágio:** persistência. O compilador de memória é opt-in: sem `memoria`, não
gera seus deltas. Promessa estruturada também exige suporte nos índices de
memória pertinentes; ser um NPC cadastrado não basta para estar indexado em
relações. O preparo de Aiko informa a ausência desse domínio.

**Correção proposta:** resolver o suporte canônico de memória antes de concluir,
sem inventar afinidade/confiança, e manter fatos com autor percebido, envolvidos,
conteúdo, limites e evidência. Uma rejeição não deve ser recuperada retirando a
obrigação sem registrar explicitamente a perda de cobertura.

**Verificação:** promessa e informação transmitida devem sobreviver à retomada
fria e à consulta dirigida, com autoria de Tanaka preservada e sem duplicação.
Histórico textual sozinho deve ser identificado como cobertura parcial.

### 4. Intenções espaciais terminam em preparos neutros

**Episódios:** vigília (S024-I0001), entrada no restaurante (S024-I0002),
perseguição (S024-I0009) e retorno ao circo (S024-I0011).

A permanência falha porque a localização consolidada não é resolvida pelo
cadastro espacial. Os preparos de trânsito falham por falta de espaço da
memória indispensável. Depois, o narrador retira esses gatilhos e prossegue com
preparo neutro: local nulo e ausência de projeção reativa. A posição muda na
descrição/deltas, mas o acesso ao módulo espacial é perdido.

**Estágio:** contexto/projeção. São falhas observadas do caminho operacional.
Não provam, isoladamente, que um encontro, chuva ou evento específico fosse
devido e tenha sido omitido.

**Correção proposta:** tornar a localização canônica resolúvel e coerente na
entrada/saída; reduzir redundância do envelope para comportar a memória
necessária. Retry deve conservar os requisitos espaciais da intenção.

**Verificação:** vigília, entrada e trânsito válidos devem manter sua projeção;
fala breve sem movimento pode permanecer neutra. Local ambíguo precisa resolução
explícita, sem aproximação que invente lugar.

### 5. O principal interlocutor não é resolvido operacionalmente

**Episódio:** confronto em S024-I0002. A consulta por Mori retorna não encontrado;
a busca recupera nome/descrição e acontecimentos, mas os preparos seguintes
entregam memória de Aiko, sem resolver o ator central.

**Estágio:** contexto. Isso demonstra uma lacuna no que foi entregue, não a
inexistência global de um registro de Mori sob outro identificador. A prosa
consegue improvisar respostas coerentes; objetivos, capacidades, conhecimento e
planos persistentes ficam sem base operacional demonstrada.

**Correção proposta:** resolver o vínculo do ator já canônico por fonte e ID
estável; se for ambíguo, manter a ambiguidade explícita. Não preencher capacidades
retroativamente para justificar o resultado de uma rolagem.

**Verificação:** uma retomada fria do confronto deve recuperar os interlocutores
efetivos e suas fontes; ambiguidade e identidade secreta continuam protegidas.

### 6. A consulta temporal da vigília não cobre a espera narrada

**Episódio:** S024-I0001. A consulta verifica 11:35 até 11:35. A narração depois
avança até 12:14. O resultado livre daquela consulta não cobre esses 39 minutos.

**Estágio:** contexto/uso da fronteira. Falha de cobertura confirmada; evento
material perdido nesse intervalo não foi demonstrado.

**Correção proposta:** consultar a janela/alvo real antes da compressão, com
novo preparo quando houver fronteira material.

**Verificação:** fixture com causa às 11:50 deve interromper a espera; fixture
sem causa deve permitir calma até o alvo. Consultar só o instante inicial não
pode aprovar o intervalo posterior.

Há outra divergência a investigar: a consulta do retorno começa em 12:26,
enquanto a conclusão anterior já emitiu 12:33. Ela considera um intervalo maior,
portanto não basta para afirmar perda de evento. Sem reconstruir o overlay e as
causas anteriores, esse quesito continua inconclusivo.

## O que a sessão fez adequadamente

- Mori age com interesses próprios: dá instruções a Aiko, resiste à coerção,
  exige prova, recusa cooperação e limita a palavra que dá. Seu “terceiro futuro”
  é uma alternativa exposta; não prova que tenha alertado empregadores depois.
- Aiko não é apenas receptora: cobra proteção concreta, não aceita perdão
  automaticamente e decide abrir por razões ligadas aos empregados.
- Os seis resultados de d20 observados são respeitados. CD é indicada antes do
  dado; não foi encontrado reroll nem transformação de falha em sucesso. Isso
  não aprova automaticamente necessidade e calibração de cada teste.
- O clima histórico disponível é céu limpo, com circulação normal. Sol e
  trânsito normal são compatíveis; esta sessão não exige chuva artificial.
- A crença de Ren na proteção de Aiko e na possível aliança com Mori permanece
  perspectiva declarada, sem confirmar segurança absoluta ou cooperação futura.

## O que permanece inconclusivo e por quê

| Tema | Fonte específica necessária |
|---|---|
| Missões aceitas, progresso, terminal, prêmios e reações | Contratos e estado histórico das missões, fases e prazos; não apenas ausência de projeção |
| Oferta de sidequest a partir da segurança de Aiko | Exame da âncora e orçamento/limites do instante; pedir ajuda/informação não é automaticamente aceitar missão |
| Impacto e adaptação do cânone | Intenção histórica protegida, janela, núcleo e liberdade de adaptação autorizada |
| Seleção entre causas e incidentes locais | Candidatos alcançáveis/adiados, localização resolvida, impedimentos e decisão de seleção |
| Capacidade e perigo dos adversários | Perfil, conhecimento, recursos, limiar perceptivo e planos comprometidos anteriores |
| Necessidade/calibração de testes contestados | Regra e base de incerteza anterior; confissão do narrador e reclamação do jogador não substituem fonte |
| Memória futura, ressentimento e vingança | Recuperação/ação posterior com fonte; a mesma conversa não demonstra funcionamento longitudinal |
| Medidas institucionais e condições não meteorológicas | Vigência, alcance e autoridade históricos; céu limpo não aprova esse tema |

O gabarito dos episódios sintéticos não foi usado para decidir a sessão. Também
não se tratou a afirmação OFF do produtor de que um teste era desnecessário como
prova suficiente. Atenção de Aiko já aparece antes; necessidade, oposição e
limiar anteriores continuam insuficientemente documentados para fechar o caso.

## Reparos do avaliador necessários nesta revisão

O normalizador guardava comandos extraídos que, em chamadas JavaScript,
podiam conter apenas `${payload}`. O envelope original continha os valores e as
tentativas de memória, mas não entrava no conjunto de fontes do parecer.
Saídas de consultas feitas em lote também podiam desaparecer da operação
normalizada quando sua correlação era desconhecida.

A revisão agora conserva entrada/saída nativas e contexto entregue em turnos
anteriores como fontes reservadas, deduplicadas e vinculadas por hash/offset.
Isso permite examinar essas evidências sem executar comandos do rollout nem
promover correlação desconhecida a sucesso. Exportação continua protegendo
trechos reservados. Abstenção com diagnóstico reservado agora recebe rótulo de
fonte insuficiente, em vez de aparecer indevidamente como resultado inadequado.

O teste direcionado protege payload, saída de lote, contexto anterior, expurgo e
abstenção. Não foi acrescentado gate ao preflight.

## Recorte, encerramento e limites da publicação

O pacote integral mantém os **2.098.214 bytes** do recorte original, SHA-256
`8be6e5f5068f3dbf21abdb02339f7d5499b854abdc0efd1d744b8e5e9965b55f`.
Mantém também as versões dos módulos realmente jogados; o avaliador posterior
não é apresentado como runtime usado na sessão.

**O recorte original termina cedo:** inclui a chamada de encerramento, mas não
seu resultado. A inspeção dirigida encontrou o recibo de encerramento logo
depois, terminando no byte **2.100.100**, antes das operações de dashboard.
Ele declara sessão encerrada, duas transações consolidadas e barreira sem novas
pendências. Essa fonte suplementar confirma que o encerramento ocorreu; não foi
inserida silenciosamente no pacote de mesmo recorte. Seu critério dentro do
pacote permanece inconclusivo. Não é necessário jogar de novo para recuperar
esse recibo existente.

O resumo/handoff da 024 foi usado para conferir a consolidação do histórico;
valores neles presentes não preencheram silenciosamente o estado anterior dos
pareceres. O registro `world_state` do rollout contém configuração do agente,
não snapshot das missões/cânone/NPCs; não resolve as lacunas acima.

## Próxima prioridade de implementação

1. Corrigir continuidade física do elenco e suporte de memória dos atores,
   preservando guardrails de presença, autoria e conhecimento.
2. Conservar projeção espacial/causal depois de falha de preparo e corrigir a
   cobertura da compressão temporal.
3. Registrar bases históricas mínimas que permitam avaliar contratos, seleção e
   risco após o jogo, sem adicionar leitura ampla ao turno.
4. Verificar essas correções em cenários isolados com resultado adequado,
   omissão e negativa legítima; depois medir recuperação e efeitos numa sessão.

Esta revisão já dá motivos concretos para corrigir esses caminhos. Ela não
autoriza afirmar que todo módulo falhou ou que toda tarefa do roadmap é
necessária. Save, cânone e acontecimentos da sessão não foram alterados.

Pacote: `evaluation/sessions/024/revisoes/s024-integral`.
Fonte privada e pareceres de trabalho ficam fora do projeto servido. Os
pareceres expurgados, evidências públicas e decisões das 408 unidades ficam no
dashboard. Original, AMV-05 e AMV14A-FINAL permanecem preservados.
