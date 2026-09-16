# Avaliação padronizada de desempenho por sessão

Esta é a receita canônica para transformar cada rollout concluído em um pacote
`modules-v2`. A medição é pós-hoc, somente leitura sobre o rollout e não altera
o cânone. O único dado criado durante o jogo é a identidade append-only das
interações, necessária para ligar evidência posterior ao par correto.

O reparo do instrumento passa a ter um
[contrato de entrada e unidades](contrato-entrada-medicao.md), com uma porta
separada para congelar fontes antes da medição. A atividade 1 não muda o gerador
nem corrige suas notas; o procedimento abaixo continua descrevendo o fluxo
existente até sua integração nas atividades seguintes.

O [corpus independente de regressão](corpus-regressao-avaliacao.md) fixa as
expectativas das correções antes de alterar o detector. Enquanto as atividades
3–9 não forem concluídas, seu comando estrito reprova o avaliador e discrimina
falha do instrumento de erro no próprio corpus.

Desde o detector 4.3.0, chamadas agrupadas são decompostas conforme o contrato
de [operações executadas](operacoes-executadas-rollout.md). A contagem nativa do
host continua por `call_id`; recibos, sucesso e sinais modulares são associados
ao resultado de cada operação interna.

O detector 4.4.0 aplica a
[classificação de resultados](classificacao-resultados-rollout.md) antes da
cobertura modular. Falha operacional, ausência de recibo, inaplicabilidade,
evidência insuficiente e erro do detector permanecem estados independentes.

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

Antes da primeira sessão real, validar o mecanismo sem tocar o save:

```bash
poetry run python ferramentas/aceitacao_modular_v2.py check
```

`pronta_para_primeira_sessao_real` significa que o gate técnico passou. Não é
uma nota de jogo e não inaugura a curva longitudinal.

Se um pacote real já existir com respostas sem referência única, o aceite real
permanece `pendente`, com a quantidade de respostas afetadas no diagnóstico.
Isso não reprova a prontidão técnica nem autoriza corrigir retroativamente as
referências no histórico ou aceitar a sessão como baseline operacional.

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

Para `sidequest_authoring` a partir da implementação 2.0.1/régua 4.0.0, a
declaração positiva ou negativa é apenas cobertura estrutural. O recibo objetivo
ou uma adjudicação produz VP, VN, FP, FN ou `indeterminado`. Precisão mede
`VP/(VP+FP)`, cobertura mede `VP/(VP+FN)` e a nota de calibração usa acurácia
balanceada somente quando as classes positiva e negativa possuem denominador.
Indeterminado fica visível e fora da nota; uma coleção de negativas declaradas
não fabrica desempenho alto.

Para `canonical_quest_integration` 2.0.0/régua 4.0.0, a unidade é cada atividade
de sidequest. Recibos completos sustentam a matriz objetiva; a calibração usa a
média das classes efetivamente observadas, com confiança baixa enquanto a
amostra for pequena. Se houve atividade mas nenhuma ponte era elegível, o card
mostra **não aplicável**, não N/D e não nota alta. Se um recibo esperado estiver
ausente ou incompleto, mostra **falha de instrumentação** e bloqueia a nota. N/D
fica reservado ao caso em que nenhuma atividade do domínio foi observada.

A mesma semântica fail-closed vale para todos os módulos na régua 4.0.0. O
detector deriva atividades obrigatórias das portas públicas executadas e exige
um recibo estruturado de cada fachada. Recibo completo `nao_aplicavel` produz
N/A; recibo completo `indeterminado` bloqueia a nota sem fabricar N/D; atividade
sem recibo completo produz **falha de instrumentação**. Assim, N/D significa
somente que a sessão não gerou unidade avaliativa para aquele módulo.

Consulta, decisão, gate e efeito são estados distintos. Um gate neutro responde
uma oportunidade elegível sem fabricar efeito; consulta ou decisão sem resultado
material não é falha de eficácia. A nota modular só existe quando há evidência
adjudicável de calibração ou efeito: confiança do detector e latência exposta,
isoladamente, permanecem diagnósticos e não fabricam desempenho numérico.
Manifestações confirmadas/parciais de boa ativação alimentam efeitos adequados;
efeito incorreto, timing e continuidade alimentam efeitos inadequados. Dimensões
de auditoria semântica adequadas/inadequadas entram na eficácia da entrega
narrativa; guardrails continuam separados e não compensáveis.
Uma manifestação de possível guardrail só vira violação crítica quando sua
adjudicação é `confirmada`; ela não entra na nota numérica do módulo.

Por sessão: calibração 30%, eficácia 30%, confiabilidade 20%, economia 15% e
fluidez 5%. N/D é excluído e os pesos restantes são renormalizados. Não existe
eixo numérico do jogador.

Prioridade combina 70% do déficit de experiência/desempenho e 30% da parcela de
custo. Zero atividade e inaplicabilidade confirmada não geram déficit; uma falha
de instrumentação usa déficit 100 para não desaparecer no fim da fila. Casos
indeterminados continuam provisórios sem nota inventada. `sem_evidencia`,
`evidencia_insuficiente` e **inaplicabilidade confirmada** são estados
diferentes. Se nenhuma oportunidade elegível exercitou
autoria ou oferta de sidequest, o gate é reportado separadamente e nem déficit
nem custo exposto entram na prioridade do módulo.

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
fixtures em `module-releases.json` antes de produzir dados novos. O registro é
append-only: adicionar a release e mover seu ponteiro em `current_releases`, sem
reescrever a predecessora. A primeira sessão real aceita vira a baseline
operacional; a fixture técnica e sessões legadas nunca entram nessa posição.
