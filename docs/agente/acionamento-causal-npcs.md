# Acionamento causal de NPCs — NV-07

## Responsabilidade

O Mundo Vivo distingue agora **revisão rotineira** de **condição concreta alcançada** nos agentes leves schema 2. Uma notificação pede avaliação do narrador: não executa plano, não transmite informação ao personagem, não cria presença, contato, sidequest, sucesso ou fracasso. Essas consequências continuam dependendo de fatos, agência e autoridades existentes. A implementação não antecipa as NV-08–11.

As dependências são explícitas: `fontes_causais` do índice de agentes leves e `envolvidos` dos compromissos canônicos. Não há inferência de destinatário por menção, nome aproximado ou texto livre. Só entram agentes ativos; NPCs não afetados não recebem uma avaliação de IA.

## Fluxo integrado

A dupla `cronica preparar` → narração → `cronica concluir` permanece a porta comum. Quando o delta altera uma relação declarada ou um compromisso de um agente afetado, o writer promove o checkpoint existente. A consolidação calcula o fato e sua notificação **no mesmo plano/journal**, incluindo o marcador de barreira. Uma queda durante a instalação é reparada pelo journal existente, não por replay criativo nem por outra fila de eventos.

Em alterações de tempo, o detector também observa os instantes exatos dos compromissos efetivos, inclusive deltas anteriores ainda não consolidados. `fronteira` usa esses mesmos instantes antes de comprimir horas. Não é preciso aguardar o próximo amanhecer nem acumular duas horas. A consulta não consome prazo, e um compromisso fora do recorte quente continua elegível.

O instante de início ou fim produz uma causa para avaliação, **não presença, cumprimento ou falha automática**. Janela apenas descritiva não ganha hora inventada. Cumprimento/cancelamento/substituição permanecem na autoridade dos compromissos; suas alterações invalidam a causa antiga, sem punição fabricada. `checkpoint recuperar` reapresenta condições não entregues.

## Prioridade sem aumentar as avaliações simultâneas

Os limites existentes continuam: uma revisão rotineira nova por checkpoint elegível e duas avaliações leves abertas. Prazos concretos precedem mudanças de fonte, que precedem rotina. Uma revisão preemptada mantém seu ID e sua origem no campo opcional `acionamento_npcs.adiadas` **do mesmo estado do Mundo Vivo**. A conclusão reabastece os slots sem exigir um novo amanhecer. A barreira conta também as adiadas e não libera o próximo turno enquanto houver trabalho não avaliado.

Mudanças do mesmo agente são reunidas; a mesma fonte conserva todos os endereços modificados, até o limite. Os recibos de prazo pertencem ao mesmo controle reservado, separados do histórico recente de 64 conclusões, para que a rotação desse histórico não ressuscite notificações. O registro da campanha e o compromisso continuam sendo as autoridades; o controle apenas registra entrega/adiamento.

Uma pendência com resolução de mundo já consolidada fica protegida de preempção ou no-op. Conclua-a pela barreira existente; consequências que precisem de nova avaliação aguardam separadamente, sem substituir o ID da operação em andamento.

## Avaliação em lote

`resolver_fronteira preparar` mantém o lote existente e acrescenta contexto causal somente aos agentes afetados. Carrega o perfil dirigido e as fontes explicitamente notificadas, não o elenco inteiro. A projeção preserva fatos inteiros e o estatuto de relatos/rumores. Não transforma a onisciência técnica do narrador em conhecimento do NPC.

O token inclui assinaturas de todas as causas e fontes, inclusive as que não couberem na página. Estado alterado invalida o preparo antes da primeira escrita. Informação indivisível que não cabe vira **aprofundamento necessário**, com fonte e endereço, nunca texto cortado. Leia a lacuna antes de decidir; validação estrutural não comprova que a IA fez essa leitura.

Decisões genuínas de `sem_mudanca` são enviadas juntas com motivo explícito. Uma condição nova não é descartada automaticamente por um cache antigo. Depois da avaliação, o cache negativo existente continua reutilizável nas revisões rotineiras enquanto fontes e perfil permanecerem válidos. Uma nova alteração causal ou um novo prazo vence esse cache.

## Custos e limites

Não há chamada independente de IA por NPC, nova porta CLI ou terceira chamada ritual. Um turno neutro sem delta causal/temporal mantém somente as duas escritas habituais e não lê fontes de acionamento. Turnos causais podem custar um checkpoint e uma avaliação do lote: isso é custo real, não economia gratuita.

A notificação acrescenta até 3 KiB de contexto causal por avaliação admitida (até duas), na fronteira existente, não no pacote normal de memória da cena. Os limites do lote e os orçamentos anteriores de memória/tickets não são elevados. Há leituras adicionais dirigidas nos caminhos causais/temporais, e o mapa completo de compromissos é consultado para não confundir recorte de exibição com autoridade temporal.

O contrato de limites está em `baseline/nv07-acionamento-causal.yaml`. Overflow falha explicitamente; não descarta obrigações para caber. As medições `NV07_BYTES` são bytes YAML do contexto causal e do lote completo em fixture; **não são tokens nativos nem prova de economia de episódios narrados equivalentes**.

## Validação e preservação

Testes de domínio puros cobrem prioridade, coalescência, adiamento, idempotência, recebimentos, invalidação, limites e leitura dirigida. Testes de integração usam campanha sintética, calendário Harptos, writer, consolidação interrompida, lote, CLI em processo novo e promessa NV-04. Nenhuma assertion congela sessão, recursos ou relógio do save vivo.

A instalação não modifica dados da campanha, agendas, perfis originais ou transcrições. O campo opcional é criado apenas quando uma operação real gera uma notificação. O suporte mecânico não comprova completude da extração de acontecimentos nem qualidade narrativa; isso exige os ensaios narrados previstos no plano.
