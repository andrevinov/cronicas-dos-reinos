# Task 34 — Persistent World Conditions

## Objetivo

Representar fatos do mundo que permanecem por várias cenas ou dias — **clima, escassez, greve, festival, toque de recolher e problemas portuários** — sem scheduler, sem RNG e sem transformar cada condição em agente/evento.

Uma condição persistente é contexto canônico durável. Ela pode influenciar a descrição e fornecer um fato consultável para sistemas posteriores, mas não cria por si só encontro, penalidade, teste, side quest, incidente, recompensa ou ação de NPC.

## Estado

O estado compacto vive em:

```text
narrador/mundo/condicoes-persistentes.yaml
```

Ele começa vazio deliberadamente. A Task 34 **não infere retroativamente** qual era o clima, se havia greve, escassez ou toque de recolher no checkpoint atual.

Estrutura:

```yaml
schema_condicoes_mundo: 1
natureza: controle_reservado
cidade: ravens_bluff
condicoes: {}
historico_recente: []
```

No máximo oito condições permanecem abertas e o histórico recente guarda até dezesseis encerramentos compactos.

## Tipos

A v1 aceita exatamente:

- `clima`;
- `escassez`;
- `greve`;
- `festival`;
- `toque_de_recolher`;
- `porto`.

O campo `assunto` distingue condições do mesmo tipo, por exemplo uma escassez específica ou um problema portuário específico.

## Escopo

Toda condição pertence a `ravens_bluff`.

- `locais: []` significa cidade inteira;
- uma lista de locais restringe a condição àqueles IDs canônicos.

Aliases são resolvidos pelo registro canônico tanto ao registrar quanto quando uma cena chega apenas por tag `local:`. O estado e a projeção usam sempre o mesmo `local_id` canônico; alias nunca cria um escopo paralelo.

## Tempo sem scheduler

Toda condição possui `inicio` e pode possuir `fim_previsto`.

A leitura compara esses instantes ao mesmo relógio de Harptos já usado pelo Mundo Vivo:

```text
antes do início → não projetada
entre início e fim → ativa
após fim previsto → não projetada
```

Nenhuma escrita acontece quando o tempo cruza o fim. Não existe wake-up, job, agenda ou pendência de expiração.

Quando uma escrita posterior ocorre, condições cujo fim previsto já passou podem ser compactadas para `historico_recente`. Isso mantém o estado pequeno sem exigir manutenção por turno.

## Causalidade canônica e replay-safe

Registrar ou encerrar uma condição exige:

- caminho de fonte em `sessoes/`, `historico/` ou `estado/`;
- evidência textual literal existente nessa fonte.

`narrador/` e `runtime/` são recusados como origem de fato: planejamento reservado e projeção derivada não podem canonizar uma condição sozinhos.

A identidade causal de uma condição é derivada de **fonte + evidência literal**, não do horário em que o comando foi executado. Consequências:

- repetir o mesmo comando enquanto a condição está aberta é idempotente;
- executar novamente a evidência depois do `fim_previsto` não ressuscita a condição;
- evidência já movida para o histórico continua consumida;
- uma recorrência legítima — outra tempestade, outra greve, outro toque de recolher — exige um **novo fato canônico**, portanto nova evidência literal.

A mesma evidência também não pode ser reutilizada para mudar tipo, assunto ou definição da condição.

Exemplo após um fato já narrado/consolidado:

```bash
poetry run python ferramentas/condicoes_mundo.py registrar \
  --tipo clima \
  --assunto 'tempestade costeira' \
  --intensidade forte \
  --descricao 'Chuva pesada e rajadas persistem sobre Ravens Bluff.' \
  --sinal 'calçadas encharcadas' \
  --sinal 'rajadas nas ruas abertas' \
  --marcador chuva_forte \
  --marcador vento_forte \
  --duracao-horas 48 \
  --fonte sessoes/NNN/resumo.md \
  --evidencia '<frase literal que canonizou a condição>'
```

Sem `--local`, a condição é municipal. `--local` pode ser repetido para restringir o escopo.

Encerramento explícito:

```bash
poetry run python ferramentas/condicoes_mundo.py encerrar <cnd-id> \
  --motivo '<o que encerrou a condição>' \
  --fonte sessoes/NNN/resumo.md \
  --evidencia '<frase literal do encerramento>'
```

## Projeção pública

Consulta rara:

```bash
poetry run python ferramentas/condicoes_mundo.py mostrar
poetry run python ferramentas/condicoes_mundo.py mostrar --local casa_de_tyr
```

A projeção expõe apenas:

- ID;
- tipo/assunto;
- intensidade;
- descrição observável;
- sinais;
- marcadores;
- fim previsto, quando houver.

Fonte e evidência ficam reservadas.

## Integração de cena

A Task 34 envolve a mesma `cena_mundo.py` já existente.

Fluxo:

```text
cena reativa
→ presença/sidequest/etc. existentes
→ detectar contexto espacial canônico
   → sem local/tag local: zero leitura Task34
   → com local: resolver ID canônico e ler condicoes-persistentes.yaml uma vez
→ projetar somente condições ativas aplicáveis
→ incluir a fonte no fingerprint transacional
```

Assim, se uma condição mudar entre `preparar` e `confirmar`, a preparação fica stale como qualquer outra fonte relevante.

Uma cena somente com NPC não paga essa leitura. Um turno neutro também não toca a camada. Fixtures/instalações sem o arquivo de estado preservam o fluxo anterior, em vez de interpretar ausência como “nenhuma condição canônica”.

## Marcadores

`marcadores` são tags compactas, não efeitos mecânicos. Eles existem para futuras camadas — especialmente incidentes — poderem testar contexto sem interpretar prosa livre.

Exemplos plausíveis: `chuva_forte`, `precos_tensionados`, `servico_reduzido`, `multidao`, `patrulha_reforcada`, `porto_lento`.

A Task 34 não atribui significado mecânico automático a nenhum marcador.

## Relação com sistemas existentes

- **Mundo Vivo:** não agenda condições e não precisa acordar por causa delas.
- **Adventure Drought Pressure:** não é alterada.
- **Microeventos:** frequência/deck não mudam automaticamente.
- **Side quests canônicas:** gates futuros podem consultar o arquivo como fonte de mundo, mas a Task 34 não cria quest.
- **Task 35 — World & Local Incidents v2:** poderá usar condições/marcadores como contexto causal sem criar um segundo estado ambiental.

## Custo

Contrato: `baseline/persistent-world-conditions-orcamento.yaml`.

- 0 scheduler;
- 0 RNG;
- 0 scan global;
- 0 leitura extra em cena sem contexto espacial;
- 1 leitura de estado compacto em cena espacial;
- estado <= 12 KiB;
- no máximo 8 condições abertas e 16 entradas de histórico.
