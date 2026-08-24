# Integração reativa v2 — preparação transacional de cena

Orientação vigente para entrada/exploração de local, começo de encontro, descoberta contextual, recompensas e lifecycle de side quests. A camada continua **reativa**: não é scheduler e não roda em turno comum.

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

`preparar` calcula contra sombras em memória. Portanto não cria mapa/recompensa, não estabelece candidato contextual como fato e não cria arquivo de preparação.

Desde a Task 31, encontro com NPC não consome gate procedural nem cria potencial aleatório. Desde a Task 32, o mesmo encontro pode avaliar **refs canônicas opacas** já escritas; detalhe secreto só abre depois de todos os gates determinísticos passarem.

Se a cena for aceita, resolver rolagens, narrar e registrar o turno normalmente. Só depois confirmar com os mesmos parâmetros. `confirmar` refaz a preparação read-only e valida fingerprint; se fonte relevante mudou, falha antes da escrita.

Se a hipótese de cena estiver errada ou não ocorrer, não confirmar. O antigo verbo `abrir` permanece alias legado de `preparar`.

## 2. Idempotência e múltiplos NPCs

`cena_id` é estável para a cena inteira. Encontro derivado:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Encontros simultâneos são resolvidos por ID canônico. A resolução de NPC continua determinística e falha em typo/ambiguidade antes de qualquer mutação.

Não existe mais sombra sequencial do antigo baralho de oportunidades. Para sidequest canônica, os refs dos NPCs explícitos são reunidos e ordenados deterministicamente por prioridade + ID; no máximo seis gates são avaliados e no máximo um detalhe é aberto por cena.

## 3. Local e recompensas

Local é normalizado pelo registro canônico antes de qualquer avaliação. Alias nunca cria novo mapa.

Para mapa inexistente, a preparação usa o mesmo gerador determinístico da confirmação e pode mostrar `mapa_seria_criado: true`; somente a confirmação instala mapa, fragmentos e índices.

Para mapa existente, a mesma área é reutilizada. **Item existir no mapa não significa que Ren o encontrou.** Descoberta/obtenção dependem da cena e do pipeline canônico normal.

## 4. Encontros e side quests — Tasks 31/32

Resolver identidade do NPC continua obrigatório.

Fluxo atual:

```text
resolver NPC explícito
→ ZERO sorteio procedural
→ procurar refs opacas no índice já carregado
   → sem refs: interação normal, ZERO custo Task32 adicional
   → com refs: avaliar gates compactos
      → nenhum passa: interação normal
      → um passa: abrir exatamente um detalhe reservado
```

`sidequest_gate_v2.py` conserva o nome por compatibilidade. Ele continua sem abrir estado, pressão, tempo, perfil procedural ou detalhe secreto; apenas transporta refs opacas quando existirem.

O engine canônico testa, com short-circuit: local → data → lifecycle/orçamento → relação → conhecimento → mundo → identidade. Relação/identidade enxergam deltas pendentes antes do checkpoint. Conhecimento e mundo usam fontes dirigidas, nunca scan global.

Presença incidental é instalada antes da camada canônica, mas não passa pelo encontro explícito e não recebe refs de quest. Estar no mesmo local não transforma NPC em quest-giver.

Quando uma quest fica elegível, o endpoint projeta apenas o necessário para o NPC poder formular o pedido. **Disponível não significa oferecida.** Se o assunto não entrar na conversa, nada é persistido.

Se o pedido realmente entrar na narração aceita, após `cronica concluir`:

```bash
poetry run python ferramentas/sidequests_canonicas.py oferecer <qsc-id> --npc <npc_id> [--local <local_id>]
```

A porta revalida o gate e escreve uma vez. Retry é idempotente. O cooldown procedural antigo não é reutilizado.

Toda quest canônica exige recusa permitida. Oferta/aceite/adiamento/recusa continuam no lifecycle de `oportunidades.py`.

Detalhes: `docs/task31-retire-procedural-sidequest-gate.md` e `docs/task32-canonical-secret-quest-engine.md`.

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

A Task 32 entrega engine e schemas com catálogo real vazio. A Task 33 popula gates/detalhes sem alterar o algoritmo para forçar aparições.

## 8. Orçamento e invariantes

Contratos relevantes:

- `baseline/mundo-vivo-integracao-orcamento.yaml`;
- `baseline/cena-transacional-orcamento.yaml`;
- `baseline/tags-contextuais-tipadas-orcamento.yaml`;
- `baseline/retire-procedural-sidequest-gate-orcamento.yaml`;
- `baseline/canonical-secret-quest-engine-orcamento.yaml`.

Invariantes atuais:

- `preparar`: 0 escritas;
- nenhum scheduler/RNG novo;
- confirmação exige `preparacao_id` e revalidação;
- estado obsoleto falha antes da escrita;
- turno sem gatilho reativo continua sem chamar esta camada;
- encontro com NPC faz 0 draws de sidequest;
- Adventure Drought Pressure não modula sidequest;
- perfis procedurais ativos no repo: 0;
- NPC sem ref canônica: 0 leituras Task32 adicionais;
- gate falho: 0 leitura de detalhe;
- no máximo 1 detalhe secreto por cena;
- presença incidental não aciona quest;
- disponibilidade ≠ oferta ≠ aceite;
- toda quest canônica permite recusa;
- nova oferta revalida o gate antes de escrever;
- lifecycle, efeitos persistentes, rastros e recompensas permanecem reutilizados.
