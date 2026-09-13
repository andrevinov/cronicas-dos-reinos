# Roadmap — arquitetura modular e avaliação v2

## Status

**Em implementação.** RM-01 e RM-02 estão concluídas; as demais tasks continuam
propostas até serem executadas.

Este roadmap transforma o catálogo plano de vinte itens em doze módulos de
domínio. Comportamentos existentes continuam preservados como subcapacidades;
cenários e regressões deixam de competir no scorecard como módulos permanentes.

## Resultado arquitetural esperado

Os módulos de primeira classe serão:

1. `context_and_memory`;
2. `turn_and_session_orchestration`;
3. `narrative_delivery`;
4. `rules_and_character_state`;
5. `sidequest_authoring`;
6. `sidequest_lifecycle`;
7. `canonical_quest_integration`;
8. `npc_continuity_and_social_behavior`;
9. `scene_world_projection`;
10. `world_boundary_resolution`;
11. `causal_narrative_routing`;
12. `adversarial_operations`.

Cada módulo possui subcapacidades observáveis. Guardrails críticos e cenários de
regressão ficam em camadas próprias.

## Mapa de migração do catálogo atual

| Origem v1 | Destino v2 | Natureza no destino |
| --- | --- | --- |
| `emergent_sidequest_opportunity` | `sidequest_authoring` | gate de elegibilidade |
| `emergent_sidequest_authoring` | `sidequest_authoring` | autoria e materialização |
| `active_sidequest_reassessment` | `sidequest_lifecycle` | projeção read-only |
| `transactional_sidequest_progress` | `sidequest_lifecycle` | commit transacional |
| `sidequest_progression` | `sidequest_lifecycle` | fases, prazos e terminais |
| `quest_rewards` | `sidequest_lifecycle` | efeito terminal exactly-once |
| `sidequest_success_reactions` | `sidequest_lifecycle` | consequência pós-progresso |
| `canon_bridge` | `canonical_quest_integration` | sidequest → cânone |
| `canonical_secret_quests` | `canonical_quest_integration` | cânone → oportunidade |
| `npc_social_initiative` | `npc_continuity_and_social_behavior` | iniciativa elegível |
| `world_local_incidents` | `scene_world_projection` | incidente ou microevento |
| `persistent_world_conditions` | `scene_world_projection` | condição persistente |
| `liveness_boundary` | `world_boundary_resolution` | vivacidade em compressão temporal |
| `batch_world_boundary` | `world_boundary_resolution` | lote de pendências |
| `reactive_pressure_routing` | `causal_narrative_routing` | arbitragem de matérias autorizadas |
| `secret_canon` | `causal_narrative_routing` | produtor canônico datado |
| `adversarial_integrity` | `adversarial_operations` | contratos e guardrails adversariais |
| `concurrent_adversarial_operations` | `adversarial_operations` | execução simultânea |
| `seven_names_migration_regression` | suíte de regressão | não é módulo |
| `underground_tournament` | extensão da campanha | não é módulo central |

## Camadas de avaliação

### Módulo

Capacidade estável, reutilizável, com gatilho, resultado e alavanca de melhoria
próprios. Recebe nota, custo e prioridade.

### Subcapacidade

Etapa interna que explica a nota do módulo. Recebe métricas e diagnóstico, mas
não concorre separadamente no ranking geral e não recebe novamente o custo total
do turno.

### Guardrail

Propriedade inegociável, como agência, sigilo, integridade de rolagem e
consistência canônica. É `ok`, `violado` ou `indeterminado`. Violação crítica não
pode ser compensada por média alta.

### Cenário/regressão

Prova de comportamento usando fixture ou snapshot justificado. Não é ativado nem
pontuado durante sessões comuns.

## Ondas de implementação

```text
RM-01 — contrato e catálogo v2
    ↓
RM-02 — ledger e telemetria hierárquica
    ↓
RM-03–RM-10 — domínios consolidados e novos módulos
    ↓
RM-11 — avaliador, feedback e painel v2
    ↓
RM-12 — aceite integrado e primeiro rollout v2
```

RM-03–RM-10 podem avançar em paralelo depois que os contratos RM-01–RM-02
estiverem congelados. A RM-11 só fecha quando os doze módulos emitirem dados no
novo contrato. A RM-12 é o corte definitivo.

## Backlog

| Item | Entrega | Dependências |
| --- | --- | --- |
| [RM-01](rm01-catalogo-hierarquico-e-corte-da-serie.md) | catálogo hierárquico, guardrails e política de série — **concluída** | nenhuma |
| [RM-02](rm02-ledger-telemetria-modular-v2.md) | eventos, atribuição e compatibilidade de telemetria — **concluída** | RM-01 |
| [RM-03](rm03-consolidacao-sidequests.md) | três módulos de sidequest | RM-01–RM-02 |
| [RM-04](rm04-consolidacao-mundo-causal.md) | projeção, fronteira e roteamento do mundo | RM-01–RM-02 |
| [RM-05](rm05-continuidade-e-comportamento-npc.md) | continuidade e comportamento social de NPCs | RM-01–RM-02 |
| [RM-06](rm06-operacoes-adversariais.md) | operações adversariais e seus guardrails | RM-01–RM-02 |
| [RM-07](rm07-contexto-e-memoria.md) | leitura econômica e memória correta | RM-01–RM-02 |
| [RM-08](rm08-orquestracao-turno-e-sessao.md) | controle transacional do turno e da sessão | RM-01–RM-02 |
| [RM-09](rm09-entrega-narrativa.md) | qualidade estrutural e perceptiva da narração | RM-01–RM-02 |
| [RM-10](rm10-regras-e-estado-personagem.md) | regras, rolagens, recursos, ficha e tempo | RM-01–RM-02 |
| [RM-11](rm11-avaliador-e-dashboard-v2.md) | scorecard hierárquico e nova série | RM-03–RM-10 |
| [RM-12](rm12-aceitacao-e-baseline-v2.md) | regressão integrada e primeiro rollout real v2 | RM-11 |

## Política para a sessão 021

O pacote `evaluation/sessions/021` permanece imutável como avaliação histórica
v1. Ele continua útil para registrar os sintomas que motivaram a refatoração,
mas não entra na mesma curva numérica das sessões v2.

Uma agregação retroativa do rollout 021 poderá ser exibida como
`referencia_legada`, com campos ausentes e confiança limitada. Ela nunca será
tratada como baseline causal do sistema refatorado.

## Definition of done global

- doze módulos de primeira classe e nenhuma regressão/campanha no ranking central;
- toda subcapacidade v1 possui destino explícito e cobertura preservada;
- custos aditivos fecham uma única vez no nível de módulo;
- guardrails aparecem fora da média ponderada;
- telemetria continua exclusivamente pós-hoc;
- turno neutro não recebe nova chamada de ferramenta;
- histórico e estado vivo não são reescritos para facilitar a migração;
- testes removidos ou consolidados têm propriedade e destino registrados;
- `test-full`, `preflight` e os perfis de domínio ficam verdes;
- primeiro rollout real v2 gera pacote válido e inaugura a nova série.
