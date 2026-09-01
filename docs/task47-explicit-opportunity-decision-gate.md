# Task 47 — Explicit Opportunity Decision Gate

## Objetivo

Fechar a lacuna observada no primeiro rollout pós-Task46: a Task40 só pode avaliar uma oportunidade se o narrador lembrar de acordá-la, mas a ausência da flag era indistinguível de uma decisão autoral consciente de que não havia âncora causal.

A Task47 não faz a Task40 rodar mais vezes. Ela torna obrigatória uma decisão barata antes de todo `cronica preparar`.

## Contrato operacional

Todo `cronica preparar` deve declarar exatamente uma das duas opções:

- `--oportunidade-sidequest`: existe uma âncora causal concreta e a Task40 deve ser consultada;
- `--sem-oportunidade-sidequest`: a cena foi avaliada e não existe âncora causal concreta suficiente para uma nova sidequest.

As opções são mutuamente exclusivas. O comando sem nenhuma das duas é inválido.

### Caminho negativo

`--sem-oportunidade-sidequest`:

- não chama Task40 nem autoria/materialização Task41/43/44/45/46;
- sem missão aceita, não acrescenta leitura, escrita, RNG, scheduler, relógio ou scan;
- com missão aceita, permite a projeção read-only Task48 de no máximo dois fragmentos Task45;
- a conclusão dessas missões usa a decisão factual separada da Task49 e não altera a decisão sobre oportunidade nova;
- não permite nenhum `--sidequest-*` junto da decisão negativa;
- preserva exatamente o resultado-base quando não há missão aceita.

A decisão existe para impedir esquecimento do narrador, não para inserir um sistema novo no turno neutro.

### Caminho positivo

`--oportunidade-sidequest` exige, antes de qualquer leitura do turno:

- `--sidequest-origem-tipo`;
- `--sidequest-ancora-tipo`;
- `--sidequest-ancora`;
- NPC explícito ou inferível quando a origem é `conversa_npc`/`consequencia_npc`.

`--sidequest-origem-id` continua podendo cair para `--cena-id`. Depois dessa validação barata, o fluxo é exatamente o da Task46: Task40 é chamada uma vez na mesma preparação.

## API programática

`cronica.prepare()` distingue omissão de decisão de decisão negativa:

- omitir `sidequest_signal` é erro Task47 e falha antes do pending gate/hot path;
- `sidequest_signal=None` é a decisão negativa explícita sobre nova oportunidade;
- `sidequest_signal={<âncora>}` é a decisão positiva explícita.

Isso impede que uma integração interna contorne silenciosamente o contrato da CLI.

## Telemetria de rollout

`analisar-rollout.py` classifica cada `cronica preparar` em:

- `oportunidade`;
- `sem_oportunidade`;
- `ausente`;
- `conflito`.

O relatório expõe `task47_opportunity_decision_gate`. Um rollout possui `ok: true` somente quando todos os `cronica preparar` observados têm exatamente uma decisão válida. A cobertura esperada é 100%.

## Regressão que motivou a task

No rollout da Sessão 015, uma conversa com Maerra continha matéria causal suficiente para possível sidequest, mas o narrador chamou `cronica preparar` sem `--oportunidade-sidequest`, interpretou `sidequests_potenciais: []` como ausência de missão e só depois percebeu que a Task40 nunca havia sido consultada.

Após a Task47, o mesmo comando sem decisão não pode prosseguir. O narrador precisa declarar explicitamente que recusou a hipótese ou fornecer a âncora para avaliação.

## Economia congelada

- turno negativo sem missão aceita: 2 chamadas de orquestração, 0 leituras Task40–45;
- turno negativo com missão aceita: mesmas 2 chamadas e projeção Task48 de até 2 fragmentos Task45;
- turno positivo: 2 chamadas de orquestração, mesmos tetos Task40/Task46;
- 0 scheduler novo;
- 0 relógio novo;
- 0 RNG novo;
- 0 scan global novo;
- 0 estado persistente novo.

## Testes

A suíte cobre:

1. CLI sem decisão falha;
2. flags positiva/negativa são mutuamente exclusivas;
3. API programática sem decisão falha antes de qualquer leitura;
4. decisão negativa sem missão aceita retorna o mesmo objeto do hot path e não chama Task40/Task46;
5. decisão negativa com missão aceita projeta Task48 sem autorar oportunidade;
6. decisão positiva chama a integração exatamente uma vez;
7. oportunidade incompleta falha antes do pending gate;
8. decisão negativa rejeita campos `--sidequest-*`;
9. regressão Maerra: o comando antigo sem decisão é inválido e a forma positiva infere o NPC explícito;
10. analisador de rollout reprova decisões ausentes/conflitantes e exige 100% de cobertura.
