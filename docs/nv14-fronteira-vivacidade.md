# NV-14 — Fronteira de vivacidade e recibo de calma

## Objetivo

A NV-14 fecha a lacuna entre módulos locais corretos e a experiência de um mundo realmente vivo. Antes dela, uma causa podia estar estruturada e devida sem existir uma camada compacta perguntando, em uma transição longa, **o que já pode alcançar a atenção do jogador agora**.

A solução não é outro scheduler. `fronteira_mundo.py` continua dizendo *quando* uma compressão temporal encontra uma fronteira determinística; `resolver_fronteira.py` continua resolvendo a fila do Mundo Vivo; `pressao_narrativa.py` continua ordenando matérias já autorizadas no hot path. A NV-14 somente agrega causas já existentes e injeta essa projeção na mesma consulta `endpoints.py fronteira`.

## Janelas

A consulta roda somente quando existe uma razão temporal relevante:

- início de dia;
- mudança de período operacional;
- compressão longa de pelo menos 180 minutos.

Os quatro períodos são relativos a `hora_amanhecer` da agenda, não novos fatos canônicos. Com amanhecer às 06:00, os inícios ficam em 06:00 (`amanhecer`), 10:00 (`dia`), 18:00 (`anoitecer`) e 22:00 (`noite`). Uma permanência da manhã à noite produz poucas avaliações por essas fronteiras, não uma sequência horária de negativas cegas.

Turno curto que não cruza período não consulta os produtores da NV-14.

## Cobertura obrigatória

Toda projeção aplicável declara cobertura dos sete domínios abaixo. Ausência de um domínio no recibo falha fechada; produtor genuinamente inexistente pode ser declarado `nao_configurado` com motivo explícito.

1. `entregas_contatos` — contatos NV-09 e entregas bloqueadas NV-13;
2. `planos_compromissos` — planos NV-08 já devidos e compromissos temporais do estado;
3. `operacoes_reacoes` — operações Task51/52 e reações Task50 já pendentes;
4. `sidequests_vivas` — prazos de missões aceitas, pendências de progresso e causas NV-11 declaradas em planos;
5. `iniciativas_elenco` — somente participantes já presentes pela memória de cena; capacidade social não fabrica assunto;
6. `ecologia_local` — exatamente um slot do local canônico atual e seus ritmos por período; não há sorteio de microevento;
7. `ambiente_publico` — condições persistentes estruturadas. Avisos públicos formais permanecem `nao_configurado` até o produtor próprio existir.

As consultas são dirigidas: fila compacta do Mundo Vivo, controle de no máximo oito planos, no máximo duas sidequests ativas, elenco de no máximo seis participantes, um perfil ecológico do local corrente e o pequeno estado de condições persistentes. Não há varredura global de NPCs.

## Seleção

Cada causa recebe a prioridade já definida em `pressao_narrativa.PRIORITIES`; a NV-14 não mantém tabela concorrente. Em cada janela:

- no máximo uma candidata elegível é `entregue` ao slot primário;
- as demais elegíveis ficam `adiada` e reaparecem na janela seguinte da mesma projeção;
- uma candidata causalmente impossível fica `bloqueada`, com motivo explícito;
- bloqueio não consome o slot primário.

`entregue` aqui significa **entregue à atenção da janela**. Não significa que uma mensagem remota chegou a Ren. Transporte, conhecimento e percepção continuam sob os contratos NV-09/NV-13/Task51/Task52 da fonte.

## Causas NV-11

`--sem-oportunidade-sidequest` decide apenas se há uma **nova** oportunidade reativa naquele `cronica preparar`. Ele não pode apagar uma causa NV-11 já declarada num passo NV-08 e cujo instante foi alcançado.

A fronteira consulta essas causas diretamente no controle do plano. Uma causa ainda sem missão aparece como `nova_oportunidade` para avaliação, mas isso não oferece, aceita, materializa ou conclui uma sidequest.

## Elenco, ecologia e ambiente

A NV-14 consulta o elenco efetivo salvo por `memoria_cena`. `iniciativa_social` pode informar quais NPCs possuem liberdade relacional para iniciar uma troca, mas essa capacidade não vira candidata sem causa concreta. A decisão obrigatória de iniciativa pertence a uma etapa posterior da integração reativa.

A ecologia usa somente `ecologia_local.lookup_canonical` e `activity`. Não chama `microeventos_locais.plan`, não consome baralho e não persiste estado.

Condições persistentes são registradas no contexto da projeção, não transformadas automaticamente em testes, encontros ou penalidades.

## Integração com a fronteira temporal

`endpoints.py fronteira` continua sendo a porta operacional. A cadeia de extensão calcula primeiro a fronteira base, depois a noite de torneio Task37 e, por último, a NV-14 sobre **somente a faixa realmente alcançável antes da primeira fronteira já conhecida**.

Se a NV-14 encontrar uma pressão anterior à fronteira existente, ela encurta `proximo_passo.fronteira`, marca `alvo_inteiro_sem_checkpoint: false` e adiciona o gate `fronteira_vivacidade`. Se não houver pressão elegível, a fronteira temporal original permanece intacta.

Não existe segunda chamada obrigatória.

## Recibo de calma

Uma janela sem pressão primária produz `recibo_calma.estado: calma_justificada`. O recibo inclui digest da cobertura e da janela. Por isso é possível distinguir:

- um dia realmente calmo, após consulta das fontes autorizadas;
- um produtor explicitamente não configurado;
- uma falha de cobertura, que não produz calma válida.

O resultado integrado inteiro continua limitado a aproximadamente 4 KiB. Se causas demais impedirem preservar decisões e cobertura, a consulta falha em vez de descartar pressão silenciosamente ou elevar o teto.

## Telemetria

`analisar-rollout.py` atribui a NV-14 como `liveness_boundary` e mede separadamente:

- avaliações observadas;
- janelas com pressão primária;
- recibos de `calma_justificada`;
- ocorrências de `modulos_nao_consultados`/cobertura incompleta.

A telemetria é pós-hoc e nunca participa da narração.

## Invariantes

- zero escrita de estado;
- zero RNG novo;
- zero scheduler novo;
- zero chamada de IA;
- zero ação, fala, emoção ou decisão atribuída a Ren;
- no máximo uma pressão primária por janela;
- causas adiadas não são descartadas;
- ausência de pressão nunca é inferida da ausência de consulta;
- nenhuma microcena ou sidequest é inventada para preencher um dia calmo.
