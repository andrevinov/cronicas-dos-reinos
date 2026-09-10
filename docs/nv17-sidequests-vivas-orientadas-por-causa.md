# NV-17 — Side quests vivas orientadas por causa

## Objetivo

A NV-17 elimina duas fontes de comportamento ruim sem voltar à autoria aleatória: o catálogo antigo de possibilidades frias deixa de competir com o runtime e uma necessidade real de NPC já estruturada pela NV-11 passa a ter caminho automático até `cronica preparar` quando vence e consegue alcançar Ren.

O princípio central é: **falta de missão aumenta atenção, não cria assunto**. Afinidade, presença, coincidência de local e `0 sidequests ativas` nunca são causa. A causa continua sendo um fato canônico dirigido do próprio NPC, referenciado por um passo NV-11.

## Migração única do catálogo legado

A migração vive em `ferramentas/sidequests_vivas.py migrar-legado` e possui três arquivos reservados em `narrador/sidequests-vivas/`:

- `evidencias-migracao.yaml`: somente mapeamentos explícitos `qsc -> plano NV-11`;
- `migracao-legado.yaml`: recibo terminal one-shot;
- `estado.yaml`: reservas do runtime, independente da migração.

Se o recibo terminal já existe, a função de migração retorna imediatamente e **não abre novamente** `narrador/sidequests-canonicas`. Quando não existe, cada detalhe/gate legado recebe exatamente um destino:

1. se houver mapeamento explícito, o plano é revalidado, o dono deve ser o mesmo NPC e a causa deve ser uma referência NV-11 canônica válida; o recibo guarda apenas `plano_id`, `causa_id` e `fonte_causa`;
2. sem esse mapeamento, a entrada é arquivada com `sem_evidencia_canonica_explicita_de_causa_viva_nv11`.

A conversão deliberadamente **não copia** título, objetivo, necessidade, terminal, reação, recompensa ou consequência do texto frio. O conteúdo vivo vem da causa NV-11. Os arquivos Task32/33 permanecem fisicamente disponíveis para auditoria e compatibilidade de histórico já materializado, mas não são fonte operacional da NV-17.

Na migração desta versão, as 36 entradas frias existentes não possuíam um mapeamento explícito para causa NV-11 e, por isso, foram arquivadas no recibo. Isso não afirma que os NPCs “não precisam de nada”; afirma apenas que o catálogo pré-escrito não é evidência de uma necessidade canônica atual.

## Contrato da necessidade viva

`sidequests_vivas.collect_due` parte do índice temporal NV-08. Ele lê somente IDs de planos em agendamentos `avaliar_plano_personagem` vencidos (mais uma referência explícita, quando fornecida) e abre apenas esses planos. Não existe scan de perfis de oportunidade ou de personagens.

Um plano só entra na projeção se:

- ainda estiver não-terminal;
- o passo estiver vencido;
- possuir `oportunidade_sidequest` validável pela NV-11;
- a referência da causa ainda corresponder ao estado canônico do próprio NPC;
- nenhuma missão/oportunidade já representar o mesmo `causa_id`.

A projeção compacta contém:

```yaml
id: scp-...
plano_id: ...
causa:
  tipo: necessidade|conflito|impedimento
  referencia: {arquivo: ..., caminho: ..., valor: ...}
  situacao: ...
dono: {tipo: leve|estrategico, id: ...}
bloqueio:
  estado_plano: ...
  condicoes: [...]
conhecimento: [...]
alcance:
  alcança_ren: true|false
  tipo: elenco_presente|contato_causal|mesmo_local_sem_presenca_confirmada|sem_rota_confirmada
reavaliacao:
  em: {data: ..., hora: ...}
  condicoes: [...]
stakes: {...}
protecoes:
  oferta_nao_e_aceite: true
  sem_terminal_inventado: true
  sem_recompensa_inventada: true
  sem_reacao_inventada: true
  agencia_de_ren_preservada: true
```

Os `stakes` são os `consequencias` já declarados no contrato NV-11. A NV-17 não os resolve e não deriva recompensa a partir deles.

## Alcance causal

Vencimento não é entrega. Uma causa só é selecionável automaticamente se também houver transporte causal até Ren.

