# Task 45 — Sidequest Progression, Deadlines & Consequences

## Objetivo

Fazer sidequests emergentes continuarem existindo no mundo depois do aceite. A Task45 mantém progresso por fatos canônicos, disponibilidade de atores, prazo, condições de sucesso/falha e consequências já materializadas.

Ela **não** cria uma segunda máquina de sidequests. O lifecycle continua em `oportunidades.py`; o relógio continua em `mundo.py`; a fronteira continua na fila de pendências; Task42 continua governando a relação com o cânone; Task43 continua governando recompensa/perda; Task44 continua governando stakes e autoridade adversarial.

## Contrato de progressão

Depois de Task41 + Task43 + Task44 e antes do aceite, `progressao_sidequests.py registrar-contrato` congela somente o que faltava para executar a quest:

- política de sucesso: todas ou qualquer condição factual;
- política de falha: todas ou qualquer condição factual;
- dependências de atores por fase e se substituição é possível;
- efeitos de estado de NPC associados a cada escalada terminal Task44.

Morte, desaparecimento, prisão ou incapacidade não podem ser adicionados neste ponto se forem incompatíveis com a gravidade, classe de impacto e reversibilidade já congeladas pela Task44.

## Progresso por fatos, não checklist

`progressao_sidequests.py fato` recebe um fato com fonte/evidência literal canônica. Esse fato pode mudar:

- uma fase para `possivel`, `impossivel` ou `resolvida`;
- uma condição de sucesso/falha para `satisfeita` ou `inviavel`.

A Task45 não interpreta palavras-chave, não soma porcentagem e não presume ação futura de Ren. O fato precisa já existir no cânone.

## Disponibilidade de personagens

Atores da quest têm projeção compacta de disponibilidade. `vida.estado` igual a `morto`, `incapacitado`, `desaparecido` ou `preso` torna o ator indisponível. Uma fase que exige esse ator, não permite substituição e ainda não foi resolvida torna-se `impossivel`.

NPC novo ainda reservado é `reservado_nao_presente`, não morto nem automaticamente inviável.

## Prazo e consequência

Task45 não cria scheduler. `reconciliar` compara a janela da missão com o relógio existente.

- `oferecida`/`adiada` + prazo vencido → `expirada`;
- `aceita` + prazo vencido → `falhada`;
- falha aceita não executa uma punição inventada: emite uma pendência `resolver_sidequest` na **fila já existente do Mundo Vivo**.

A pendência contém apenas IDs de escaladas de falha/inação que já estavam congeladas pela Task44. Resolver exige prova literal da condição e passa por `resolve_escalation_choice` + `authorize_sidequest_consequence`.

## Tomas morto com bilhete

Esse caso só é válido se, antes do aceite:

1. Tomas estiver em `alvos_em_risco`;
2. uma escalada Task44 declarar condição, capacidade, conhecimento, gravidade `grave`, impacto `vida`, reversibilidade `irreversivel` e consequência compatível;
3. Task45 mapear essa escalada para `vida.estado: morto`;
4. no desfecho, uma fonte canônica provar literalmente que a condição ocorreu.

O prazo pode tornar a consequência devida; ele não cria a morte retrospectivamente.

## Protected Core

Task45 não possui exceção própria. Toda consequência passa pela Task44. Sidequest lateral continua sujeita ao Protected Core procedural; sidequest formalmente canônica só pode atravessar o guardrail com a autoridade Task42 que a Task44 exige.

## Recompensas e perdas

Sucesso só pode ser encerrado quando a política factual estiver satisfeita. Depois do lifecycle `concluida`, Task45 delega a entrega a Task43, preservando exatamente-once.

Task45 não reabre nem prolonga a missão para acomodar repercussões do sucesso.
Depois do terminal factual, a Task50 pode avaliar aquele fato e criar uma reação
causal separada, preservando os bytes deste progresso e do contrato Task44.

Falha/prazo podem delegar perdas contratadas a Task43 durante a resolução da consequência. Ausência de contrato ou prova continua impedindo a perda.

## Cânone

Todo desfecho terminal usa `canon_bridge_runtime.finish`. Falha pode liberar/reancorar a **forma** futura do cânone, mas nunca satisfaz nem apaga uma intenção canônica por si só. Convergência/transformação concluída ainda precisa da evidência Task42 para suprimir realização padrão.

## Economia

- zero scheduler novo;
- zero RNG;
- zero scan global;
- fragmento Task45 por quest <= 24 KiB;
- projeção de pendência <= 8 KiB;
- no máximo 48 fatos e 24 atores por quest;
- no máximo 2 pendências Task45, alinhado ao teto já existente de 2 sidequests aceitas;
- desde a Task48, turno comum projeta read-only no máximo dois fragmentos Task45 de missões aceitas;
- a Task49 valida evidência do próprio turno, instala fatos com journal e chama os terminais idempotentes desta Task;
- autoria/materialização de nova sidequest continua reservada à Task46.
