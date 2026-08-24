# Task 31 — Retire Procedural Side Quest Gate

## Problema

O sistema anterior de side quests tentava obter raridade por encontro:

1. Ren encontrava um NPC elegível;
2. um baralho global consumia uma ficha;
3. oito fichas produziam `nada` e duas `oportunidade`;
4. Adventure Drought Pressure podia promover até três fichas `nada`;
5. uma oportunidade abria um perfil procedural do NPC e escolhia uma necessidade;
6. a necessidade virava apenas `potencial`, ainda dependente de avaliação do narrador.

O sistema era determinístico e barato por operação, mas não resolveu o problema de produto. Depois de muitos encontros, ele produziu candidatos que foram repetidamente descartados por não combinarem com o cânone e não entregou side quests com peso dramático real.

A nova direção é oposta: **side quest não nasce de sorteio. Side quest nova exige fonte canônica explícita.** A Task 31 remove o gate operacional; a Task 32 criará o engine canônico secreto.

## O que foi retirado

O hot path de encontro não executa mais:

- sorteio 8 `nada` : 2 `oportunidade`;
- promoção de `nada` pela Adventure Drought Pressure;
- leitura de `narrador/oportunidades/estado.yaml` só para encontro;
- abertura de perfil procedural;
- seleção de `necessidade` procedural;
- criação de `pendencias_avaliacao` por encontro;
- escrita de estado de oportunidades por encontro.

`sidequest_gate_v2.py` permanece apenas como **nome de compatibilidade** porque `cena_mundo.py` já o instala como adaptador. Sua implementação agora resolve a identidade do NPC e devolve:

```yaml
resultado: interacao_normal
motivo: gate_procedural_retirado
sidequest:
  gate_procedural: retirado
  nova_origem: canonica_explicita
```

Nenhum draw, pressão ou perfil é consultado.

## Defesa em profundidade

A aposentadoria não depende apenas do adaptador público.

Todos os 12 perfis procedurais do índice atual foram marcados `inativo`. Portanto a primitiva legada `oportunidades.py encontro`, se chamada diretamente no estado real do repo, retorna `npc_sem_perfil_ativo` antes de abrir tempo, estado, perfil ou baralho.

O índice declara:

```yaml
estatuto_operacional: gate_procedural_retirado_task31
nova_origem_sidequests: canonica_explicita
regras:
  gate_procedural_operacional: false
  encontro_nao_gera_nova_sidequest: true
  fonte_nova_sidequest: canonica_explicita
  perfis_procedurais_sao_legado: true
```

Reativar um desses perfis para produzir novas quests viola a Task 31.

## O que foi preservado

A Task 31 não apaga o lifecycle de side quest.

Continuam válidos em `oportunidades.py`:

- `oferecida`;
- `aceita`;
- `adiada`;
- `recusada`;
- `expirada`;
- `concluida`;
- `falhada`;
- limite de 2 missões `aceita` simultaneamente;
- validação de janela temporal;
- reabertura quando explicitamente permitida;
- efeitos persistentes preparados por `interacoes_mundo.py preparar-sidequest`;
- integração pós-canônica de rastro e recompensa.

Essas peças são reutilizadas pelas próximas tasks; não há razão para reconstruí-las.

O orçamento legado `max_em_aberto: 3` também é preservado nesta task para não misturar aposentadoria do gate com redesign de lifecycle. O engine canônico da Task 32 poderá endurecer a disponibilidade/oferta para o novo limite narrativo sem alterar história antiga.

## Adventure Drought Pressure

Adventure Drought Pressure **não foi removida**.

Ela continua sendo uma heurística válida para promover microeventos locais em cenas que já acionaram essa camada. O que foi removido é somente seu acoplamento a side quests.

No índice de oportunidades, a configuração antiga continua armazenada com:

```yaml
estatuto: legado_congelado_nao_modula_sidequest
```

Isso permite auditar como os 22 sorteios históricos foram produzidos sem manter o mecanismo operacional.

## Estado vivo e migração

Antes da Task 31 havia:

- zero missões oferecidas;
- zero missões aceitas;
- uma única `pendencia_avaliacao` procedural, `sq-5ca38554df96dc88`, ligada a Maerra.

Essa pendência nunca foi oferecida e nunca virou cânone. Ela foi retirada de `pendencias_avaliacao` e preservada sob `legado_procedural.pendencias_aposentadas`, além de receber uma entrada `avaliacao_aposentada_task31` no histórico.

Assim:

- nada canônico foi apagado;
- nenhuma missão ativa foi perdida;
- a antiga semente não pode aparecer depois como “quest fantasma”;
- auditoria histórica continua possível.

O estado do baralho (`ciclo: 3`, `sorteios: 22`, fichas restantes) também permanece congelado para auditoria, mas nunca mais é consumido pela porta operacional.

## Relação com Task 30

NPC Social Initiative pode fazer um NPC legitimamente presente puxar assunto, pedir algo cotidiano ou trazer uma necessidade própria. Isso **não** é autorização para criar side quest procedural.

Uma necessidade social pode existir como ficção normal. Para ganhar lifecycle formal de side quest, precisa passar pela fonte canônica explícita que será criada pela Task 32.

Isso evita que “NPC tomou iniciativa” vire um novo nome para o mesmo gerador procedural aposentado.

## Relação com Task 32

Task 31 deixa a fronteira limpa:

```text
encontro com NPC
  -> conversa / iniciativa social normal
  -> ZERO geração de side quest

fonte canônica explícita da Task 32
  -> elegibilidade determinística
  -> lifecycle existente de oportunidade/missão
```

A Task 31 deliberadamente **não cria catálogo secreto, datas, requisitos, premissas ou conteúdo de quest**. Isso pertence à Task 32/33 e evita misturar infraestrutura com spoilers futuros.

## Custo

Contrato: `baseline/retire-procedural-sidequest-gate-orcamento.yaml`.

Para cada encontro com NPC, o gate aposentado tem:

- 0 draws;
- 0 leitura de pressão;
- 0 leitura de estado de oportunidades;
- 0 leitura de perfil procedural;
- 0 escrita de oportunidades;
- 0 scheduler;
- 0 RNG;
- 0 scan.

O único trabalho restante é resolução do NPC pelo índice já dirigido.
