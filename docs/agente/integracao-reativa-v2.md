# Integração reativa v2 — preparação transacional de cena

Orientação vigente para entrada/exploração de local, começo de encontro, descoberta contextual, recompensas, incidentes e lifecycle de side quests. A camada continua **reativa**: não é scheduler e não roda em turno comum.

## 1. Porta ao vivo: preparar → registrar → confirmar

Antes de narrar uma fronteira de cena que possui gatilho reativo:

```bash
python3 ferramentas/cena_mundo.py preparar \
  --cena-id "sessao-013:galeria" \
  --local galeria_dos_escribas --acao entrar --tier 1 --periculosidade baixa \
  --npc tomas_rell \
  --contexto-tag local:galeria_dos_escribas \
  --contexto-tag assunto:documentos
```

`preparar` calcula contra sombras em memória. Portanto não cria mapa/recompensa, não estabelece candidato contextual ou incidente como fato e não cria arquivo de preparação.

Desde a Task 31, encontro com NPC não consome gate procedural nem cria potencial aleatório. Desde a Task 32, o mesmo encontro pode avaliar sidequests canônicas previamente escritas; detalhe secreto só abre depois de todos os gates determinísticos passarem. A Task 33 popula esse catálogo sem mudar o algoritmo. Task 34 projeta condições persistentes; Task 35 pode usar esse contexto para selecionar um incidente sério sem criar uma segunda camada ambiental.

Se a cena for aceita, resolver rolagens, narrar e registrar o turno normalmente. Só depois confirmar com os mesmos parâmetros. `confirmar` refaz a preparação read-only e valida fingerprint; se fonte relevante mudou, falha antes da escrita.

Se a hipótese de cena estiver errada ou não ocorrer, não confirmar. O antigo verbo `abrir` permanece alias legado de `preparar`.

## 2. Idempotência e múltiplos NPCs

`cena_id` é estável para a cena inteira. Encontro derivado:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Encontros simultâneos são resolvidos por ID canônico. A resolução de NPC continua determinística e falha em typo/ambiguidade antes de qualquer mutação.

Não existe mais sombra sequencial do antigo baralho de oportunidades. Para sidequest canônica, refs de NPCs explícitos são reunidas e ordenadas deterministicamente por prioridade + ID; no máximo seis gates são avaliados e no máximo um detalhe é aberto por cena.

Incidentes usam a mesma `cena_id` com `local_id` canônico. Retry do mesmo par reutiliza o resultado e não consome novamente os baralhos.

## 3. Local e recompensas

Local é normalizado pelo registro canônico antes de qualquer avaliação. Alias nunca cria novo mapa.

Para mapa inexistente, a preparação usa o mesmo gerador determinístico da confirmação e pode mostrar `mapa_seria_criado: true`; somente a confirmação instala mapa, fragmentos e índices.

Para mapa existente, a mesma área é reutilizada. **Item existir no mapa não significa que Ren o encontrou.** Descoberta/obtenção dependem da cena e do pipeline canônico normal.

Dungeon preparada usa o mesmo `local_id`, mas não entra automaticamente no pacote
de todo local. Depois que um gatilho canônico confirma o acesso, consultar apenas o
manifesto e o nível alcançado. O registro da dungeon não cria presença, encontro,
descoberta ou recompensa; a porta reativa continua responsável por confirmar a
cena, e o writer normal registra progresso factual. Checkpoint não povoa nível nem
concede o prêmio final.

## 4. Encontros e side quests — Tasks 31–33

Resolver identidade do NPC continua obrigatório.

Fluxo atual:

```text
resolver NPC explícito
→ ZERO sorteio procedural
→ índice quente verifica somente se o NPC pertence ao catálogo Task33
   → fora do catálogo: interação normal, ZERO leitura Task33 adicional
   → catalogado: abrir um único roteador opaco daquele NPC
      → avaliar até três refs desse NPC
         → nenhum gate passa: interação normal
         → um passa: abrir exatamente um detalhe reservado
```

