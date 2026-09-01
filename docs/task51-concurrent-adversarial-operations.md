# Task 51 — Concurrent Adversarial Operations & Decision Boundaries

## Status e dependências

**Implementada.** O domínio vive em `ferramentas/operacoes_concorrentes.py`,
integra a fronteira/checkpoint existentes e é verificado pelo preflight.

Depende da fila/fronteira do Mundo Vivo, da Task44, da Task50 e dos contratos existentes de encontros simultâneos. Não altera a autoridade do jogador sobre Ren.

## Problema

Uma facção pode ter motivo e recursos para agir contra dois alvos na mesma janela: atacar uma comitiva para tomar provas e pressionar simultaneamente o local onde testemunhas ou protegidos permanecem. O sistema atual resolve pendências individualmente e não representa de forma explícita:

- reserva independente de recursos;
- compromisso simultâneo antes da escolha de Ren;
- continuidade da operação não escolhida;
- atraso e meio pelo qual Ren descobre o segundo ataque;
- consequências de cada frente sem no-op conveniente.

Sem esse contrato, uma escolha difícil pode ser apenas aparência: o evento não escolhido pode desaparecer ou ser inventado depois da decisão.

## Objetivo

Representar operações concorrentes como ações reais do mundo, comprometidas antes da escolha do jogador, sem usar os mesmos recursos duas vezes e sem conceder informação impossível a Ren.

## Implementação

### Grupo de operações

Adicionar `grupo_operacoes` ao domínio de reação, contendo:

- ID estável do grupo;
- janela temporal compartilhada;
- operações membros, cada uma com alvo, local, objetivo e reação de origem;
- células, atores e recursos reservados por operação;
- dependências e bloqueios próprios;
- regra de simultaneidade;
- canais de percepção/comunicação disponíveis;
- estado de compromisso de cada operação;
- ordem determinística apenas para processamento técnico, nunca para prioridade ficcional.

Uma operação física só entra no grupo se atores e recursos distintos estiverem disponíveis. O mesmo agente, unidade, item único ou capacidade exclusiva não pode ser reservado em dois locais incompatíveis.

Os artefatos reservados ficam em
`narrador/sidequest-reacoes/operacoes-concorrentes/`: índice e estado mutável,
contratos imutáveis em `grupos/` e encontros congelados em `encontros/`. A
reação Task50 reivindicada deixa de emitir pendência individual; o grupo possui
uma única pendência até o compromisso atômico.

### Preparação e fronteira

Quando a janela é alcançada:

1. `resolver_fronteira.py preparar` projeta o grupo inteiro;
2. cada operação é validada contra estado, conhecimento, presença e recursos atuais;
3. operações válidas são comprometidas em lote antes de qualquer narração;
4. bloqueio causal elimina somente a operação afetada;
5. `aplicar` materializa todas as operações comprometidas e suas pendências;
6. o turno seguinte apresenta apenas sinais que Ren pode perceber legitimamente.

`resolver_fronteira.py preparar` classifica o grupo como
`comprometer_grupo_operacoes`. `aplicar` recebe a decisão no mesmo plano:

```yaml
lote_id: frn1.<token>
grupos_operacoes:
  - id: mundo-<id>
    token: <token-do-item>
    bloqueios: {}
```

O commit usa `runtime/operacoes-concorrentes-journal.yaml`: estado Task50,
reservas, encontros e fila do Mundo Vivo são preparados antes da primeira
escrita. Retry termina o journal sem duplicar efeitos. Depois, cada frente tem
pendência `resolver_operacao_adversarial` e resultado factual independente.

Escolher uma frente não cancela as outras. NPCs aliados e inimigos continuam agindo fora da presença de Ren. Resultados remotos só viram conhecimento de Ren quando um canal plausível os entrega.

`percepcao-ren` projeta somente os sinais do local informado e entregas já
realizadas. `entregar-informacao` exige canal declarado (`mensageiro`,
`sinal_magico` ou `testemunha`), prova literal, atraso mínimo e fatos dentro do
escopo congelado do canal.

