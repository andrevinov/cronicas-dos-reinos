# RM-08 — Orquestração de turno e sessão

## Status e dependências

**Implementada.** Depende das RM-01–RM-02.

## Problema

O par `cronica preparar/concluir`, tickets, retries, checkpoints e recovery são o
controle transacional do jogo, mas não possuem um módulo responsável. Falhas
aparecem diluídas em confiabilidade global ou atribuídas aos módulos narrativos
que estavam presentes no mesmo turno.

## Objetivo

Criar `turn_and_session_orchestration` como control plane explícito do turno e da
sessão, sem acrescentar chamada ao hot path.

## Implementação

- definir máquina de estados observável para preparar, bloqueio, narração,
  resolução mecânica, concluir, checkpoint, encerramento e recovery;
- emitir recibos versionados no output das chamadas já existentes;
- correlacionar ticket, cena, retry e commit exactly-once;
- identificar preparo obsoleto antes de qualquer efeito;
- atribuir separadamente custo de controle e custo dos domínios carregados;
- integrar lifecycle de sessão sem tornar checkpoint uma etapa de todo turno;
- manter telemetria e avaliação exclusivamente pós-hoc.

## Indicadores

- proporção de turnos com um preparar e um concluir;
- chamadas de orquestração por turno e por classe;
- retries válidos, desnecessários e recuperados;
- tickets obsoletos ou incompatíveis;
- commits duplicados ou incompletos;
- duração por fase;
- checkpoints e recoveries bem-sucedidos;
- sessão iniciada e encerrada no lifecycle correto.

## Testes

- turno neutro usa exatamente duas chamadas de orquestração;
- rolagem material pode ocorrer entre elas sem quebrar correlação;
- bloqueio de pendência impede narração e conclusão;
- retry reaproveita reservas válidas e não duplica efeitos;
- ticket obsoleto exige novo preparo;
- journal interrompido recupera antes de nova narração;
- checkpoint e encerramento preservam ordem canônica.

## Definition of done

- todos os turnos narrativos emitem estado transacional correlacionável;
- falha de orquestração deixa de ser atribuída por aproximação a sidequest ou NPC;
- nenhuma terceira chamada ritualística é criada;
- lifecycle de sessão permanece compatível;
- perfis `cronica` e `sessoes` ficam verdes.