`narrador/oportunidades/index.yaml` não contém as 36 refs. Ele guarda apenas o marcador compacto `roteamento: fragmentado_por_npc_task33`. Cada quest-giver possui um fragmento sob `narrador/sidequests-canonicas/roteadores/<npc_id>.yaml`, lido somente quando aquele NPC é explicitamente encontrado. Cada ref contém apenas `id`, `gate` e `prioridade`.

`sidequest_gate_v2.py` conserva o nome por compatibilidade. Ele continua sem abrir estado, pressão, tempo, perfil procedural ou detalhe secreto. Para NPC catalogado, lê somente o roteador dirigido e transporta refs opacas para a camada canônica.

O engine testa, com short-circuit: local → data → lifecycle/orçamento → relação → conhecimento → mundo → identidade. Relação/identidade enxergam deltas pendentes antes do checkpoint. Conhecimento e mundo usam fontes dirigidas, nunca scan global.

A Task 33 mantém três quests reservadas por quest-giver recorrente. No snapshot de implantação em **17 Eleasis, 1372 DR**, duas eram mecanicamente quentes por NPC quando a condição espacial correspondia; a terceira dependia de data, relação, conhecimento, mundo ou identidade. A campanha pode legitimamente desbloqueá-la depois. Não existe flag `hot` persistida.

Presença incidental é instalada antes da camada canônica, mas não passa pelo encontro explícito e não recebe refs de quest. Estar no mesmo local não transforma NPC em quest-giver.

Quando uma quest fica elegível, o endpoint projeta apenas o necessário para o NPC poder formular o pedido. **Disponível não significa oferecida.** Se o assunto não entrar na conversa, nada é persistido.

Se o pedido realmente entrar na narração aceita, após `cronica concluir`:

```bash
poetry run python ferramentas/sidequests_canonicas.py oferecer <qsc-id> --npc <npc_id> [--local <local_id>]
```

A porta revalida o gate e escreve uma vez. Retry é idempotente. O cooldown procedural antigo não é reutilizado.

Toda quest canônica exige recusa permitida. Oferta/aceite/adiamento/recusa continuam no lifecycle de `oportunidades.py`.

Detalhes: `docs/task31-retire-procedural-sidequest-gate.md`, `docs/task32-canonical-secret-quest-engine.md` e `docs/task33-secret-npc-quest-catalog.md`.

## 5. Descoberta contextual — tags tipadas

Até oito tags explícitas da cena podem alimentar `contexto_cena`; não inferir tags por busca ampla. Toda tag usa:

```text
tipo:valor
```

Tipos iniciais:

- `local:<id>`;
- `assunto:<id>`;
- `acao:<id>`;
- `pessoa:<id>`;
- `risco:<id>`.

Tags antigas sem namespace são inválidas. Normalização é lexical; o código não adivinha tipo.

### Presença e compatibilidade espacial

Binding de `presenca` precisa declarar pelo menos uma tag `local:*` e só passa se uma tag local da cena coincidir. Assunto não vira localização.

Candidatos permanecem avaliações, nunca fatos:

- presença → avaliar interseção física, arco, marco, mobilidade e conhecimento;
- entrada → avaliar aparição orgânica de aliado;
- operação → avaliar linha operacional, sem escolher executor/método;
- direção → avaliar destino, sem avançar direção.

Preparar/confirmar cena não canoniza candidato contextual.

## 6. Contrato de Arco e agentes

O Contrato de Arco permanece acima do Mundo Vivo. Peça controlada não listada é bloqueada; linha operacional é necessidade estratégica, não ação concreta.

Quando uma linha for relevante:

```text
arcos.py linha <linha> --executor <agente>
arcos.py metodos <linha> --executor <agente>
```

Método continua repertório, não acontecimento.

## 7. Side quest aceita e pós-canônico

A resposta de Ren continua explícita:

```bash
poetry run python ferramentas/oportunidades.py responder <sqc-id> aceitar|adiar|recusar
```

Efeitos secretos de uma quest canônica só podem ser abertos depois de `aceita`:

```bash
poetry run python ferramentas/sidequests_canonicas.py efeitos <sqc-id>
```

