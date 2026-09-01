# Task 50 — Sidequest Success Fallout & Adversarial Reactions

## Status e dependências

**Planejada.** Este documento não autoriza reação no jogo antes da implementação.

Depende do terminal factual da Task49, da autoridade adversarial da Task44, da ponte canônica da Task42 e da fila existente do Mundo Vivo. Não altera contratos adversariais históricos.

## Problema

O modelo atual cobre consequências de falha e inação congeladas antes do aceite, mas não possui uma camada explícita para repercussões causadas pelo **sucesso** ou por progresso excepcional do jogador.

Uma missão simples pode produzir fatos que mudam o mundo: uma célula descoberta, agente capturado, testemunha preservada, provas apreendidas ou rota institucional exposta. Encerrar a missão e esquecer esses fatos torna antagonistas passivos. Acrescentar novos riscos ao contrato original depois do resultado, porém, violaria a integridade adversarial.

## Objetivo

Criar contratos imutáveis de reação causal derivados de fatos novos, sem:

- reabrir a missão concluída;
- ampliar retroativamente seus stakes;
- exigir que Ren aceite uma quest para o antagonista agir;
- conceder conhecimento, presença ou capacidade por conveniência;
- transformar toda repercussão em combate obrigatório.

## Implementação

### Novo domínio: reação de sidequest

Adicionar uma porta de domínio, preferencialmente `reacoes_sidequest.py`, com artefatos reservados próprios. Cada reação possuirá:

- `reaction_id`, missão e quest de origem;
- fato causal de progresso ou terminal;
- instante em que o fato se tornou canônico;
- antagonista responsável e objetivo atual;
- capacidades canônicas disponíveis;
- conhecimentos canônicos disponíveis e respectivas fontes;
- alvos possíveis;
- janela temporal mínima/máxima;
- alternativas operacionais mutuamente exclusivas ou combináveis;
- recursos exigidos;
- gravidade, impacto e reversibilidade;
- bloqueios causais;
- relação opcional com direção/ponte canônica;
- estado `planejada`, `elegivel`, `comprometida`, `resolvida` ou `cancelada`.

O contrato é criado somente depois que o fato-gatilho existe, mas antes de qualquer resolução, encontro ou rolagem da reação. Ele não modifica bytes Task44 da missão de origem.

### Três saídas possíveis

A avaliação produz exatamente uma classificação:

1. `reacao_mundo` — a facção age independentemente de Ren aceitar missão;
2. `oportunidade_sucessora` — existe necessidade/proposta que ainda exige o gate Task47 e oferta literal;
3. `sem_reacao` — os fatos não sustentam ação material naquele momento.

Uma reação do mundo pode posteriormente gerar uma sidequest, mas não nasce como oferta automática. Um ataque, resgate de prisioneiro ou fraude institucional é ação da facção, não pedido ao protagonista.

### Conhecimento e capacidade

O planejador pode usar somente:

- conhecimentos já registrados no agente/facção;
- informações adquiridas por evento canônico posterior;
- capacidades operacionais já existentes;
- presença/mobilidade compatível para atores físicos;
- recursos ainda não comprometidos em outra ação.

Direção canônica pode aumentar prioridade e fornecer ponte temática, mas nunca substitui prova de conhecimento, capacidade ou presença.

### Integração com Mundo Vivo

Reação `elegivel` entra na agenda/fila já existente com `reaction_id`, janela e condição. Não será criado scheduler paralelo.

Ao vencer a condição:

1. a fronteira materializa uma pendência específica;
2. a resolução seleciona uma alternativa autorizada;
3. a alternativa e seus recursos tornam-se `comprometidos` antes da narração;
4. preparação de combate ou especialidade ocorre antes de qualquer rolagem;
5. o resultado factual encerra a reação sem reabrir a sidequest original.

### Reações jurídicas, furtivas e violentas

O contrato não privilegia automaticamente combate. Um antagonista competente escolhe o método coerente com objetivo, custo e exposição, por exemplo:

- ordem de soltura fraudulenta;
- corrupção ou substituição de agente público;
- extração furtiva;
- destruição de prova;
- assassinato de testemunha;
- invasão aberta;
- emboscada para criar distração.

Cada alternativa precisa de capacidade própria. “Encontrada morta na cela” é resultado de uma operação bem-sucedida, não consequência escolhida depois que a cena acabou.

## O que esta Task resolve

- Antagonistas reagem ao sucesso e às descobertas de Ren.
- Investigações podem escalar organicamente para novas situações e combates.
- Sidequests mantêm escopo e terminal claros.
- Stakes antigos permanecem imutáveis e auditáveis.
- Ações hostis não dependem de uma oferta aceita pelo jogador.
- Direções canônicas produzem pressão sem virar trilhos ou onisciência.

## Testes

Criar `tests/test_sidequest_success_reactions.py`.

Cobertura obrigatória:

1. terminal de sucesso pode gerar contrato de reação sem reabrir a missão;
2. progresso não terminal excepcional também pode ser gatilho quando declarado;
3. bytes do contrato Task44 original permanecem idênticos;
4. planejamento reservado não serve como prova de condição;
5. capacidade ausente bloqueia a alternativa correspondente;
6. conhecimento ausente bloqueia ação sobre alvo desconhecido;
7. presença física incompatível bloqueia ator local;
8. direção canônica isolada não autoriza ação;
9. `reacao_mundo` entra na fila existente sem criar scheduler;
10. `oportunidade_sucessora` não materializa sidequest antes de oferta e aceite;
11. `sem_reacao` não cria arquivos ou pendências espúrias;
12. replay da avaliação não duplica contrato nem pendência;
13. alternativas mutuamente exclusivas não são materializadas juntas;
14. gravidade e Protected Core continuam passando pela Task44/rede protegida;
15. recursos já comprometidos não podem ser reutilizados.

Todos os testes funcionais usam repositórios temporários. Nomes e números da campanha real só aparecem em fixture histórica explicitamente justificada ou no teste end-to-end da Task53.

## Definition of done

- reação possui domínio e schema próprios;
- contratos antigos são byte a byte imutáveis;
- Mundo Vivo recebe apenas reações elegíveis;
- capacidade/conhecimento/presença são gates obrigatórios;
- nenhuma ação depende de RNG ou scheduler novo;
- `test-domain sidequests mundo`, `test-full` e `preflight` verdes.
