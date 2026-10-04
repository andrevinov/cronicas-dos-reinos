# AMV-03 — Atividades e recibos com o mesmo contrato

**Data:** 2026-10-04. **Status:** proposta. **Dependências:** AMV-01–02.

## O que implementar

Definir, nas fachadas existentes, contratos versionados de atividade e fases:
preparação, conclusão, permanência, fronteira, lifecycle e subfases legítimas,
incluindo `concluir_iniciativa`. Registrar qual operação produz cada atividade,
sua unidade, alvo quando houver e as condições de aplicabilidade.

Fazer produtor e detector usarem esse contrato. Associar recibos por operação,
atividade, fase e objeto, admitindo subatividades realmente produzidas pela mesma
operação. Um recibo genérico não comprova automaticamente todos os efeitos de
uma subfase. A atividade esperada não pode depender apenas da existência do
próprio recibo: invocação e gatilhos observados continuam fontes independentes.

Representar separadamente recibo ausente, incompleto, duplicado, contraditório e
órfão. Recibo órfão com zero atividades reconhecidas é falha de associação, não
ausência tranquila de atividade. Negativa válida registra causa e escopo examinado.

Preservar vínculo com ticket, interação e versão efetivamente executada. Recibos
duplicados por retry idempotente não devem ser confundidos com dois efeitos.

## Por que corrige a causa

O detector atual não conhece uma fase que seu próprio produtor emite. Um contrato
compartilhado elimina a divergência de sintaxe e unidade. A confirmação continua
dependendo do que realmente aconteceu; aceitar toda fase ou desligar a detecção
de órfãos esconderia integrações quebradas.

## Prova de correção e aceite

- Conclusão com os recibos genéricos e uma iniciativa legítima fica completamente
  associada, sem órfão falso nem dupla contagem.
- Remover o recibo da subatividade realmente executada gera falta detectável.
- Adicionar fase inventada, objeto errado ou recibo de outro ticket reprova.
- Módulo com recibo órfão e nenhuma atividade reconhecida aparece com erro de
  instrumentação, incluindo diagnóstico de associação.
- Retry, resultado fragmentado e recovery preservam a mesma identidade lógica.
- Cobertura parcial ou ausente bloqueia apenas as conclusões que exigem aquela
  prova, sem produzir uma nota saudável por exclusão silenciosa.

## Onde mudar e o que poderá sair

Contratos e emissão nas fachadas, ledger de atividade e geração de avaliação.
Depois da migração comprovada, tabelas paralelas de fases e heurísticas locais
podem ser removidas. Regressões de ausência, duplicação e órfãos continuam ativas,
incluindo os casos que antes tinham falso positivo.
