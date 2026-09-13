# RM-03 — Consolidação dos módulos de sidequest

## Status e dependências

**Proposta.** Depende das RM-01–RM-02.

## Objetivo

Substituir nove módulos planos por três módulos de domínio:

- `sidequest_authoring`;
- `sidequest_lifecycle`;
- `canonical_quest_integration`.

## Implementação

### Sidequest authoring

Criar uma fachada única para decisão de oportunidade, validação da âncora,
autoria, congelamento do contrato e materialização pela oferta. O caminho
negativo continua obrigatório, determinístico e barato; não abre autoria.

### Sidequest lifecycle

Unificar a projeção read-only de missões ativas, decisão factual no concluir,
progressão de fases, prazos, terminais, recompensa e reação. O contrato deve
preservar atomicidade, idempotência e evidência literal, sem fazer toda etapa
parecer um módulo ativado independentemente.

### Canonical quest integration

Unificar os dois sentidos da fronteira entre sidequest e cânone: oportunidade
reservada autorizada e ponte causal produzida por missão aceita. Sigilo,
autoridade e conhecimento permanecem guardrails explícitos.

Os scripts atuais podem permanecer como implementações internas durante a
migração. A fachada v2 deve ser o contrato público; remoção ou renomeação física
só ocorre depois que imports, documentação e testes tiverem destino registrado.

## Invariantes

- negativa de oportunidade não oculta causa válida já existente;
- oferta não narrada não materializa missão;
- missão aceita não é esquecida no hot path;
- progresso exige fato e evidência;
- terminal e recompensa são exactly-once;
- reação não reabre missão nem inventa capacidade;
- integração canônica não vaza segredo nem controla Ren.

## Testes

Consolidar testes por propriedades de domínio, preservando modos de falha. O
snapshot de Sete Nomes continua regressão histórica isolada, nunca módulo.
Atualizar `tests/historical-test-review.yaml` antes de retirar qualquer cobertura.

## Definition of done

- três fachadas v2 cobrem todas as nove subcapacidades v1;
- `cronica preparar/concluir` usa contratos v2 sem chamada extra;
- custos e ativações aparecem uma vez por módulo pai;
- estado e histórico de sidequests não sofrem migração destrutiva;
- perfis `sidequests`, `cronica` e `mundo` ficam verdes.
