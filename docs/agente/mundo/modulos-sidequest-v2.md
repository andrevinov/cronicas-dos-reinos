# Módulos de sidequest v2

## Contrato público

A RM-03 reúne a cadeia de sidequests em três fachadas permanentes. Elas não
criam motores, writers, schedulers, RNG ou formatos persistidos novos:

- `sidequest_authoring.py`: gate de oportunidade, autoria do contrato e
  materialização condicionada à oferta narrada;
- `sidequest_lifecycle.py`: projeção de missões aceitas, progresso factual,
  fases, prazos, terminais, recompensas e reações;
- `canonical_quest_integration.py`: ponte sidequest→cânone e projeção
  cânone→oportunidade.

Os scripts das Tasks 40–49 continuam existindo como implementações internas e
portas de compatibilidade. Código novo deve depender das três fachadas, nunca de
funções privadas desses motores.

## Fluxo no turno

```text
cronica preparar
  → sidequest_authoring.prepare, somente com oportunidade positiva
  → sidequest_lifecycle.prepare, sempre para não esquecer missões aceitas

cronica concluir
  → sidequest_authoring.prepare_conclusion
  → writer canônico único
  → sidequest_authoring.install_conclusion
  → sidequest_lifecycle.install_conclusion
```

A integração canônica entra pela fachada tanto na seleção da cena quanto nos
terminais do lifecycle. Tudo permanece dentro do mesmo `preparar/concluir`; não
há terceira chamada de orquestração.

## Propriedades preservadas

- `--sem-oportunidade-sidequest` não abre autoria e não suprime causa NV-11
  vencida/alcançável;
- sem oferta literal, `mutacoes_sidequest` permanece zero;
- missões aceitas são projetadas read-only e todas recebem decisão factual;
- fatos e terminais exigem evidência literal;
- instalação, terminal, recompensa e reação continuam idempotentes/exactly-once;
- reação não reabre missão nem inventa capacidade;
- ponte canônica exige fonte, autoridade e camada de conhecimento válidas;
- nenhuma fachada controla decisão ou ação de Ren.

Tickets, journals, receipts e fragmentos históricos não são migrados. Os schemas
Task46/48/49 continuam aceitos nas bordas internas; `schema_fachada_modular: 2`
identifica somente o contrato agregado dos checks.

## Operação e manutenção

O jogo continua usando `cronica preparar/concluir`. Consultas e operações
dirigidas podem usar:

```bash
poetry run python ferramentas/sidequest_lifecycle.py status <mission-id>
poetry run python ferramentas/canonical_quest_integration.py oferecer <qsc-id> --npc <npc-id>
poetry run python ferramentas/canonical_quest_integration.py efeitos <mission-id>
```

Os três gates frios são:

```bash
poetry run python ferramentas/sidequest_authoring.py check
poetry run python ferramentas/sidequest_lifecycle.py check
poetry run python ferramentas/canonical_quest_integration.py check
```

Cada gate executa e identifica todos os validadores internos do seu domínio. O
preflight chama somente essas três fachadas, evitando apresentar as nove
subcapacidades históricas como módulos independentes.
