# Entrega — prova antecipada da AMV-14 e fluxo de revisão

**Data:** 2026-10-06. **Escopo:** avaliador pós-sessão. Integração dos módulos
de jogo na AMV-14 e acompanhamento longitudinal da AMV-16 continuam pendentes.

## Implementação e motivo

- `avaliar-sessao preparar/casos/concluir` liga fonte congelada, leitura pelo
  agente, decisões e pacote final. O agente executa a revisão; uma fila pendente
  deixou de satisfazer o pedido de avaliação.
- Padrão integral; seleção parcial declara alcance. A conclusão rejeita decisões
  faltantes, duplicadas, fora do corte ou com citações falsas. Abstenção legítima
  possui razão e fonte; desconhecimento da fonte não vira negativa válida.
- Falha exige estágio causal, hipótese ou referência de reprodução, correção e
  teste. Localizar sintoma não confirma uma causa no código.
- Staging, identidade congelada e recibo protegem publicação contra pacote
  parcial, alteração de fonte, retry duplicado e substituição de histórico.
- Fontes reservadas ficam fora do projeto servido. Publicação expurga citações
  privadas e apresenta descrição genérica do estágio e da investigação.
- Guardrails críticos precedem médias. Amostra com nota 100 sem falha sai da
  fila de problemas. O dashboard protege também a leitura das filas antigas e
  declara que as notas rápidas são operacionais parciais.

## Prova antecipada

[Aceite](../../../evaluation/aceite-experiencia-v1/README.md): 24 episódios,
13 propriedades e **168/168 verificações** da revisão executada pelo agente.
Há dez pares, uma divergência de persistência, um par por canal remoto e um caso
de fonte insuficiente. Essa distribuição é de cenários, não amostra de jogo.

Cobertura: aviso omitido sem recibo e sem frase explícita de omissão, silêncio
legítimo, conhecimento indevido, acordo negado, oposição, mundo fora de cena,
recompensa e persistência, clima e instituição, adaptação canônica, rolagem e
agência. Pedidos do revisor não recebem gabarito ou rótulo de falha.

A fonte v1 omitia o marcador nativo de início de turno, perdendo a entrada do
jogador no scanner. A v2 corrigiu a fonte; v1 e seu manifesto foram preservados.
**Nenhuma expectativa foi alterada para acompanhar a implementação.**

O agente registrou a revisão por leitura das fontes. Replay desses pareceres
testa o pipeline. Os testes incluem reprovação de aprovação indiscriminada,
preservação do caso legítimo e da abstenção, mesmas operações bem-sucedidas com
ficções distintas, expurgo, retry, perda de arquivo e publicação incompleta.

## Demonstração na 024

Um pacote derivado pelo novo fluxo revalida os 13 pareceres históricos. A agência
violada fica em primeiro lugar; amostras adequadas saem da fila de problemas.
Original e AMV-05 permanecem preservados. **Revalidação parcial não é revisão
semântica nova:** continuam 8 conclusivos, 5 indeterminados e 395 combinações
sem parecer. Fontes históricas ausentes não foram inventadas.

Pacote final: `evaluation/sessions/024/revisoes/amv14a-final`. Publicações
intermediárias desta mesma entrega ficam preservadas em
`/tmp/cronicas-publicacoes-intermediarias-amv14a-20261006`, sem repetir entradas
no seletor. Original da 024 e AMV-05 continuam intactos no projeto.

## Verificação da entrega

66 testes direcionados passaram; dois testes em Chrome conferiram o DOM real,
incluindo fila crítica, escopo parcial, provas e proteção de fontes reservadas.
Schemas de avaliações, adjudicações e proveniência foram validados. Os 28
arquivos do original e da AMV-05 coincidem com seus hashes históricos.
Registro: [verificação](../../../evaluation/aceite-experiencia-v1/verificacao-entrega.json).
Suíte integral e preflight não foram repetidos nesta entrega e continuam sendo
gates antes de merge; nenhum novo gate foi acrescentado ao preflight.

## Alcance do aceite

O G0 anterior foi amplo demais para liberar investimento só com aqueles checks.
A prova antecipada demonstra fluxo, sensibilidade destes casos e prioridades.
Não aprova todos os 34 critérios, qualquer hipótese causal, os módulos de jogo,
satisfação ou generalização. Referência e revisão têm participação do mesmo
agente; não se alega validação cega por terceiro.

Nova avaliação deve executar a revisão das novas fontes. Colar pareceres antigos
não substitui essa etapa. Não existe juiz universal automático ou API externa
adicional atrás da CLI; o trabalho semântico pertence ao agente pós-hoc.

O uso após nova sessão tem fluxo verificável. Critério sem fonte suficiente
continua inconclusivo. Episódios integrados e acompanhamento da AMV-16 ainda
precisam comprovar mudanças no jogo, sem fabricar eventos para elevar amostra.
Não houve alteração dos módulos de jogo, do save ou do preflight nesta entrega.
