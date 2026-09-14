# Avaliação padronizada de desempenho por sessão

Esta é a receita canônica para transformar cada rollout concluído em um pacote
`modules-v2`. A medição é pós-hoc, somente leitura sobre o rollout e não altera
o cânone. O único dado criado durante o jogo é a identidade append-only das
interações, necessária para ligar evidência posterior ao par correto.

## Fontes e unidades

- sessão canônica: unidade do pacote;
- `interaction_ref`: unidade primária de evidência do jogador;
- evento modular: interação/turno × módulo-pai × subcapacidade observada;
- módulo-pai: única unidade do ranking e da prioridade;
- subcapacidade: diagnóstico, nunca uma prioridade concorrente;
- guardrail: bloco crítico não compensável, fora da média.

Fontes versionadas: rollout JSONL, `catalogo-modulos-v2.json`,
`metas-avaliacao-v2.json`, `module-releases.json`, política de séries, baseline,
ledger `sessoes/NNN/interacoes.jsonl` e adjudicações opcionais.

## 1. Durante a sessão

Cada resposta final visível recebe exatamente uma referência:

- ON: `Interação SNNN-INNNN` dentro do `RODAPE_CANONICO`;
- OFF/RECALL/operacional: `INTERAÇÃO — SNNN-INNNN` no fim da resposta.

O registro contém hashes do par, não duplica a prosa. Retry reaproveita a
reserva; entrada nova avança o ordinal. Uma manifestação do jogador é feita em
OFF, preferencialmente no Codex:

```text
[AVALIAÇÃO S022-I0049 — havia uma boa oportunidade para um NPC tomar
iniciativa, mas ele permaneceu passivo.]
```

Isso não avança tempo, mundo ou personagem. O texto original é preservado como
percepção pendente; módulo, subcapacidade e verdade medida são camadas de
adjudicação separadas.

## 2. Gerar o pacote automático

Após encerrar a sessão:

```bash
poetry run python ferramentas/gerar-avaliacao-sessao.py \
  /caminho/para/rollout.jsonl \
  --sessao-id 022
```

Destino padrão: `evaluation/sessions/022/`. Para fornecer exportação do painel
ou adjudicações externas:

```bash
poetry run python ferramentas/gerar-avaliacao-sessao.py \
  /caminho/para/rollout.jsonl \
  --sessao-id 022 \
  --interacoes /caminho/manifestacoes-jogador-sessao-022.json \
  --adjudicacoes-modulares /caminho/adjudicacoes-modulares.json \
  --validade /caminho/validade-medicao.json
```

Sem `--interacoes`, o gerador usa automaticamente o ledger da sessão, quando
existe. A regeneração preserva manifestações e adjudicações já empacotadas.

## 3. Adjudicar sem apagar observação

`adjudicacoes-modulares.json` pode corrigir elegibilidade, ativação,
materialização ou efeito de um evento, executar auditoria semântica e classificar
uma manifestação. O observado pelo detector permanece intacto.

Estados da manifestação: `pendente`, `confirmada`, `parcial`,
`nao_confirmada` ou `indeterminada`. Somente confirmação total/parcial alimenta
as métricas factuais; pendência continua visível. Informação reservada pode
sustentar a adjudicação, mas não deve ser exposta ao jogador.

`validade-medicao.json` registra falsos positivos/negativos do próprio medidor e
violações críticas. Agência, sigilo, integridade de rolagem e consistência
canônica nunca são compensados por outra nota.

## 4. Indicadores e notas

Por módulo:

- calibração: precisão e cobertura sobre oportunidades adjudicáveis;
- eficácia/integridade: proporção de efeitos adequados observáveis;
- confiabilidade: confiança das evidências e contratos do módulo;
- fluidez: latência exposta, explicitamente não causal;
- economia: custo aditivo, parcela da sessão e custo exposto; permanece N/D na
  nota modular até existir baseline por classe de oportunidade;
- manifestações confirmadas, falsos positivos/negativos e problemas;
- versão de implementação, versão de avaliação e confiança da amostra.

Por sessão: calibração 30%, eficácia 30%, confiabilidade 20%, economia 15% e
fluidez 5%. N/D é excluído e os pesos restantes são renormalizados. Não existe
eixo numérico do jogador.

Prioridade combina 70% do déficit de experiência/desempenho e 30% da parcela de
custo. Quando a nota é N/D, usa-se déficit de evidência de 50 apenas para ordenar
a fila; `prioridade_provisoria` deixa explícito que isso não é uma nota
inventada.

Uma sessão é provisória. Estabilidade exige ao menos três sessões comparáveis e
dez oportunidades por módulo.

## 5. Artefatos uniformes

```text
evaluation/sessions/<id>/
├── manifest.json
├── telemetria.json
├── turnos.csv
├── eventos-modulares.csv
├── resumo-modulos.csv
├── resumo-modulos.json
├── interacoes.json
├── manifestacoes-jogador.json
├── adjudicacoes-modulares.json
├── validade-medicao.json
├── scorecard.json
└── relatorio.md
```

O manifesto preserva versões de gerador, detector, catálogo, metas, contrato e
as duas versões de cada módulo. O índice longitudinal é reconstruído
automaticamente.

## 6. Comparação longitudinal

Sessões `legacy-v1`, incluindo a 021, podem aparecer lado a lado como referência
mas não entram na curva v2. Comparação global exige a mesma série, metas e
contrato de avaliação. Comparação entre implementações exige o mesmo módulo e
uma versão de avaliação compatível. Uma release de um módulo não quebra a série
dos outros onze.

Patch de implementação é ajuste compatível; minor é mudança substancial que
preserva responsabilidade e régua; major muda responsabilidade/interface. Para
a régua, major muda denominador, elegibilidade, indicador, peso ou significado.
Toda alteração registra predecessora, natureza, compatibilidade, motivo e
fixtures em `module-releases.json` antes de produzir dados novos.
