# Módulos do mundo causal v2

## Contrato público

A RM-04 reúne seis aliases históricos em três fachadas permanentes:

- `scene_world_projection.py`: projeção única de cena, permanência, incidentes,
  microeventos e condições persistentes;
- `world_boundary_resolution.py`: vivacidade em compressões temporais e lote de
  pendências do Mundo Vivo;
- `causal_narrative_routing.py`: arbitragem de matérias já autorizadas, incluindo
  pressão comprometida e evento canônico datado.

As fachadas não criam scheduler, fila, writer, RNG ou estado paralelo. Os
produtores anteriores continuam separados internamente e permanecem disponíveis
como portas de compatibilidade e reparo.

## Fluxo operacional

O turno ao vivo continua com duas chamadas de orquestração:

```text
cronica preparar
  → scene_world_projection, somente com gatilho espacial real
  → causal_narrative_routing, somente quando há matéria autorizada

cronica concluir
  → revalidação e confirmação pelos mesmos produtores
  → writer canônico único
```

Compressão temporal continua usando uma única consulta `endpoints.py fronteira`.
O endpoint delega a composição para `world_boundary_resolution` e não acrescenta
um ritual ao turno curto.

Quando a barreira bloquear o preparo, a resolução em lote passa pela fachada:

```bash
poetry run python ferramentas/world_boundary_resolution.py preparar
poetry run python ferramentas/world_boundary_resolution.py aplicar < plano.yaml
```

`resolver_fronteira.py` continua sendo o motor interno e a porta de
compatibilidade. Retry reaplica apenas o que ainda falta e não sorteia nem duplica
evento.

## Projeção espacial

Uma cena espacial pode consultar ecologia, reservar microevento ou incidente e
projetar condições ativas. Para avaliação, tudo isso constitui uma ativação de
`scene_world_projection`; as etapas continuam subcapacidades observáveis.

Preparação é read-only. Confirmação revalida o mesmo fingerprint antes de
consumir qualquer baralho. Permanência reutiliza a identidade
`local+data+período`, inclusive entre retries e `scene_id` distintos. Uma
condição persistente descreve contexto e nunca impõe por si teste, penalidade,
presença ou incidente.

## Fronteira do mundo

`world_boundary_resolution` só é elegível quando existe compressão temporal
material ou pendência vencida/alcançável. Turno curto não consulta vivacidade.

Ausência de causa, depois da cobertura completa dos domínios autorizados, produz
recibo de `calma_justificada`. Pendência que exige resolução permanece bloqueante;
evento canônico devido nunca aceita no-op.

A saída da fachada distingue:

- `sem_pendencias`, `gate_neutro_aplicado` e `retry_sem_duplicacao`: gate
  neutro, sem fato novo;
- `pendencias_projetadas`: decisão ainda sem materialização;
- `lote_aplicado`: plano ou grupo adversarial materializado, com recibos
  exactly-once do motor existente.

## Roteamento causal

O roteador recebe somente matérias com autorização e fonte causal explícitas. Ele
não consulta produtores nem abre fontes reservadas durante a ordenação.

A precedência é estável:

```text
evento canônico datado devido
→ pendência/pressão comprometida
→ perigo ou fronteira imediata
→ prazo e reação elegível
→ oportunidade e iniciativa incidental
```

`materia_selecionada` significa prioridade de atenção, não execução do efeito e
nunca decisão de Ren. Lista vazia produz `sem_materia`, sem fabricar ameaça.

## Telemetria e manutenção

Os aliases v1 continuam reconhecidos pelo analisador, mas custo e ativação fecham
uma única vez no módulo pai. Gate neutro, decisão e efeito material permanecem
estados distintos no ledger v2.

Checks públicos:

```bash
poetry run python ferramentas/scene_world_projection.py check
poetry run python ferramentas/world_boundary_resolution.py check
poetry run python ferramentas/causal_narrative_routing.py check
```

O preflight chama essas fachadas. A aceitação integrada de vivacidade permanece
uma regressão independente: ela prova o encadeamento, mas não vira quarto módulo.
