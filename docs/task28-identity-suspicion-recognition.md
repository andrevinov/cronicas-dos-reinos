# Task 28 — Identity Suspicion & Recognition

## Problema

Ren já opera sob personas como **Shinta Ryoushi** e **Kage**, e o talento Actor ajuda a
estabelecer/sustentar outra identidade. Isso não pode produzir dois extremos errados:

1. NPCs tratados como incapazes de notar semelhanças ou padrões; ou
2. qualquer semelhança convertida imediatamente em conhecimento certo de que a persona é Ren.

A Task 28 introduz uma camada intermediária: **suspeita de identidade**.

## Fonte de verdade

As personas do jogador ficam em `personagens/jogador/identidades.yaml`:

- `ren` — Ren Kagehira;
- `shinta` — Shinta Ryoushi;
- `kage` — Kage.

O registro diz quais personas existem; ele **não** diz quem conhece a verdade.

O estado de cada observador continua no fragmento NPC já existente em
`estado/npcs/<id>.yaml`, sob o campo opcional `reconhecimento_identidade`. Não há
arquivo de estado paralelo por identidade nem scheduler.

Ausência do campo significa simplesmente: nenhuma suspeita/confirmacao operacional foi
registrada. A implementação não inventa suspeitas retroativas.

## Suspeita

Uma suspeita é uma aresta:

```yaml
observada: kage
possivel: ren
evidencias:
  - id: ids-...
    tipo: fisica
    fonte: sessao:...
```

A quantidade de evidências únicas determina apenas o grau operacional:

- 1 → `possibilidade`;
- 2 → `suspeita`;
- 3 → `suspeita_forte`.

O teto é intencional. **A quarta pista não transforma suspeita forte em certeza.** Se a
identidade passar a ser conhecida, deve existir um fato canônico explícito de confirmação.

Cada evidência tem ID SHA-256 determinístico sobre NPC + aresta + tipo + fonte + fato.
Repetir o mesmo fato é no-op, não mais um ponto.

## Tipos de evidência

A v1 aceita cinco classes compactas:

- `atuacao` — voz, maneirismo performado, escolha consciente de persona;
- `fisica` — rosto, corpo, cicatriz, proporções, semelhança visual não mascarada;
- `contextual` — conhecimento improvável, horários, presença, coincidências, acesso;
- `contradicao` — erro factual/comportamental que quebra a cobertura;
- `testemunho` — terceiro entrega informação que liga personas.

Todos valem uma evidência por fato. A categoria existe para determinar a interação com
Actor, não para criar pesos subjetivos.

## Actor

Actor continua exatamente com a função mecânica que já tinha: vantagem em Enganação ou
Atuação quando Ren tenta passar-se por outra pessoa.

Quando uma pista é **puramente `atuacao`** e a rolagem pertinente de Actor teve sucesso,
`identidades.py evidencia` retorna `sem_delta`. O NPC não ganha nova pista de performance.

Actor não é metamorfose, lavagem de memória nem controle de crença. Portanto sucesso em
Actor não remove suspeitas existentes e não bloqueia:

- evidência física;
- coincidência/contexto;
- contradição independente;
- testemunho de terceiro.

Uma falha de Actor pode produzir evidência `atuacao` quando a ficção realmente mostrou
algo observável. A falha mecânica sozinha não cria automaticamente o texto/fato da pista.

## Confirmação

Confirmação é outra transição:

```yaml
observada: kage
identidade: ren
fonte: sessao:...
```

Ela exige no delta:

- `motivo_identidade: confirmacao`;
- `confirmacao_canonica: true`;
- `fato_canonico` concreto;
- `fonte` rastreável.

Ao confirmar, a suspeita equivalente pode ser removida. Outras suspeitas permanecem.
Nenhuma quantidade de evidências chama confirmação automaticamente.

## Porta read-only rara

Quando uma cena realmente cria uma pista de identidade, usar:

```bash
poetry run python ferramentas/identidades.py evidencia <npc> \
  --observada kage \
  --possivel ren \
  --tipo fisica \
  --fato '<fato observável concreto>' \
  --fonte '<fonte canônica>' \
  --actor nao_aplicavel
```

A ferramenta **não escreve**. Ela devolve o delta completo para entrar na mesma transação
normal do turno. Se for repetição, teto já atingido, identidade já confirmada ou Actor
bloquear a pista performática, devolve `sem_delta`.

Confirmação explícita:

```bash
poetry run python ferramentas/identidades.py confirmar <npc> \
  --observada kage \
  --identidade ren \
  --fato '<fato que realmente confirmou a identidade>' \
  --fonte '<fonte canônica>'
```

Também é read-only.

## Transação e checkpoint

O delta usa o alvo NPC já existente:

```json
{
  "alvo": "npc:<id>",
  "op": "set",
  "caminho": "reconhecimento_identidade",
  "valor": {"schema_reconhecimento_identidade": 1, "suspeitas": [], "confirmacoes": []},
  "motivo_identidade": "evidencia",
  "fato_canonico": "...",
  "fonte": "...",
  "actor_resultado": "nao_aplicavel"
}
```

O writer valida forma/evidência antes do buffer. O checkpoint simula a transição contra o
fragmento consolidado e recusa:

- salto de mais de uma evidência por fato;
- remoção de suspeita via evidência;
- alteração de duas arestas no mesmo fato;
- ID de evidência que não corresponde a fato/fonte;
- pista `atuacao` após Actor bem-sucedido;
- confirmação implícita ou sem prova.

O fragmento staged é revalidado antes da instalação.

## Contexto e custo

`contexto npc <nome>` já lê o fragmento NPC e o overlay transacional. Assim um delta de
suspeita fica visível ao narrador **antes do checkpoint sem nova fonte**. NPC sem suspeita
não ganha campo extra nem leitura adicional.

Contrato: `baseline/identity-suspicion-recognition-orcamento.yaml`.

O caminho comum permanece com zero chamadas novas. `identidades.py` só é usado quando a
ficção realmente criou uma pista/confirmacao de identidade.
