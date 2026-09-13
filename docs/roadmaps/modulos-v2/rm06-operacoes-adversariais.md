# RM-06 — Operações adversariais

## Status e dependências

**Proposta.** Depende das RM-01–RM-02.

## Objetivo

Unificar `adversarial_integrity` e `concurrent_adversarial_operations` em
`adversarial_operations`, tratando integridade como contrato e guardrail do
domínio, não como segundo módulo concorrente.

## Implementação

- criar fachada para proposta, compromisso, reserva de recursos, execução e
  consequência de operações adversariais;
- preservar operações simultâneas como subcapacidade identificável;
- congelar capacidade, conhecimento, risco e limites antes da escolha de Ren;
- separar recursos e consequências por frente;
- impedir que ordem de resolução altere resultados já comprometidos;
- emitir eventos distintos para consulta, compromisso e efeito material.

## Guardrails

- nenhum poder, recurso ou conhecimento aparece retroativamente;
- sucesso de Ren não aumenta dificuldade já congelada;
- direção canônica não autoriza execução adversarial;
- alternativa bloqueada não vira fato por aparecer no preparo;
- operações simultâneas não duplicam agente ou recurso exclusivo;
- avaliação reservada não vaza para o jogador.

## Testes

- uma operação simples e duas simultâneas atravessam o mesmo contrato;
- recursos exclusivos não podem ser reservados duas vezes;
- ordem de conclusão não muda consequências congeladas;
- retry é idempotente;
- capacidade inexistente falha antes da mutação;
- guardrail violado aparece fora da média do módulo.

## Definition of done

- os dois aliases v1 resolvem para um módulo pai;
- integridade permanece verificável como guardrail;
- custo modular não é duplicado entre contrato e concorrência;
- nenhum contrato histórico é reescrito;
- perfis adversariais, mundo e cronica ficam verdes.
