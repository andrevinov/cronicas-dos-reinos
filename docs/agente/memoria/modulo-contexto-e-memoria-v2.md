# Contexto e memória v2

## Contrato público

`context_and_memory.py` é a fachada do módulo `context_and_memory`. Ela reúne,
sem mover as fontes atuais:

- política de acesso L0–L5 e seus tetos;
- contexto e memória de cena;
- retomada fria;
- persistência de fatos duráveis no concluir;
- separação entre conhecimento do narrador, mundo, NPCs, Ren e jogador.

`contexto.py` continua sendo a CLI de leitura. `cronica preparar/concluir` e as
portas de retomada usam a fachada na mesma orquestração existente. Os motores
`politica_acesso.py`, `memoria_cena.py` e `memoria_duravel.py` permanecem
internos e compatíveis; runtime, handoffs, fragmentos, transcrição, buffer e
writer não são migrados nem duplicados.

## Leitura econômica

L0 significa que o contexto já presente basta e não produz chamada. L1 entrega
estado quente; L2 é dirigido; L3, L4 e L4T exigem lacuna e escalada válidas.
Alvo histórico conhecido pode saltar a busca ampla, mas transcrição continua
exigindo L4 insuficiente.

Toda saída de `contexto.py` recebe `contexto_modular`, com nível, número de
fontes, teto, lacuna preservada, escalada justificada e indicação de leitura de
transcrição. O recibo é observacional: não afirma que toda lacuna foi resolvida
quando a própria consulta declara aprofundamento necessário.

O módulo não cria log no jogo, scan global ou cache persistente. O recibo de
memória de cena só pode ser reutilizado quando a base ainda está no contexto do
narrador. Retomada fria ignora recibos e entrega pacote completo.

## Persistência e conhecimento

Fato persistente continua sendo declarado em `memoria.fatos` no mesmo `cronica
concluir`. A fachada preserva validação literal, participantes, autoria,
proveniência e o guard social da RM-05 antes de delegar ao writer transacional.

Somente depois do writer retornar, `memoria_contexto` publica:

- fatos esperados, validados e confirmados;
- quantos produziram novo efeito naquele chamado;
- cobertura de evidência;
- tipos e camadas de destino, sem o conteúdo reservado.

Retry já registrado informa `retry_sem_duplicacao` e zero fatos novos. Rumor
permanece rumor; participante não destinatário não recebe informação; memória
do narrador não vira conhecimento de Ren ou NPC por inferência.

## Telemetria

O detector pós-hoc distingue:

- `contexto_l0_suficiente`;
- L1/L2 dirigido;
- aprofundamento L3/L4/L4T justificado;
- contexto obsoleto e leitura RAW ou repetida;
- memória consultada;
- memória durável materializada ou retry.

Tokens totais e não-cache permanecem no custo do pai. As subcapacidades
`routed_context_access`, `scene_and_durable_memory` e
`knowledge_layer_separation` expõem diagnóstico sem somar o custo novamente.

## Manutenção

O gate modular é read-only:

```bash
poetry run python ferramentas/context_and_memory.py check
```

Os perfis dirigidos são:

```bash
poetry run test-domain contexto
poetry run test-domain memoria
poetry run test-domain retomada
```
