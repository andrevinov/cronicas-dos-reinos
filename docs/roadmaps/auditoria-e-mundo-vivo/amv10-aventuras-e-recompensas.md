# AMV-10 — Aventuras opcionais com duração, progresso e prêmios

**Data:** 2026-10-04. **Status:** proposta. **Dependências:** AMV-07–09.

## O que implementar

Ligar causas reais — pedidos, problemas locais, planos de NPCs, consequências,
notícias ou pistas legitimamente acessíveis — ao percurso oportunidade → autoria
→ contrato → oferta narrada → lifecycle. A autoria deve conseguir desenvolver
uma âncora válida, e não apenas reapresentar missões já preenchidas. Conversa
incidental e baixa quantidade de quests não bastam para criar uma obrigação.

Auditar causas alcançáveis no preparar, inclusive com negativa manual; preservar
a exigência de exatamente uma flag de oportunidade. Só a oferta narrada
materializa a missão. Aceitação depende do jogador, e entrada de NPC ou encontro
não é inventada para oferecer uma quest. Manter os limites de uma nova oportunidade
por data/período e duas missões ativas.

Projetar aventuras em fases significativas, com investigação, negociação,
deslocamento, oposição e resolução quando a causa comportar essas etapas.
Cada fase exige fatos de progresso, admite escolhas e consequências, e tem
custo temporal compatível com fronteiras canônicas. Encadeamentos podem criar
nova âncora após um terminal legítimo; não prolongar missão por obstáculos vazios.

Congelar condições de recompensa, risco e progresso no contrato aplicável.
Entregar dinheiro, item, favor, acesso, informação ou avanço permitido pela
campanha quando o fato terminal autorizar, uma única vez. A reação posterior
não reabre missão concluída. Pontes podem aproximar frentes canônicas sem mover
Ren ou exigir adesão ao roteiro.

## Por que corrige a causa

O gate de oportunidade sozinho não constrói uma aventura sustentada. A autoria
ligada a objetivos do mundo cria matéria jogável; fases e efeitos terminais
dão duração com propósito. Oferta e recusa observáveis permitem distinguir falta
de conteúdo de escolha do jogador por seguir outro caminho.

## Prova de correção e aceite

- Âncora válida sem missão previamente escrita gera oferta concreta e opcional,
  com objetivo, risco, recompensa e fatos de progresso verificáveis.
- Causa alcançável não desaparece por `--sem-oportunidade-sidequest`; ausência
  legítima de causa não gera quest artificial.
- Aceitação, recusa, adiamento, sucesso, falha e abandono seguem caminhos distintos.
- Episódio de várias cenas demonstra fases, escolhas e consequências; a duração
  não vem de repetir a mesma tarefa sem mudança material.
- Missão aceita reaparece quando relevante; recompensa devida é entregue uma vez
  e não é produzida por checkpoint, retry ou terminal sem prova.
- Temporalidade e ponte canônica preservam núcleo protegido e agência, incluindo
  cenário em que o jogador escolhe não seguir a oportunidade.

## Onde mudar e o que poderá sair

Autoria, causas vivas, lifecycle, recompensas e integração canônica. Remover
projeções ou tabelas duplicadas apenas após equivalência de contratos. O motor
de recompensas por local não se confunde com o de recompensas de sidequest;
suas propriedades continuam cobertas mesmo se uma execução repetida sair.
