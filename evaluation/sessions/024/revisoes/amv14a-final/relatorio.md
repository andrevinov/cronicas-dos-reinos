# Avaliação modular v2 — sessão 024

> Artefato pós-hoc de engenharia; não altera cânone.

**Validade:** comprometida_guardrail. Sem nota global conclusiva.
**Qualidade:** violacao_critica.
**Cobertura:** {'unidades_interacao_criterio': 408, 'com_parecer': 13, 'sem_parecer': 395, 'confirmadas_verificadas': 8, 'estados': {'indeterminada': 400, 'confirmada': 8}}.
**Revisão:** Reavaliação AMV14A-FINAL · mesma sessão; versões jogadas preservadas.

- Conclusão da medição: bloqueada por resultado_operacao_ausente, evidencia_operacional_insuficiente.
- Entrada congelada: sim.
- Agregação modular: completa.
- Módulos incluídos: 4 de 12.
- Módulos bloqueados excluídos: nenhum.

<details><summary>Indicadores operacionais parciais</summary>

Desempenho observado sem autorização de conclusão: 82.51 / 100. Não aprova qualidade da experiência.

</details>

## Módulos-pai e filas independentes

| Reparo | Experiência | Custo contábil | Módulo | Implementação | Avaliação | Ativação | Desempenho operacional | Qualidade por interação | Denominador de qualidade | Custo | Confiança |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| N/D | N/D | 1 | context_and_memory | 1.0.2 | 4.0.0 | ativou a contento | 73.06 | 100.0 | 2 | 864536 | provisoria |
| N/D | N/D | 5 | turn_and_session_orchestration | 1.0.2 | 4.0.0 | ativou a contento | 92.36 | 100.0 | 1 | 864529 | provisoria |
| N/D | 1 | 2 | narrative_delivery | 1.0.2 | 4.0.0 | ativou a contento | 94.31 | 50.0 | 2 | 864535 | provisoria |
| N/D | N/D | 3 | rules_and_character_state | 1.0.1 | 4.0.0 | ativou a contento | 84.31 | 100.0 | 1 | 864533 | provisoria |
| N/D | N/D | 4 | sidequest_authoring | 2.0.1 | 4.0.0 | indeterminado | N/D | N/D | 0 | 864531 | N/D |
| N/D | N/D | N/D | sidequest_lifecycle | 1.0.1 | 4.0.0 | não aplicável | N/D | N/D | 0 | 0 | N/D |
| N/D | N/D | N/D | canonical_quest_integration | 2.0.0 | 4.0.0 | N/D | N/D | N/D | 0 | 0 | N/D |
| N/D | N/D | 6 | npc_continuity_and_social_behavior | 1.1.0 | 4.0.0 | indeterminado | N/D | 100.0 | 2 | 658195 | N/D |
| N/D | N/D | 7 | scene_world_projection | 1.0.1 | 4.0.0 | não aplicável | N/D | N/D | 0 | 425940 | N/D |
| N/D | N/D | N/D | world_boundary_resolution | 1.0.1 | 4.0.0 | indeterminado | N/D | N/D | 0 | 0 | N/D |
| N/D | N/D | N/D | causal_narrative_routing | 1.0.1 | 4.0.0 | não aplicável | N/D | N/D | 0 | 0 | N/D |
| N/D | N/D | N/D | adversarial_operations | 1.0.1 | 4.0.0 | N/D | N/D | N/D | 0 | 0 | N/D |

## Validade

- Manifestações registradas: 1.
- Qualidade por interação: 8 avaliação(ões) pontuável(is), 0 oportunidade(s) perdida(s).
- Violações críticas: 1; não participam da média.
- Não existe ranking global; custo não altera a prioridade de experiência nem a fila de reparo.
- Tokens são rateados para reconciliação contábil e triagem; o rateio não demonstra causalidade.
- Subcapacidades são diagnóstico e não concorrem nas filas.
- Uma sessão é provisória; comparação estável exige amostra mínima e régua compatível.

## Revisão pós-sessão executada

Escopo: parcial_declarado. 13 unidades decididas. Fontes insuficientes: 5. Pareceres bloqueados: 0.

Revisão pelo agente, não validação cega por terceiro nem aprovação longitudinal.


### S024-I0005 · rules_and_character_state.rules_resolution

Estágio: indeterminada; causa: hipotese.

Achado: Necessidade e dificuldade do teste contestado sem base prévia suficiente no recorte.

Correção: Comprometer motivo do teste, canal perceptivo, CD e consequência antes do dado; preservá-los no ticket.

Teste: Sem acesso perceptivo suficiente, resolver sem teste; com incerteza justificada, manter dificuldade e consequência prévias.

Parecer: `revisao-4eaf0f3b7531b27b36f5`. Fontes e trechos vinculados no dashboard.


### S024-I0011 · narrative_delivery.narrative_density

Estágio: narracao; causa: hipotese.

Achado: Narração acrescentou decisão voluntária de Ren sem autorização na entrada.

Correção: Distinguir consequências e deslocamento autorizados de decisões adicionais; exigir escolha antes de acrescentar espera voluntária.

Teste: Mesma entrada de retorno não autoriza espera; quando o jogador ordenar esperar, a espera é legítima.

Parecer: `revisao-26f12116ddb673819a1e`. Fontes e trechos vinculados no dashboard.
