# Sessão 024 — revisão da experiência

**Data da revisão:** 2026-10-04. **Natureza:** revisão pós-hoc de um corte histórico;
não corrige fatos da sessão, não modifica seu pacote e não usa o estado atual.

Fonte: UUID `01a0aac8-9b23-7c12-9520-be10b50ed451`, prefixo de 2.098.214 bytes,
SHA-256 `8be6e5f5068f3dbf21abdb02339f7d5499b854abdc0efd1d744b8e5e9965b55f`.
As sete âncoras do gabarito foram conferidas. Bruto não versionado.
Revisor: Codex em papel pós-hoc, rubrica `objetivos-jogo/1.0.0`.
Esta revisão não é validação cega por terceiro nem prova de independência entre autores.

## Resultado disponível agora

O pacote original tinha zero avaliações de qualidade por interação. A revisão
entrega **13 pareceres: oito confirmados, cinco indeterminados**. Os estados,
citações e hashes estão em [experiencia-s024-amv04.json](experiencia-s024-amv04.json).
Os critérios sem parecer ou com fontes insuficientes não foram aprovados.

| Interação / objetivo | Julgamento local | Evidência e limite |
| --- | --- | --- |
| I0004 — convicções e iniciativa de Mori | Adequada | “Mas o senhor omitiu um terceiro futuro.” e “É crédito pedido por um desconhecido.”: ele oferece alternativa e recusa risco sem prova. Isso não comprova execução futura de seu plano. |
| I0005 — fechamento transacional | Adequado no recorte | Conclusão terminal correlacionada à resposta visível. Não comprova todos os efeitos persistentes do mundo. |
| I0005 — integridade do resultado | Adequada | CD 13 no comando anterior; d20 1 + 4 = 5; a resposta mantém a falha. O envelope não registra código terminal da CLI, que permanece separado da integridade literal do resultado entregue. |
| I0005 — necessidade e dificuldade do teste | Indeterminada | Proximidade, risco e atenção existem; oposição ativa, limiar perceptivo e fundamento da CD não estão suficientemente comprometidos nas fontes anteriores. |
| I0005 — percepção de Mori | Canal observável para suspeita | Aiko empalidece e diz “Eu não vi nada”; Mori olha para ela e não confirma nem contesta. Não há comprovação de conhecimento exato das linhas que ela leu. |
| I0006 — acordo e continuidade | Adequados na formulação | Promessa limita atos de Mori e seus subordinados; ele não aceita cooperação nem garante os atos de toda a cidade. Persistência futura não avaliada. |
| I0011 — emoção declarada | Legítima neste aspecto | O jogador declara Ren “um tanto frustrado”; repetir a frustração não impõe emoção nova. |
| I0011 — crença e conhecimento | Adequados neste aspecto | Proteção atribuída à perspectiva de Ren, qualificada como limitada; eventual aliança permanece possibilidade. |
| I0011 — agência na narração | Inadequada; guardrail violado | Entrada autoriza voltar normalmente. Resposta acrescenta “Ren espera alguns minutos antes de deixar o telhado.”, sem escolha do jogador nem impedimento externo apresentado. |
| Progresso de aventura, condições persistentes, adaptação do cânone e planos adversários | Indeterminados | Faltam missões/obrigações alcançáveis, seguimento ou fontes anteriores suficientes. Não se introduzem planos atuais para julgar retrospectivamente o episódio. |

## Reclamação de S024-I0005

A manifestação original está preservada integralmente em
[pareceres-s024-amv04.json](pareceres-s024-amv04.json), com decisões por alegação.
Nenhuma nota foi exigida do jogador.

- **Teste desnecessário:** limitado por fonte insuficiente. A declaração posterior
  do próprio narrador de que errou e a percepção do jogador não substituem a
  avaliação da oposição e da incerteza antes do teste.
- **Mori percebe sem canal legítimo:** não confirmada nessa formulação. Há sinais
  observáveis para suspeita. Isso não aprova percepção infalível nem conhecimento
  exato das duas linhas lidas.
- **Integridade do resultado entregue:** confirmada; a falha foi mantida.

Assim, a adjudicação da manifestação é **parcial**. Sua classificação original
de sobreativação percebida continua sendo a voz do jogador; não foi convertida
automaticamente em falso positivo factual do módulo.

## Achados e correções testáveis

| Categoria | Achado | Correção proposta e prova |
| --- | --- | --- |
| Extração/avaliação | O caso de referência com compromisso vencido tinha presença, conhecimento e canal, mas nenhum recibo de NPC: a omissão era invisível. Mensagens sem `turn_id` também podiam ser perdidas após uma identificação explícita de turno. | Herdar a identificação explícita e extrair gates da consulta de cena. Com os mesmos comandos, retirar o aviso deve registrar uma omissão; entregar o aviso deve eliminá-la. Esse controle passa agora. |
| Aplicação de instrução / comportamento narrativo | I0011 introduziu espera voluntária de Ren. O rodapé correto não protegeu a agência. | Restringir novas decisões voluntárias à entrada do jogador. Par controlado: retorno normal não decide espera; entrada que manda esperar autoriza a espera. A avaliação deve reprovar o primeiro e aceitar o segundo. A violação atual é registrada separadamente das notas positivas. |
| Limitação de fonte / dados de arbitragem | I0005 não preserva compromisso mecânico específico suficiente para justificar necessidade e percepção. | Registrar previamente motivo do teste, canal, CD e consequência. Cenário sem acesso perceptivo suficiente não exige teste; cenário com incerteza justificada mantém compromisso anterior ao dado. Não alterar o resultado histórico para satisfazer esse teste. |
| Extração/avaliação de feedback | Manifestação parcialmente adjudicada podia ser contada diretamente como sobreativação factual. | A contagem passa pelo parecer por critério e sua evidência. Reclamação sozinha não muda oportunidade ou qualidade; teste permanente protege essa separação. |

Uma violação confirmada na prosa não demonstra qual função Python causou a
decisão do narrador. O responsável avaliativo é `narrative_delivery`; localização
da causa no runtime exige as próximas tarefas. Este relatório distingue o
comportamento observado da atribuição causal ainda não demonstrada.

## Calibração e limite do aceite

Os seis julgamentos do gabarito histórico foram revistos, incluindo os dois
aspectos reservados de I0011. As cinco expectativas confirmadas mantiveram seus
resultados locais; a necessidade do teste, antes pendente, terminou revisada mas
indeterminada por falta de fonte. A espera não autorizada é achado adicional e
não altera o gabarito congelado.

As referências sintéticas passam **17 de 19 verificações**, incluindo o caso
reservado: falha conhecida, negativas legítimas e fonte insuficiente são
distinguíveis. As duas falhas restantes são do dashboard na AMV-05.
Nenhuma expectativa foi afrouxada para aprovar o avaliador.

Ainda não há confirmação longitudinal dos módulos. O snapshot integral do mundo
anterior a cada interação não está disponível; o conjunto de 34 objetivos não
fica aprovado pelos poucos aspectos confirmados neste recorte.
**G0 continua pendente da apresentação e revisão derivada no dashboard (AMV-05).**
Não é preciso jogar outra sessão para consultar estes novos pareceres.
