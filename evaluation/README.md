# Contratos e pacotes de avaliação

Este diretório contém artefatos pós-hoc de engenharia. Nada aqui é memória
canônica da campanha nem autoriza ação no mundo.

## Entrada congelada de medição

A atividade 1 do reparo publica `contrato-medicao.json`, contratos locais em
`contratos-modulos/` e três schemas de entrada/unidades. A porta
`ferramentas/entrada_medicao.py` congela corte e hash do rollout, snapshots das
fontes e versões selecionadas, sem copiar o bruto ou recalcular notas.

Uso e limites: [contrato de entrada e unidades](../docs/agente/engenharia/contrato-entrada-medicao.md).
Desde a atividade 9, o gerador 4.4.0 consome essa entrada como autoridade única,
valida código e ambiente antes da análise e publica a proveniência e o gate de
conclusão. Contrato:
[reprodutibilidade do pacote](../docs/agente/engenharia/reprodutibilidade-pacote-avaliacao.md).

## Corpus de regressão

A atividade 2 publica `regressoes-rollout-v1/`, com entradas nativas reduzidas,
configuração congelada e gabaritos independentes do analisador. O executor
`ferramentas/verificar_corpus_avaliacao.py` percorre entrada, detector, gerador,
agregação e aceite. O resultado inicial permanece vermelho para que as correções
seguintes tenham um critério observável de conclusão.

Contrato, execução e limites: [corpus independente de regressão](../docs/agente/engenharia/corpus-regressao-avaliacao.md).

A atividade 3 introduz o ledger `executed_operations`, mantendo métricas nativas
por chamada e evidência modular por operação. Correlação, transporte e limites:
[operações executadas no rollout](../docs/agente/engenharia/operacoes-executadas-rollout.md).

A atividade 4 publica `operation_outcomes`, com resultado e fonte de evidência
por operação, e tipa separadamente os estados da cobertura modular. Semântica e
precedência: [classificação de resultados](../docs/agente/engenharia/classificacao-resultados-rollout.md).

A atividade 5 publica `module_activities`, com identidade por operação, módulo,
fase e objeto opaco. Recibos são ligados um a um; duplicações, `units` agregados
e órfãos permanecem visíveis. Contrato:
[ledger de atividades modulares](../docs/agente/engenharia/ledger-atividades-modulares.md).

A atividade 6 aplica o bloqueio até o scorecard. Componentes de módulos com
falha de instrumentação são excluídos antes das médias, e o pacote publica os
denominadores válidos e a natureza parcial da nota restante. Contrato:
[agregação fail-closed](../docs/agente/engenharia/agregacao-fail-closed.md).

A atividade 7 publica avaliações de qualidade por interação, módulo e critério.
Cada registro exige evidência e adjudicação; oportunidades perdidas são
observáveis mesmo sem evento automático, e conformidade operacional permanece
separada da qualidade. Contrato:
[qualidade adjudicada por interação](../docs/agente/engenharia/qualidade-por-interacao.md).

A atividade 8 remove o ranking misto. Reparo do medidor, problemas da
experiência e investigação de custo usam filas independentes; tokens aparecem
como atribuição contábil sem inferência causal. Contrato:
[filas de decisão e atribuição contábil](../docs/agente/engenharia/filas-prioridade-e-custo.md).

A atividade 9 integra o corte congelado ao gerador, impede leituras implícitas
de fontes mutáveis, compara código e ambiente e exige igualdade byte a byte na
aceitação técnica. Correlação ambígua, resultado ausente, evidência insuficiente
e erro do detector bloqueiam conclusões dependentes sem apagar fatos observados.

A atividade 10 fecha o corpus em 226/226, promove-o ao `preflight` e adiciona
`validacao-externa-v1/`: um recorte real e hash-ancorado da sessão 022 com seis
resultados operacionais conferidos por gabarito independente. O aceite real
agora exige proveniência reproduzível, conclusão permitida, agregação completa,
ausência de falha de instrumentação e referências únicas. A sessão 023 continua
pendente e não é transformada retroativamente em baseline.

## Série de produção

`modules-v2` é a série de produção desde a RM-11. Ela usa:

- `catalogo-modulos-v2.json`: os doze módulos-pai e suas subcapacidades;
- `metas-avaliacao-v2.json`: pesos, faixas, confiança e filas de decisão;
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

O gerador de produção consome o prefixo congelado do rollout e os snapshots
selecionados explicitamente. Ele publica:

- telemetria e eventos ligados por `interaction_id`/`interaction_ref`;
- três filas independentes somente entre os doze módulos-pai;
- drilldown diagnóstico das subcapacidades;
- atribuição contábil aditiva no pai e apenas exposição na subcapacidade;
- versões de implementação e avaliação vigentes;
- manifestações concretas do jogador e sua adjudicação;
- guardrails fora da média;
- proveniência reproduzível e gate explícito de conclusão;
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