- dono já presente no elenco corrente: alcançável;
- contato cuja entrega foi revalidada pelo motor social: alcançável;
- passo apontando o mesmo local de Ren sem presença confirmada: **não** alcançável; a coincidência apenas indexa a causa;
- nenhuma dessas condições: permanece viva, mas aguarda nova reavaliação/rota.

Assim Silva, Nera, Jack ou qualquer outro NPC que venha a possuir uma causa NV-11 real tem o mesmo caminho funcional. O sistema não contém exceções por nome e não promove uma “semente” antiga só porque Ren gosta do NPC ou está perto dele.

## Zero side quests ativas

O limite canônico continua em duas side quests ativas. Quando `ativas == 0`, uma causa **já validada, vencida e alcançável** recebe `prioridade_elevada_por_zero_ativas: true` e ganha precedência dentro das causas elegíveis. O valor zero nunca fabrica uma causa, não abre perfil legado e não relaxa alcance.

Se já existem duas missões ativas, nenhuma oportunidade nova é encaminhada.

## Uma oportunidade por janela

A janela NV-17 usa a mesma divisão operacional da NV-14: `data + período` (`amanhecer`, `dia`, `anoitecer`, `noite`). O primeiro encaminhamento válido é gravado no controle reservado `narrador/sidequests-vivas/estado.yaml`.

A reserva não cria fato narrativo. Sua função é apenas impedir que retries, outro `scene_id` ou múltiplos `preparar` na mesma janela substituam o sinal Task40. No máximo 32 janelas recentes são mantidas.

Ordem na primeira avaliação da janela:

1. causa NV-11 vencida e alcançável;
2. âncora nova surgida na própria cena;
3. nenhum sinal.

Se uma causa viva ocupa o slot e também foi declarada uma âncora nova, `ancora_manual_adiada: true`; não há segunda oportunidade na mesma janela.

## Semântica da decisão Task47

A CLI continua exigindo exatamente uma decisão Task47 para compatibilidade operacional. A semântica muda:

- `--sem-oportunidade-sidequest`: **não surgiu âncora nova nesta cena**;
- `--oportunidade-sidequest`: há uma âncora nova originada na própria cena;
- `--sidequest-plano`: compatibilidade para referenciar explicitamente um plano NV-11, submetido aos mesmos gates de vencimento e alcance.

Portanto, a negativa não participa da decisão sobre uma causa NV-11 já existente. Uma causa vencida e alcançável continua sendo projetada.

## Integração com Tasks 40–49

A NV-17 não cria um segundo motor de autoria. Ela transforma a causa selecionada no mesmo sinal `{plano_id, local_id, periculosidade, tier}` já aceito por `sidequests_personagens`/Task46. A partir daí o pipeline existente continua autoritativo:

`NV-11 -> NV-17 -> Task40 -> Task41/43/44/45 -> Task46 -> Task48/49`.

A materialização continua acontecendo apenas no `cronica concluir` quando a oferta efetivamente narrada aparece literalmente na transação. Se o narrador não oferecer, `oferta_nao_materializada` permanece o resultado e nenhuma missão é criada.

## Economia e segurança

Invariantes mensuráveis da NV-17:

- zero leitura do catálogo Task32/33 no runtime;
- migração com no máximo uma varredura, seguida por recibo terminal;
- IDs de planos vêm da agenda NV-08 ou referência explícita;
- no máximo oito causas dirigidas examinadas por chamada;
- no máximo duas side quests ativas projetadas;
- no máximo uma nova oportunidade por janela;
- nenhum scheduler novo;
- nenhum RNG novo;
- nenhuma chamada de IA;
- nenhuma varredura global de NPCs;
- presença não cria causa;
- ausência de missões não cria causa;
- reserva técnica não cria cânone;
- oferta não é aceite;
- somente oferta narrada pode materializar.

## Checks e testes

`sidequests_vivas.py check` valida o recibo da migração, estado de reservas e orçamento de duas missões ativas sem reabrir o catálogo legado. O preflight inclui esse check.

Os testes NV-17 são construídos sobre diretórios temporários e monkeypatches de portas, evitando depender dos valores atuais da campanha. Eles cobrem descoberta dirigida, ausência de criação por presença/zero missões, prioridade com zero ativas, limite de duas, estabilidade de janela, negativa incapaz de suprimir causa vencida, migração one-shot e integração da porta `cronica`.
