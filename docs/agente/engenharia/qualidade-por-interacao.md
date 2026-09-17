# Qualidade adjudicada por interação

A atividade 7 separa a conformidade operacional da avaliação de qualidade. O
detector 4.6.0 aceita `quality_assessments` e o gerador 4.2.0 publica
`avaliacoes-qualidade.json`. Um efeito ou recibo estrutural bem-sucedido continua
sendo evidência operacional, mas não cria nota de qualidade.

## Unidade e identidade

Cada avaliação usa exatamente uma unidade
`interaction_ref × module_id × criterion_id`. `assessment_id` também é único.
Duplicar qualquer identidade falha antes da agregação. A interação precisa
existir no ledger, o módulo precisa existir no catálogo e o critério precisa ser
um `indicador_especializado` daquele módulo. `capability_id`, quando informado,
também precisa pertencer ao módulo.

O registro contém:

- elegibilidade: `sim`, `nao` ou `indeterminada`;
- ativação: `presente`, `ausente` ou `indeterminada`;
- qualidade: `adequada`, `inadequada`, `indeterminada` ou `nao_aplicavel`;
- avaliador e adjudicação com estado e motivo;
- ao menos uma evidência estruturada, com fonte, localizador, observação e
  visibilidade pública ou reservada.

Evidência pública conserva localizador e observação. Para evidência reservada,
o ledger e o pacote guardam somente os hashes SHA-256 desses dois campos; o
conteúdo usado pelo avaliador não é publicado no artefato servido pelo painel.

Ativação ausente exige qualidade `nao_aplicavel`: uma oportunidade perdida não
é reclassificada como prosa ruim. Ativação indeterminada não admite julgamento
conclusivo de qualidade.

## Denominadores

Somente adjudicações `confirmada` entram nas métricas. `pendente`, `parcial`,
`nao_confirmada` e `indeterminada` permanecem no artefato, mas ficam fora dos
denominadores.

Elegibilidade e ativação confirmadas formam uma matriz explícita:

| Elegibilidade | Ativação | Classe |
|---|---|---|
| sim | presente | verdadeiro positivo |
| sim | ausente | falso negativo, ou oportunidade perdida |
| não | presente | falso positivo |
| não | ausente | verdadeiro negativo |

A nota de oportunidade é a média das classes observáveis de cobertura e
especificidade. Qualidade usa apenas ativações presentes julgadas `adequada` ou
`inadequada`. `nota_experiencia_interacao_0a100` é a média das duas notas que
tenham denominador; ausência nunca vira zero.

Cada módulo expõe contagens recebidas, confirmadas, pendentes, pontuáveis e não
pontuáveis, a matriz de oportunidade, os dois denominadores e as notas de
oportunidade, qualidade e experiência. O scorecard resume a cobertura
qualitativa da sessão.

## Separação da telemetria estrutural

`nota_conformidade_operacional_0a100` e
`efeitos_conformidade_operacional_avaliaveis` preservam a leitura anterior de
efeitos observáveis. Elas não alimentam `nota_qualidade_interacao_0a100`. O
dashboard e o relatório mostram as duas medidas separadamente.

A atividade 8 usa `nota_experiencia_interacao_0a100` somente na fila de
problemas da experiência. Falha do instrumento e atribuição contábil de custo
ocupam filas independentes, descritas em
[filas de decisão e atribuição contábil](filas-prioridade-e-custo.md).

## Regressão

Os testes usam ledgers temporários e verificam oportunidade perdida sem evento
automático, exclusão de pendências, separação entre conformidade e qualidade,
identidades duplicadas, critério desconhecido e evidência vazia. O snapshot
`evaluation/regressoes-rollout-v1/resultado-atividade-07.json` conserva o corpus
de desenvolvimento em 225 de 226 checks; o aceite final continua reservado à
atividade 10.
