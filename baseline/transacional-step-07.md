# Etapa 7 — baseline estrutural da narração transacional

Esta baseline registra o contrato operacional implantado para reduzir `write amplification` e ciclos modelo → ferramenta → modelo durante narração.

## Problema observado antes da refatoração

No rollout usado como baseline, os 13 avanços narrativos analisados produziram em média cerca de 15,6 inferências por avanço e patches que atingiam, em média, aproximadamente 8,4 arquivos por interação. O mesmo acontecimento era frequentemente reproduzido em transcrição, estado, tempo, relações, conhecimento e registros reservados.

A baseline quantitativa original continua em `baseline/rollout-2026-08-15.json`.

## Contrato da Etapa 7

Um avanço narrativo comum possui apenas dois destinos de escrita:

1. `sessoes/NNN/transcricao.md` — prosa integral da troca;
2. `runtime/eventos-pendentes.jsonl` — ID, resumo curto, deltas e metadados necessários à consolidação.

Arquivos canônicos consolidados não são atualizados durante o turno comum.

### Meta estrutural por interação

- arquivos escritos: **2**;
- arquivos canônicos de estado/ficha/relações/conhecimento escritos: **0**;
- regenerações de `runtime/contexto.yaml`/`runtime/cena.yaml`: **0**;
- commits, `git status`, `git diff` ou suíte global de testes: **0**;
- gravação separada de rolagem oculta: **0** durante o turno; rolagens relevantes podem permanecer no registro transacional até consolidação.

A Etapa 8 será responsável por aplicar os deltas em lote aos destinos canônicos.

## Leitura do estado após o turno

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base do último checkpoint consolidado.

`ferramentas/contexto.py` aplica `runtime/eventos-pendentes.jsonl` em memória para produzir o estado efetivo. Consultas de status, cena, relação, NPC e conhecimento podem portanto enxergar mudanças recém-ocorridas sem exigir reescrita dos arquivos canônicos.

## Recuperação de interrupção

`ferramentas/turno.py registrar` usa ID estável e marcador interno na transcrição.

Reexecutar exatamente a mesma transação:

- não duplica transcrição já gravada;
- não duplica evento já gravado;
- repara caso apenas um dos dois destinos tenha sido persistido antes de interrupção;
- recusa silenciosamente sobrescrever o mesmo ID com conteúdo divergente.

`python3 ferramentas/turno.py check` valida a correspondência entre buffer e marcadores de transcrição.

## Rolagens

`ferramentas/rolar-lote.py` permite executar múltiplas rolagens independentes em uma única chamada de ferramenta, usando internamente o mesmo `rolar-dados.py`.

Não é permitido antecipar rolagens condicionais: se a necessidade da segunda depende do resultado da primeira, elas continuam em rodadas separadas.

## Testes de regressão

A suíte da Etapa 7 cobre:

- schema e validação de deltas;
- rejeição de IDs duplicados;
- projeção de PV, Ki, tempo, localização e modo de cena;
- projeção de relação e medidores de NPC;
- descoberta de conhecimento antes da consolidação;
- isolamento de rolagens/deltas reservados de consultas públicas;
- prova de que um turno comum preserva hashes de estado, tempo e ficha;
- idempotência da repetição do mesmo turno;
- recuperação dos dois cenários de interrupção entre as escritas;
- interação, exploração, combate, descanso e descoberta;
- retomada usando snapshot-base + eventos pendentes;
- consulta CLI real por `contexto.py` com sobreposição transacional;
- lote de rolagens independentes.

## Critério de sucesso em jogo

Depois da refatoração completa, a telemetria de rollout deverá verificar se a redução estrutural se converte em menos chamadas de ferramenta, menos inferências e menor tráfego de contexto por ação, sem perda de continuidade ou integridade canônica.
