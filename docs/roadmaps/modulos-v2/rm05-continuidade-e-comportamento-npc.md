# RM-05 — Continuidade e comportamento social de NPCs

## Status e dependências

**Proposta.** Depende das RM-01–RM-02.

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
