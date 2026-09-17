# Ledger de atividades modulares

A atividade 5 do reparo materializa a unidade `atividade_modular` definida no
contrato de medição. O detector 4.5.0 publica `module_activities_schema: 1` e
`module_activities`; esse ledger passa a ser a fonte primária da cobertura dos
onze módulos que usam recibos compactos.

## Identidade e origem

Cada atividade tem identidade determinística formada por:

1. `operacao_id`;
2. `module_id`;
3. `fase`;
4. `objeto_ref`.

`atividade_id` é o SHA-256 do vetor canônico desses quatro campos. O objeto de
cena, ticket ou consulta é representado por uma referência tipada e opaca, como
`cena:sha256:...`; o relatório não replica o valor bruto. A mesma operação e o
mesmo objeto geram a mesma identidade em execuções repetidas do analisador.
Agrupar operações numa chamada nativa pode mudar `call_id` e a contagem de
chamadas, mas preserva os fatos de atividade extraídos de cada operação.

Somente uma operação classificada como `sucesso` cria atividades. Falha
operacional, não execução, resultado ausente ou ambíguo, evidência insuficiente
e erro do detector não criam uma obrigação artificial de recibo.

## Correspondência dos recibos

O recibo compacto só pode cobrir uma atividade da própria operação, no mesmo
módulo e na fase esperada. A cobertura válida exige:

- schema 1 presente;
- exatamente uma ocorrência;
- `units=1`;
- recibo nativo complementar quando o contrato do módulo o exige.

O ledger preserva todas as ocorrências. Duas linhas iguais produzem
`receipt_state: duplicado`; `units=2` produz `incompleto`, pois uma declaração
agregada não substitui duas identidades individuais. Um recibo de fase errada ou
sem atividade correspondente aparece em `orphan_receipts` e não pode ser
reaproveitado por outra atividade.

Os estados publicados são `completo`, `ausente`, `incompleto` e `duplicado`.
Aplicabilidade continua separada em `aplicavel`, `nao_aplicavel` e
`indeterminado`. Assim, um recibo completo indeterminado significa evidência
insuficiente; ele não é uma falha de transporte nem uma avaliação negativa.

## Agregação derivada

`module_coverage_gates` não reinterpreta o rollout. Seus contadores e
`assessments` são projetados diretamente das linhas de `module_activities`, e
cada assessment conserva `activity_id`, `operation_id`, objeto, hashes de
comando/saída e marcador. Isso impede que uma contagem agregada afirme cobertura
sem uma atividade individual correspondente.

O contrato JSON está em
`evaluation/schemas/atividades-modulares-rollout.schema.json`. A integração
canônica conserva seu ledger específico por missão e não é convertida para este
formato nesta atividade.

## Evidência de regressão

Os testes isolados cobrem identidade estável, equivalência entre chamadas
agrupadas e separadas, duplicação literal, `units` inválido, recibo órfão, falha
operacional e derivação dos gates. O snapshot
`evaluation/regressoes-rollout-v1/resultado-atividade-05.json` registra 224
aprovações e 2 reprovações em 226 verificações. As reprovações restantes são a
propagação do bloqueio para o agregado e o aceite final, reservadas às atividades
6 e 10.
