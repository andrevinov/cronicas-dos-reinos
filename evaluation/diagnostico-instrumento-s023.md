# Diagnóstico do instrumento de avaliação — sessão 023

Auditoria pós-hoc do PDF `evaluation/sessao23.pdf`, do pacote
`evaluation/sessions/023/`, do rollout correspondente e do código do detector,
gerador e painel. Este documento avalia o medidor; não modifica o histórico,
o cânone ou o pacote existente.

O pacote apresenta oito módulos com falha de instrumentação, dois com nota e
dois sem atividade avaliável. As marcações de erro não sustentam a conclusão
de que os oito módulos funcionaram mal. Foram identificados defeitos concretos
na extração e correlação das evidências. A nota geral e o ranking atual não
devem orientar uma priorização de qualidade da experiência.

## Fonte e reprodução

Fonte registrada no manifesto:
`rollout-2026-09-15T08-32-03-01a0a4d6-9ecd-7991-a7be-aeb9c5c61c5b.jsonl`.
O arquivo nativo recebeu eventos posteriores à geração do pacote. Seus primeiros
10.757.383 bytes correspondem exatamente ao SHA-256 do manifesto:
`22d3055ecf3ea3d85267a4f7f54879ea793e4b7e8849444637efe17eb84441c7`.
Esse trecho termina em uma linha JSON completa, em
`2026-09-15T16:33:28.962Z`. A auditoria foi repetida sobre esse trecho congelado,
em `/tmp`, sem copiar o bruto para o repositório.

No trecho exato, os registros nativos confirmam os totais de `all_turns`:
280 eventos de inferência, 259 chamadas de ferramenta, 30.015.960 tokens de
entrada, 29.017.728 tokens de entrada em cache e 184.287 tokens de saída.
Esses são totais de tráfego de tokens; não são valores de cobrança nem medição
causal do custo de cada módulo. O recorte narrativo de 18 turnos é uma seleção
do analisador, distinta desses totais.

## Cobertura que o pacote apresenta

| Módulo | Atividades esperadas | Recibos completos | Ausentes | Incompletos |
| --- | ---: | ---: | ---: | ---: |
| context_and_memory | 62 | 51 | 10 | 1 |
| turn_and_session_orchestration | 70 | 66 | 4 | 0 |
| sidequest_authoring | 30 | 28 | 2 | 0 |
| sidequest_lifecycle | 30 | 28 | 2 | 0 |
| npc_continuity_and_social_behavior | 53 | 51 | 2 | 0 |
| scene_world_projection | 30 | 28 | 2 | 0 |
| world_boundary_resolution | 23 | 18 | 5 | 0 |
| causal_narrative_routing | 30 | 28 | 2 | 0 |
| rules_and_character_state | 29 | 29 | 0 | 0 |
| narrative_delivery | 23 | 23 | 0 | 0 |
| adversarial_operations | 0 | 0 | 0 | 0 |
| **Total deste contrato de cobertura** | **380** | **350** | **29** | **1** |

`canonical_quest_integration` usa seu contrato específico e não teve atividade
avaliável registrada. Não entra nessa soma. Nenhum recibo duplicado foi marcado.

## Por que aparecem os erros

Em `ferramentas/analisar-rollout.py`, `_scan_observations` define
`output_is_observation` como falso para chamadas classificadas como
`read_search` ou `validation` (linha 1542). A mesma decisão impede a leitura
dos recibos de cobertura (linha 1595), embora as atividades esperadas continuem
sendo derivadas dos comandos executados.

Das 30 marcações de ausência/incompletude, **21 possuem recibo estrutural
presente no resultado executado**. Desembrulhando o resultado de cada comando,
o próprio `_module_coverage_receipts` reconhece esses recibos como completos.
As 21 marcações estão em chamadas classificadas como `read_search`.
Completude estrutural não prova, por si, adequação semântica.

Um exemplo de propagação é `call_x1z7XqGYozos780kfjIJsj0H`: uma única chamada
contém uma busca com `rg` e um `cronica preparar`. O preparo termina com
`exit_code: 0` e emite os sete recibos exigidos. A classificação global de
leitura faz o detector descartar os sete, criando erro em sete módulos.

As nove marcações restantes correspondem a três operações que falharam:

- `call_GWDmUBmgUOS5GB4p7lJNzijy`: consulta bem-sucedida e preparo com
  `exit_code: 2`, por exceder o orçamento do recibo objetivo de oportunidade.
  O detector usa o sucesso do conjunto e espera sete recibos do preparo que
  falhou. O recibo da consulta não substitui o do preparo.
