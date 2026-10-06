# Structured Deterministic Endpoints

Esta camada projeta decisões que Python já calcula. Ela não substitui as
ferramentas existentes nem duplica a CLI unificada.

A porta é:

```bash
python3 ferramentas/endpoints.py <subcomando> ...
```

Todos os endpoints são **somente leitura**. Cada um chama no máximo uma função determinística subjacente e reorganiza a resposta sem abrir novas fontes.

## Contrato comum

Toda resposta usa `schema_endpoint_deterministico: 1` e contém exatamente as categorias operacionais comuns:

- `ids`: identidades estáveis necessárias para continuar;
- `filtros`: regras determinísticas que já limitaram o espaço de candidatos;
- `disponibilidade`: o que está mecanicamente disponível naquele estado;
- `gates`: resultados de travas/gates já calculados;
- `modificadores`: modificadores estruturados; começa vazio quando a regra atual não possui nenhum;
- `deltas_previstos`: mudanças estruturadas que o narrador deve registrar em fase posterior, sem aplicá-las aqui;
- `proximo_passo`: próximo passo de protocolo, nunca uma escolha narrativa;
- `fontes_lidas`: somente as fontes que a função subjacente já havia lido.

O endpoint inteiro tem teto de 6 KiB. A projeção não pode criar nova leitura, escrita, scheduler ou fragmento adicional.

## Cena

```bash
python3 ferramentas/endpoints.py cena \
  --cena-id <id> \
  --npc <nome-ou-id> \
  --contexto-tag local:<id>
```

Aceita também o quarteto local `--local`, `--acao`, `--tier`, `--periculosidade` e, quando necessário, `--data` + `--hora`.

A função subjacente continua sendo `cena_mundo.prepare_scene`. O endpoint não confirma nada. Ele devolve IDs canônicos, duplicatas já filtradas indiretamente pelo resultado, candidatos contextuais por classe, gates de encontro/sidequest e o `preparacao_id` necessário para a confirmação posterior.

`sidequest_potencial` continua sendo potencial, nunca oferta automática.

## Fronteira temporal

```bash
python3 ferramentas/endpoints.py fronteira \
  --data-alvo "15 Eleasis, 1372 DR" \
  --hora-alvo "07:00"
```

Usa a mesma consulta de `fronteira_mundo.py`. Se existir fronteira, `proximo_passo` manda resolver apenas até ela e checkpointar antes de continuar. Se não existir, informa que o intervalo inteiro pode ser comprimido. Nenhuma camada é processada pela consulta.

Os argumentos são **o fim pretendido**, nunca a hora atual. `--data` e `--hora`
continuam aliases de compatibilidade com o mesmo significado. O início vem de
`estado/tempo.yaml` com overlay dos deltas pendentes da sessão atual; não é digitado
pelo narrador nem substituído pelo cursor de processamento do mundo.

Conferir `disponibilidade.inicio`, `alvo` e `janela_consultada`: ela informa
`duracao_minutos`, `cobertura` e `limite_narravel`. Exemplo: início 11:35, alvo
12:14, causa às 11:50 → janela pretendida de 39 minutos, narração permitida até
11:50. Duração zero é `instante_sem_compressao`: não comprova a espera de 39 minutos
e não devolve autorização para comprimir tempo. Informar o alvo final verdadeiro.

Registrar só o instante alcançado pelo writer de `cronica concluir`. Ao interromper,
checkpoint e resolução causal existentes precedem a continuação: consultar novamente
o alvo restante a partir do novo tempo efetivo e usar novo `cronica preparar`.
Permanência usa `--permanencia-local` em cada janela; não saltar o limite nem remover
o gatilho espacial. Retry repete o concluir anterior, sem novo avanço ou resolução.
Se o alvo/intenção mudar, a consulta antiga não cobre a nova janela.

Fala/ação curta continua sem consulta adicional de fronteira. A saída é um contrato
operacional; não é um ticket que imponha sozinho o limite ao writer ou detecte uma
compressão omitida pelo narrador. A revisão semântica verifica essa correspondência.

## Pendências do Mundo Vivo

```bash
python3 ferramentas/endpoints.py pendencias
```

Projeta a fila já existente de `mundo.pending_view`. A saída informa a barreira em `gates`, agrupa IDs por tipo e diz apenas se o próximo turno pode continuar ou se as pendências precisam ser resolvidas primeiro.

## Direção canônica

```bash
python3 ferramentas/endpoints.py direcao ponte_de_kozakura
```

Usa `direcoes_destino.project`. Quando permitido, o gate contém critério e guardrails do marco corrente. O próximo passo é somente `avaliar_fato_canonico_para_marco`; o endpoint nunca escolhe executor, alvo, método, ação, cena ou momento.

## Efeitos de sidequest

```bash
python3 ferramentas/endpoints.py sidequest <id> <<'YAML'
- tipo: pressao
  relogio: exemplo
YAML
```

Usa `interacoes_mundo.prepare_sidequest_effects`. `deltas_previstos` separa explicitamente:

- `fase: turno`: deltas que entram no mesmo `cronica concluir`;
- `fase: pos_canonico`: rastro/recompensa que só podem ser materializados depois que o fato-base estiver canônico.

Agente novo continua exigindo classificação NPC v2 antes de ganhar agência.

## Compatibilidade e custo

As CLIs anteriores continuam válidas para manutenção, testes e inspeção detalhada. No hot path, preferir `endpoints.py` quando a pergunta for uma dessas cinco decisões determinísticas, pois ele evita uma segunda etapa de interpretação de payloads heterogêneos.

O contrato de regressão está em
`baseline/endpoints-deterministicos-orcamento.yaml`. Redução real de
inferências/tool calls deve ser medida **pós-hoc em rollout**; este manual não
inventa um percentual sem medição.
