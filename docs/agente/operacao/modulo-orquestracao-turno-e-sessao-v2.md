# Módulo de orquestração de turno e sessão v2

`turn_and_session_orchestration` é o control plane do avanço narrativo e do
lifecycle de sessão. A fachada pública é
`ferramentas/turn_and_session_orchestration.py`; os motores, writers, journals e
fontes continuam nos seus donos históricos.

## Escopo

O módulo reúne três subcapacidades:

- `transactional_turn`: correlaciona `cronica preparar` e `cronica concluir`;
- `idempotent_commit`: torna replay e reparo observáveis sem duplicar efeitos;
- `session_lifecycle`: observa status, checkpoint, recovery, encerramento e
  abertura de sessão.

Ele não decide ficção, regra, sidequest, comportamento de NPC ou consequência
do mundo. Também não cria cache persistente, writer, scheduler, RNG ou terceira
chamada de ferramenta.

## Máquina de estados do turno

```text
preparar ──► preparado ──► narração [──► resolução mecânica] ──► concluir
    │                                                            │
    ├──► bloqueado_pendencias ──► resolver fronteira ──► preparar │
    └──► bloqueado_recuperacao ──► sessao recuperar ──► preparar │
                                                                 ▼
                                                             concluído
```

O fluxo primário continua tendo exatamente duas chamadas de orquestração. Uma
rolagem material entre elas pertence ao módulo mecânico e não altera a
correlação. `confirmar` e `registrar` são portas de reparo, não etapas rituais do
turno comum.

Um journal de consolidação aberto produz
`fase: bloqueada_recuperacao_sessao`, sem ticket e sem escrita. A recuperação é
explícita por `poetry run cronica sessao recuperar`; somente depois dela um novo
preparo pode autorizar narração.

## Recibo de turno

As respostas públicas de turno incluem `orquestracao` com:

- `schema_turn_and_session_orchestration: 1` e identidade do módulo;
- operação e estado;
- correlação por cena, preparação, ticket, transação e sessão, quando cada ID já
  existe;
- posição no fluxo primário e total esperado de duas chamadas;
- resultado exactly-once do commit;
- classificação de custo como `controle`, separada dos domínios carregados.

O recibo nunca contém o token completo do ticket. `commit_exatamente_uma_vez`
indica efeito novo; `replay_sem_duplicacao` indica retry desnecessário que não
reaplicou efeito; `reparo_recuperado_sem_duplicacao` indica que uma assimetria
anterior foi reparada. Falha parcial usa `commit_incompleto` e aponta para
reparo explícito.

## Lifecycle de sessão

`cronica sessao status|checkpoint|encerrar|iniciar|recuperar` recebe recibo da
mesma fachada. Checkpoint, encerramento e recovery preservam a ordem:

```text
cânone → lifecycle → mundo → memória
```

Checkpoint não integra o turno comum e não deve ser chamado depois de cada ação.
Abertura continua exigindo encerramento válido de N e cria somente N+1; recovery
continua reutilizando o journal/staging já existente.

## Telemetria pós-hoc

O analisador de rollouts mede por sessão e por turno:

- pares exatos e pares com ticket correlacionado;
- chamadas por classe (`turno_primario`, `turno_reparo`, `lifecycle_sessao`);
- bloqueios por pendência ou recovery;
- retries válidos, desnecessários e recuperados;
- tickets obsoletos/incompatíveis e commits duplicados/incompletos;
- duração observável por fase;
- operações e sucesso do lifecycle;
- custo atribuído à classe `controle`, separado da soma dos módulos de domínio.

A medição permanece exclusivamente pós-hoc. Nenhuma análise de rollout é
executada durante o jogo.

## Verificação

O gate público read-only é:

```bash
poetry run python ferramentas/turn_and_session_orchestration.py check
```

Ele agrega os checks dos componentes preservando a autoria de cada diagnóstico.
Os perfis de aceitação da implementação são:

```bash
poetry run test-domain cronica sessoes
```

