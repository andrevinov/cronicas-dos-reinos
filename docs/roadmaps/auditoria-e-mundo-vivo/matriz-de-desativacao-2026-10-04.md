# Matriz de desativação e remoção após o roadmap

**Data:** 2026-10-04. **Status:** proposta condicional.
**Execução:** AMV-15, depois das provas de cobertura das tarefas correspondentes.

## Regra para qualquer retirada

Registrar: propriedade protegida, relevância atual, dono substituto, teste ou
episódio que detecta a mesma falha, dependências e evidência de antes/depois.
Desativar uma execução recorrente, consolidar um check e apagar implementação
são decisões diferentes. O destino preferencial de uma regressão útil é a suíte
de domínio; seu cenário histórico pode permanecer como evidência isolada.

Nenhum item desta matriz deve ser retirado agora apenas por estar lento, vermelho,
antigo ou associado a `nvNN`/`taskNN`.

## 1. Repetições comprovadas: primeiros candidatos

| Item atual | Ação proposta | Propriedade e destino obrigatório | Condição de retirada |
| --- | --- | --- | --- |
| Sete comandos de `auditoria-final.py:gate_baseline_and_regressions` também presentes diretamente no preflight: migrar estado, migrar memórias, reindexar conhecimento, gerar runtime, ruleset, integridade e baseline histórica | Retirar sua reexecução dentro da auditoria quando o dono já os executou no escopo válido | Estado/índices/runtime coerentes, regras consistentes e história preservada; checks únicos do registro AMV-15 | Relatório comprova execução válida de cada propriedade; execução ausente ou falha bloqueia |
| Quatro comandos adicionais da mesma função: turno, consolidar, sessões e checkpoint | Comparar com fachadas e consolidar os que realmente repetem cobertura | Transação, lifecycle, recuperação e memória; orquestração/contexto e regressões correspondentes | Não presumir equivalência pelo nome: demonstrar mesmas falhas, inclusive journals e pendências |
| Passos de `.github/workflows/integridade.yml` que repetem os validadores já executados pelo workflow de Preflight | Dar um dono a cada propriedade e retirar a segunda execução | Mesmas invariantes, numa revisão identificada e com resultado obrigatório | Validar requisitos de merge e dependências; não aceitar resultado de outro commit ou estado |
| Nove testes ancorados executados por `aceitacao_modular_v2.py check`, além da suíte integral | Separar validação de contrato da execução de testes; evitar repetição quando a suíte é o dono | Episódios técnicos e regressões, já alcançados por discovery | A suíte completa executa os casos; sem esse resultado não há dispensa |
| Smoke do benchmark antigo no workflow de Preflight e partes equivalentes da auditoria/Integridade | Tirar a aprovação baseada em um único rollout antigo do gate de experiência; conservar regressão do parser | Classificação operacional, ausência de arquivo temporário, orçamento do fluxo atual | AMV-02–03 e AMV-14 provam formatos atuais, casos negativos e orçamento pertinente |

Os sete comandos exatos são `migrar-estado-atual.py --check`,
`migrar-memorias-fragmentadas.py --check`, `reindexar-conhecimento.py --check`,
`gerar-runtime.py --check`, `ruleset_5_5e.py check`, `verificar-integridade.py`
e `verificar-integridade.py --verificar-baseline-historica`.

## 2. Aceites que devem ser substituídos antes de sair

| Item | Limitação observada | Ação após implementação | Cobertura que fica |
| --- | --- | --- | --- |
| `experiencia_integrada.py check` como prova de experiência | Valida piloto e documentação; não executa episódio narrado novo | Retirar o gate recorrente restrito aos três pilotos depois de AMV-08/14 | Perfil generalizado, presença/percepção, episódio de memória → decisão → consequência; regras vigentes verificadas por contrato |
| `aceitacao_vivacidade.py check` como aceite global | Avalia candidatas previamente fornecidas e cadeia de uma fixture operacional antiga | Substituir o gate pelo aceite atual da AMV-14 | Calma legítima, causa descoberta, fronteira, reserva, ausência de scan extra e efeito persistente |
| `aceitacao_modular_v2.py check` como autorização de experiência | Prova integração técnica; aceita prontidão sem primeira sessão real, por desenho | Evoluir e desmembrar; manter contratos técnicos, separar aceite semântico e longitudinal | Proveniência, versões, interações, pacote idempotente, episódios atuais e acompanhamento AMV-16 |
| Afirmação de redução de input superior a 70% contra baseline antiga nos scripts de CI | Serve ao experimento histórico; não prova qualidade nem desempenho causal atual | Mover comparação para regressão/experimento histórico, fora da aprovação geral atual | Parser/comparador preservados; orçamento atual versionado e comparação de recortes equivalentes |
| Asserts de existência de arquivos `baseline/*step-*`, handoff de sessão específica e frases literais em AGENTS | Podem proteger instalação de etapa antiga em lugar do comportamento vigente | Revisar caso a caso e substituir os que não protegem contrato atual | Imutabilidade de baseline continua; acesso, retomada, roteamento e documentação atual recebem verificações próprias |
| `migracao_sete_nomes.py check` recorrente | Mistura potencialmente comprovação de migração concluída com integridade relevante | Mover a parte de migração histórica ao perfil/regressão isolada; manter invariante instalada relevante | Snapshot histórico justificado, teste de migração e lifecycle dos dados instalados |

