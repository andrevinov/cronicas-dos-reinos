# RM-02 — Ledger e telemetria modular v2

## Status e dependências

**Concluída em 2026-09-13.** Depende da RM-01, já concluída.

## Problema

A detecção atual associa marcadores a vários módulos e fraciona o custo do turno
entre todos eles. Isso fecha matematicamente, mas não distingue produtor,
subcapacidade, gate neutro e efeito material. A mesma cadeia aparece várias
vezes no ranking e o custo marginal permanece desconhecido.

## Objetivo

Produzir um ledger pós-hoc hierárquico que detecte subcapacidades, agregue-as uma
única vez no módulo pai e preserve evidência, confiança e natureza da atribuição.

## Contrato do evento

Cada evento modular deve carregar:

- sessão, turno e unidade de análise;
- `module_id` v2 e `capability_id`;
- fonte do sinal: comando, output, ticket, resposta ou adjudicação;
- elegibilidade: sim, não ou indeterminada;
- ativação: ausente, gate neutro, consulta, decisão ou efeito;
- resultado materializado e evidência observável;
- confiança da inferência;
- custo exposto não aditivo;
- custo atribuído aditivo no módulo pai;
- versão do detector e do módulo.

## Implementação

1. Evoluir `ferramentas/analisar-rollout.py` para schema narrativo 2 sem quebrar
   a leitura de rollouts antigos.
2. Detectar aliases v1 como subcapacidades v2.
3. Emitir eventos para os quatro módulos novos da RM-07 à RM-10.
4. Fechar tokens uma única vez entre módulos pais. A distribuição interna entre
   subcapacidades deve ser explicitamente aditiva ou marcada como exposição.
5. Separar contagem observada de elegibilidade adjudicada.
6. Manter falsos positivos, desconhecidos e correções no ledger, sem sobrescrever
   a observação original.
7. Não adicionar telemetria ao loop de jogo; análise continua pós-hoc.

## Artefatos implementados

- `ferramentas/analisar-rollout.py`: extensão narrativa 2, ledger
  `modules-v2`, adaptador `legacy-v1` e adjudicações preservativas;
- `evaluation/schemas/ledger-modular-v2.schema.json`: contrato do ledger;
- `evaluation/schemas/adjudicacoes-ledger-v2.schema.json`: entrada de correções;
- `tests/test_telemetria_modular.py`: cobertura de aliases, gates, custos,
  indeterminação, adjudicação, módulos novos e operação read-only;
- `docs/agente/engenharia/telemetria-rollouts.md`: contrato operacional e receita.

O gerador v1 seleciona a visão legada explicitamente. O ledger v2 fica
disponível para as RM-03–RM-10, mas ainda não inaugura a série de scorecards
`modules-v2`, responsabilidade da RM-11/RM-12.

## Compatibilidade

O analisador deve conseguir gerar uma visão `legacy-v1` para auditoria histórica
e uma visão v2 para rollouts novos. Backfill não cria sinais que o rollout antigo
não registrou e nunca transforma ausência em zero.

## Testes

- um turno com várias subcapacidades de sidequest conta um único módulo pai;
- soma dos custos atribuídos aos módulos pais fecha no total narrativo;
- gate neutro não é confundido com efeito;
- alias v1 resolve para exatamente uma subcapacidade;
- sinais indeterminados permanecem indeterminados;
- correção manual preserva observado e adjudicado;
- análise não escreve em estado, runtime ou sessão.

## Definition of done

- ledger v2 documentado e estável;
- adaptador v1 coberto;
- atribuição pai/subcapacidade sem dupla contagem;
- quatro novos módulos possuem sinais observáveis possíveis;
- testes de telemetria e orçamento ficam verdes.
