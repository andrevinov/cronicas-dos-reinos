# Corpus independente de regressão do avaliador

Atividade 2 do reparo do instrumento. O corpus `1.0.0` estabelece resultados
esperados antes das correções do detector, do agregador e do aceite. Ele começa
em registros nativos de rollout e termina nos artefatos usados pelo pacote de
avaliação. As fixtures são isoladas e não descrevem o estado vivo da campanha.

O diretório `evaluation/regressoes-rollout-v1/` contém 19 casos, 201 checks de
gabarito e duas relações metamórficas com 25 comparações. Cinco casos são
reduções sintéticas dos formatos observados na sessão 023 e registram somente
os `call_id` de origem. O bruto e a conversa da sessão não foram copiados.

## Fonte dos resultados esperados

Cada gabarito foi escrito como regra normativa a partir do contrato de unidades
da atividade 1 e da evidência literal da fixture. O analisador não produz os
valores esperados. Todo check declara:

- unidade avaliativa;
- caminho do valor no pacote projetado;
- resultado esperado;
- justificativa;
- linha, ponteiro JSON e fragmento literal do rollout, ou ponteiro para uma
  adjudicação congelada.

O validador resolve essas âncoras e rejeita fragmento inexistente, unidade
desconhecida, campo duplicado, path fora do corpus e mudança de qualquer rollout,
gabarito ou configuração. Catálogo, metas, baseline sintética, contratos,
releases, série, guardrails e entradas humanas estão congelados por SHA-256.
O baseline identifica explicitamente sua natureza sintética.

Uma alteração futura de contrato cria uma nova versão do corpus. Não se edita a
versão antiga para fazê-la concordar com a implementação nova.

## Casos cobertos

| Grupo | Propriedade observada |
| --- | --- |
| Controle direto | Preparo e recibos completos; leitura separada; saída em blocos |
| Agrupamento | Leitura junto de preparo preserva sete atividades e recibos |
| Sucesso misto | Consulta bem-sucedida não promove preparo, lote ou fecho falho |
| Correlação | `call_id`, resultados fora de ordem e operação sem resultado |
| Transporte | Resultado fragmentado e retransmitido não perde nem duplica efeito |
| Menção | Comando ou recibo citado em documentação não é execução |
| Ausência | Preparo bem-sucedido sem recibos abre falha real de instrumentação |
| Retry | Duas operações concluídas materializam uma única memória durável |
| Agregação | Componentes de módulos bloqueados não alteram eixos ou nota geral |
| Evidência humana | Manifestação pendente não vira confirmação ou auditoria |
| Formato futuro | Envelope desconhecido bloqueia a entrada e não produz scorecard |
| Aceite | Pacote com falha de instrumentação não recebe aceite final |

As relações metamórficas exigem que:

1. leitura e preparo separados ou agrupados produzam os mesmos fatos de
   atividade e cobertura; a contagem de chamadas nativas fica explicitamente
   fora dessa igualdade;
2. permutar consulta bem-sucedida e preparo falho preserve a atribuição de
   resultados.

## Executar

Validar somente os dados e gabaritos:

```bash
poetry run python ferramentas/verificar_corpus_avaliacao.py --somente-validar
```

Executar entrada nativa, analisador, gerador, propriedades e aceite:

```bash
poetry run python ferramentas/verificar_corpus_avaliacao.py \
  --saida /tmp/resultado-corpus.json
```

Selecionar casos durante uma correção:

```bash
poetry run python ferramentas/verificar_corpus_avaliacao.py \
  --caso leitura_e_preparo_agrupados \
  --caso consulta_sucesso_preparo_falha
```

O retorno é `0` quando todos os checks selecionados passam, `1` quando o
avaliador reprova algum gabarito ou relação e `2` quando o próprio corpus é
inválido. `--json` imprime o relatório completo. Uma saída existente diferente
não é sobrescrita.

