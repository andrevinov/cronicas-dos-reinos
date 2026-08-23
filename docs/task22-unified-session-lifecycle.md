# Task 22 — Unified Session Lifecycle

Task 22 completa a transformação de `cronica` na porta operacional principal da campanha. A Task 21 comprimiu o ciclo de **turno**; esta task comprime o ciclo de **sessão** e o level-up sem criar novas autoridades canônicas.

## Sessão

### Status

```bash
cronica sessao status
```

Resume lifecycle, journals, checkpoint/memória e se existe nível já desbloqueado por milestone.

### Checkpoint de cena

```bash
cronica sessao checkpoint
```

É apenas uma porta de alto nível para a autoridade já existente `checkpoint.checkpoint(repo, "cena")`. Consolidação, lifecycle, Mundo Vivo, direções e regeneração de handoff/índice continuam pertencendo aos módulos atuais.

### Encerrar

```bash
cronica sessao encerrar
```

Delega **exatamente** a `checkpoint.checkpoint(repo, "sessao")`. Portanto produz os mesmos bytes que o fluxo anterior: consolida o buffer, encerra N como `entre_sessoes`, sincroniza mundo/lifecycle/direções, atualiza runtime e materializa handoff/índice de encerramento.

O comando só responde sucesso depois de `checkpoint.check` confirmar que a campanha ficou formalmente retomável. Se houver level-up desbloqueado e ainda não aplicado, o próximo passo o aponta explicitamente.

### Iniciar

```bash
cronica sessao iniciar
```

Delega **exatamente** a `sessoes.start_next`. A operação continua usando o journal/staging canônico já existente, cria somente N+1 e nunca copia a transcrição anterior. A nova transcrição nasce apenas com o cabeçalho da sessão.

### Recuperar

```bash
cronica sessao recuperar
```

Delega a `checkpoint.recover`. Não existe journal paralelo da Task 22. Uma queda durante consolidação, encerramento, início ou progressão mecânica usa a mesma rota de recuperação já testada no repositório.

## Progressão mecânica

O lifecycle não decide que Ren ganhou um nível. Primeiro precisa existir um milestone registrado. Na faixa 8–17 isso significa uma entrada válida da Task 19 em `narrador/juppongatana/estado-progressao.yaml`.

Depois do encerramento da sessão, um plano mecânico completo pode ser aplicado em uma única operação:

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

O plano informa **o que muda mecanicamente**, mas não controla `identidade.nivel`: esse campo é reservado ao lifecycle. O comando exige que `nivel_novo` seja exatamente o próximo nível e que `milestone_preparacao_id` corresponda ao registro que o desbloqueia.

A primeira versão aplica automaticamente somente a faixa protegida 8–17. Depois do 17, a progressão geral volta a depender do sistema de marcos e pode receber uma extensão posterior sem relaxar o gate atual.

## Atomicidade do level-up

Antes da primeira escrita, a CLI calcula todos os documentos finais. Em um único journal/staging ela instala:

1. `estado/estado-atual.yaml`;
2. `personagens/jogador/ficha.yaml`;
3. `personagens/jogador/resumo-de-poderes.md`;
4. `sessoes/NNN/experiencia.md`;
5. `runtime/contexto.yaml`;
6. `runtime/cena.yaml`;
7. `sessoes/NNN/handoff.yaml`;
8. `sessoes/index.yaml`.

Os espelhos entre estado e ficha são sincronizados pelo mesmo mecanismo do consolidador. Assim nível, PV, Ki, CA e dinheiro não podem ficar divergentes quando o plano mexer nesses campos.

Se o processo cair depois de uma ou mais escritas staged, o journal permanece e `cronica sessao recuperar` ou o legado `checkpoint.py recuperar` termina os mesmos bytes sem recalcular o level-up.

## Equivalência e compatibilidade

As primitivas anteriores continuam válidas:

- `checkpoint.py cena|sessao|recuperar`;
- `sessoes.py iniciar`;
- `consolidar.py ...`;
- `progressao_juppongatana.py ...`;
- toda a Task 21, preservada em `_cronica_turn_core.py`.

Testes com repositórios gêmeos comparam os bytes produzidos pelo lifecycle unificado com os bytes produzidos pelas operações legadas. A Task 22 não ganha permissão para produzir uma versão “equivalente o bastante”.

## Benchmark

A telemetria pós-hoc reconhece `cronica sessao checkpoint|encerrar|iniciar|recuperar` e `cronica progressao aplicar` como operações mutantes. Ganho percentual de ferramentas ou inferências só será declarado depois de um rollout real; a implementação apenas reduz a quantidade de comandos que o agente precisa orquestrar manualmente.
