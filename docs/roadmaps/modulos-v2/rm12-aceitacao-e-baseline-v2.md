# RM-12 — Aceitação integrada e baseline v2

## Status e dependências

**Proposta.** Último item do roadmap; depende da RM-11 e de todos os módulos v2.

## Objetivo

Provar que a nova arquitetura preserva os contratos do jogo, não encarece o
turno neutro e consegue produzir o primeiro pacote real da série `modules-v2`.

## Etapas de aceite

### 1. Regressão estrutural

- executar testes por domínio e rastrear cada teste consolidado ao seu novo dono;
- executar auditorias de estado vivo e histórico;
- validar catálogo, aliases, guardrails e soma de custos;
- confirmar que Sete Nomes continua regressão e Torneio continua extensão;
- provar que nenhuma fachada v2 criou writer, scheduler, RNG ou scan paralelo.

### 2. Episódios controlados

Em `TemporaryDirectory`, cobrir ao menos:

- turno curto neutro;
- cena social com memória e relação;
- regra e rolagem com recurso persistente;
- oportunidade negativa e autoria positiva de sidequest;
- progresso e terminal exactly-once;
- permanência e compressão temporal;
- evento canônico devido;
- duas operações adversariais simultâneas;
- retry e recovery em pontos de commit.

### 3. Rollout técnico pós-hoc

Executar um rollout controlado fora de sessão para verificar correlação,
compatibilidade e orçamento. Ele não inaugura a série de experiência do jogador.

### 4. Primeira sessão real v2

Somente depois dos gates verdes, jogar uma sessão normal no sistema refatorado,
encerrá-la pelo lifecycle e gerar seu pacote pós-hoc. Esse pacote recebe:

- `serie_avaliacao: modules-v2`;
- status provisório;
- feedback do jogador;
- adjudicação de validade;
- notas e custos dos doze módulos;
- baseline operacional observada v2.

## Comparabilidade

O primeiro rollout real v2 é o ponto inicial da nova curva. Sessão 021 não entra
no cálculo de delta, média móvel ou tendência v2. Pode aparecer ao lado como
referência legada, com aviso explícito de incompatibilidade.

Uma sessão permite avaliação provisória. A leitura longitudinal começa no
segundo ponto e só recebe status estável após pelo menos três sessões comparáveis
e amostra mínima por módulo.

## Gates finais

Executar, nesta ordem:

```text
poetry run test-fast
poetry run test-domain mecanica cronica sessoes sidequests mundo runtime
poetry run test-full
poetry run preflight
poetry run python ferramentas/gerar-avaliacao-sessao.py <rollout> --sessao-id <id>
```

A medição continua pós-hoc e nunca roda durante o jogo.

## Definition of done

- todos os gates ficam verdes;
- turno neutro preserva duas chamadas de orquestração;
- nenhum guardrail crítico é violado;
- primeiro pacote `modules-v2` é produzido e revisado;
- dashboard inicia uma nova série sem comparar notas incompatíveis;
- baseline registra valores observados, não economia estimada;
- limitações da primeira sessão permanecem explícitas.
