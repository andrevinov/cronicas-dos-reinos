# Integração reativa v2 — preparação transacional de cena

Orientação vigente para entrada/exploração de local, começo de encontro, descoberta contextual, recompensas, incidentes e lifecycle de side quests. A camada continua **reativa**: não é scheduler e não roda em turno comum.

## 1. Porta ao vivo: `cronica preparar` → narrar → `cronica concluir`

Antes de narrar uma fronteira de cena que possui gatilho reativo:

```bash
poetry run cronica preparar \
  --cena-id "sessao-013:galeria" \
  --local galeria_dos_escribas --acao entrar --tier 1 --periculosidade baixa \
  --participante tomas_rell \
  --contexto-tag local:galeria_dos_escribas \
  --contexto-tag assunto:documentos \
  --sem-oportunidade-sidequest
```

`cronica preparar` calcula contra sombras em memória, projeta memória do elenco e
devolve um ticket único. Portanto não cria mapa/recompensa, não estabelece
candidato contextual ou incidente como fato e não cria arquivo de preparação.

Encontro com NPC não consome gate procedural nem cria potencial aleatório. O
mesmo encontro pode avaliar sidequests canônicas previamente escritas; detalhe
secreto só abre depois de todos os gates determinísticos passarem. O catálogo
reservado acrescenta conteúdo sem mudar o algoritmo. Condições persistentes são
projetadas antes de um eventual incidente sério, sem criar uma segunda camada
ambiental.

Se a cena ocorrer, resolver rolagens, narrar e concluir com o ticket devolvido:

```bash
poetry run cronica concluir --ticket '<campo ticket>' <<'JSON'
{
  "jogador": "Ren ...",
  "narracao": "...",
  "resumo": "Resumo curto do fato ocorrido.",
  "modo": "exploração",
  "deltas": []
}
JSON
```

`cronica concluir` revalida e confirma a cena antes do writer. Se uma fonte
relevante mudou, falha antes da escrita e exige novo preparo.

Se a hipótese de cena estiver errada ou não ocorrer, descarte o ticket. As portas
`cena_mundo.py preparar|confirmar` e o alias `abrir` permanecem primitivas de
manutenção e reparo, não passos adicionais do turno normal.

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

## 4. Encontros e side quests

Resolver identidade do NPC continua obrigatório.

Fluxo atual:

```text
resolver NPC explícito
→ ZERO sorteio procedural
→ índice quente verifica somente se o NPC pertence ao catálogo reservado
   → fora do catálogo: interação normal, ZERO leitura adicional
   → catalogado: abrir um único roteador opaco daquele NPC
      → avaliar até três refs desse NPC
         → nenhum gate passa: interação normal
         → um passa: abrir exatamente um detalhe reservado
```

`narrador/tramas/oportunidades/index.yaml` não contém as 36 refs. Ele guarda apenas o marcador compacto `roteamento: fragmentado_por_npc_task33`. Cada quest-giver possui um fragmento sob `narrador/tramas/sidequests/canonicas/roteadores/<npc_id>.yaml`, lido somente quando aquele NPC é explicitamente encontrado. Cada ref contém apenas `id`, `gate` e `prioridade`.

`sidequest_gate_v2.py` conserva o nome por compatibilidade. Ele continua sem abrir estado, pressão, tempo, perfil procedural ou detalhe secreto. Para NPC catalogado, lê somente o roteador dirigido e transporta refs opacas para a camada canônica.

O engine testa, com short-circuit: local → data → lifecycle/orçamento → relação → conhecimento → mundo → identidade. Relação/identidade enxergam deltas pendentes antes do checkpoint. Conhecimento e mundo usam fontes dirigidas, nunca scan global.

O catálogo mantém três quests reservadas por quest-giver recorrente. No snapshot
de implantação em **17 Eleasis, 1372 DR**, duas eram mecanicamente quentes por
NPC quando a condição espacial correspondia; a terceira dependia de data,
relação, conhecimento, mundo ou identidade. A campanha pode legitimamente
desbloqueá-la depois. Não existe flag `hot` persistida.

Presença incidental é instalada antes da camada canônica, mas não passa pelo encontro explícito e não recebe refs de quest. Estar no mesmo local não transforma NPC em quest-giver.

