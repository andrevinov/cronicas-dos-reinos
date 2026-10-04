# AMV-05 — Um dashboard que mostre o que é possível concluir

**Data:** 2026-10-04. **Status:** proposta. **Dependências:** AMV-02–04.

## O que implementar

Separar, no pacote e no painel, execução operacional, cobertura de oportunidades,
qualidade da experiência e guardrails. A visão inicial deve mostrar validade da
medição e cobertura antes de qualquer número. Com instrumentação bloqueada ou
qualidade não avaliada, exibir a limitação correspondente; não pintar uma nota
parcial como experiência saudável. Métricas operacionais parciais continuam
consultáveis, identificadas com seu escopo.

Por módulo, mostrar objetivo, oportunidades elegíveis/atendidas/omitidas, amostra,
qualidade revisada, pendências e provas por interação. Guardrail violado permanece
destacado fora das médias. A conclusão geral não pode melhorar simplesmente
porque módulos difíceis ficaram sem evidência e saíram do denominador.

Congelar versões de implementação executada, detector, rubrica e gerador, além
das entradas do pacote. Comparar apenas pontos compatíveis por módulo. Reanálise
de uma sessão produz um artefato derivado vinculado ao original; não atualiza
silenciosamente suas versões para as do catálogo corrente.

Mostrar custo observado com unidade e atribuição claras. Separar custo exclusivo,
custo compartilhado alocado e custo marginal desconhecido. Não atribuir o mesmo
contexto nativo inteiro a todos os módulos nem inferir benefício narrativo pela
redução de tokens. Comparações de eficiência precisam de recortes equivalentes.

## Por que corrige a causa

O problema visual não é resolvido apenas acrescentando um aviso ao lado de 85,1
verde. A hierarquia e a classificação passam a corresponder ao alcance real da
medição. Séries versionadas evitam interpretar mudança de régua como evolução
da campanha ou dos módulos.

## Prova de correção e aceite

- O pacote 024 original abre como medição incompleta, sem selo global saudável
  e sem tendência calculada a partir de sua nota bloqueada.
- Operação 100 com qualidade confirmada 0 aparece como execução correta e
  experiência inadequada no critério; não recebe aprovação narrativa.
- Falta de qualidade, falta de amostra e negativa válida têm estados diferentes.
- Violação crítica nunca é compensada por economia, fluidez ou outra nota alta.
- Testar o comportamento renderizado e os dados consumidos pelo painel, incluindo
  acesso à evidência e proteção de conteúdos reservados.
- Regeneração preserva proveniência, manifestações e decisões; versões
  incompatíveis não entram em deltas ou médias móveis comuns.
- A soma de custos atribuídos fecha uma vez; estimativas são identificadas.

## Onde mudar e o que poderá sair

Gerador, schemas de avaliação e `evaluation/dashboard/`. Retirar a classificação
global atual quando ela sugere experiência saudável com medição bloqueada.
Campos históricos continuam legíveis como referência; testes que congelam a
apresentação enganosa devem ser substituídos por testes desses estados de validade.

## Entrega obrigatória para G0

Exibir a sessão 024 com uma opção de reavaliação derivada, acessível na seleção
daquela sessão. Preservar o pacote original e identificar fonte, revisão do
avaliador e versões dos módulos que realmente foram jogados. Escolher a revisão
não deve fazer a 024 se passar por uma sessão posterior às mudanças de runtime.

Conferir na interface os contadores corrigidos, a cobertura real, os julgamentos
de experiência e os diagnósticos por interação. Exibir fontes insuficientes quando
existirem; não reduzir a entrega a trocar a cor da nota ou rotular tudo como N/D.
Esta demonstração usa a sessão existente e encerra a etapa A, sem exigir novo jogo.
