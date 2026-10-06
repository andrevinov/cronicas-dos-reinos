# Auditoria confiável e mundo vivo

**Data:** 2026-10-04; atualização em 2026-10-06. **Status:** AMV-01–05 entregues; avaliador da AMV-14 e fluxo de revisão entregues; alterações de jogo e demais aceites pendentes.

**Revisão em 2026-10-06:** a [prova do avaliador e o fluxo de revisão](entrega-avaliador-2026-10-06.md)
foram antecipados da AMV-14/16. O alcance do G0 foi restringido à prova documentada;
integração de jogo e acompanhamento longitudinal seguem pendentes. A entrega
corrige a fila que omitia a violação crítica e atribui a revisão semântica ao agente.

Este roteiro responde ao diagnóstico do avaliador, do dashboard e da composição
dos módulos de campanha. O objetivo é conseguir medir o que aconteceu em cada
sessão e produzir um mundo que age, lembra, oferece aventuras e reage às escolhas
do jogador, preservando agência, sigilo e dificuldade justa.

## Documentos

- [Próximo ciclo: correção e validação por sessão](../correcao-e-validacao-por-sessao/roadmap-2026-10-06.md): proposta de reparos delimitados, captura de evidências e aceite antes de novo jogo; entregas contam parcialmente nas AMVs.
- [Revisão integral da 024](revisao-integral-s024-2026-10-06.md): achados concretos, reprodução de presença e limites das fontes históricas.
- [Roadmap datado](roadmap-2026-10-04.md): prioridades, dependências e aceite global.
- [Diagnóstico e evidências](diagnostico-2026-10-04.md): defeitos observados e hipóteses que precisam de validação.
- [Matriz de desativação e remoção](matriz-de-desativacao-2026-10-04.md): candidatos, propriedades protegidas e substituições necessárias.
- Tarefas AMV-01–AMV-16: especificação individual de implementação, motivo e prova de correção, indexada no roadmap.
- [Entrega AMV-01](../../../evaluation/aceite-avaliacao-v1/README.md): contratos, regressões, referência da 024 e inventário medido.
- [Entrega AMV-02](amv02-operacoes-e-metricas.md): classificação unificada, métricas e reanálise operacional da 024.
- [Entrega AMV-03](amv03-atividades-e-recibos.md): contrato de atividades, associação de subfases e reanálise da 024.
- [Entrega AMV-04](amv04-avaliacao-de-experiencia.md): oportunidades sem recibo, pareceres vinculados e diagnóstico da 024.
- [Entrega AMV-05 e G0](amv05-dashboard-e-series.md): revisão da 024 no dashboard, provas, validade, custos e séries compatíveis.

## Como ler a proposta

Começar pelo roadmap e consultar a tarefa correspondente a cada entrega.
A etapa A só termina com o G0: reavaliação da sessão 024 demonstrada no dashboard,
com contagens e diagnóstico de experiência, sem exigir uma nova sessão. As
mudanças de runtime ficam condicionadas a essa entrega.
A matriz de desativação é condicional: ela não autoriza apagar cobertura antes
de demonstrar que a substituição detecta a mesma falha.

O diagnóstico foi feito antes das mudanças. A AMV-01 adicionou contratos e
referências de aceite; preflight, CI, estado da campanha e sessões concluídas
permanecem preservados. A medição inicial reproduz sete verificações com falha;
essa fotografia inicial foi preservada. A AMV-05 demonstrou o G0 com os 19 checks
congelados aprovados e provas no navegador. O aceite tem o alcance descrito na
tarefa: não aprova o runtime nem supre as fontes e amostras que continuam ausentes.

As tarefas aproveitam os doze módulos existentes. O catálogo modular não será
reinventado. O [roadmap anterior](../modulos-v2/README.md) permanece como contexto
da arquitetura; esta proposta corrige insuficiências descobertas depois dele.

- [Entrega parcial RCV-03: obrigação espacial e envelope](../correcao-e-validacao-por-sessao/entrega-rcv03-2026-10-06.md).

- [Entrega parcial RCV-04: janela temporal efetiva](../correcao-e-validacao-por-sessao/entrega-rcv04-2026-10-06.md).

- [Entrega parcial RCV-05: agência na prosa e revisão contrastada](../correcao-e-validacao-por-sessao/entrega-rcv05-2026-10-06.md).

- [Entrega parcial RCV-06: interlocutor recuperado por fonte](../correcao-e-validacao-por-sessao/entrega-rcv06-2026-10-06.md).

- [Entrega parcial RCV-07: evidências causais preservadas](../correcao-e-validacao-por-sessao/entrega-rcv07-2026-10-06.md).