Quando uma quest fica elegível, o endpoint projeta apenas o necessário para o NPC poder formular o pedido. **Disponível não significa oferecida.** Se o assunto não entrar na conversa, nada é persistido.

Se o pedido realmente entrar na narração aceita, após `cronica concluir`:

```bash
poetry run python ferramentas/canonical_quest_integration.py oferecer <qsc-id> --npc <npc_id> [--local <local_id>]
```

A porta revalida o gate e escreve uma vez. Retry é idempotente. O cooldown procedural antigo não é reutilizado.

Toda quest canônica exige recusa permitida. Oferta/aceite/adiamento/recusa continuam no lifecycle de `oportunidades.py`.

Detalhes: `docs/agente/mundo/sidequest-gate-v2.md`.

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
poetry run python ferramentas/canonical_quest_integration.py responder <sqc-id> aceitar|adiar|recusar
```

Efeitos secretos de uma quest canônica só podem ser abertos depois de `aceita`:

```bash
poetry run python ferramentas/canonical_quest_integration.py efeitos <sqc-id>
```

A saída alimenta `interacoes_mundo.py preparar-sidequest <id>`; deltas de pressão/consequência pertencem ao mesmo turno que narra o efeito. Rastro/recompensa ficam em `pos_canonico` até o fato-base existir.

No checkpoint, lifecycle pode invalidar quest giver morto; checkpoint não gera sidequest nem loot.

O engine/schema começou vazio por desenho; o catálogo fornece conteúdo reservado
e roteamento dirigido. Isso não muda a autoridade do engine nem força aparição,
oferta ou aceite.

## 8. Reações causais após progresso ou sucesso

O lifecycle termina a missão e fixa o instante do fato; ele não inventa
repercussão. Quando o fato novo sustentar resposta adversarial concreta, a porta
de reações avalia
exatamente `reacao_mundo`, `oportunidade_sucessora` ou `sem_reacao`.

`reacoes_sidequest.py preparar` é read-only. Capacidade, conhecimento com prova,
presença física quando exigida, recursos livres e autoridade adversarial do
Protected Core são gates reais. Direção ou ponte canônica apenas relacionam o
contrato; nunca suprem um gate. `materializar` preserva o SHA do contrato
adversarial original.

`reacao_mundo` usa a fila já existente. A fronteira exige
`reacoes_sidequest.py comprometer` antes de narrar ou rolar e exige prova factual
em `resolver`; não aceita no-op. `oportunidade_sucessora` não cria missão nem
oferta e continua dependente do gate explícito e do lifecycle normal.

## 9. Incidentes sérios

A porta de incidentes roda somente quando a preparação já possui um `local_id`
canônico. Ela reutiliza a ecologia do local e `condicoes_mundo` já projetadas.

Fluxo:

```text
local canônico
→ condições persistentes já projetadas
→ baralho municipal 11 rotina : 1 incidente
   → se não materializar candidato, baralho local 7 rotina : 1 incidente
