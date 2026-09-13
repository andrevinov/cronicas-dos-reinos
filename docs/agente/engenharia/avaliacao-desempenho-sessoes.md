# Avaliação padronizada de desempenho por sessão

Este documento é a receita canônica para transformar um rollout concluído em
um pacote de avaliação comparável. A avaliação é pós-hoc, somente leitura sobre
o rollout e não participa do loop narrativo nem altera o cânone.

## Princípios

1. A unidade lógica é a sessão canônica; um arquivo de rollout é apenas a fonte.
2. O rollout bruto não é copiado para o repositório.
3. Contador nativo, inferência observacional, adjudicação semântica e percepção
   do jogador permanecem identificáveis e separados.
4. Presença de marcador não prova elegibilidade, materialização nem correção do
   efeito de um módulo.
5. Ausência de evidência produz `N/D` ou `indeterminada`, nunca aprovação tácita.
6. Custo exposto não é aditivo; custo fracionado é aditivo, mas não causal.
7. Cada sessão preserva seu próprio pacote antes de qualquer agregação histórica.
8. Módulos reservados não são apresentados nominalmente no formulário do jogador.

## Fontes versionadas

- `ferramentas/analisar-rollout.py`: coleta operacional schema 3, extensão
  narrativa 2 e visão compatível `legacy-v1`;
- `evaluation/catalogo-modulos.json`: catálogo v1 ainda usado em produção;
- `evaluation/catalogo-modulos-v2.json`: contrato hierárquico preparado, ainda
  não usado pelo gerador;
- `evaluation/catalogo-guardrails-v2.json`: propriedades críticas externas à
  média modular;
- `evaluation/series-avaliacao.json`: corte e comparabilidade das séries;
- `evaluation/metas-avaliacao.json`: pesos, metas e faixas;
- `baseline/rollout-2026-08-15.json`: baseline histórica;
- rollout JSONL concluído;
- adjudicação opcional da validade da medição;
- auditoria semântica e feedback preservados no pacote.

Alterar catálogo ou metas exige incrementar o respectivo schema. Comparações
longitudinais devem mostrar as versões usadas em cada sessão.

### Corte entre séries

Até a RM-11, o catálogo v1 e a série `legacy-v1` continuam sendo o padrão de
produção. Pacotes sem `serie_avaliacao` são classificados como `legacy-v1`; não
se reescreve o snapshot apenas para acrescentar o campo. Por isso a sessão 021
permanece intacta e aparece como legado no índice derivado.

`modules-v2` exige declaração explícita depois da habilitação do avaliador v2.
Não se calcula média, tendência ou baseline misturando `legacy-v1` e
`modules-v2`. Também não se agregam silenciosamente pacotes cujas versões de
catálogo, metas ou gerador divergem. O contrato executável está em
`ferramentas/catalogo_avaliacao.py`.

## Pré-condição

Preferir um rollout iniciado com `cronica sessao iniciar` e encerrado com
`cronica sessao encerrar`. Se uma sessão ocupar vários rollouts, reunir os
resultados sob o mesmo `sessao-id`; se um rollout contiver várias sessões,
separá-las pelas fronteiras do lifecycle antes de publicar os pacotes.

## Comando uniforme

Primeira geração automática:

```bash
poetry run python ferramentas/gerar-avaliacao-sessao.py \
  /caminho/para/rollout.jsonl \
  --sessao-id 022
```

O destino padrão é `evaluation/sessions/022/`. Para semear uma auditoria ou uma
adjudicação já existentes:

```bash
poetry run python ferramentas/gerar-avaliacao-sessao.py \
  /caminho/para/rollout.jsonl \
  --sessao-id 022 \
  --auditoria /caminho/para/auditoria-modulos.csv \
  --validade /caminho/para/validade-medicao.json
```

O comando pode ser repetido. `auditoria-modulos.csv`, `feedback-jogador.csv` e
`validade-medicao.json` já existentes no pacote são lidos antes da regeneração,
preservando o trabalho humano.

## Fluxo de produção

### 1. Gerar a camada automática

Executar o comando uniforme. Conferir em `manifest.json`:

- hash e nome do rollout;
- ID técnico do Codex;
- quantidade de turnos narrativos;
- quantidade de módulos catalogados;
- igualdade entre tokens narrativos e tokens fracionados, salvo o campo
  explícito `tokens_sem_atribuicao`;
- avisos de correlação de turnos ou latência.

### 2. Adjudicar a validade da medição — N0

Editar `validade-medicao.json` apenas quando houver evidência de falso positivo,
falso negativo ou status desconhecido do analisador. Cada correção registra:

