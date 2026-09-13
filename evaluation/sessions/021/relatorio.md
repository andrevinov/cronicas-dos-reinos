# Avaliação de desempenho — sessão 021

> Artefato pós-hoc de engenharia. Pode conter nomes de módulos reservados e não deve ser usado como memória de jogo.

**Nota geral provisória:** 61.59 / 100 (ruim).

## Saúde da sessão

| Indicador | Valor |
| --- | --- |
| Turnos narrativos | 35 |
| Input bruto | 42067441 |
| Redução contra baseline | 44.0% |
| Inferências/turno | 11.6 |
| Tools/turno | 10.429 |
| L0–L2 limpo | 42.9% |
| Turnos com RAW | 57.1% |
| Latência mediana | 188.7 s |
| Latência p90 | 353.9 s |
| Latência máxima | 725.5 s |

## Notas por eixo

| Eixo | Nota | Peso |
| --- | --- | --- |
| calibracao | 70.0 | 25 |
| eficacia_integridade | 62.5 | 25 |
| confiabilidade | 68.57 | 15 |
| economia | 51.87 | 20 |
| fluidez | 32.85 | 5 |
| jogador | N/D | 10 |

A nota do jogador está pendente quando aparece como N/D; ela não é substituída por uma nota neutra.

## Módulos

| Prioridade | Módulo | Ativação | Desempenho | Tokens atribuídos | Confiança |
| --- | --- | --- | --- | --- | --- |
| 1 | emergent_sidequest_authoring | sobreativou | 22.09 | 1000592 | provisoria |
| 2 | transactional_sidequest_progress | ativou a contento | 42.24 | 3747459 | provisoria |
| 3 | sidequest_progression | sobreativou | 26.86 | 1467112 | provisoria |
| 4 | active_sidequest_reassessment | ativou a contento | 47.8 | 3747480 | provisoria |
| 5 | reactive_pressure_routing | sobreativou | 41.92 | 4134774 | provisoria |
| 6 | adversarial_integrity | ativou a contento | 43.31 | 1094192 | provisoria |
| 7 | batch_world_boundary | ativou a contento | 43.75 | 2351313 | provisoria |
| 8 | npc_social_initiative | sobreativou | 37.3 | 4779554 | provisoria |
| 9 | persistent_world_conditions | sobreativou | 45.17 | 3936365 | provisoria |
| 10 | emergent_sidequest_opportunity | ativou a contento | 58.13 | 6715858 | provisoria |
| 11 | canon_bridge | sobreativou | 48.04 | 1560798 | provisoria |
| 12 | quest_rewards | sobreativou | 47.97 | 1283528 | provisoria |
| 13 | liveness_boundary | ativou a contento | 59.33 | 995691 | provisoria |
| 14 | sidequest_success_reactions | sobreativou | 52.13 | 600336 | baixa |
| 15 | world_local_incidents | ativou a contento | 63.45 | 1322255 | provisoria |
| 16 | secret_canon | ativou a contento | 63.43 | 1179991 | provisoria |
| 17 | canonical_secret_quests | ativou a contento | 67.37 | 1000593 | provisoria |
| 18 | underground_tournament | sobreativou | 57.09 | 714142 | baixa |
| 19 | concurrent_adversarial_operations | ativou a contento | 71.11 | 312085 | baixa |
| 20 | seven_names_migration_regression | sobreativou | 59.62 | 387308 | baixa |

## Principais problemas observados

- **emergent_sidequest_authoring** — Houve repeticao de autoria e remontagem de contratos em apenas tres turnos; os turnos de oferta de Halessa e Tomas ficaram entre os maiores outliers; foi necessario ler documentacao e testes para reconstruir schemas; a missao de Halessa nasceu com profundidade insuficiente.
- **transactional_sidequest_progress** — A ativacao era esperada enquanto havia missoes aceitas, mas ocorreu em quase todo turno subsequente; houve falhas de schema Task49, evidencia longa, mapa de fases invalido e fato sem alteracao; o mecanismo persistiu corretamente fatos cuja qualidade autoral era ruim.
- **sidequest_progression** — Duas fases de Rastros Sob a Placa foram consideradas resolvidas com uma cadeia investigativa curta; a entrega a Halessa parecia suficiente para terminal; o jogador precisou contestar duas vezes e o narrador reconheceu compressao excessiva.
- **active_sidequest_reassessment** — A cobertura foi correta e permitiu a revisao precisa das duas missoes, mas a projecao repetida estourou o teto Task48 em varios preparos e carregou as missoes em turnos triviais de movimento e conversa.
- **reactive_pressure_routing** — Foi detectado em 26 de 35 turnos, inclusive conversas e deslocamentos rotineiros, mas quase nenhuma pressao material apareceu na ficcao; a presenca de sidequests ativas parece mante-lo no hot path mesmo quando o resultado e neutro.
- **adversarial_integrity** — Ativou nos turnos corretos de autoria e compromisso, mas o contrato de Tomas exigiu varias tentativas por classificacao de impacto e estado incompatíveis; o agente precisou consultar schemas e testes durante o jogo.
- **batch_world_boundary** — A fronteira de sono materializou corretamente a iniciativa de Jack, mas exigiu checkpoint, buscas de schema, no-op de agente leve, writer legado e repetidos preparos; um unico turno chegou a 40 tools.
- **npc_social_initiative** — Foi consultado em 20 turnos de dialogo, quase sempre iniciados por Ren, com apenas a abertura de Jack como iniciativa autonoma claramente materializada; houve ainda uma parada artificial enquanto Ren aguardava Halessa.
- **persistent_world_conditions** — Apareceu em 18 turnos sem que uma condicao persistente tivesse papel perceptivel na narracao; parece acoplado a preparos espaciais e de sidequest mesmo quando o resultado e neutro.
- **emergent_sidequest_opportunity** — A cobertura real foi 73 de 73 preparos com exatamente uma decisao; repeticoes vieram de retries e multiplas subcenas; o analisador gerou falso alarme ao contar um rg que apenas mencionava cronica preparar; por ser gate universal, a atribuicao fracionada superestima seu custo marginal.

## Validade da medição

- `violacoes_gate_oportunidade`: observado=1; adjudicado=0. O detector contou um comando rg que apenas citava cronica preparar; as 73 chamadas reais continham exatamente uma decisão.
- `writers_bem_sucedidos`: observado=0; adjudicado=40. Os outputs de concluir registraram transcricao_escrita:true e evento_escrito:true, mas a correlação do analisador classificou as escritas como desconhecidas.
- `leituras_transcricao_concluidas_em_turnos_narrativos`: observado=0; adjudicado=6. As buscas L4T foram concluídas, embora o schema 3 tenha preservado apenas as tentativas por não reconhecer o formato de resultado do executor.

## Limitações desta primeira sessão

- Elegibilidade e efeito esperado por turno ainda aparecem como indeterminados quando o rollout não oferece prova suficiente.
- O custo fracionado é uma atribuição aditiva, não uma estimativa causal.
- A estabilidade longitudinal só poderá ser calculada após novas sessões comparáveis.
- Módulos com uma ou duas ocorrências permanecem com confiança baixa.
