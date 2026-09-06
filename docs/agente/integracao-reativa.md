# Integração reativa v1 — referência histórica

Este documento descrevia a primeira integração de contexto, encontros,
sidequests e recompensas. Sua porta operacional foi substituída por
[`integracao-reativa-v2.md`](integracao-reativa-v2.md) e pelas Tasks 40–52.

Não use as antigas chamadas diretas de preparação, confirmação ou escrita no
hot path. A operação vigente é:

```text
cronica preparar → narrar e resolver mecânica necessária → cronica concluir
```

O contexto fornecido ao preparo deve representar somente gatilhos reais da cena.
O ticket resultante preserva a revalidação transacional, memória de cena,
sidequests ativas e pressões já comprometidas. As primitivas diretas permanecem
disponíveis apenas para manutenção e reparo conforme o manual v2.

O desenho e os detalhes da versão anterior continuam preservados no histórico do
Git; manter uma segunda receita operacional neste arquivo criaria instruções
concorrentes.
