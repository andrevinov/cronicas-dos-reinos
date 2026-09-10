# NV-15 — Permanência espacial reativa

## Problema

Uma cena podia permanecer horas no mesmo lugar sem passar pelo gatilho de entrada/exploração. O resultado era uma falsa lacuna: o local já estava consolidado, mas a preparação não consultava ecologia, presença incidental, rotina, incidentes ou condições daquele espaço. Recriar a cena com outro `scene_id` também podia gerar uma nova tentativa de sorteio em produtores cuja chave histórica era a cena.

## Porta operacional

A NV-15 adiciona o modo explícito:

```bash
poetry run cronica preparar \
  --cena-id <id-estavel> \
  --permanencia-local \
  --sem-oportunidade-sidequest \
  --sem-participantes
```

`--local` é opcional. Quando omitido, a permanência herda somente o local atual já consolidado em `estado/estado-atual.yaml`. Se `--local` for informado, ele precisa resolver para o mesmo local consolidado. Permanência nunca move Ren nem cria um local por aproximação.

O modo é incompatível com `--transito-urbano`, `--npc`, `--contexto-tag`, `--acao`, `--tier` e `--periculosidade`. Elenco efetivamente conhecido continua sendo declarado pela memória de cena (`--participante` / `--sem-participantes`); presença incidental é uma avaliação separada e nunca estabelece presença automaticamente.

## Chave de frescor

A identidade de uma avaliação é:

```text
local_id + data + periodo
```

O período reutiliza a mesma divisão operacional da NV-14, relativa ao amanhecer configurado. `scene_id` não participa da identidade. Os produtores de microeventos e incidentes recebem uma identidade sintética `permanencia:<local>:<data>:<periodo>` apenas como chave histórica; seus decks, catálogos e regras continuam sendo os mesmos.

Consequências:

- renomear/recriar uma cena não rerrola a permanência;
- retries no mesmo local/data/período reutilizam o recibo;
- no máximo uma avaliação nova é reservada por janela;
- um candidato ativo da janela anterior do mesmo local é carregado em vez de desaparecer;
- mudança canônica de local invalida candidatos espaciais ainda ativos do local antigo.

## Avaliação espacial

Na primeira permanência da janela, `permanencia_espacial.py` consulta somente produtores já existentes e dirigidos:

1. **ecologia local** — `ecologia_local.lookup_canonical` + ritmo do período;
2. **presença incidental ancorada** — índice operacional de presença, sem abrir fragmentos globais de NPC;
3. **microevento rotineiro** — mesmo baralho local da cena reativa;
4. **incidente local** — mesmos decks global/local e mesmos filtros ecológicos/ambientais;
5. **condições ambientais** — projeção persistente para o local atual.

Não há scheduler, scan global de personagens, geração por IA nem segunda chamada de modelo.

Microeventos e incidentes são **reservados** no primeiro `preparar`: o estado de seus decks é consumido e o resultado histórico é gravado, mas nenhum candidato se torna fato canônico. Essa reserva deliberada é o que impede reroll quando outro preparo ocorre antes da narração. O recibo da NV-15 é escrito por último; se houver interrupção parcial, repetir a mesma chave encontra os históricos produtores já reservados e reconstrói o mesmo resultado.

## Pressão primária e calma

A permanência registra todos os resultados dos cinco domínios. Entre candidatos realmente produzidos, existe no máximo uma pressão primária:

1. incidente local sério;
2. presença incidental;
3. microevento rotineiro.

Os demais candidatos da mesma janela ficam explicitamente `adiada_pelo_orcamento_da_janela`. Isso não inventa ocorrência e preserva o limite de atenção introduzido pela fronteira de vivacidade.

Se nenhum produtor oferecer candidato, a avaliação termina em `calma_espacial`. O recibo ainda registra `incidente_local.resultado: rotina`, presença vazia, microevento rotineiro, ecologia e condições consultadas. Portanto “nada aconteceu” é distinguível de “o sistema não rodou”.

## Estabilidade e conclusão

Quando existe pressão primária, o recibo permanece `ativa` até o `cronica concluir`. A transação deve declarar:

```json
{
  "permanencia_espacial": {
    "avaliacao_id": "perm-...",
    "resultado": "resolvida",
    "evidencia_literal": "trecho que aparece literalmente na narração ou resumo"
  }
}
```

ou, quando a pressão não entra na cena:

```json
{
  "permanencia_espacial": {
    "avaliacao_id": "perm-...",
    "resultado": "adiada",
    "motivo": "razão causal concreta para não materializar agora"
  }
}
```

`invalidada` usa o mesmo formato com `motivo`. A instalação é idempotente; retry divergente falha fechado. Uma janela já concluída não é sorteada outra vez.

## Estado reservado

`narrador/permanencia-espacial/estado.yaml` é um controle pequeno, não cânone narrativo. Ele guarda até 64 avaliações recentes. Ao atingir o teto, avaliações terminais antigas podem ser descartadas; avaliações ativas nunca são descartadas silenciosamente.

## Economia

- turno comum sem `--permanencia-local`: **zero leitura NV-15**;
- uma reserva nova por `local + data + período`;
- retries leem o recibo reservado e não consomem decks novamente;
- local herdado vem do estado consolidado, sem scan;
- presença usa apenas o índice opt-in já limitado;
- ecologia, microeventos, incidentes e condições continuam indexados por local;
- zero chamadas de IA na camada.

## Critérios de aceitação cobertos

- permanência no circo herda `circo_hooft` do estado consolidado e nunca emite `ids.local: null`;
- rotina, visitante, crime/incidente e condições podem ser avaliados, sem garantia de ocorrência;
- mudar `scene_id` na mesma janela reutiliza a mesma avaliação;
- candidato não narrado continua estável até resolução, adiamento ou invalidação;
- ausência de incidente é persistida como `rotina` e não confundida com falta de execução;
- turno curto sem permanência continua no hot path anterior sem leitura espacial nova.
