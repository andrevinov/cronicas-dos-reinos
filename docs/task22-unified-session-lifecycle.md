# Task 22 — Unified Session Lifecycle

Task 22 completa a transformação de `cronica` na porta operacional principal da campanha. A Task 21 comprimiu o ciclo de **turno**; esta task comprime o ciclo de **sessão** e o level-up sem criar novas autoridades canônicas.

## Sessão

### Status / retomada

```bash
cronica sessao status
```

Além de lifecycle/journal/progressão, a porta pública devolve `retomada`: uma projeção quente de data, hora, localização, recursos e último resumo explícito. Ela usa runtime estruturado + overlay de eventos pendentes ou ledger/handoff e **não abre transcrição**. Campos livres legados como `periodo_do_dia` ou prazos textuais não entram nessa projeção justamente porque podem envelhecer sem que data/hora/deltas estejam errados.

Se `retomada` responder à lacuna, parar. Não chamar `contexto.py retomada`, abrir handoff cru ou ler implementação apenas para reconstruir o mesmo presente.

### Checkpoint de cena

```bash
cronica sessao checkpoint
```

É apenas uma porta de alto nível para `checkpoint.checkpoint(repo, "cena")`. Consolidação, lifecycle, Mundo Vivo, direções e regeneração derivada continuam pertencendo aos módulos atuais.

### Encerrar

```bash
cronica sessao encerrar
```

Delega **exatamente** a `checkpoint.checkpoint(repo, "sessao")`: consolida o buffer, encerra N como `entre_sessoes`, sincroniza mundo/lifecycle/direções, atualiza runtime e materializa handoff/índice. Só responde sucesso depois de `checkpoint.check` confirmar estado retomável.

### Iniciar

```bash
cronica sessao iniciar
```

Delega **exatamente** a `sessoes.start_next`, usando o journal/staging canônico, criando somente N+1 e nunca copiando a transcrição anterior. A nova transcrição nasce apenas com cabeçalho.

A porta pública acrescenta ao resultado duas projeções read-only:

- `recap_sessao_anterior`: últimos resumos explícitos do handoff compacto de N;
- `retomada`: presente estruturado de N+1.

Esses blocos existem para que o pedido “inicie uma sessão e resuma a anterior” seja atendido pela **mesma chamada que abre a sessão**. Não há chamada obrigatória posterior a `contexto.py retomada` nem leitura de transcrição/handoff cru.

### Recuperar

```bash
cronica sessao recuperar
```

Delega a `checkpoint.recover`. Não existe journal paralelo da Task 22. Uma queda durante consolidação, encerramento, início ou progressão mecânica usa a mesma rota de recuperação já testada.

## Progressão mecânica

O lifecycle não decide que Ren ganhou nível. Primeiro precisa existir um milestone registrado. Na faixa 8–17 isso significa uma entrada válida da Task 19 em `narrador/juppongatana/estado-progressao.yaml`.

Depois do encerramento, um plano mecânico completo pode ser aplicado em uma única operação:

```bash
cronica progressao aplicar <<'YAML'
schema_progressao_mecanica: 1
nivel_novo: 8
milestone_preparacao_id: 0123456789abcdef01234567
alteracoes_ficha:
  - caminho: combate.pontos_de_vida.maximos
    valor: 59
  - caminho: combate.pontos_de_vida.atuais
    valor: 59
  - caminho: recursos_de_classe.ki.pontos_maximos
    valor: 8
  - caminho: recursos_de_classe.ki.pontos_atuais
    valor: 8
resumo_de_poderes: |
  # Resumo de poderes de Ren
  Ren é um monge do Caminho da Sombra, nível 8.
  ...
marco: Primeiro Juppongatana neutralizado de forma durável.
motivo: O milestone registrado desbloqueou o nível 8.
escolhas_pendentes: []
YAML
```

O plano informa **o que muda mecanicamente**, mas não controla `identidade.nivel`: esse campo é reservado ao lifecycle. `nivel_novo` precisa ser exatamente o próximo nível e `milestone_preparacao_id` precisa corresponder ao registro que o desbloqueia.

A primeira versão aplica automaticamente somente a faixa protegida 8–17.

## Atomicidade do level-up

Antes da primeira escrita, a CLI calcula todos os documentos finais. Em um único journal/staging instala:

1. `estado/estado-atual.yaml`;
2. `personagens/jogador/ficha.yaml`;
3. `personagens/jogador/resumo-de-poderes.md`;
4. `sessoes/NNN/experiencia.md`;
5. `runtime/contexto.yaml`;
6. `runtime/cena.yaml`;
7. `sessoes/NNN/handoff.yaml`;
8. `sessoes/index.yaml`.

Os espelhos entre estado e ficha são sincronizados pelo mesmo mecanismo do consolidador. Se cair após uma ou mais escritas staged, `cronica sessao recuperar` ou `checkpoint.py recuperar` termina os mesmos bytes sem recalcular o level-up.

## Equivalência e compatibilidade

Continuam válidos:

- `checkpoint.py cena|sessao|recuperar`;
- `sessoes.py iniciar`;
- `consolidar.py ...`;
- `progressao_juppongatana.py ...`;
- toda a Task 21, preservada em `_cronica_turn_core.py`.

As projeções read-only de recap/retomada não mudam os bytes canônicos produzidos por abrir/fechar sessão; apenas evitam que o agente reabra fontes já resumidas.

## Benchmark

A telemetria pós-hoc reconhece `cronica sessao checkpoint|encerrar|iniciar|recuperar` e `cronica progressao aplicar` como operações mutantes. Ganho percentual de ferramentas ou inferências só será declarado depois de rollout real; a implementação não inventa economia por estimativa.
