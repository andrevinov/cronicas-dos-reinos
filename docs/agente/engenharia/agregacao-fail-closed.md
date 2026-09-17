# Agregação fail-closed do scorecard

A atividade 6 do reparo impede que componentes de módulos bloqueados alimentem
os eixos ou a nota geral. O gerador 4.1.0 publica
`scorecard.agregacao_modular`, schema 1, antes de formar qualquer média da
sessão.

## Regra de inclusão

Uma linha modular é bloqueada quando declara `aplicabilidade_avaliacao:
falha_instrumentacao` ou `avaliacao_ativacao: falha de instrumentação`. A segunda
forma mantém compatibilidade com cartões antigos cuja aplicabilidade ainda era
classificada como evidência insuficiente.

Os componentes de calibração, eficácia e confiabilidade de uma linha bloqueada
são removidos antes das médias. Valores residuais nesses campos não podem mudar
o eixo nem a nota geral. Componentes globais independentes, como economia do hot
path, correlação da interação e latência, conservam seus próprios denominadores.
Pesos de eixos sem evidência são renormalizados como já determina o contrato.

A nota restante é identificada como parcial. `status_avaliacao` passa a
`bloqueada_instrumentacao`, `conclusao_permitida` fica falso e o relatório lista
os módulos excluídos. Uma violação crítica confirmada continua tendo precedência
no status como `comprometida`, sem apagar o bloqueio registrado em
`agregacao_modular`.

## Denominadores e rastreabilidade

O bloco publica:

- quantidade de módulos catalogados, incluídos e bloqueados;
- módulo, motivo e diagnóstico de cada exclusão;
- módulos sem aplicabilidade avaliável, que também ficam fora dos denominadores;
- módulos válidos usados em calibração, eficácia e confiabilidade;
- componentes globais usados em confiabilidade, economia e fluidez;
- eixos válidos e sem evidência usados na nota geral.

O dashboard mostra que a nota é parcial, a quantidade de módulos incluídos e o
denominador válido de cada eixo. O relatório Markdown apresenta a mesma condição.
O contrato estrutural está em
`evaluation/schemas/agregacao-scorecard-v2.schema.json`.

A atividade 8 consome esse bloqueio na fila exclusiva de reparo do medidor.
Qualidade e custo ocupam filas independentes, descritas em
[filas de decisão e atribuição contábil](filas-prioridade-e-custo.md).

## Evidência de regressão

O teste metamórfico altera os três componentes numéricos de todos os módulos
bloqueados entre 1 e 99. Eixos e nota geral precisam permanecer byte logicamente
iguais, enquanto a alteração de um módulo válido precisa continuar observável.

O snapshot `evaluation/regressoes-rollout-v1/resultado-atividade-06.json`
registra 225 aprovações e 1 reprovação em 226 verificações. A única reprovação
restante é o aceite de pacote com falha de instrumentação, reservado à atividade
10.
