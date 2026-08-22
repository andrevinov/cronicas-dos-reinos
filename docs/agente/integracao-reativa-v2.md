# Integração reativa v2 — preparação transacional de cena

Esta é a orientação operacional vigente para entrada/exploração de local, começo de encontro, descoberta contextual, recompensas e side quests. A camada continua **reativa**: não é scheduler e não roda em turno comum.

## 1. Porta ao vivo: preparar → registrar → confirmar

Antes de narrar uma fronteira de cena que possui gatilho reativo:

```bash
python3 ferramentas/cena_mundo.py preparar \
  --cena-id "sessao-013:galeria" \
  --local galeria_dos_escribas --acao entrar --tier 1 --periculosidade baixa \
  --npc tomas_rell \
  --contexto-tag documentos
```

`preparar` calcula o que a abertura faria, mas trabalha contra sombras em memória. Portanto:

- não cria mapa de recompensas;
- não cria fragmentos de item;
- não atualiza índices de recompensa;
- não consome ficha do gate de side quest;
- não cria `pendencias_avaliacao`;
- não estabelece candidato contextual como fato;
- não cria arquivo de preparação.

A saída contém `preparacao_id`. Se a cena for aceita, resolver rolagens, narrar e registrar o turno normalmente. **Só depois de `turno.py registrar`** confirmar com os mesmos parâmetros:

```bash
python3 ferramentas/cena_mundo.py confirmar \
  --preparacao-id "scene-prep-..." \
  --cena-id "sessao-013:galeria" \
  --local galeria_dos_escribas --acao entrar --tier 1 --periculosidade baixa \
  --npc tomas_rell \
  --contexto-tag documentos
```

`confirmar` refaz a preparação em modo read-only. O fingerprint inclui o resultado e hashes das fontes lidas. Se algo relevante mudou, a preparação é `obsoleta` e a confirmação falha antes de qualquer escrita; refaça `preparar`.

Se a hipótese de cena estiver errada, for corrigida ou simplesmente não ocorrer, **não confirmar**. Abandonar uma preparação deixa zero resíduos.

O antigo verbo `cena_mundo.py abrir` é apenas alias legado de `preparar` e também escreve zero arquivos.

## 2. Idempotência e múltiplos NPCs

`cena_id` é estável para a cena inteira. Não criar ID novo a cada fala.

Encontro derivado:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Durante a preparação, encontros simultâneos são ordenados por ID canônico. A sombra do estado de oportunidades é **sequencial**: o segundo NPC enxerga o gate simulado do primeiro, exatamente como ocorreria na confirmação, sem persistir nada.

Repetir a mesma preparação sem mudança de fontes devolve o mesmo `preparacao_id` e o mesmo resultado. Depois de uma confirmação que altera estado, o identificador antigo fica obsoleto; isso impede aplicar duas vezes a mesma previsão.

## 3. Local e recompensas

Local é normalizado pelo registro canônico antes de qualquer avaliação. Alias nunca cria novo mapa.

Para mapa inexistente, a preparação executa o mesmo gerador determinístico usado pela confirmação e pode mostrar `mapa_seria_criado: true`. O campo `mapa_criado` permanece `false` na preparação. Somente a confirmação instala mapa, fragmentos e índices.

Para mapa existente, a mesma área é reutilizada; tier/periculosidade novos não rerrolam o local.

**Item existir no mapa não significa que Ren o encontrou.** Descoberta/obtenção continuam dependendo da cena e do pipeline canônico normal.

## 4. Encontros e side quests

Resolver identidade antes do gate. ID exato é o caminho preferencial; alias humano só é aceito quando globalmente unívoco. Typo/ambiguidade falha antes de qualquer efeito.

Fluxo lógico:

```text
resolver NPC
→ perfil ativo?
→ orçamento/cooldown permitem?
→ encontro já processado?
→ gate determinístico 8 nada / 2 oportunidade
   → nada: interação normal
   → oportunidade: abrir no máximo 1 perfil dirigido
                  → escolher necessidade disponível
                  → produzir potencial
```

Durante `preparar`, tudo acima ocorre somente na sombra. Em `confirmar`, o mesmo resultado é persistido se o fingerprint ainda for válido.

`potencial` não é oferta. Oferta/aceite/adiamento/recusa continuam explícitos em `oportunidades.py`.

## 5. Descoberta contextual

Até oito tags explícitas da cena podem alimentar `contexto_cena`; não inferir tags por busca ampla.

Candidatos permanecem avaliações, nunca fatos:

- presença → avaliar interseção física respeitando arco, marco, mobilidade e conhecimento;
- entrada → avaliar aparição orgânica de aliado dentro da ordem/janela;
- operação → avaliar linha operacional, sem escolher executor/método automaticamente;
- direção → avaliar marco/destino, sem avançar direção.

Preparar ou confirmar uma cena **não canoniza candidato contextual**. Presença concreta, avanço de direção e demais mudanças continuam usando suas portas próprias e evidência apropriada.

## 6. Contrato de Arco e agentes

O Contrato de Arco permanece acima do Mundo Vivo. Peça controlada não listada é bloqueada. Linha operacional é necessidade estratégica, não ação concreta.

Quando uma linha for relevante:

```text
arcos.py linha <linha> --executor <agente>
arcos.py metodos <linha> --executor <agente>
```

Método continua repertório, não acontecimento. Presença, conhecimento e contexto precisam sustentar a manifestação.

## 7. Side quest aceita e pós-canônico

`interacoes_mundo.py preparar-sidequest <id>` continua preparando deltas de pressão/consequência para o mesmo turno. Rastro e recompensa que dependem de fato-base ficam em `pos_canonico` até o fato estar instalado.

No checkpoint, lifecycle pode invalidar quest giver morto; checkpoint não sorteia side quest nem gera loot.

## 8. Orçamento e invariantes

Contratos:

- `baseline/mundo-vivo-integracao-orcamento.yaml`;
- `baseline/cena-transacional-orcamento.yaml`.

Invariantes adicionais da v2:

- `preparar`: 0 escritas no repositório;
- nenhum arquivo temporário de preparação;
- nenhum scheduler novo;
- sem confirmação, mapa novo = 0;
- sem confirmação, consumo de gate = 0;
- confirmação exige `preparacao_id` e revalidação;
- estado obsoleto falha antes da escrita;
- primitivas de recompensa/oportunidade não são duplicadas;
- turno sem gatilho reativo continua sem chamar esta camada;
- turno comum continua com duas escritas.

Regressões principais:

- `tests/test_cena_mundo.py`;
- `tests/test_cena_mundo_contexto.py`;
- `tests/test_cena_mundo_transacional.py`;
- `tests/test_interacoes_mundo.py`.
