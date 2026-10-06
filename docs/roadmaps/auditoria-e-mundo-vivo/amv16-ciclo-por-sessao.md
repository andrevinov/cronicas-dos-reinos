# AMV-16 — Aprendizado por sessão e validação em jogo real

**Data:** 2026-10-04. **Status:** revisão entregue em 2026-10-06; acompanhamento longitudinal pendente. **Dependências:** AMV-05, AMV-14–15.

Antecipação: [porta de revisão pelo agente](../../agente/engenharia/revisao-pos-sessao.md)
e [entrega](entrega-avaliador-2026-10-06.md). O agente executa a revisão e publica;
solicitação de parecer não completa a tarefa. Aceite integrado e sessões
comparáveis permanecem nas condições abaixo.

## O que implementar

Entregar uma entrada de manutenção que, depois de encerrar a sessão pelo lifecycle,
congele o recorte nativo, reconstrua operações e oportunidades, execute a revisão
prevista pelo agente, gere pacote e relatório e atualize a série compatível.
Evoluir o gerador atual; não criar outro painel ou uma segunda fonte de métricas.
Incerteza e revisão indisponível produzem estado explícito, sem nota presumida.

O relatório de cada sessão deve conter: validade; o que funcionou; oportunidades
perdidas; consequências e promessas ainda relevantes; manifestações do jogador;
problemas de regra/agência/sigilo; e correções propostas com interação, causa,
responsável e forma de comprovação. Priorizar violações críticas, erros de medição
e falhas de experiência antes de otimizações marginais de custo.

Vincular uma correção à evidência que a motivou, à versão implementada e ao episódio
ou sessão em que foi verificada. Problema sem prova de solução continua aberto;
mudança de régua não encerra o problema. A avaliação não edita código ou cânone
automaticamente durante o jogo.

## Por que corrige a causa

Sem um fluxo efetivo de revisão, a telemetria acumula números e reclamações sem
virar aprendizado. O relatório e a rastreabilidade permitem examinar a experiência
de cada sessão e testar uma correção concreta, em vez de procurar melhora numa
nota global que mudou de denominador.

## Prova de correção e aceite técnico

- Sessão concluída gera pacote com proveniência, qualidade ou pendência explícita,
  oportunidades, evidências e relatório utilizável pelo painel.
- Repetir a geração não duplica feedback, revisão, custos ou correções; regeneração
  não apaga a primeira versão nem muda os fatos da campanha.
- Sessão truncada ou com fontes insuficientes é diagnosticada e não inaugura
  baseline válida por conveniência.
- Manifestação textual do jogador entra sem exigir nota numérica ou formulário.
- Não há chamada de medição no turno ao vivo nem dependência de relatório para narrar.

## Aceite operacional, separado do técnico

O avaliador e a visualização revisada da sessão 024 já devem ter passado pelo G0
na etapa A. As sessões abaixo verificam a experiência produzida pelas mudanças
de jogo e a estabilidade da medição; não servem como condição para entregar a
primeira avaliação utilizável.

Observar pelo menos três sessões comparáveis, com rubrica estável e versões
executadas registradas. Esse é um mínimo de processo, não uma garantia estatística
de qualidade. Cada módulo precisa do mínimo de oportunidades definido na AMV-01;
sem amostra suficiente, permanece inconclusivo. Critérios raros têm cobertura em
episódios e aguardam ocorrência natural no jogo, sem fabricar eventos.

Revisar se as falhas diagnosticadas reapareceram, se a auditoria conseguiu detectá-las
e se as correções tiveram o efeito esperado. A percepção do jogador permanece
evidência relevante da experiência. Aceite técnico pode ser concluído antes desse
acompanhamento; aceite longitudinal não pode ser marcado concluído sem sessões reais.

## Onde mudar e o que poderá sair

Entrada de medição, gerador, relatórios, fila de prioridades e séries do dashboard.
Planilhas ou relatórios paralelos que repetem métricas podem ser descontinuados
quando todos os consumidores estiverem cobertos. Pacotes históricos e feedback
original permanecem preservados.