### Limite de decisão de Ren

Quando Ren recebe informação suficiente para escolher, a narração apresenta situação e urgência, não um menu rígido. O jogador pode:

- permanecer em uma frente;
- tentar alcançar outra;
- dividir aliados;
- enviar aviso;
- abandonar ambas;
- propor qualquer ação coerente.

O sistema preserva tempos de deslocamento, capacidade de comunicação e consequências durante a decisão. Não move Ren nem escolhe prioridade por ele.

### Encontro e combate

Composição de inimigos, terreno, surpresa, objetivo tático e papel de especialistas são congelados antes da primeira rolagem. Um especialista pode usar o combate como distração para roubo, fuga ou extração sem precisar ser o combatente principal.

O snapshot de encontro inclui composição canônica resolvida por alias, avaliação
de ameaça para Ren solo e aliados realmente presentes, terreno, iniciativa,
surpresa, objetivo e rotas de retirada. `registrar-rolagem` fixa também o SHA do
snapshot; qualquer alteração posterior falha no replay e no `check`.

Antes da resolução mecânica:

- validar ficha/arquetipo dos adversários;
- avaliar ameaça para Ren solo e aliados realmente presentes;
- definir número de inimigos e recursos;
- registrar rotas de retirada que existam causalmente;
- impedir ajuste de dificuldade depois do resultado.

Protected Core não impede ataque ou combate. Ele impede apenas consequências graves automáticas sem autoridade; morte, captura e perda durante combate efetivamente resolvido seguem as regras e resultados normais.

## O que esta Task resolve

- Permite escolhas simultâneas realmente pesadas.
- Impede duplicação de recursos adversariais.
- Garante que a frente não escolhida continue existindo.
- Evita conhecimento instantâneo ou telepático para Ren.
- Suporta combate como distração para objetivo estratégico.
- Preserva agência, causalidade e dificuldade congelada.

## Testes

`tests/test_concurrent_world_operations.py` contém quinze cenários sintéticos em
`TemporaryDirectory`; os perfis `mundo`, `sidequests` e `cronica` incluem o
arquivo. O orçamento permanente está em
`baseline/concurrent-adversarial-operations-orcamento.yaml` e a telemetria
pós-hoc usa `concurrent_adversarial_operations`.

Cobertura obrigatória:

1. duas operações com recursos independentes são comprometidas no mesmo batch;
2. o mesmo recurso exclusivo em duas operações falha antes de efeitos;
3. bloqueio de uma operação não apaga a outra;
4. escolha ou presença de Ren em uma frente não conclui a outra como no-op;
5. operação remota continua processável fora da presença de Ren;
6. Ren não recebe informação sem canal e atraso compatíveis;
7. mensageiro, sinal mágico ou testemunha válida entregam somente o que poderiam saber;
8. ordem de aliases e operações é determinística;
9. retry do batch não duplica reservas, encontros ou consequências;
10. queda entre compromisso e materialização é recuperável;
11. composição mecânica fica imutável depois da primeira rolagem;
12. ator `fora_da_area` ou `indeterminado` não executa ação física local;
13. Protected Core bloqueia consequência automática não autorizada, mas não remove risco de combate;
14. uma saída plausível é perceptível/investigável quando a ameaça for letal ou esmagadora;
15. nenhuma assertion depende do estado vivo atual.

Regressões a preservar:

- fronteira batch do Mundo Vivo;
- encontros simultâneos e colapso de aliases;
- elegibilidade local de agentes;
- integridade adversarial e rede protegida;
- contratos de ameaça e adversários.

## Definition of done

- compromisso em lote é anterior à escolha de Ren;
- recursos são reservados uma única vez;
- conhecimento remoto possui canal explícito;
- encontros são congelados antes da rolagem;
- testes de recovery e idempotência verdes;
- `test-domain mundo sidequests cronica`, `test-full` e `preflight` verdes.
