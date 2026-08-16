# Runtime — estado quente e sobreposição transacional

`runtime/` contém o contexto operacional mais provável de ser necessário na próxima interação narrativa.

`contexto.yaml` e `cena.yaml` são projeções-base do último checkpoint consolidado. Durante sessão ativa, `eventos-pendentes.jsonl` contém deltas posteriores. `ferramentas/contexto.py` projeta base + deltas em memória e entrega o estado efetivo.

Nenhum arquivo de runtime é fonte canônica independente.

## Runtime v2

Desde a Etapa 9, os ponteiros quentes mudaram de prioridade. A transcrição continua conhecida, mas aparece explicitamente como `transcricao_fria`. Para retomada normal, usar:

```bash
python3 ferramentas/contexto.py retomada
```

O runtime aponta para:

- `sessoes/index.yaml`: índice compacto de sessões;
- `sessoes/NNN/handoff.yaml`: checkpoint compacto da sessão atual;
- `ferramentas/contexto.py retomada`: porta de reentrada;
- `sessoes/NNN/transcricao.md`: apenas como arquivo frio de último recurso para leitura.

## Arquivos normais

- `contexto.yaml`: snapshot-base pequeno de sessão, personagem, recursos, tempo e localização;
- `cena.yaml`: snapshot-base da situação imediata;
- `eventos-pendentes.jsonl`: buffer transacional, uma linha por avanço ainda não consolidado;
- `consultas-contexto.jsonl`: telemetria local opcional ignorada pelo Git.

## Escrita durante narração

Um avanço comum escreve somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

Use `ferramentas/turno.py registrar`. A prosa completa fica na transcrição; o buffer guarda ID, sessão, resumo, deltas e rolagens ocultas necessárias.

**Append-only para escrita não significa quente para leitura.** Não reler a transcrição para simplesmente retomar a cena.

## Estado efetivo e retomada

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py relacao kethra
python3 ferramentas/contexto.py npc nera
python3 ferramentas/contexto.py conhecimento "ponte baixa"
```

As consultas aplicam deltas pendentes sem regravar os YAMLs-base. `retomada` acrescenta o handoff consolidado e resumos das pendências recentes sem abrir transcrição.

## Checkpoint

Checkpoint de cena:

```bash
python3 ferramentas/checkpoint.py cena
```

Fechamento de sessão:

```bash
python3 ferramentas/checkpoint.py sessao
```

Na primeira fase, `consolidar.py` calcula documentos canônicos finais, cria staging/journal de hashes, instala os arquivos afetados e coloca `eventos-pendentes.jsonl` por último. O novo runtime é parte dessa transação.

Na segunda fase, `checkpoint.py` deriva handoff/índice da situação já instalada. Esses dois arquivos são cache reconstruível e não participam da autoridade canônica.

## Recuperação

Durante instalação canônica podem existir:

```text
runtime/consolidacao-em-andamento.json
runtime/.consolidacao-stage/
```

Enquanto o journal existir, `contexto.py` e `turno.py` recusam operação normal.

Recuperar com:

```bash
python3 ferramentas/checkpoint.py recuperar
```

A recuperação instala os bytes já staged sem recalcular deltas e depois atualiza a memória compacta. Se não houver journal e somente o handoff/índice precisar de reparo, o mesmo fluxo os reconstrói sem mudar fatos da campanha.

## Histórico e transcrição

Busca histórica estruturada:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico
```

Transcrição só mediante escalada explícita:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico --transcricoes
```

Isso permite que transcrições cresçam como registro integral sem crescer automaticamente dentro do prompt.

## Deltas suportados

Operações: `set`, `inc`, `append`, `remove`, `registrar`.

Domínios: `estado`, `tempo`, `ficha`, `progressao`, `relacao:<id>`, `npc:<id>`, `conhecimento`, `consequencia`, `relogio:<id>`.

Conteúdo com `visibilidade: narrador` não pode ser instalado em domínio público.

## Verificação

```bash
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/sessoes.py check
python3 ferramentas/checkpoint.py check
python3 ferramentas/gerar-runtime.py --check
```

`gerar-runtime.py` continua útil depois de alteração canônica manual. O checkpoint normal já deixa runtime e memória compacta coerentes.

## Limites

- `contexto.yaml` e `cena.yaml`: abaixo de 8 KiB;
- `sessoes/NNN/handoff.yaml`: abaixo de 8 KiB;
- `eventos-pendentes.jsonl`: limite operacional de 512 KiB;
- transcrição: sem teto histórico artificial, mas fora do caminho quente de leitura.

Runtime não é diário histórico: transcrição guarda prosa, ledger guarda batches, arquivos canônicos guardam estado corrente e handoff guarda apenas o ponto compacto de retomada.
