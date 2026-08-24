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

Desde a Task 31, **encontro com NPC também não consome gate nem cria potencial de side quest**. O Side Quest Gate procedural foi aposentado; side quest nova exige fonte canônica explícita.

Se a cena for aceita, resolver rolagens, narrar e registrar o turno normalmente. Só depois confirmar com os mesmos parâmetros. `confirmar` refaz a preparação read-only e valida fingerprint; se fonte relevante mudou, falha antes da escrita.

Se a hipótese de cena estiver errada ou não ocorrer, não confirmar. O antigo verbo `abrir` permanece alias legado de `preparar`.

## 2. Idempotência e múltiplos NPCs

`cena_id` é estável para a cena inteira. Encontro derivado:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Encontros simultâneos são resolvidos por ID canônico. A resolução de NPC continua determinística e falha em typo/ambiguidade antes de qualquer mutação.

A antiga sombra sequencial do baralho de oportunidades não existe mais no caminho operacional: todos os encontros produzem interação normal quanto a side quest. Isso reduz custo e elimina dependência da ordem de NPCs para geração de missão.

## 3. Local e recompensas

Local é normalizado pelo registro canônico antes de qualquer avaliação. Alias nunca cria novo mapa.

Para mapa inexistente, a preparação usa o mesmo gerador determinístico da confirmação e pode mostrar `mapa_seria_criado: true`; somente a confirmação instala mapa, fragmentos e índices.

Para mapa existente, a mesma área é reutilizada. **Item existir no mapa não significa que Ren o encontrou.** Descoberta/obtenção dependem da cena e do pipeline canônico normal.

## 4. Encontros e side quests — Task 31

Resolver identidade do NPC continua obrigatório, mas o fluxo antigo foi encerrado.

Fluxo atual:

```text
resolver NPC
→ interação normal
→ ZERO sorteio de side quest
→ ZERO abertura de perfil procedural
→ ZERO pendência de avaliação gerada pelo encontro
```

O adaptador `sidequest_gate_v2.py` conserva esse nome só por compatibilidade com `cena_mundo.py`; ele agora devolve `gate_procedural_retirado` e não abre estado, pressão ou perfil procedural.

Todos os perfis antigos em `narrador/oportunidades/index.yaml` estão `inativo`. O baralho 8:2 e sua integração histórica com Adventure Drought Pressure permanecem apenas como auditoria congelada.

Adventure Drought Pressure continua válida para **microeventos locais**; não modula mais side quest.

O lifecycle de missão continua em `oportunidades.py`: oferta, aceite, adiamento, recusa, conclusão, falha, expiração e reabertura quando permitida. A origem de uma nova side quest, porém, deve ser `canonica_explicita`. A Task 32 fornece essa origem.

Detalhes: `docs/task31-retire-procedural-sidequest-gate.md`.

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

## 7. Side quest canônica aceita e pós-canônico

Depois que uma side quest proveniente de fonte canônica explícita entra no lifecycle e é aceita, `interacoes_mundo.py preparar-sidequest <id>` continua preparando deltas de pressão/consequência para o mesmo turno.

Rastro/recompensa que dependem de fato-base ficam em `pos_canonico` até o fato estar instalado. No checkpoint, lifecycle pode invalidar quest giver morto; checkpoint não gera side quest nem loot.

A Task 31 não cria catálogo ou conteúdo de quest. Tasks 32/33 fazem isso sem reativar o gate procedural.

## 8. Orçamento e invariantes

Contratos relevantes:

- `baseline/mundo-vivo-integracao-orcamento.yaml` — legado geral da integração;
- `baseline/cena-transacional-orcamento.yaml`;
- `baseline/tags-contextuais-tipadas-orcamento.yaml`;
- `baseline/retire-procedural-sidequest-gate-orcamento.yaml` — substitui operacionalmente as cláusulas antigas do gate 8:2.

Invariantes atuais:

- `preparar`: 0 escritas;
- nenhum arquivo temporário de preparação;
- nenhum scheduler novo;
- confirmação exige `preparacao_id` e revalidação;
- estado obsoleto falha antes da escrita;
- turno sem gatilho reativo continua sem chamar esta camada;
- presença exige coincidência `local:*`;
- encontro com NPC faz 0 draws de side quest;
- encontro faz 0 leitura de Adventure Drought Pressure para side quest;
- encontro faz 0 leitura/escrita do estado de oportunidades para side quest;
- perfis procedurais ativos no repo: 0;
- nova side quest exige fonte canônica explícita;
- lifecycle, efeitos persistentes, rastros e recompensas permanecem reutilizados.
