# Contratos e pacotes de avaliação

Este diretório contém artefatos pós-hoc de engenharia. Nada aqui é memória
canônica da campanha nem autoriza ação no mundo.

## Série de produção

`modules-v2` é a série de produção desde a RM-11. Ela usa:

- `catalogo-modulos-v2.json`: os doze módulos-pai e suas subcapacidades;
- `metas-avaliacao-v2.json`: pesos, faixas, confiança e prioridade;
- `catalogo-guardrails-v2.json`: propriedades críticas fora da média;
- `module-releases.json`: log append-only das versões de implementação e de
  avaliação, mais o mapa explícito `current_releases` para a release vigente de
  cada módulo;
- `series-avaliacao.json`: corte de série e regras de comparabilidade;
- `schemas/`: contratos JSON publicados.

`catalogo-modulos.json` e `metas-avaliacao.json` permanecem somente para ler e
regenerar pacotes `legacy-v1`. Um manifesto sem `serie_avaliacao` é classificado
como legado; por isso `sessions/021` continua intacto e não ganha identidades ou
notas reconstruídas artificialmente.

Validação estrutural:

```bash
poetry run python ferramentas/catalogo_avaliacao.py --json
```

O validador exige os doze módulos, migração única dos vinte itens v1,
guardrails sem peso, política de série e release corrente coerente com as duas
versões SemVer do catálogo. Uma alteração adiciona outra entrada com `release_id`
único e move somente o ponteiro corrente; nunca edita a entrada predecessora.

## Pacote por sessão

O gerador de produção consome o rollout e, quando disponível, o ledger
append-only `sessoes/NNN/interacoes.jsonl`. Ele publica:

- telemetria e eventos ligados por `interaction_id`/`interaction_ref`;
- ranking somente dos doze módulos-pai;
- drilldown diagnóstico das subcapacidades;
- custo aditivo no pai e apenas exposição na subcapacidade;
- versões de implementação e avaliação vigentes;
- manifestações concretas do jogador e sua adjudicação;
- guardrails fora da média;
- scorecard e relatório da sessão.

Não existe nota numérica direta do jogador na série v2. Uma manifestação só
altera métrica factual depois de adjudicada e preserva sempre o texto original.

Comparação global exige a mesma série, contrato de avaliação e metas. Comparar
versões de um módulo exige o mesmo `module_id` e versão de avaliação compatível;
a versão de implementação é a dimensão em disputa e não fragmenta a série dos
outros módulos.

A receita completa está em
`docs/agente/engenharia/avaliacao-desempenho-sessoes.md` e a visualização em
`dashboard/README.md`.

O aceite reproduzível da arquitetura é executado por:

```bash
poetry run python ferramentas/aceitacao_modular_v2.py check
```

Ele usa uma sessão técnica isolada e não cria ponto na série real.