- `call_6fB4Boykl7e7xBOiqQUZEIg4`: aplicação de lote recusada com `erro:`;
  o envelope `Script completed` é interpretado como sucesso, gerando uma
  expectativa de recibo.
- `call_ZL43KEjr4YfRKBILc6zcwb9k`: encerramento com `FALHA CRONICA` e leituras
  posteriores bem-sucedidas no mesmo conjunto. O detector considera a chamada
  bem-sucedida e espera um recibo de encerramento.

Há falhas operacionais reais nesses três casos. Elas precisam ser atribuídas
às operações corretas e separadas da falta de instrumentação. As 21 evidências
descartadas e as nove expectativas de sucesso incorretas explicam as 30
marcações deste pacote. Isso não demonstra que uma extração corrigida teria
cobertura perfeita: separar os comandos pode mudar também o denominador.

## Por que a nota geral não sustenta uma avaliação de qualidade

O cartão do módulo bloqueia `nota_desempenho_provisoria_0a100` quando há falha
de cobertura, mas preserva componentes numéricos de calibração e eficácia.
`_scorecard_v2`, em `ferramentas/gerar-avaliacao-sessao.py` (linha 1760), agrega
esses componentes de todas as linhas, sem excluir os módulos bloqueados.
Assim, os erros coexistem com calibração geral 100, eficácia 92,86 e nota geral
79,15. O bloqueio aplicado ao módulo não é respeitado pela agregação da sessão.

O pacote contém **zero auditorias semânticas e seis manifestações do jogador,
todas pendentes**. Nenhuma dessas manifestações entrou como confirmação de
desempenho. Ainda assim, o painel usa o rótulo `Nota auditada provisória`
(`evaluation/dashboard/app.js`, linha 293).

Em `narrative_delivery`, os eventos observados são 18 entregas com rodapé
correlacionado, seis exposições de mecânica e 18 registros
`densidade_nao_avaliada`. Os 100% de eficácia medem os efeitos estruturais
observados. Não houve avaliação da densidade, voz, diálogo ou qualidade da
experiência que justifique interpretar a nota modular 92,83 como qualidade
narrativa.

## Custo e prioridade

O custo por módulo é dividido igualmente entre os pais detectados em cada
turno (`_allocate_integer` e `_build_modular_ledger`). Cinco módulos recebem
aproximadamente 4,27 milhões de tokens cada. Isso é consequência do rateio;
não demonstra que cada um causou esse consumo.

A prioridade atribui déficit 100 a qualquer falha de instrumentação e combina
esse valor com a parcela rateada de tokens. Para os oito cartões com erro,
a ordenação depende principalmente desse rateio. Ela não identifica qual
problema mais prejudicou o jogador nem qual correção economizaria mais tokens.

Os sete testes de `test_fail_closed_evaluation.py` passaram durante a auditoria.
Os casos reais acima mostram que esses testes ainda não validam suficientemente
a extração de chamadas agrupadas e a propagação do bloqueio até o scorecard.

## Requisitos para tornar o instrumento utilizável

1. Correlacionar comando, resultado, sucesso e recibo por operação executada,
   inclusive em `functions.exec` com várias operações. Leituras de código não
   devem ativar módulos por menção; consultas operacionais com recibos precisam
   permanecer observáveis.
2. Separar falha operacional, ausência real de recibo, erro do detector,
   inaplicabilidade e evidência insuficiente. Toda ocorrência deve apontar para
   evidência verificável.
3. Impedir que componentes bloqueados alimentem uma nota geral de desempenho.
   Exibir cobertura e denominadores das amostras válidas.
4. Avaliar qualidade por interação, com critério, evidência e adjudicação
   explícitos. Examinar também oportunidades em que o módulo deveria agir e
   não agiu. Conformidade estrutural deve conservar seu significado próprio.
5. Apresentar o rateio de custo como atribuição contábil. Separar a fila de
   reparo do medidor da prioridade de problemas da experiência.
6. Adicionar regressões para os formatos reais acima e validar uma amostra
   manual do rollout antes de tratar o instrumento como medidor confiável.

A telemetria nativa global é verificável. A extração modular apresenta defeitos
demonstrados. A qualidade narrativa e a gravidade dos problemas da experiência
ainda não foram avaliadas neste pacote.

## Por que a correção anterior não comprovou a validade do instrumento

