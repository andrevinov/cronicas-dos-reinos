# Consolidação transacional de cena e sessão

Este documento define **quando e como transformar `runtime/eventos-pendentes.jsonl` em cânone**. Não deve ser lido durante um turno comum. Consultá-lo em fechamento de cena importante, encerramento de sessão, recuperação de falha ou manutenção da arquitetura transacional.

## Princípio

Durante o jogo, `turno.py` registra cada avanço em transcrição + deltas. Enquanto esses deltas permanecem pendentes, `contexto.py` projeta-os sobre o último snapshot consolidado.

A consolidação existe para fazer o movimento inverso em lote:

```text
estado canônico anterior
+ eventos pendentes
        ↓
pré-cálculo completo em memória
        ↓
staging + journal
        ↓
instalação verificada
        ↓
novo cânone + novo runtime
        ↓
buffer pendente esvaziado
```

Ela **não relê toda a campanha para reinterpretar o que aconteceu**. Os fatos a aplicar vêm dos deltas explícitos já registrados.

## Quando consolidar

Não consolidar depois de cada ação do jogador. Isso recriaria a write amplification que a Etapa 7 removeu.

Usar `cena` quando existir uma fronteira natural e um checkpoint canônico for útil, por exemplo:

- fim de combate ou perseguição relevante;
- saída de uma dungeon/local de risco;
- passagem para outro dia ou descanso que feche um bloco importante;
- grande descoberta seguida de mudança clara de foco;
- buffer grande o bastante para que um checkpoint reduza risco operacional.

Usar `sessao` antes de considerar a sessão encerrada.

```bash
python3 ferramentas/consolidar.py cena
python3 ferramentas/consolidar.py sessao
```

`cena` e `sessao` aplicam os mesmos deltas canônicos. `sessao` também marca os artefatos automáticos da sessão como encerrados. Ele **não** incrementa o número da sessão, não cria a próxima sessão e não inventa eventos ausentes.

## Domínios suportados

### Estado, tempo e ficha

Deltas `estado`, `tempo` e `ficha` são aplicados em memória. Campos que representam o mesmo fato são espelhados automaticamente quando necessário:

- data, hora, período, clima e prazo entre estado e tempo;
- nível, PV, Ki, CA e dinheiro entre estado e ficha.

Se dois deltas do mesmo lote tentarem impor valores incompatíveis às duas representações, a consolidação falha antes de escrever.

### Relações e NPCs

`relacao:<id>` atualiza apenas `estado/relacoes/<id>.yaml`; `npc:<id>` atualiza apenas `estado/npcs/<id>.yaml`.

O consolidador também:

- atualiza o índice correspondente;
- registra o evento pós-migração no histórico específico da entidade;
- pode criar uma nova relação/NPC quando o ID ainda não existir;
- mantém os antigos blobs legados intactos para auditoria.

Não usar `registrar` nesses alvos: o estado atual deve ser expresso por `set`, `inc`, `append` ou `remove`; a cronologia é produzida automaticamente a partir da transação que causou a mudança.

### Conhecimento

`conhecimento` aceita `registrar`. Cada transação cria, de forma determinística, um fragmento incremental sob:

```text
personagens/jogador/conhecimento/incrementais/sessao-NNN/
```

O índice global e `conhecimento/ativo.yaml` são atualizados sem alterar os 90 fragmentos legados cuja reconstrução byte a byte é protegida pela Etapa 6.

Só registrar conhecimento que Ren realmente adquiriu. Um acontecimento do mundo não vira automaticamente conhecimento do personagem.

### Consequências e progressão

`consequencia` aceita `registrar` e alimenta o artefato de consequências da sessão.

`progressao` pode registrar marcos/recompensas explícitos. Registrar um marco não autoriza o consolidar a escolher opções de nível ou progressão pelo jogador. Mudança mecânica efetiva de nível/recursos deve estar representada por delta apropriado de estado/ficha.