O snapshot `resultado-inicial.json` registra o estado anterior às correções:
153 checks aprovados e 73 reprovados em 226 verificações. Ele é evidência
histórica, com hashes do corpus e dos quatro componentes executáveis; seus
números não são uma meta permanente. A meta do comando corrente é zero falhas.

O snapshot `resultado-atividade-03.json` registra a separação entre chamada
nativa e operação executada: 222 checks aprovados e 4 reprovados. As 69
correções cobrem agrupamento, correlação por operação, resultados fora de ordem,
fragmentação e retransmissão. As quatro falhas preservadas pertencem à
classificação semântica de erro, agregação bloqueada e aceite final.

O snapshot `resultado-atividade-04.json` registra a classificação explícita dos
resultados: 224 checks aprovados e 2 reprovados. Uma promessa entregue não
promove mais uma operação cujo resultado próprio contém erro ou recusa. As duas
falhas preservadas pertencem à agregação bloqueada e ao aceite final.

O snapshot `resultado-atividade-05.json` preserva 224 checks aprovados e 2
reprovados após introduzir o ledger primário de atividades. Os totais conhecidos
não mudam porque o corpus já esperava a cobertura por atividade; agora cada
total possui identidade e recibo individual auditável. As duas falhas restantes
continuam reservadas à agregação bloqueada e ao aceite final.

O snapshot `resultado-atividade-06.json` registra a propagação fail-closed até o
scorecard: 225 checks aprovados e 1 reprovado. Alterar componentes internos dos
sete módulos bloqueados não muda mais eixos nem nota geral. A única falha
preservada é o aceite final, reservado à atividade 10.

O snapshot `resultado-atividade-07.json` mantém 225 checks aprovados e 1
reprovado depois de introduzir qualidade adjudicada por interação. O corpus
confirma que manifestação pendente e ausência de auditoria não fabricam
qualidade; os testes da atividade cobrem também critérios, evidências,
denominadores e oportunidades perdidas. A única falha preservada continua sendo
o aceite final.

O snapshot `resultado-atividade-08.json` mantém 225 checks aprovados e 1
reprovado depois de separar reparo do medidor, problemas da experiência e
investigação de custo. Testes metamórficos próprios garantem que mudar o rateio
de tokens não muda as filas de reparo ou experiência. A única falha preservada
continua sendo o aceite final.

O snapshot `resultado-atividade-09.json` mantém 225 checks aprovados e 1
reprovado depois de fazer o executor consumir a entrada congelada. A aceitação
técnica compara todos os bytes de duas gerações, e os testes adversariais cobrem
alteração posterior do rollout e das fontes, hash de código, ambiente, formato
desconhecido, correlação ambígua e resultado ausente. A única falha preservada
continua sendo o aceite externo da atividade 10.

O snapshot `resultado-atividade-10.json` registra o fechamento: 226 checks
aprovados e nenhuma falha. O aceite recusa agora pacotes com instrumentação
bloqueada mesmo quando todas as referências visíveis são únicas. O comando
estrito integra `preflight` como gate final.

A amostra histórica real reservada foi validada separadamente em
`evaluation/validacao-externa-v1/`. Ela não foi acrescentada aos 19 casos nem
usada para recalcular seus gabaritos. Contrato e limites:
[validação externa e aceite fail-closed](validacao-externa-e-aceite.md).

Os testes permanentes verificam o contrato, adulterações e seis controles de
ponta a ponta, além do resultado final integral.

## Limites

O corpus é o conjunto de desenvolvimento da correção. Ele impede que o código
seja ajustado apenas aos outputs que ele mesmo gera, mas não substitui validação
externa. A amostra real da sessão 022 foi aberta na atividade 10, depois das
correções 3–9, e permanece em conjunto e comando próprios.

Os casos estruturais não avaliam literatura automaticamente. Qualidade narrativa
exige critérios, evidência e adjudicação humana explícita; aqui se testa somente
que a ausência dessa adjudicação permaneça visível e não seja promovida a nota
de qualidade.