- métrica;
- valor observado;
- valor adjudicado;
- motivo verificável.

Violações críticas de agência, segredo, integridade de rolagem ou corrupção
canônica entram em `violacoes_criticas` e permanecem separadas da nota média.

### 3. Auditar semanticamente os módulos — N3

Preencher `auditoria-modulos.csv`. Para cada módulo:

- `avaliacao_ativacao`: `ativou a contento`, `sobreativou`, `subativou`,
  `ativacao mista` ou vazio;
- impactos de experiência e custo em escala 1–5, na qual 5 é pior;
- prioridade, problemas, justificativa, confiança e evidências.

O arquivo `eventos-modulares.csv` é o ledger para localizar os turnos. Nesta
primeira versão, elegibilidade e efeito esperado permanecem indeterminados até
que uma auditoria por turno forneça evidência suficiente.

### 4. Coletar percepção do jogador

O jogador preenche `feedback-jogador.csv` depois da sessão. Primeiro responde às
dimensões globais; depois, opcionalmente, aos módulos de efeito direto ou
indireto. Valores aceitos:

- `nota_1a5`: 1 a 5, maior é melhor;
- `ativacao_menos2a2`: -2 a 2;
- `impacto_menos2a2`: -2 a 2;
- `observado`: sim, não ou incerto.

Campo vazio significa N/D e não vira nota neutra. O formulário não lista
módulos reservados ou puramente técnicos.

### 5. Regenerar e congelar o pacote da sessão

Repetir o comando uniforme sem `--auditoria`/`--validade`: as entradas humanas
do próprio pacote serão reutilizadas. Conferir `scorecard.json`,
`resumo-modulos.csv` e `relatorio.md`.

Uma sessão concluída é um snapshot histórico de avaliação. Correção posterior
deve ser explícita na adjudicação ou em nova versão do pacote; não reescrever
silenciosamente a evidência original.

## Artefatos

```text
evaluation/sessions/<sessao-id>/
├── manifest.json
├── telemetria.json
├── turnos.csv
├── eventos-modulares.csv
├── auditoria-modulos.csv
├── resumo-modulos.csv
├── resumo-modulos.json
├── feedback-jogador.csv
├── validade-medicao.json
├── scorecard.json
└── relatorio.md
```

- `telemetria.json`: saída integral do analisador existente;
- `turnos.csv`: uma linha por avanço narrativo, com classe, custo e latência;
- `eventos-modulares.csv`: uma linha para cada combinação módulo × turno;
- `auditoria-modulos.csv`: julgamento semântico preservado;
- `resumo-modulos.csv`: junção de telemetria, auditoria, notas e prioridade;
- `resumo-modulos.json`: equivalente estruturado consumido pela visualização;
- `feedback-jogador.csv`: formulário player-safe;
- `validade-medicao.json`: correções N0 e violações críticas;
- `scorecard.json`: nota geral, eixos e métricas para visualização futura;
- `relatorio.md`: síntese humana da sessão.

## Notas

Os eixos e pesos ficam em `evaluation/metas-avaliacao.json`:

- calibração: 25%;
- eficácia e integridade: 25%;
- confiabilidade: 15%;
- economia: 20%;
- fluidez: 5%;
- jogador: 10%.

Notas ausentes são excluídas e os pesos restantes são renormalizados. A nota
modular de confiabilidade usa, por enquanto, a proporção de turnos com exatamente
um `preparar` e um `concluir` como proxy. A nota de fluidez modular usa latência
exposta, não causal. Ambas devem aparecer com essa limitação.

Faixas:

- 90–100: excelente;
- 80–89: saudável;
- 65–79: atenção;
- 50–64: ruim;
- abaixo de 50: crítico.

Uma sessão isolada é sempre provisória. Estabilidade exige pelo menos três
sessões e dez oportunidades avaliáveis por módulo.

## Preparação para a visualização longitudinal

A visualização deve consumir `scorecard.json` e `resumo-modulos.json`, não
o rollout bruto. `evaluation/sessions/index.json` é reconstruído pelo gerador e
permite descobrir novas sessões sem editar o painel. A visualização deve exibir separadamente:

- sessão atual;
- média móvel de três sessões;
- tendência de dez sessões;
- notas por eixo;
- desempenho e prioridade por módulo;
- custo total, fracionado e futuramente marginal;
- confiança e tamanho da amostra;
- mudanças de versão do catálogo, metas ou analisador.

Nunca comparar médias de classes de turno diferentes sem estratificação. Uma
fronteira temporal, uma autoria de sidequest e um avanço comum precisam de
referências próprias.
