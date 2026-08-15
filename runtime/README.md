# Runtime — estado quente e sobreposição transacional

`runtime/` contém o contexto operacional mais provável de ser necessário na próxima interação narrativa.

`contexto.yaml` e `cena.yaml` são projeções-base do último checkpoint consolidado. Durante sessão ativa, `eventos-pendentes.jsonl` contém deltas posteriores a esse checkpoint. `ferramentas/contexto.py` projeta base + deltas em memória e entrega o estado efetivo.

Nenhum desses arquivos é fonte canônica independente.

## Arquivos normais

- `contexto.yaml`: snapshot-base pequeno de sessão, personagem, recursos, tempo e localização;
- `cena.yaml`: snapshot-base da situação imediata;
- `eventos-pendentes.jsonl`: buffer transacional, uma linha por avanço ainda não consolidado;
- `consultas-contexto.jsonl`: telemetria local opcional ignorada pelo Git.

## Escrita durante narração

Um avanço comum escreve somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

Use `ferramentas/turno.py registrar` para essas duas persistências. A prosa completa fica apenas na transcrição; o buffer guarda ID, sessão, resumo, deltas e rolagens ocultas necessárias.

## Estado efetivo antes do checkpoint

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py relacao kethra
python3 ferramentas/contexto.py npc nera
python3 ferramentas/contexto.py conhecimento "ponte baixa"
```

As consultas aplicam deltas pendentes sem regravar os YAMLs-base.

## Consolidação

Checkpoint de cena:

```bash
python3 ferramentas/consolidar.py cena
```

Fechamento de sessão:

```bash
python3 ferramentas/consolidar.py sessao
```

O consolidador calcula os documentos finais em memória, cria staging e journal de hashes, instala os arquivos afetados e coloca `eventos-pendentes.jsonl` por último. O novo `contexto.yaml` e `cena.yaml` são preparados no mesmo lote.

Depois de consolidação bem-sucedida não é necessário executar `gerar-runtime.py` novamente por rotina.

O ledger `sessoes/NNN/consolidacoes.jsonl` registra os IDs já aplicados e impede reaplicação.

## Recuperação de consolidação interrompida

Durante a instalação podem existir, temporariamente:

```text
runtime/consolidacao-em-andamento.json
runtime/.consolidacao-stage/
```

Esses caminhos são ignorados pelo Git. Enquanto o journal existir, `contexto.py` e `turno.py` recusam operação normal para impedir uso de um checkpoint parcialmente instalado.

Recupere com:

```bash
python3 ferramentas/consolidar.py recuperar
```

A recuperação instala os bytes já staged; não recalcula os deltas. Para cada arquivo, aceita somente o hash anterior ou o hash final esperado. Um terceiro hash interrompe a recuperação em vez de sobrescrever edição concorrente.

## Deltas suportados

Operações: `set`, `inc`, `append`, `remove`, `registrar`.

Domínios consolidados:

- `estado`;
- `tempo`;
- `ficha`;
- `progressao`;
- `relacao:<id>`;
- `npc:<id>`;
- `conhecimento`;
- `consequencia`;
- `relogio:<id>`.

Conteúdo com `visibilidade: narrador` não pode ser instalado em domínio público.

## Verificação

```bash
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py status
python3 ferramentas/consolidar.py check
python3 ferramentas/gerar-runtime.py --check
```

`gerar-runtime.py` continua útil depois de uma alteração canônica manual. O consolidador já gera o runtime do checkpoint que instala.

## Limites

`contexto.yaml` e `cena.yaml` permanecem abaixo de 8 KiB. `eventos-pendentes.jsonl` tem limite operacional de 512 KiB; alcançar esse limite exige checkpoint antes de novos turnos.

Runtime não é diário histórico: transcrição guarda a prosa; o ledger guarda batches; arquivos canônicos guardam o estado corrente.
