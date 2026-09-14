# RM-05 — Continuidade e comportamento social de NPCs

## Status e dependências

**Implementada em 2026-09-13; gates próprios verdes.** Depende das RM-01–RM-02,
já concluídas.

## Problema

`npc_social_initiative` mede quem pode iniciar uma troca, mas não é responsável
pela continuidade que torna essa troca crível: identidade, voz, conhecimento,
memória, relação, reputação, presença e objetivo próprio.

## Objetivo

Expandir o domínio para `npc_continuity_and_social_behavior`, mantendo iniciativa
como subcapacidade e acrescentando qualidade e consistência longitudinal.

## Implementação

- compor memória de cena, memória durável, estado relacional, identidade e
  reputação sem duplicar suas fontes de verdade;
- distinguir presente, contactável, mencionado e apenas conhecido;
- projetar somente fatos que o NPC pode saber;
- manter uma decisão de iniciativa por janela e tópico causal;
- registrar fato social persistente no mesmo concluir quando aplicável;
- preservar objetivos autônomos sem criar ação física fora de canal válido;
- emitir telemetria de continuidade, repetição, contradição e rendimento visível.

## Artefatos implementados

- `ferramentas/npc_continuity_and_social_behavior.py`: fachada pública e check
  agregado, com propriedade explícita das fontes existentes;
- caminhos de memória e iniciativa de `cronica preparar/concluir` migrados para
  a fachada, sem nova chamada ou writer;
- classificação estruturada entre presente, contactável, mencionado e apenas
  conhecido na projeção de iniciativa;
- incremento relacional posterior sem `memoria.fatos` e evidência literal passa
  a falhar antes do writer; bootstrap permanece independente;
- recibo de conclusão expõe abertura, silêncio e repetição, preservando
  exactly-once;
- conclusão com memória social expõe contagem, evidência e tipos somente depois
  do writer bem-sucedido, sem estado ou chamada adicional;
- `ferramentas/analisar-rollout.py`: continuidade dirigida deixa de ser
  confundida com iniciativa, e as três subcapacidades ganham sinais próprios;
- `tests/test_npc_continuity_module_v2.py`: contratos estruturados de voz,
  conhecimento, retomada, identidade, reputação, iniciativa e custo neutro;
- `docs/agente/narrativa/modulo-continuidade-npc-v2.md`: contrato operacional
  permanente.

Nenhuma ficha, relação, memória, reputação, suspeita, recibo reservado ou
histórico foi migrado. Os componentes v1 continuam sendo as fontes e os motores
internos.

## Guardrails

- interlocutor não cria presença;
- iniciativa não cria encontro, segredo, sidequest ou ação de Ren;
- suspeita não vira identidade confirmada;
- reputações de personas não são fundidas automaticamente;
- memória do narrador não é conhecimento do NPC;
- conselho repetido exige fato novo.

## Testes

- continuidade de voz e fatos usa fixture controlada, não substring literária;
- NPC não conhece evidência não transmitida;
- retomada fria preserva elenco e memória necessária;
- mudança relacional nova exige memória e evidência;
- iniciativa inelegível permanece silêncio explícito;
- consulta dirigida não vira scan de todos os NPCs.

## Definition of done

- iniciativa v1 é subcapacidade do novo módulo;
- métricas cobrem elegibilidade e qualidade longitudinal;
- nenhuma fonte canônica é duplicada;
- perfis sociais, memória e cronica ficam verdes;
- custo de turno sem NPC permanece inalterado.

As regressões próprias, o check modular e os perfis dirigidos fecham verdes. A
suíte agregada continua sujeita às falhas anteriores no estado vivo já
documentadas pela RM-04; a RM-05 não reescreve esse estado para mascará-las.
