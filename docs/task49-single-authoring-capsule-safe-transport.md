# Task 49 — Single Authoring Capsule & Safe Transport

## Problema observado

No primeiro rollout pós-Task46, a oportunidade e a autoria funcionaram, mas o agente precisou redescobrir quatro contratos internos (Tasks 41/43/44/45) e tentou transportar um payload grande por uma sessão de shell interativa. Isso produziu erros de schema e, no pior caso, truncamento do JSON antes de `cronica concluir`.

## Contrato operacional

Task49 não cria outro motor. `poetry run cronica` passa por `cronica_task49.py`, um adapter sobre a porta 47/48 já existente.

Quando Task40 não produz material, nada muda. Quando a oportunidade entra no ticket, a mesma saída de `cronica preparar` recebe `contrato_autoria_sidequest`, com uma interface única:

```text
sidequest_emergente
├── oferta
└── capsula_autoral
    ├── schema: 1
    ├── aventura
    ├── recompensas
    ├── adversidade
    └── progressao
```

A saída lista campos de topo, enums permitidos e o pequeno contexto necessário (intenções canônicas candidatas, Juppongatana disponível e envelope de recompensa). O agente não precisa abrir documentação, testes ou implementação para descobrir as quatro APIs internas.

## Compilação sem nova autoridade

`capsula_autoral` não substitui os validadores existentes. Antes do writer, ela é projetada deterministicamente para:

- `aventura` → `quest` Task41;
- `recompensas` → `contrato_recompensa` Task43;
- `adversidade` → `contrato_adversarial` Task44;
- `progressao` → `contrato_progressao` Task45.

Depois disso, Task46 executa exatamente os mesmos validadores e a mesma instalação journalada de antes. Chave extra, enum inválido, recompensa fora do envelope, capacidade inventada, conhecimento inexistente, agência futura de Ren ou consequência incompatível continuam falhando antes do writer.

Payload Task46 antigo continua aceito para recovery de tickets/journals já iniciados.

## Transporte

A porta continua sendo `cronica concluir`. O contrato manda enviar um único JSON completo por stdin no mesmo processo, sem `write_stdin` interativo e sem arquivo temporário. Task49 não cria arquivo de transporte, scheduler, RNG, relógio, estado persistente nem chamada adicional.

## Economia

- turno neutro: byte-logicamente igual ao fluxo 47/48;
- Task40–45 no neutro: 0 leituras;
- chamadas de orquestração: 2 (`preparar` + `concluir`);
- contrato da cápsula: <= 3 KiB e só aparece no turno raro;
- cápsula recebida: <= 64 KiB antes dos limites mais estritos dos validadores internos;
- writes novos: 0;
- scheduler/RNG/scan global/relógio paralelo: 0.

## Regressões obrigatórias

1. cápsula válida compila exatamente para o bloco Task46 antigo;
2. os validadores 41/43/44/45 continuam aceitando o compilado sem alteração semântica;
3. chave extra na cápsula falha antes da delegação;
4. enum inválido continua falhando no validator proprietário;
5. payload Task46 legado permanece aceito;
6. turno neutro não recebe contrato autoral;
7. preparação rara entrega contrato autocontido na mesma chamada;
8. JSON grande com português, travessões e Unicode atravessa stdin sem corrupção;
9. `poetry run cronica` aponta para o adapter Task49 sem criar um terceiro comando de orquestração.