### Segredos, rolagens ocultas e relógios

Rolagens ocultas armazenadas na transação são consolidadas em `narrador/sessoes/NNN/rolagens-ocultas.md` em lote.

Relógios reservados usam `relogio:<id>` e ficam sob `narrador/relogios/`.

Um delta com `visibilidade: narrador` **não pode ser instalado em domínio público** como estado, ficha, conhecimento, relação ou consequência. Se isso ocorrer, a consolidação falha antes de escrever.

## Artefatos da sessão

Cada lote consolidado entra em:

```text
sessoes/NNN/consolidacoes.jsonl
```

Esse ledger guarda IDs de batch e IDs das transações já incorporadas. É a barreira contra reaplicação.

O consolidar também mantém seções automáticas em:

- `resumo.md`;
- `consequencias.md`;
- `alteracoes-de-estado.yaml` ou, quando já existir um formato manual incompatível, `alteracoes-transacionais.yaml`;
- `experiencia.md`, somente quando há progressão explícita.

Texto manual fora dos marcadores automáticos é preservado. O resumo automático usa apenas os resumos curtos já registrados nas transações; não inventa causalidade, intenção ou fato ausente.

## Segurança multiarquivo

Git e filesystem não oferecem uma transação atômica única para dezenas de arquivos. Por isso a consolidação usa duas estruturas transitórias ignoradas pelo Git:

```text
runtime/consolidacao-em-andamento.json
runtime/.consolidacao-stage/
```

Primeiro todos os bytes finais são calculados e validados. Depois são gravados no staging e seus hashes entram no journal. Só então começa a instalação.

`runtime/eventos-pendentes.jsonl` é instalado **por último**. Portanto os deltas não desaparecem antes que o restante do novo cânone esteja preparado.

Enquanto o journal existir, `transacoes.load_pending()` recusa operação normal. Isso bloqueia `contexto.py` e `turno.py`, impedindo que a campanha continue sobre um estado parcialmente instalado.

## Recuperação depois de queda

Se o processo for interrompido:

```bash
python3 ferramentas/consolidar.py recuperar
```

A recuperação usa os bytes já staged. Ela não recalcula o lote e não reaplica `inc` sobre arquivos parcialmente atualizados.

Para cada destino, o hash atual precisa ser:

- o hash anterior ao lote; ou
- o hash final já instalado.

Qualquer terceiro hash indica edição externa concorrente; nesse caso a recuperação recusa sobrescrever silenciosamente o arquivo.

Depois de instalar tudo, a ferramenta confere os hashes finais, remove journal/staging e só então libera a narração normal.

## Idempotência

Há três camadas de proteção:

1. `turno.py` impede duplicação da mesma transação no buffer/transcrição;
2. `consolidacoes.jsonl` registra quais IDs já entraram no cânone;
3. o batch ID é derivado deterministicamente da sessão, tipo e IDs das transações.

Reexecutar `consolidar.py cena` sem pendências não altera o cânone. Se uma transação já consolidada reaparecer no buffer por recuperação manual, ela é removida como stale sem reaplicar o delta.

## Runtime depois da consolidação

O novo runtime é calculado **antes das escritas**, a partir dos documentos canônicos já transformados em memória. Ele faz parte do mesmo staging.

Assim, depois de consolidação bem-sucedida:

- `runtime/contexto.yaml` e `runtime/cena.yaml` já representam o novo checkpoint;
- `eventos-pendentes.jsonl` não contém as transações aplicadas;
- não é necessário executar `gerar-runtime.py` novamente por rotina.

## Verificação

Metadados rápidos:

```bash
python3 ferramentas/consolidar.py status
```

Integridade:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/gerar-runtime.py --check
```

`consolidar.py check` detecta journal interrompido, IDs duplicados, uma transação simultaneamente pendente e consolidada e índices incrementais de conhecimento quebrados.

A suíte completa de CI continua sendo usada em manutenção e PRs, não durante cada ação do jogador.