A saída alimenta `interacoes_mundo.py preparar-sidequest <id>`; deltas de pressão/consequência pertencem ao mesmo turno que narra o efeito. Rastro/recompensa ficam em `pos_canonico` até o fato-base existir.

No checkpoint, lifecycle pode invalidar quest giver morto; checkpoint não gera sidequest nem loot.

A Task 32 entregou engine/schema vazio por desenho; a Task 33 fornece conteúdo reservado e roteamento dirigido. Isso não muda a autoridade do engine nem força aparição, oferta ou aceite.

## 8. Incidentes sérios — Task 35

A Task 35 roda somente quando a preparação já possui um `local_id` canônico. Ela é instalada depois da Task 34 e reutiliza a ecologia do local e `condicoes_mundo` já projetadas.

Fluxo:

```text
local canônico
→ condições persistentes Task34 já projetadas
→ baralho municipal 11 rotina : 1 incidente
   → se não materializar candidato, baralho local 7 rotina : 1 incidente
→ no máximo um incidente sério
```

Condição persistente **não aumenta a frequência**. Marcadores como `chuva_forte`, `multidao`, `precos_tensionados` ou `patrulha_reforcada` apenas habilitam cartas compatíveis dentro do pool normal.

Um incidente é candidato até entrar na narração aceita. O endpoint expõe de forma compacta tipo, severidade, premissa, rotas observáveis e papéis anônimos plausíveis. Ele não escolhe NPC nomeado e não cria automaticamente sidequest, recompensa, segredo, conhecimento, reputação ou relação.

Incidente pode ser resolvido inteiramente na mesma cena. Ren pode intervir ou não quando houver escolha física real. Combate não é obrigatório; oposição esmagadora precisa deixar saída observável como fuga, cobertura, negociação ou ajuda.

O Local Microevent Deck permanece separado e cotidiano. Task 35 não relaxa os vetos de combate/quest/recompensa dos microeventos.

Detalhes: `docs/task35-world-local-incidents-v2.md`.

## 9. Orçamento e invariantes

Contratos relevantes:

- `baseline/mundo-vivo-integracao-orcamento.yaml`;
- `baseline/cena-transacional-orcamento.yaml`;
- `baseline/tags-contextuais-tipadas-orcamento.yaml`;
- `baseline/retire-procedural-sidequest-gate-orcamento.yaml`;
- `baseline/canonical-secret-quest-engine-orcamento.yaml`;
- `baseline/secret-npc-quest-catalog-orcamento.yaml`;
- `baseline/world-local-incidents-v2-orcamento.yaml`.

Invariantes atuais:

- `preparar`: 0 escritas;
- nenhum scheduler/RNG novo;
- confirmação exige `preparacao_id` e revalidação;
- estado obsoleto falha antes da escrita;
- turno sem gatilho reativo continua sem chamar esta camada;
- encontro com NPC faz 0 draws de sidequest;
- Adventure Drought Pressure não modula sidequest;
- perfis procedurais ativos no repo: 0;
- índice de oportunidades permanece abaixo do teto quente legado;
- NPC fora do catálogo: 0 leituras Task33 adicionais;
- NPC catalogado: 1 roteador opaco dirigido antes dos gates;
- gate falho: 0 leitura de detalhe;
- no máximo 1 detalhe secreto por cena;
- presença incidental não aciona quest;
- disponibilidade ≠ oferta ≠ aceite;
- toda quest canônica permite recusa;
- 12 quest-givers recorrentes × 3 quests;
- terceira quest sempre depende de condição canônica real, sem `hot` persistido;
- nova oferta revalida o gate antes de escrever;
- lifecycle, efeitos persistentes, rastros e recompensas permanecem reutilizados;
- cena sem local: 0 leituras Task35;
- cena espacial: 2 leituras pequenas Task35;
- no máximo 1 incidente sério por cena;
- condição Task34 muda pool, nunca frequência Task35;
- incidente não cria sidequest/NPC nomeado/recompensa automaticamente;
- microevento local continua camada de textura separada.