**Não remover em bloco:** a associação a uma migração histórica não torna todo
o check dispensável. A AMV-01 precisa decompor suas propriedades, e a AMV-14
precisa provar as que continuarão relevantes.

## 3. Destino dos 31 checks diretos atuais

Este inventário cobre `checks(incluir_testes=False)` observado no diagnóstico.
Não inclui todas as chamadas internas. “Manter dono” permite evoluir o check
para provar comportamento; não significa que sua implementação atual já basta.

| # | Check/comando | Destino proposto |
| --- | --- | --- |
| 1 | `turn_and_session_orchestration.py check` | Manter dono de transação/lifecycle; consolidar repetições com auditoria/CI |
| 2 | `context_and_memory.py check` | Manter dono de acesso/memória; preservar retomadas e overlay distintos |
| 3 | `recompensas.py check` | Candidato a eliminar execução isolada se `interacoes_mundo` ou outro dono validar exatamente mapas, índices e reserva; conservar engine |
| 4 | `sidequest_authoring.py check` | Manter dono; ampliar descoberta e autoria pela AMV-10/14 |
| 5 | `sidequest_lifecycle.py check` | Manter dono de progresso, terminais, prêmios e reações |
| 6 | `canonical_quest_integration.py check` | Manter dono de pontes e núcleo protegido |
| 7 | `adversarial_operations.py check` | Manter dono de operações e guardrails; provar execução temporal |
| 8 | `scene_world_projection.py check` | Manter dono de projeção, reserva e alcance |
| 9 | `world_boundary_resolution.py check` | Manter dono de fronteira, calma justificada e lote |
| 10 | `causal_narrative_routing.py check` | Manter dono de arbitragem causal e eventos devidos |
| 11 | `migracao_sete_nomes.py check` | Separar migração concluída de invariantes ainda vivas; destino na seção 2 |
| 12 | `interacoes_mundo.py check` | Revisar composição: manter invariantes próprias; retirar subchecks repetidos somente com destino demonstrado |
| 13 | `npc_continuity_and_social_behavior.py check` | Manter dono; retirar restrição ao piloto, provar autonomia generalizada |
| 14 | `aceitacao_modular_v2.py check` | Desmembrar validação técnica, testes e aceite real; não repetir suíte |
| 15 | `verificar_corpus_avaliacao.py` | Manter corpus com um dono; ampliar casos do diagnóstico |
| 16 | `narrative_delivery.py check` | Manter entrega estrutural; separar qualidade semântica independente |
| 17 | `rules_and_character_state.py check` | Manter dono de mecânica/recursos; incluir justificativa e resolução |
| 18 | `experiencia_integrada.py check` | Substituir gate de piloto por episódios atuais, conforme seção 2 |
| 19 | `reconhecibilidade_persona.py check` | Manter identidade, evidência e canais de percepção; consolidar execução se coberta por dono equivalente |
| 20 | `clima_diario.py check` | Manter reserva e clima vigente; só mover execução com cobertura equivalente |
| 21 | `politica_civica.py check` | Manter autoridade, publicação, entrega e alcance; provar efeitos continuados |
| 22 | `aceitacao_vivacidade.py check` | Substituir gate limitado por episódios AMV-14 |
| 23 | `migrar-estado-atual.py --check` | Manter consistência atual em dono único; parte de migração única pode ir para regressão |
| 24 | `migrar-memorias-fragmentadas.py --check` | Manter integridade de memória em dono único; não repetir na auditoria/CI |
| 25 | `reindexar-conhecimento.py --check` | Manter índice consistente em dono único; preservar separação das fontes |
| 26 | `gerar-runtime.py --check` | Manter runtime derivado coerente com estado e pendências em dono único |
| 27 | `ruleset_5_5e.py check` | Manter consistência de regras em dono único |
| 28 | `gate_adnd.py check` | Manter prevenção de mistura de rulesets; só consolidar com prova de mesma falha |
| 29 | `verificar-integridade.py` | Manter invariantes instaladas; retirar reexecuções redundantes |
| 30 | `verificar-integridade.py --verificar-baseline-historica` | Preservar imutabilidade histórica; execução única ou teste dono equivalente |
| 31 | `auditoria-final.py --json --sem-testes` | Preservar ensaios próprios; eliminar cascata repetida e atualizar relatório |