O checkpoint Git `d3115f8`, anterior à sessão 023, registra a evolução para o
detector 4.2.0 e a introdução de `test_fail_closed_evaluation.py`. O histórico de
releases identifica o contrato uniforme como `uniform-fail-closed-coverage-v1`.
Há correções efetivas de schema, cobertura e semântica de indeterminação, mas
a validação desse contrato deixou lacunas importantes.

Nos testes específicos, chamadas são construídas com `command_executed: True`,
`output_success: True` e `module_coverage` já extraído. Isso permite testar a
cobrança de recibos, mas pula a classificação da chamada, o desembrulho do
resultado e a determinação de sucesso. Esses são precisamente os pontos que
falham nas evidências reais. O teste do scorecard nessa suíte verifica a linha
do módulo por `_module_summary_v2`, sem passar pela agregação `_scorecard_v2`.

O aceite de sessão real, `first_real_session_status`, verifica série, existência
dos doze módulos, ausência de nota numérica do jogador e referências únicas nas
respostas observadas. Não exige cobertura modular válida nem impede a média
de componentes bloqueados. Em uma cópia em `TemporaryDirectory`, foram mantidos
os oito módulos com falha e a nota geral 79,15, ajustando somente
`visible_exactly_once` nas respostas observadas. O resultado foi
`estado: aceita` e `aceite_final: true`. A sessão real permaneceu intacta.

O pacote arquivado da sessão 022 usa detector 3.0.4 e contrato 3.0.0. Portanto,
esse pacote não comprova a validade do contrato 4.0.0 usado na sessão 023.
Os dados da sessão 023 bastam para demonstrar os defeitos aqui descritos;
mais sessões não substituem a correção dos critérios de validação.

## Condições de uma próxima correção verificável

Estas são condições propostas de aceite, ainda não implementadas ou satisfeitas:

- Casos mínimos derivados das falhas reais devem reprovar o código atual antes
  da correção e passar depois, percorrendo entrada nativa, detector, agregação
  e saída usada pelo painel.
- Operações equivalentes isoladas ou agrupadas devem produzir os mesmos fatos
  de domínio extraídos. Isso não exige igualdade das contagens nativas de
  chamadas, pois agrupá-las muda legitimamente essa métrica.
- Permutar resultados independentes não pode trocar sua atribuição. Fragmentos,
  retries e repetição de um resultado não podem fabricar sucesso ou novo efeito.
- Comando citado em documentação não pode ser confundido com execução. Recibo
  executado não pode desaparecer por estar junto de uma leitura de documentação.
- Sucesso de uma operação não pode substituir a falha de outra no mesmo conjunto.
- Componentes bloqueados não podem alimentar uma nota geral de desempenho.
  Métricas estruturais não podem ser rotuladas como auditoria da prosa.
- Uma amostra de outra sessão, não usada para ajustar a correção, precisa ser
  conferida contra resultados esperados estabelecidos independentemente do
  medidor. Testes que só reproduzem sua própria saída não provam acerto.
- Repetir um pacote de entradas imutáveis deve produzir o mesmo resultado
  avaliativo: fonte/corte, versões do código e dos contratos, metas, baseline,
  snapshots relevantes e adjudicações explícitas pertencem a esse pacote.
- Formato desconhecido, evidência ausente ou correlação ambígua precisam gerar
  um diagnóstico explícito e impedir a conclusão dependente da lacuna.

Determinismo garante repetição sob entradas e regras fixas; não garante que uma
interpretação esteja correta. Objetividade operacional exige critérios
observáveis e uma fonte de referência independente. Julgamentos de voz,
densidade e adequação social exigem adjudicação fundamentada; sua agregação e
reprodução podem ser determinísticas depois de registrada a adjudicação.
Não existe garantia de recuperar evidência que um rollout não contém, nem de
avaliar corretamente um formato futuro que ainda não foi especificado.

## Estado após o reparo

As atividades 1–10 implementaram as condições técnicas acima. O corpus de
desenvolvimento termina com 226/226 verificações aprovadas; uma amostra real da
sessão 022, mantida fora desse corpus e aberta depois das correções 3–9, termina
com 6/6 resultados operacionais compatíveis com seu gabarito independente. O
`preflight` executa ambos os gates.

O aceite agora verifica entrada congelada, proveniência, conclusão de medição,
agregação modular, falhas de instrumentação, violações críticas e referências
de interação. Por isso o pacote 023 arquivado recebe `pendente`, em vez de ser
aceito depois de uma correção apenas cosmética nas referências. Essa sessão não
é reescrita nem promovida a baseline. A validação prospectiva continua sendo a
próxima sessão real produzida integralmente pelos contratos corrigidos.
