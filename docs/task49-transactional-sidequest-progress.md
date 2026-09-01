# Task 49 — Transactional Sidequest Progress

## Status e dependências

**Planejada.** Não é contrato operacional até implementação, testes e atualização explícita do roteador.

Depende da projeção read-only da Task48 e reutiliza Task42–46. Não cria um lifecycle paralelo.

## Problema

Task45 aceita fatos canônicos por comando explícito, mas o fluxo `cronica preparar → narrar → cronica concluir` não exige que o narrador classifique os acontecimentos de uma missão ativa. A transcrição pode registrar um fato terminal enquanto o fragmento de progresso permanece atrasado.

Também não há integração transacional confortável para um fato produzido no próprio turno: a evidência ainda não existe na transcrição antes do writer, mas registrar o turno e só depois atualizar a sidequest abre uma janela de falha parcial.

## Objetivo

Permitir que o mesmo `cronica concluir`:

1. registre a cena;
2. registre fatos de progresso com evidência literal da própria cena;
3. atualize fases e condições;
4. reconheça substitutos permitidos;
5. encerre a missão exatamente uma vez quando a política factual for satisfeita.

## Implementação

### Decisão explícita por missão ativa

O `contrato_reavaliacao` emitido pela Task48 exigirá, para cada missão projetada, exatamente uma decisão no payload de conclusão:

- `sem_fato_sidequest`: o turno não produziu fato capaz de alterar fase/condição;
- `fatos_sidequest`: lista compacta de fatos factuais e seus efeitos declarados.

Omissão ou conflito falham antes de qualquer escrita. A decisão não interpreta palavras-chave nem exige que todo diálogo produza progresso; ela apenas impede esquecimento silencioso.

Cada fato terá:

- ID estável no domínio da missão;
- descrição factual curta;
- evidência literal contida em `narracao` ou `resumo`;
- fases afetadas e novo estado permitido;
- condições de sucesso/falha afetadas;
- atores envolvidos;
- substituição de ator, quando aplicável;
- visibilidade e fonte transacional.

### Evidência da própria transação

Antes da escrita, o integrador valida que o trecho de evidência existe literalmente no payload narrativo. O journal Task46/49 guarda:

- ID da transação;
- digest da narração e do resumo;
- fatos normalizados;
- estado anterior esperado dos fragmentos;
- bytes finais staged.

Depois que o writer registra a cena, a evidência passa a apontar para a transcrição canônica e para a transação. Falha entre writer e instalação do progresso é recuperada pelo mesmo journal, sem duplicar turno, fato, recompensa ou terminal.

### Substituição de atores

Quando uma fase declarar `substituicao_permitida: true`, o fato poderá apresentar ator substituto. A validação exigirá:

- presença ou participação canônica;
- capacidade funcional compatível com a fase;
- evidência literal da atuação;
- ausência de segredo ou autoridade inventada;
- registro do ator efetivo no histórico da fase.

Assim, um oficial competente como Luath pode exercer a verificação institucional sem reescrever o verificador originalmente proposto.

### Terminal factual

Depois de aplicar todos os fatos:

1. recalcular políticas de sucesso e falha;
2. recusar sucesso e falha simultâneos;
3. usar `canon_bridge_runtime.finish` para o terminal;
4. delegar recompensa à Task43 exatamente uma vez;
5. registrar resultado e gatilho no fragmento Task45;
6. não materializar reação pós-sucesso nesta Task.

O terminal depende somente de fatos já registrados. Planejamento, resumo inferido ou possibilidade futura não satisfazem condições.

## O que esta Task resolve

- Elimina o atraso entre narrativa e progresso mecânico da sidequest.
- Faz o narrador reavaliar explicitamente missões ativas.
- Permite caminhos emergentes e substitutos sem exigir o local ou NPC inicialmente proposto.
- Encerra a missão no momento factual correto, não apenas no prazo.
- Preserva atomicidade, idempotência e autoridade das Tasks 42–45.

## Testes

Criar `tests/test_transactional_sidequest_progress.py` e ampliar a matriz de lifecycle existente.

Cobertura obrigatória:

1. missão ativa projetada exige `sem_fato_sidequest` ou `fatos_sidequest`;
2. decisão `sem_fato` registra o turno sem alterar bytes Task45;
3. evidência ausente da narração/resumo falha antes do writer;
4. fato válido resolve fase e condição na mesma transação lógica;
5. substituto permitido e competente é aceito e registrado;
6. substituto proibido, ausente ou sem capacidade é recusado;
7. política `todas` não termina com condição parcial;
8. satisfação completa termina a missão e entrega recompensa uma vez;
9. sucesso/falha simultâneos falham fechado;
10. retry do mesmo ticket não duplica transcrição, fato, terminal ou recompensa;
11. falha simulada antes do writer, após o writer e durante instalação staged é recuperável;
12. ticket obsoleto por mudança concorrente de progresso é recusado;
13. sidequest terminal não pode receber novo fato comum;
14. provas reservadas não vazam na projeção pública.

Usar `TemporaryDirectory` para todos os cenários funcionais. Eventual snapshot histórico deve declarar natureza, instante e motivo conforme a política permanente.

Regressões a preservar:

- `tests/test_sidequest_progression_deadlines_consequences.py`;
- `tests/test_sidequest_lifecycle_matrix.py`;
- `tests/test_sidequest_integration_transaction.py`;
- `tests/test_canon_bridge_rewriter.py`;
- `tests/test_quest_rewards_discoveries_losses.py`;
- testes de idempotência de `cronica concluir`.

## Definition of done

- decisão de progresso incorporada ao contrato de conclusão;
- journal único cobre turno + fatos + terminal;
- substituição de atores possui validação causal;
- nenhum parse semântico automático de prosa;
- testes de crash/retry e exatamente-once verdes;
- `test-domain sidequests cronica sessoes`, `test-full` e `preflight` verdes.
