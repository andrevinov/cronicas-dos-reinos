# Auditoria confiável e mundo vivo

**Data:** 2026-10-04. **Status:** proposta para revisão; implementação não iniciada.

Este roteiro responde ao diagnóstico do avaliador, do dashboard e da composição
dos módulos de campanha. O objetivo é conseguir medir o que aconteceu em cada
sessão e produzir um mundo que age, lembra, oferece aventuras e reage às escolhas
do jogador, preservando agência, sigilo e dificuldade justa.

## Documentos

- [Roadmap datado](roadmap-2026-10-04.md): prioridades, dependências e aceite global.
- [Diagnóstico e evidências](diagnostico-2026-10-04.md): defeitos observados e hipóteses que precisam de validação.
- [Matriz de desativação e remoção](matriz-de-desativacao-2026-10-04.md): candidatos, propriedades protegidas e substituições necessárias.
- Tarefas AMV-01–AMV-16: especificação individual de implementação, motivo e prova de correção, indexada no roadmap.

## Como ler a proposta

Começar pelo roadmap e consultar a tarefa correspondente a cada entrega.
A etapa A só termina com o G0: reavaliação da sessão 024 demonstrada no dashboard,
com contagens e diagnóstico de experiência, sem exigir uma nova sessão. As
mudanças de runtime ficam condicionadas a essa entrega.
A matriz de desativação é condicional: ela não autoriza apagar cobertura antes
de demonstrar que a substituição detecta a mesma falha.

O diagnóstico foi feito sem implementar mudanças nos módulos. A criação desta
pasta também não altera preflight, CI, estado da campanha, sessões concluídas
ou manuais operacionais vigentes.

As tarefas aproveitam os doze módulos existentes. O catálogo modular não será
reinventado. O [roadmap anterior](../modulos-v2/README.md) permanece como contexto
da arquitetura; esta proposta corrige insuficiências descobertas depois dele.
