# Task 48 — Stable Task40 Snapshot & Effective Clock

## Problema observado

O primeiro rollout pós-Task46 mostrou dois falsos positivos de revalidação:

1. Task40 podia planejar usando `estado/tempo.yaml` consolidado enquanto o turno já possuía um `tempo/instante` pendente mais recente;
2. Task46 calculava o digest do pacote Task40 inteiro, incluindo `fontes_lidas`, `metricas` e `orcamento_pacote`. Assim duas leituras semanticamente iguais podiam produzir hashes diferentes apenas porque uma reconstrução recebeu `now` explícito e a outra precisou ler o relógio.

## Contrato

### Relógio efetivo

No caminho Task46/48:

- `--data/--hora` explícitos continuam tendo precedência;
- se não houver instante explícito e existir avanço temporal pendente, o adapter lê o último instante transacional e o fornece explicitamente à Task40;
- se não houver avanço temporal pendente, continua passando `now=None`, preservando o fail-fast original da Task40: orçamento cheio pode encerrar antes de abrir `estado/tempo.yaml`;
- o ticket registra a origem do instante como `explicita`, `canonico` ou `overlay_transacional`;
- na conclusão, relógios derivados (`canonico`/`overlay_transacional`) são comparados contra o relógio efetivo corrente. Mudança temporal real torna o ticket obsoleto; relógio explicitamente fornecido permanece congelado pelo ticket.

Não existe scheduler, relógio paralelo ou checkpoint obrigatório novo.

### Digest semântico

Tickets Task48 continuam usando o campo `pacote_digest`, mas seu valor passa a ser SHA-256 de uma projeção explícita contendo apenas matéria autoral:

- origem causal;
- relação efetiva;
- orçamento/estado das quests;
- instante, local e condições persistentes;
- intenções canônicas compatíveis;
- atores causalmente disponíveis;
- Juppongatana possíveis;
- envelope de recompensa;
- autoridade do pacote.

Ficam deliberadamente fora do digest:

- `fontes_lidas`;
- `metricas`;
- `orcamento_pacote`;
- contagem `horizonte_intencoes_canonicas.avaliadas` e texto explicativo da regra.

Esses campos continuam disponíveis para observabilidade e orçamento, mas não representam mudança do mundo.

## Compatibilidade

Ticket Task46 emitido antes da Task48 não possui `agora_fonte`. Ele continua sendo revalidado pelo digest bruto legado e pelo instante já congelado, evitando quebrar uma conclusão transitória preparada antes da atualização.

## Regressões obrigatórias

Os testes congelam:

1. `fontes_lidas`, métricas e metadados de orçamento podem mudar sem mudar o digest semântico;
2. relação, quest ativa, condição persistente, intenção canônica, ator, Juppongatana ou envelope de recompensa alterados mudam o digest;
3. `19:38` consolidado + `20:00` pendente faz Task40 receber `20:00` sem checkpoint intermediário;
4. instante explícito prevalece sobre overlay;
5. sem instante pendente, o adapter não lê antecipadamente o relógio canônico;
6. relógio efetivo mudando de verdade entre preparar/concluir invalida o ticket;
7. ticket Task46 legado continua concluível pelo contrato antigo.

## Orçamento

O turno neutro da Task47 permanece idêntico: zero Task40–45. Task48 só existe depois da decisão positiva. Não adiciona chamada de orquestração, escrita, RNG, scheduler, scan global ou estado persistente.
