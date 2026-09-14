# RM-10 — Regras e estado do personagem

## Status e dependências

**Implementada; gates próprios verdes.** Depende das RM-01–RM-02.

## Problema

Regras, CDs, dados, recursos, ficha, condições e tempo de Ren são capacidades
centrais do jogo, mas não estão representados no catálogo modular. Seus custos e
falhas desaparecem em métricas genéricas de tools ou confiabilidade.

## Objetivo

Criar `rules_and_character_state`, ativado somente quando o turno exige regra,
rolagem, gasto persistente ou mutação autorizada de ficha/tempo.

## Implementação

- correlacionar consulta de regra, definição de CD, rolagem e consequência;
- registrar modificadores e dificuldade antes do resultado;
- correlacionar gasto pré-comprometido com delta persistente exatamente uma vez;
- validar limites e concordância entre ficha, estado e runtime;
- tratar avanço temporal e condições de Ren sem assumir responsabilidade pelo
  Mundo Vivo, que permanece no módulo de fronteira;
- distinguir consulta útil, redescoberta de assinatura e chamada redundante.

## Indicadores

- rolagens com CD e modificadores predefinidos;
- integridade do resultado e da consequência;
- consultas de regra por oportunidade;
- redescobertas de schema ou CLI;
- recursos comprometidos versus aplicados;
- divergência de ficha, estado e runtime;
- tempo canônico coerente;
- correções mecânicas solicitadas pelo jogador.

## Guardrails

- resultado não é alterado depois da rolagem;
- vitória, falha ou dificuldade não são garantidas retroativamente;
- Focus não é gasto sem obrigação no ticket;
- direção canônica não vira ação de Ren;
- estado não é atualizado diretamente fora do concluir autorizado.

## Testes

- sucesso e falha produzem consequências compatíveis com o contrato prévio;
- gasto de recurso é exactly-once em retry;
- rolagens independentes preservam independência;
- consultas desnecessárias são observáveis sem bloquear regra rara legítima;
- fixtures, e não estado vivo, congelam números absolutos;
- guardrail violado marca a avaliação separadamente.

## Definition of done

- turnos mecânicos aparecem no novo módulo e turnos puramente narrativos não;
- custo de regra deixa de ser custo órfão;
- ficha, recursos e tempo preservam fontes de verdade atuais;
- testes de dados, mecânica, ficha e cronica ficam verdes.
