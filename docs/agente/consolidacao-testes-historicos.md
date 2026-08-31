# Consolidação de testes históricos — Task 3

## Objetivo

Esta etapa separa propriedades permanentes do sistema da história de como elas
foram implementadas. A origem é a fotografia da Task 1, que classificou 39
arquivos como `task_historica` por nome de arquivo, classe ou método.

A classificação automática nunca foi um veredito. A revisão semântica completa
está em:

```text
tests/historical-test-review.yaml
```

Cada um dos 39 arquivos declara:

- requisito original protegido;
- classificação;
- destino atual da cobertura.

O gate correspondente é:

```bash
python ferramentas/verificar-testes-historicos.py
```

## Resultado da classificação

| Classificação | Quantidade | Tratamento |
| --- | ---: | --- |
| permanente | 19 | continua como teste de domínio |
| histórico | 4 | continua congelado porque a história é a propriedade |
| redundante | 7 | removido após provar cobertura equivalente |
| substituível | 9 | movido para arquivo de domínio estável |
| obsoleto | 0 | nenhum teste foi descartado por perda de relevância |

Total: **39** arquivos revisados.

## Scaffolding removido

Os sete arquivos abaixo verificavam principalmente detalhes de implementação:
ordem de Tasks no `AGENTS.md`, existência de documentação numerada e strings de
nome de gate contendo `TaskNN`.

```text
test_task40_router_contract.py
test_task41_router_contract.py
test_task42_router_contract.py
test_task43_router_contract.py
test_task44_router_contract.py
test_task45_router_contract.py
test_task46_router_contract.py
```

As propriedades permanentes não foram removidas. Elas já são cobertas pelos
motores de domínio — oportunidade, autoria, canon bridge, recompensas,
integridade adversarial, progressão e integração — e a presença dos checks no
Preflight passou a ser verificada centralmente em `tests/test_preflight.py` pelo
**comando executado**, não pelo número histórico da Task.

Os nomes apresentados pelo Preflight também passaram a ser nomes de domínio:
`recompensas de sidequest`, `integridade adversarial`, `progressão e
consequências de sidequest`, `integração de sidequests emergentes` e `canon
bridge`. Os comandos e a proteção executada não mudaram.

## Testes movidos para domínios estáveis

Nove arquivos possuíam comportamento permanente, mas ainda carregavam a etapa
do desenvolvimento no nome. Eles foram substituídos assim:

| Origem histórica | Cobertura estável |
| --- | --- |
| `test_analisar_rollout_task38.py` | `test_analisar_rollout_sistemas.py` |
| `test_analisar_rollout_task46.py` | `test_analisar_rollout_sistemas.py` |
| `test_analisar_rollout_task47.py` | `test_analisar_rollout_sistemas.py` |
| `test_task38_narrative_systems_integration.py` | `test_narrative_systems_integration.py` |
| `test_task45_boundary_guard.py` | `test_sidequest_boundary_guard.py` |
| `test_task46_budget_regression.py` | `test_sidequest_integration_budget.py` |
| `test_task46_integration_transaction.py` | `test_sidequest_integration_transaction.py` |
| `test_task46_rollout_matrix.py` | `test_sidequest_lifecycle_matrix.py` |
| `test_task47_explicit_opportunity_decision_gate.py` | `test_sidequest_opportunity_decision.py` |

Os cenários continuam distintos quando protegem falhas diferentes. Por exemplo,
rollback transacional, limite de duas sidequests aceitas, recusa, expiração,
satisfação de intenção canônica e decisão explícita continuam sendo casos
separados.

## Testes históricos legítimos

Quatro arquivos continuam classificados como históricos porque a própria
compatibilidade com o passado é a propriedade sob teste:

```text
tests/sidequests_canonicas_task32_cases.py
tests/test_migracao_ren_5_5e.py
tests/test_secret_npc_quest_catalog.py
tests/test_sidequest_gate_v2.py
```

A migração de Ren, por exemplo, precisa continuar provando o snapshot do instante
de ativação 5.5e. Da mesma forma, os contratos de sidequest aposentados precisam
continuar provando que o legado permanece frio e não retorna ao hot path.

## O que o gate impede

`verificar-testes-historicos.py` falha quando:

- qualquer um dos 39 arquivos originais fica sem classificação;
- uma classificação inválida é usada;
- o requisito protegido não é descrito;
- um destino de cobertura não existe;
- um teste `permanente` ou `historico` é apagado;
- um teste `redundante` ou `substituivel` continua presente depois da
  consolidação;
- surge um novo arquivo classificado como `task_historica` que não esteja entre
  os históricos legitimamente preservados.

A suíte também exige que nenhum arquivo de discovery volte a usar o padrão
`test_taskNN...`.

## Limites desta Task

Esta consolidação não altera regras, gameplay, cânone, estado corrente, runtime
ou sessões. Também não tenta renomear internamente todo identificador histórico
do produto: chaves de schema, baselines e compatibilidades podem conter
`TaskNN` quando isso faz parte do contrato real ou do legado.

O alvo é específico: os **testes permanentes** devem expressar o domínio que
protegem em vez da ordem em que esse domínio foi implementado.
