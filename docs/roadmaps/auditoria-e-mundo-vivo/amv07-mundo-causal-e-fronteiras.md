# AMV-07 — Causas alcançáveis e mundo que continua no tempo

**Data:** 2026-10-04. **Status:** proposta. **Dependência:** AMV-06.

## O que implementar

Integrar agentes, planos, compromissos, eventos e agenda existentes em uma cadeia
com identidade e fontes rastreáveis: fato percebido → objetivo → decisão → plano
ou tentativa → resolução → efeito → memória. Distinguir agente ativo de plano
executável; cadastrar um agente não comprova que ele agirá.

Definir como uma causa relevante entra na avaliação e em que fronteira temporal
pode produzir efeito. Usar a agenda e a barreira existentes para planos fora de
cena. Um impedimento legítimo pode adiar ou cancelar uma tentativa, com motivo e
próxima condição de avaliação; não pode criar uma sequência infinita de no-ops
para uma obrigação vencida. Calma justificada exige cobertura do recorte alcançável.

Reconciliar a instalação atual usando estado consolidado mais pendências, índices
e história dirigida quando necessária. Classificar dados ausentes, legado,
causa terminal, objetivo ainda ativo e causa sem plano. Migração não fabrica
acontecimentos passados. Novas decisões prospectivas podem gerar planos a partir
de motivações e capacidades legítimas, com data e proveniência.

Fazer a projeção alcançar o narrador no preparar correto, com informação mínima
necessária e camadas de conhecimento preservadas. Nas compressões, interromper
na primeira fronteira material e retomar pela mesma porta transacional.

## Por que corrige a causa

O estado pode conter agentes e componentes verdes sem uma ligação que transforme
objetivos em ação no momento adequado. Essa cadeia torna a causa executável e
torna sua interrupção ou omissão diagnosticável. Reconciliar o estado efetivo
evita tanto esquecer pendências quanto inventar planos para preencher um vazio.

## Prova de correção e aceite

- Em episódio isolado, um ator com causa e meios age fora da presença de Ren;
  a ação é resolvida e altera uma cena posterior por canal legítimo.
- Dormir ou viajar não atravessa silenciosamente uma causa devida e material.
- Turnos curtos sem causa não consultam repetidamente fronteira nem criam evento.
- Impedimento real adia com razão verificável; evento canônico devido não vira no-op.
- Retry e recovery não repetem ação, sorteio, consequência ou fronteira resolvida.
- A reconciliação identifica pendência não consolidada e dado realmente ausente
  sem tratar o snapshot do diagnóstico como estado vivo obrigatório.
- Omissão deliberada de uma resolução alcançável é detectada pela AMV-04.

## Onde mudar e o que poderá sair

Planos, agenda, barreira, resolução de fronteira, projeção e roteamento causal.
Adaptadores de migração única podem sair do preflight após transferir invariantes
permanentes; a capacidade de recuperação e a regressão histórica permanecem.
