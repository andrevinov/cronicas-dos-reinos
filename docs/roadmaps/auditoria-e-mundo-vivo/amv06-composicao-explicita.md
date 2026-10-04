# AMV-06 — Composição explícita nas portas existentes

**Data:** 2026-10-04. **Status:** proposta.
**Dependências:** AMV-01–05 e G0 aprovado na reavaliação da sessão 024.

## O que implementar

Mapear a composição efetiva de preparar, concluir, fronteira e checkpoint,
incluindo wrappers carregados por `exec` e funções globais substituídas. Declarar
uma sequência explícita de etapas, entradas, saídas, responsáveis e dependências
nas fachadas existentes. Preservar a ordem transacional e de autoridade vigente.

Substituir gradualmente a execução encadeada de fontes históricas por imports e
interfaces explícitas nos caminhos alterados por este roteiro. Não fazer uma
reescrita integral como pré-condição para corrigir o avaliador. Mover uma etapa
por vez, com prova de comportamento antes/depois e diagnóstico de qual versão
efetivamente rodou. Aplicar o mesmo princípio ao registro de checks do preflight.

Manter o único writer, agenda, RNG e estado autoritativo existentes. Preparação
não materializa efeito canônico; reservas operacionais já previstas continuam
estáveis e distinguíveis de fatos. Conclusão revalida ticket e instala efeitos
na transação existente. Migrar dados e envelopes com versão e compatibilidade
explícitas, incluindo tickets e journals interrompidos quando aplicável.

Atualizar a documentação operacional apenas quando cada fluxo estiver vigente,
com uma entrada clara por tarefa. A nova composição deve diminuir a necessidade
de o narrador descobrir quais módulos chamar manualmente.

Completar a entrega ao narrador com a situação em curso, matéria causal relevante,
iniciativas autorizadas e consequências que precisam aparecer naquela cena.
Atualizar `narrative_delivery` e suas instruções para transformar essa matéria
em ações, diálogo e mudança de situação na prosa, com densidade adequada ao
acontecimento. Não impor conflito, tamanho mínimo ou recapitulação em todo turno;
o texto deve manter continuidade entre cenas e deixar espaço para a decisão do
jogador. Detalhes de implementação ficam fora da apresentação diegética.

## Por que corrige a causa

Composição implícita facilita capacidades existirem no arquivo sem participarem
do caminho de jogo. Interfaces e ordem explícitas tornam a ativação inspecionável,
testável e mais segura para evoluir. Também permitem apagar uma versão antiga
sem depender de suposições sobre os efeitos de carregamento dela.

## Prova de correção e aceite

- Uma inspeção da composição mostra etapas e versões que serão executadas,
  sem precisar reconstruir substituições de globais.
- Turno neutro usa preparar + concluir, sem consulta, scan ou medição novos.
- Bloqueio por pendências, sidequest ativa, iniciativa, mecânica e memória são
  exercitados pela porta pública, com ordem e efeitos corretos.
- Ticket obsoleto, retry, falha durante commit e recuperação mantêm integridade;
  efeitos já instalados não são executados novamente.
- Antes/depois do refactor preserva resultados e artefatos dos cenários que
  não representam uma mudança comportamental intencional.
- Uma sequência de cenas demonstra continuidade, iniciativa e consequência na
  resposta final; uma saída composta apenas de resumo passivo ou rodapé não
  satisfaz os critérios narrativos da AMV-04.
- Toda fonte histórica removida possui fechamento de dependências verificado,
  incluindo import, `exec`, CLI, teste, documentação e recuperação persistida.

## Onde mudar e o que poderá sair

Orquestrador, fachadas e composição de planos/checkpoint/preflight. Arquivos
`_..._nvNN.py` podem sair somente quando não fornecerem implementação ou adaptação
necessária. O prefixo histórico, sozinho, não prova que o arquivo é obsoleto.
