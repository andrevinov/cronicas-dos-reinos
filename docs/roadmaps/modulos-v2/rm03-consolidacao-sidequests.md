# RM-03 — Consolidação dos módulos de sidequest

## Status e dependências

**Concluída em 2026-09-13.** Depende das RM-01–RM-02, já concluídas.

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

## Artefatos implementados

- `ferramentas/sidequest_authoring.py`: fachada de gate, autoria e oferta;
- `ferramentas/sidequest_lifecycle.py`: fachada de projeção, progresso e efeitos
  terminais;
- `ferramentas/canonical_quest_integration.py`: fachada bidirecional da fronteira
  canônica;
- `ferramentas/_sidequest_facade.py`: agregação read-only uniforme dos checks;
- `ferramentas/_cronica_nv14.py` e `ferramentas/sidequests_canonicas_cena.py`:
  hot path migrado para as fachadas, sem chamada adicional;
- `ferramentas/preflight.py`: nove checks públicos históricos consolidados em
  três checks modulares, preservando os validadores internos;
- `tests/test_sidequest_modules_v2.py`: contrato, roteamento, negativa, journal,
  aliases e preflight;
- `docs/agente/mundo/modulos-sidequest-v2.md`: contrato operacional permanente.

Nenhum ticket, journal, receipt, estado ou histórico de sidequest foi reescrito.
Os componentes anteriores permanecem como implementação interna e compatibilidade.

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
