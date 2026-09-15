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
  → sidequest_authoring.assess_opportunity, emite recibo objetivo em todo preparo instalado
  → sidequest_authoring.prepare, somente com oportunidade positiva
  → sidequest_lifecycle.prepare, sempre para não esquecer missões aceitas

cronica concluir
  → sidequest_authoring.prepare_conclusion
  → writer canônico único
  → sidequest_authoring.install_conclusion, emite recibo canônico da oferta materializada
  → sidequest_lifecycle.install_conclusion, emite um recibo canônico por missão reavaliada
```

A integração canônica entra pela fachada tanto na seleção da cena quanto nos
terminais do lifecycle. Tudo permanece dentro do mesmo `preparar/concluir`; não
há terceira chamada de orquestração.

## Propriedades preservadas

- `--sem-oportunidade-sidequest` não abre autoria e não suprime causa NV-11
  vencida/alcançável;
- a flag registra a percepção do narrador, mas não prova elegibilidade nem
  ausência; o recibo separa declaração, decisão efetiva e resultado esperado;
- somente predicados duros sustentados por fonte estruturada produzem
  `elegivel` ou `nao_elegivel`; falta de prova produz `indeterminado` e fica fora
  da pontuação até adjudicação;
- sem oferta literal, `mutacoes_sidequest` permanece zero;
- missões aceitas são projetadas read-only e todas recebem decisão factual;
- fatos e terminais exigem evidência literal;
- instalação, terminal, recompensa e reação continuam idempotentes/exactly-once;
- reação não reabre missão nem inventa capacidade;
- ponte canônica exige fonte, autoridade e camada de conhecimento válidas;
- oferta, resposta, progresso e terminal de sidequest produzem recibo de
  integração completo; ausência ou incompletude é falha de instrumentação, não
  prova de inatividade;
- nenhuma fachada controla decisão ou ação de Ren.

O `sidequest_authoring` 2.0.0 acrescenta o recibo read-only
`schema_avaliacao_oportunidade_sidequest: 1`; ele não escreve cânone, não revela
segredo e não introduz chamada de orquestração. Tickets, journals e fragmentos
históricos não são migrados. Os schemas
Task46/48/49 continuam aceitos nas bordas internas; `schema_fachada_modular: 2`
identifica somente o contrato agregado dos checks.

O `canonical_quest_integration` 2.0.0/régua 4.0.0 acrescenta
`schema_avaliacao_integracao_canonica: 1`. O recibo usa referência opaca da
missão e não publica ID de evento, intenção, fonte ou relação reservada. Ele
classifica apenas a obrigação da ponte e a presença do efeito estrutural no
ledger Task42. Oferta e progresso saudável provam cobertura sem multiplicar
acertos; resposta aceita e terminal são pontuáveis. Progresso que perdeu uma
reserva exigida é falha pontuável.

## Operação e manutenção

O jogo continua usando `cronica preparar/concluir`. Consultas e operações
dirigidas podem usar:

```bash
poetry run python ferramentas/sidequest_lifecycle.py status <mission-id>
poetry run python ferramentas/canonical_quest_integration.py oferecer <qsc-id> --npc <npc-id>
poetry run python ferramentas/canonical_quest_integration.py responder <mission-id> aceitar|adiar|recusar
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