Na linha 3, `recompensas.py` não é `recompensas_sidequest.py`. O primeiro valida
mapas por local; o segundo compõe o lifecycle. A possível repetição vem de
`interacoes_mundo` também chamar validação de mapas, não da semelhança do nome.

## 4. Código e regras que poderão ser apagados

| Candidato | Substituição | Condição adicional |
| --- | --- | --- |
| Decisão duplicada de sucesso em `_analisar_rollout_core.py` | Ledger normalizado AMV-02 | Compatibilidade de formatos antigos demonstrada; adaptadores necessários continuam |
| Tabelas divergentes de fases e heurísticas ad hoc de recibos | Contrato versionado AMV-03 | Falhas de ausência, fase inválida, duplicação e órfão continuam detectadas |
| Dependência de `PILOTS` e papel textual literal para personalidade geral | Perfil de domínio AMV-08 | Todos os pilotos mantêm propriedades válidas; NPC novo e lacuna são tratados corretamente |
| Aprovação de experiência derivada só de rodapé ou bloco mecânico | Dimensões separadas AMV-04/05 | Checks estruturais continuam ativos em entrega/mecânica |
| Execução encadeada de `_preflight_nv19.py`, `_preflight_nv21.py` e `_preflight_nv22.py` | Registro explícito AMV-06/15 | Nenhum check necessário depende mais desses carregamentos |
| Wrappers históricos de planos, checkpoint e orquestração substituídos | Composição explícita AMV-06 | Fechamento de dependências e compatibilidade com envelopes/recuperação persistidos |
| Testes de Task que apenas repetem cobertura demonstrada | Testes de domínio e registro histórico | Propriedade, destino e mesma falha constam do registro de revisão |

Não apagar todos os `_nv*` de uma vez: hoje vários deles fornecem a implementação
ativa. CLI de reparo também não é código morto só porque saiu do caminho comum.

## 5. Proteções que devem continuar existindo

- Agência de Ren, ON/OFF/RECALL e segredo por camada de conhecimento.
- Integridade de rolagem, dificuldade comprometida e gasto de recurso autorizado.
- Barreira de pendências, ticket obsoleto, writer único, retry e recovery.
- Overlay de pendências e retomada sem transcrição quando a camada quente basta.
- Reserva de nomes, RNG estável e ausência de reroll oportunista.
- Progresso por fatos, terminais e recompensas uma vez, limites de oportunidades.
- Núcleo canônico protegido, adaptação autorizada e evento devido sem no-op.
- Imutabilidade de história e baseline; auditoria e medição sem mutação do save.
- Proveniência, comparabilidade, privacidade de rollouts e ausência de vazamento.
- Suíte completa como gate de merge, com execução única pela CI responsável.

## 6. Roadmaps e documentação anterior

Este roteiro complementa os domínios do roadmap `modulos-v2` e substitui o alcance
de aceite insuficiente identificado especialmente em RM-11/RM-12. Após entrega,
atualizar o índice para apontar o contrato vigente e marcar a proposta anterior
como histórica/superada no aspecto correspondente. Não apagar manual vigente
antes da substituição operacional nem reescrever seu histórico como se a nova
garantia sempre tivesse existido.

## Saída exigida da AMV-15

Um manifesto de cobertura e aposentadorias, logs de execução antes/depois,
tempo observado em condições equivalentes e prova de falha para cada substituição.
A meta é eliminar reexecução da mesma propriedade e trocar aceites insuficientes
por provas melhores. O número final de checks será consequência desse mapa,
não uma quota arbitrária de redução.
