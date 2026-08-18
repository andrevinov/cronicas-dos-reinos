# Recompensas por local

Camada reservada e reativa para itens, tesouros e prêmios físicos do mundo. Ela
fica **ao redor** do Mundo Vivo: não possui scheduler, não roda no amanhecer e não
entra no checkpoint por conta própria.

## Regra central

```text
Ren entra/explora um local
        ↓
consulta narrador/recompensas/index.yaml
        ↓
mapa já existe?
  sim → reutiliza exatamente o mesmo mapa
  não → gera uma única vez com SHA-256
```

A chave procedural usa:

```text
semente da campanha de recompensas + local_id + tier + periculosidade
```

Depois que o mapa existe, `garantir` ignora novos valores de tier/periculosidade e
**não rerrola**. A geração nova é feita apenas por Python/tabelas; não exige
inferência narrativa.

## Estrutura

- `index.yaml`: índice compacto por local; é a primeira e normalmente única leitura.
- `mapas/<local>.yaml`: mapa operacional do local, com estado, condição de descoberta,
  posse, importância e origem.
- `itens-index.yaml`: índice dirigido de recompensa → mapa + fragmento.
- `itens/<id>.yaml`: detalhe reservado do item; só deve abrir quando a condição
  realmente se tornar relevante.
- `tabelas.yaml`: catálogo procedural; só entra na criação inédita de um mapa.
- `planejadas.yaml`: recompensas autorais/canônicas/quest já conhecidas antes da
  primeira geração daquela área; também só entra na criação inédita.

Consulta normal:

```bash
python3 ferramentas/recompensas.py consultar sarbreen_setor_a
```

Criação inédita:

```bash
python3 ferramentas/recompensas.py garantir sarbreen_setor_a \
  --tier 2 --periculosidade alta
```

Detalhe dirigido:

```bash
python3 ferramentas/recompensas.py mostrar sarbreen_setor_a-r01
```

Manutenção/CI:

```bash
python3 ferramentas/recompensas.py status
python3 ferramentas/recompensas.py check
```

## Descoberta não é existência

Um item em `mapas/<local>.yaml` **existe reservadamente no local**, mas isso não
significa que Ren o encontrou. A consulta compacta expõe apenas metadados
operacionais: ID, tipo, estado, condição, posse, importância e origem. Nome,
descrição e valor ficam no fragmento dirigido.

Estados previstos:

```text
oculto → descoberto → obtido
                 ↘ indisponivel
```

A ligação dessas mudanças ao registro transacional da narração pertence à etapa
final de integração. Esta camada, isoladamente, não altera inventário, dinheiro ou
cânone público.

## Recompensa procedural x planejada

O gerador procedural pode produzir dinheiro, gemas, consumíveis, ferramentas,
pergaminhos, itens mágicos menores e curiosidades compatíveis com o tier. Ele
**nunca** produz `importancia: arco`.

Recompensa de arco precisa ser explícita e possuir uma origem não procedural:

```text
quest | direcao_canonica | autoral
```

`planejadas.yaml` permite que o mapa criado pela primeira vez misture recompensas
procedurais e planejadas sem confundir a proveniência.

A posse procedural aceita `ambiente` ou um `papel_local` (`guardiao`/`ocupante`).
O gerador não escolhe silenciosamente um NPC canônico para possuir um item. Uma
recompensa planejada pode usar `posse.tipo: npc` com ID explícito.

## Orçamento

- zero scan de locais na consulta normal;
- local ausente: 1 leitura (`index.yaml`);
- local já mapeado: 2 leituras (`index.yaml` + mapa local);
- detalhe: índice dirigido + mapa local + um fragmento;
- tabelas e planejadas só são lidas na primeira geração;
- no máximo 4 recompensas procedurais por mapa e 8 totais;
- nenhuma geração repetida e nenhum scheduler novo.

A etapa de integração ligará esta porta à entrada/exploração de locais. Até lá, a
ferramenta pode ser chamada explicitamente sem alterar o hot path da narração.
