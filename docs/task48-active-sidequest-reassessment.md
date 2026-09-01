# Task 48 — Active Sidequest Reassessment

## Status e dependências

**Implementada.** A projeção read-only vive em `ferramentas/sidequests_ativas.py`,
é anexada por `cronica preparar` e faz parte do contrato operacional do
`AGENTS.md`.

Depende das Tasks 41–47 e preserva suas autoridades: Task42 governa pontes canônicas, Task43 recompensas, Task44 integridade adversarial, Task45 progresso factual, Task46 materialização transacional e Task47 a decisão explícita sobre **novas** oportunidades.

## Problema

O hot path atual trata `--sem-oportunidade-sidequest` como ausência completa das Tasks 40–45. Isso é correto para impedir custo permanente de **autoria**, mas também torna invisíveis missões já aceitas. Depois do aceite, fatos relevantes podem surgir durante investigação, combate, custódia, conversa ou deslocamento sem que `cronica preparar` projete fases, condições terminais ou pressões existentes.

O resultado observado em “Sete Nomes Antes do Amanhecer” foi uma missão ainda `aceita` e com progresso terminal pendente, embora Ren já tivesse produzido prova material, testemunha e participação institucional.

## Objetivo

Separar dois conceitos hoje fundidos:

1. **decisão de nova oportunidade** — continua governada pela Task47;
2. **reavaliação de missão aceita** — passa a ocorrer de forma compacta sempre que houver sidequest ativa.

`--sem-oportunidade-sidequest` passará a significar “não autorar nem oferecer uma nova sidequest neste turno”. Nunca significará “ignorar sidequests já aceitas”.

## Implementação

### Índice compacto de missões ativas

`narrador/oportunidades/estado.yaml` já é o índice autoritativo consultado para
localizar IDs em estado `aceita`; nenhum índice derivado novo é escrito. O teto
existente de duas sidequests aceitas permanece. A projeção não duplica contratos
nem fatos e abre diretamente, por caminho determinístico, no máximo dois
fragmentos Task45.

A porta read-only de domínio `sidequests_ativas.py projetar` devolve para cada missão:

- `mission_id`, `quest_id`, título e prazo;
- fases abertas, resolvidas, impossíveis ou indeterminadas;
- condições de sucesso e falha ainda não decididas;
- atores necessários e possibilidade de substituição;
- terminal atual;
- IDs de pressões adversariais já contratadas;
- digests do registro da missão e do fragmento Task45 lido.

A saída deve ser compacta e não expor segredos ao jogador. O ticket pode transportar somente IDs, digests e decisões exigidas; conteúdo reservado completo permanece no repositório.

### Integração ao `cronica preparar`

Depois da integração Task46 e antes da emissão final do ticket:

1. consultar o índice compacto;
2. se não houver missão aceita, preservar o resultado neutro atual;
3. se houver, projetar no máximo duas missões em ordem determinística;
4. anexar `sidequests_ativas`, `contrato_reavaliacao` e metadados compactos ao ticket;
5. não mutar progresso, agenda, mundo, transcrição ou lifecycle nesta etapa.

O caminho positivo da Task47 continua sendo o único capaz de chamar Task40 e autorar Task41/43/44/45 para uma nova oferta. O caminho negativo deixa de zerar a leitura Task45 somente quando já existir missão aceita.

### Relevância e economia

Enquanto o teto for duas missões aceitas, ambas podem ser projetadas sem heurística semântica ou scan. Se o teto aumentar no futuro, uma Task posterior deverá introduzir índice por local/NPC/assunto antes de ampliar o custo.

Orçamento proposto:

- zero sidequest aceita: saída e número de leituras equivalentes ao baseline, salvo a leitura do índice já necessária para confirmar o vazio;
- uma ou duas aceitas: no máximo um índice + dois fragmentos Task45;
- projeção combinada: até 6 KiB;
- zero RNG, scheduler, relógio ou escrita;
- mesmas duas chamadas de orquestração do turno comum.

### Observabilidade

A consulta `sidequests_ativas.py status <id>` aceita `mission_id` **ou**
`quest_id`, sem exigir payload de resolução. Ela distingue claramente:

- inexistente;
- oferecida/adiada;
- aceita;
- terminal;
- contrato Task45 ausente em missão aceita legada.

Isso elimina a necessidade de abrir manualmente arquivos reservados apenas para descobrir se uma sidequest continua ativa.

## O que esta Task resolve

- Sidequests aceitas deixam de desaparecer do hot path.
- A decisão negativa da Task47 deixa de bloquear progresso legítimo.
- O narrador recebe contexto operacional para reconhecer fatos relevantes.
- Estado ficcional e lifecycle tornam-se observáveis antes do prazo terminal.
- A economia continua limitada pelo teto já existente de missões ativas.

Esta Task ainda não registra fatos nem encerra missões; isso pertence à Task49.

## Testes

Foi criado `tests/test_active_sidequest_projection.py` e foram ampliados testes de
domínio existentes, sem nomes permanentes baseados no número da Task.

Cobertura obrigatória:

1. `--sem-oportunidade-sidequest` com zero missões aceitas não chama Task40 nem abre fragmentos Task41/44/45;
2. a mesma flag com uma missão aceita projeta somente seu estado Task45 e não autoriza nova oferta;
3. duas missões aceitas são ordenadas deterministicamente e respeitam o teto;
4. missões `oferecida`, `adiada`, `concluida`, `falhada` ou `expirada` não entram como ativas;
5. a projeção é read-only, verificada por hashes antes/depois em `TemporaryDirectory`;
6. omitir a decisão Task47 continua falhando antes do hot path;
7. flags positiva e negativa continuam mutuamente exclusivas;
8. a consulta aceita `mission_id` e `quest_id` e recusa ambiguidade;
9. orçamento de bytes, número de fragmentos e ausência de scan global são assertados em fixture controlada;
10. nenhuma assertion congela o estado vivo da campanha.

Regressões existentes a preservar:

- `tests/test_sidequest_opportunity_decision.py`;
- `tests/test_sidequest_integration_budget.py`;
- `tests/test_cronica_hotpath_rollout.py`;
- `tests/test_cronica_pending_gate.py`.

## Definition of done

- contrato negativo da Task47 atualizado em documentação, CLI e API;
- projeção ativa disponível no preparo e em consulta read-only;
- nenhum writer chamado durante projeção;
- testes de domínio passam em fixture isolada;
- `test-domain sidequests cronica`, `test-full` e `preflight` verdes;
- `AGENTS.md` descreve o comportamento já implementado.