→ no máximo um incidente sério
```

Condição persistente **não aumenta a frequência**. Marcadores como `chuva_forte`, `multidao`, `precos_tensionados` ou `patrulha_reforcada` apenas habilitam cartas compatíveis dentro do pool normal.

Um incidente é candidato até entrar na narração aceita. O endpoint expõe de forma compacta tipo, severidade, premissa, rotas observáveis e papéis anônimos plausíveis. Ele não escolhe NPC nomeado e não cria automaticamente sidequest, recompensa, segredo, conhecimento, reputação ou relação.

Incidente pode ser resolvido inteiramente na mesma cena. Ren pode intervir ou não quando houver escolha física real. Combate não é obrigatório; oposição esmagadora precisa deixar saída observável como fuga, cobertura, negociação ou ajuda.

O Local Microevent Deck permanece separado e cotidiano. Incidentes sérios não
relaxam os vetos de combate, quest ou recompensa dos microeventos.

Detalhes: `docs/agente/mundo/ecologia-local.md` e
`docs/agente/mundo/microeventos-locais.md`.

## 10. Roteamento causal

Os hot paths dependem de `causal_narrative_routing`: `cronica preparar` entrega
as pressões já autorizadas, enquanto endpoint e barreira projetam o evento
canônico datado devido. Evento canônico e operação adversarial comprometida
prevalecem sobre prazo, nova oportunidade e iniciativa incidental. O ticket
recebe `contrato_pressao`;
`cronica concluir` deve declarar `apresentada`, `resolvida`,
`adiada_por_bloqueio` ou `continua` para cada operação.

A exceção à barreira é estreita: só atravessa quando a fila inteira contém
operações adversariais presentes no contrato do ticket. Uma pendência estranha
restaura o bloqueio normal. Operação remota sem canal continua ativa, mas não
expõe detalhes a Ren. Ataque comprometido já possui encontro e mecânica
congelados antes da primeira rolagem.

Iniciativa social não cria presença nem conhecimento e perde prioridade para
pressão superior. `topico_censura` repetido com o mesmo digest causal é
suprimido; fato novo reautoriza a resposta sem parser literário.

## 11. Orçamento e invariantes

Contratos relevantes:

- `baseline/mundo-vivo-integracao-orcamento.yaml`;
- `baseline/cena-transacional-orcamento.yaml`;
- `baseline/tags-contextuais-tipadas-orcamento.yaml`;
- `baseline/retire-procedural-sidequest-gate-orcamento.yaml`;
- `baseline/canonical-secret-quest-engine-orcamento.yaml`;
- `baseline/secret-npc-quest-catalog-orcamento.yaml`;
- `baseline/world-local-incidents-v2-orcamento.yaml`;
- `baseline/sidequest-success-reactions-orcamento.yaml`.
- `baseline/concurrent-adversarial-operations-orcamento.yaml`;
- `baseline/reactive-pressure-routing-orcamento.yaml`.
- `baseline/seven-names-migration-integration-orcamento.yaml`.

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
- NPC fora do catálogo: 0 leituras adicionais;
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
- cena sem local: 0 leituras de incidente;
- cena espacial: 2 leituras pequenas de incidente;
- no máximo 1 incidente sério por cena;
- condição persistente muda pool, nunca frequência do incidente;
- incidente não cria sidequest/NPC nomeado/recompensa automaticamente;
- microevento local continua camada de textura separada.
- reação nasce somente de progresso canônico;
- contrato adversarial original permanece byte a byte idêntico;
- ação do mundo não exige aceite de Ren, mas compromisso precede narração/rolagem;
- oportunidade sucessora não é oferta automática;
- capacidade, conhecimento, presença, recursos e Protected Core continuam gates;
- reação usa checkpoint/fila existentes, sem RNG, scheduler ou scan global.
- pressão comprometida exige decisão explícita e conversa neutra não a fecha;
- a ordem de atenção não escolhe ação de Ren;
- turno sem pressão não lê o domínio adversarial;
- censura social repetida exige identidade de fato nova, sem parser de tom.

## 12. Operações adversariais concorrentes

Reações independentes podem compartilhar uma janela somente quando
células, atores, recursos e capacidades exclusivas não se sobrepõem. O grupo é
comprometido pela fronteira antes da narração ou escolha de Ren; um bloqueio
causal remove apenas sua frente. As demais operações continuam com pendências
próprias fora da presença de Ren.

Informação entre frentes não é automática: percepção direta exige o mesmo local;
mensageiro, sinal ou testemunha exigem canal, prova, atraso e escopo declarados.
Composição e ameaça do encontro são congeladas antes da primeira rolagem.

## 13. Migração histórica e regressão “Sete Nomes”

`migracao_sete_nomes.py dry-run <mission_id-ou-quest_id>` valida os contratos
de autoria, recompensa, risco e lifecycle, seus digests e a evidência literal
sem escrever. `aplicar`
exige o `preparacao_id`, usa journal recuperável e receipt histórico idempotente.
A migração importa três fatos consolidados, mantém ausente a confirmação formal
que Luath ainda não havia dado e não materializa reação.

O marco excepcional apenas define `necessita_reavaliacao_reacao`. A partir daí,
a porta de reações continua obrigada a provar conhecimento, capacidade, presença e recurso
do antagonista. O teste histórico prova que uma preparação negativa para oferta
nova ainda projeta a missão ativa, que Luath pode ser substituto institucional
quando sua competência e atuação são literais e que operações simultâneas só
nascem em contratos posteriores e independentes.
