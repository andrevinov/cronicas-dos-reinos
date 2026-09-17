# Telemetria externa de rollouts

Este documento define como medir o custo operacional de **Crônicas dos Reinos** sem introduzir telemetria no loop narrativo.

## Princípio

A campanha não deve gastar uma interação para calcular o próprio desempenho. Durante narração ao vivo, não criar `runtime/telemetria.jsonl`, não atualizar dashboards, não calcular médias e não executar analisadores de rollout. O ledger append-only `sessoes/NNN/interacoes.jsonl` é somente identidade/correlação do par jogador–resposta e manifestações do jogador; não executa análise nem guarda a prosa.

A telemetria normal é **pós-hoc e somente leitura**:

```text
sessão de jogo
→ rollout-*.jsonl nativo do Codex
→ analisar-rollout.py
→ comparar-rollouts.py
→ decisão de engenharia
```

`contexto.py` também não grava `runtime/consultas-contexto.jsonl` por padrão. O log local, quando disponível, é apenas diagnóstico opt-in.

## Ferramentas

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --visao legacy-v1 --json
python3 ferramentas/comparar-rollouts.py ~/.codex/sessions/.../rollout-novo.jsonl
```

A baseline padrão é `baseline/rollout-2026-08-15.json` e as metas ficam em `baseline/metas-rollout-pos-refatoracao.json`. O comparador também aceita vários rollouts e normaliza os resultados por avanço narrativo.

## Schema público e extensão de integração narrativa

O relatório principal continua em **`schema_version: 3`**. A extensão não força
consumidores existentes a migrar apenas para receber observabilidade adicional.

Quando a extensão está presente, o relatório também contém:

```text
narrative_systems_schema: 2
modular_ledger_schema: 2
modular_ledger_v2: {...}
```

Ela acrescenta o ledger hierárquico sem remover ou reinterpretar as métricas do
schema 3 nem os contadores planos v1. `modules-v2` é a visão de produção desde a
RM-11. `--visao legacy-v1` remove o ledger e restitui
`narrative_systems_schema: 1` somente para auditorias históricas.

### Ledger modular v2

`modular_ledger_v2.events` contém uma linha lógica por combinação
turno × módulo pai × subcapacidade observada. Cada evento registra:

- sessão, turno, ordinal, `interaction_id`, `interaction_ref` e unidade de análise;
- `module_id` e `capability_id` do catálogo v2;
- fontes `comando`, `output`, `ticket` ou `resposta` e evidência compacta;
- elegibilidade observada separada da ativação observada;
- ativação como `ausente`, `gate_neutro`, `consulta`, `decisao` ou `efeito`;
- resultado observado, efeito materializado e confiança;
- custo exposto não aditivo e custo atribuído aditivo no pai;
- versões do detector, implementação e avaliação vigentes no evento;
- adjudicação opcional, sem alterar os campos observados.

Aliases do catálogo v1 são resolvidos para uma única subcapacidade v2. Sete
Nomes e Torneio Clandestino permanecem em `non_module_observations`, sem nota ou
custo modular. Sinais dos módulos `context_and_memory`,
`turn_and_session_orchestration`, `narrative_delivery` e
`rules_and_character_state` são extraídos das operações que já existem; nenhuma
chamada é adicionada ao turno.

Um marcador ou uma declaração não prova elegibilidade. Na ausência de prova, o
ledger mantém `eligibility_observed: indeterminada`. A decisão
`--sem-oportunidade-sidequest` é um `gate_neutro`, sem efeito material, e não um
verdadeiro negativo automático. A implementação 2.0.1 emite
`schema_avaliacao_oportunidade_sidequest: 1`, separando declaração, decisão
efetiva, resultado esperado e classificação. Somente recibo pontuável ou
adjudicação alimenta VP/VN/FP/FN; indeterminados não entram no denominador.

A integração canônica 2.0.0/régua 4.0.0 emite
`schema_avaliacao_integracao_canonica: 1` em toda oferta materializada e para
cada missão processada em resposta, progresso ou terminal. O recibo contém uma
referência opaca, não contém evento, intenção, fonte nem relação reservada. O
desde o detector 4.2.0, esses recibos são a fonte de verdade da matriz VP/VN/FP/FN;
comandos e marcadores servem somente para provar quantos recibos deveriam
existir. Recibo ausente ou incompleto abre `falha_instrumentacao`, nunca N/D.

Operações adversariais emitem `consulta`, `compromisso` e `efeito` como eventos
separados do pai `adversarial_operations`. `operacoes_simultaneas: true` ativa a
subcapacidade concorrente; `false` mantém somente integridade/execução simples.
Os aliases históricos continuam observáveis, mas não recebem duas parcelas de
custo. Violações de integridade pertencem ao catálogo de guardrails e ficam fora
da média modular.

`context_and_memory` aparece em todo turno narrativo com demanda de contexto.
Sem leitura, o detector registra `contexto_l0_suficiente`; consultas roteadas
preservam L1–L4T, motivo de escalada e lacunas. Contexto obsoleto, RAW, repetição
da mesma consulta e L3+ sem justificativa permanecem evidências negativas
explícitas. Memória de cena/retomada é consulta; somente `memoria_contexto`
emitido depois do writer é efeito durável. Retry confirma a memória sem contar
novo efeito, e destinos de
conhecimento são observados sem expor o conteúdo do fato.

`narrative_delivery` correlaciona o recibo `schema_narrative_delivery: 1` do
`cronica concluir` com a última mensagem visível `final`. O relatório mede
resposta e recibo presentes, rodapé na última linha, linhas mecânicas, exposição
procedimental sem ficção, tamanho por classe de turno e latência quando há
timestamps. `densidade_nao_avaliada` é deliberado: extensão não equivale a
qualidade, e rollouts anteriores sem recibo aparecem como
`entrega_legada_observada`.

`rules_and_character_state` correlaciona consultas dirigidas, alvo prévio,
rolagem e o recibo `schema_rules_and_character_state: 1` anexado depois do
writer. A visão `rules_and_character_state` mede consultas únicas/redundantes,
redescoberta de CLI, rolagens com CD/CA prévia, obrigações e aplicações de
recurso, deltas de personagem/tempo, instantes atômicos, retries e correções
mecânicas explícitas do jogador. Um `alvo: estado` genérico só conta quando o
caminho pertence a recursos, personagem, equipamento ou efeitos de Ren;
localização, mundo, relações e elenco não ativam a RM-10.

Rollouts antigos podem fornecer evidência de confiança média pelos comandos e
deltas observáveis. O recibo novo eleva a correlação para alta confiança sem
expor números da ficha ou reexecutar validação. Ausência de recibo, alvo ou
opinião não é convertida em aprovação automática: permanece indeterminada ou
N/D conforme o indicador.

### Custo no ledger

Para cada turno, input e output são divididos uma única vez entre os módulos
pais observados. `module_parent_costs`, `cost_class_totals` e `cost_closure` são
aditivos e precisam fechar no total narrativo. A classe `controle` contém
`turn_and_session_orchestration`; os demais pais entram em `dominio`. Essa
separação é contábil e não presume custo marginal causal. Dentro do módulo, as subcapacidades usam
`capability_cost_mode: exposicao_apenas`: todas mostram o custo exposto, mas
somente o evento primário carrega a parcela aditiva do pai. Custo marginal
permanece `indeterminado`; a divisão é atribuição contábil, não causal.

### Unidades de interação, adjudicações e percepção do jogador

`modular_ledger_v2.interactions` audita se cada resposta final possui recibo e
exatamente uma referência visível. Em ON, `cronica preparar` reserva a identidade
e `cronica concluir` a completa e a propaga no rodapé. OFF/RECALL/operacional usa
`poetry run interacao registrar`; o registro não toca tempo, mundo, ficha ou
transcrição. Retry reaproveita a reserva e hashes detectam divergência do par.

Correções opcionais seguem
`evaluation/schemas/adjudicacoes-ledger-v2.schema.json`:

```bash
python3 ferramentas/analisar-rollout.py rollout.jsonl --json \
  --adjudicacoes-modulares adjudicacoes.json
```

A correção entra em `event.adjudication` e em `corrections`. Os valores
`eligibility_observed`, `activation_observed`, evidência e resultado originais
permanecem intactos. O schema estável do ledger fica em
`evaluation/schemas/ledger-modular-v2.schema.json`.

O mesmo arquivo pode conter `semantic_audits` para progressão jogável,
densidade proporcional, voz/diálogo, camadas de conhecimento e conclusão
aberta. `player_feedback` não contém notas: preserva uma manifestação concreta,
sua `interaction_ref`, tipo percebido, impacto opcional, classificação sugerida
e adjudicação. Pendência não vira falha confirmada. Agência, sigilo e integridade
de rolagem são guardrails separados: não participam nem podem ser compensados
pela média. O ledger nunca cria nota literária automática.

O detector modular vigente é `4.6.0`. A linha 4.6 recebe avaliações de qualidade
por interação, módulo e critério, valida suas identidades e evidências e mantém
oportunidades perdidas observáveis mesmo sem evento automático. Seu contrato
está em [qualidade adjudicada por interação](qualidade-por-interacao.md). A linha
4.5 cria o ledger primário de
atividades e correlaciona exatamente um recibo de `units=1` a cada passagem de
domínio. Duplicações e recibos órfãos permanecem explícitos, e os gates agregados
são derivados desse ledger. Seu contrato está em
[ledger de atividades modulares](ledger-atividades-modulares.md). A linha 4.4
classifica o resultado de cada operação com evidência explícita e separa falha operacional, não execução,
resultado ausente ou ambíguo, evidência insuficiente e erro do detector. Seu
contrato está em
[classificação de resultados](classificacao-resultados-rollout.md). A linha 4.3
separa chamadas nativas e operações executadas, correlaciona cada resultado
interno por índice ou ordem e preserva fragmentos e retransmissões sem transferir
sucesso entre operações. Seu contrato está em
[operações executadas no rollout](operacoes-executadas-rollout.md). A linha 4.2
aplica o contrato de cobertura fail-closed aos doze módulos: cada atividade
esperada precisa de recibo completo;
ausência, incompletude ou duplicação bloqueia a nota como falha de instrumentação.
Um recibo explícito pode declarar `nao_aplicavel` ou `indeterminado`; N/D fica
reservado a zero atividade avaliativa. A integração canônica conserva seu recibo
específico por missão, enquanto os outros onze módulos usam também
`schema_avaliacao_cobertura_modular: 1`. A linha 4.1 acrescentou recibos por
atividade e auditoria de completude da integração canônica. A linha 4 introduziu
a verdade avaliativa independente da declaração de oportunidade, a matriz de
confusão e a exclusão explícita dos indeterminados. A linha 3 já distinguia
consulta, gate e efeito e
só reconhecia o programa
efetivamente invocado. Menções encontradas por busca/leitura não ativam módulo,
chamadas aninhadas no tool unificado são desdobradas por operação observada e
gatilhos espaciais tipados do `cronica preparar` são atribuídos à fachada
`scene_world_projection`, mesmo sem uma chamada CLI adicional.
Cada evento conserva também
`module_implementation_version` e `module_evaluation_version`, impedindo que uma
regeneração atribua ao passado a versão corrente do catálogo.

### Orquestração

A extensão reconhece as fases `cronica preparar`, `cronica concluir`, `cronica registrar` e `cronica confirmar` e expõe:

- `orchestration_calls`;
- `avg_orchestration_calls_per_turn`;
- `orchestration_phases`;
- `cronica_pair_turns`;
- `fraction_turns_with_cronica_pair`.

`turn_and_session_orchestration` acrescenta a visão detalhada:

- chamadas por classe e duração observada por fase;
- pares bem-sucedidos, correlacionados, divergentes ou indeterminados;
- bloqueios por pendência/recovery;
- retries válidos, desnecessários e recuperados;
- tickets obsoletos/incompatíveis e commits duplicados/incompletos;
- operações e taxa de sucesso do lifecycle de sessão.

Quando `schema_turn_and_session_orchestration: 1` está presente, o detector usa
o recibo como evidência de alta confiança. Rollouts anteriores continuam
mensuráveis pelos comandos e outputs legados, deixando correlação como
indeterminada quando os IDs não são observáveis. Falha reconhecida de ticket ou
commit fica no control plane e não ativa sidequest/NPC por substring incidental.

Um turno conta como a dupla preferencial quando possui exatamente um `preparar` e um `concluir` como chamadas de orquestração. Rolagens materialmente necessárias entre as duas não deixam de ser válidas: elas são tools de mecânica, não uma terceira fase de orquestração.

### Contadores planos v1 preservados

Os campos `narrative_system_calls`, `narrative_system_turns` e
`narrative_systems_observed` continuam disponíveis para auditorias históricas.
Eles mantêm os vinte IDs v1 e sua semântica observacional anterior; não devem ser
somados ao custo do ledger v2.

A atribuição usa o comando e marcadores do output da própria ferramenta. Isso permite que uma única chamada de `cronica preparar` seja marcada, por exemplo, como incidente + condição persistente + sidequest canônica **sem contar três tool calls**.

Essa classificação é **inferência observacional**. Um marcador de `canonical_secret_quests` significa que aquela camada apareceu no fluxo observado; não significa que a quest foi oferecida, aceita ou canonizada. O mesmo vale para incidente, cânone futuro, torneio e demais sistemas.

`narrative_system_calls` pode somar mais que `tool_calls` porque uma mesma chamada pode carregar mais de uma família. `narrative_system_turns` conta cada família no máximo uma vez por turno.

## Compatibilidade operacional atualizada

A extensão de integração narrativa também fecha três lacunas da telemetria anterior:

- `cronica concluir` e `cronica registrar` são sinais de avanço narrativo moderno, além do writer legado `turno.py registrar`;
- `poetry run dados` e `poetry run dados-lote` são classificados como `dice`, mantendo compatibilidade com `rolar-dados.py` / `rolar-lote.py` antigos;
- `contexto.py reputacao` é reconhecido como consulta L2.
- `contexto.py continuidade` é reconhecido como consulta L2 reservada e dirigida.

## O que é medido diretamente pelo rollout

São métricas nativas/exatas dentro do arquivo:

- eventos de inferência (`token_count` / `last_token_usage`);
- input tokens e cached input tokens;
- output tokens e reasoning output tokens;
- número de tool calls;
- compactações;
- tamanho do `AGENTS.md` observado em `world_state`, quando presente.

O analisador calcula ainda média, pico e p95 de input por inferência, input não-cache aproximado (`input - cached`) e tool-output bytes anexados ao histórico do modelo.

`input - cached` é aproximação operacional. **Não é fórmula de faturamento nem de quota semanal.**

## O que é inferido pelo analisador

Além dessa extensão, continuam sendo inferências observacionais:

- categorias `read_search`, `write`, `dice`, `validation` e `other`;
- consultas roteadas por `contexto.py` / `contexto-buscar-muitos.py`;
- leituras cruas com `rg`, `sed`, `grep`, `cat`, `find`, `ls`, `git show` ou equivalentes;
- descoberta de interface/schema por `--help` ou leitura direta de `ferramentas/*.py`;
- caminhos mencionados em operações de leitura/escrita;
- alvos implícitos de writers conhecidos;
- leitura de transcrição;
- nível L1/L2/L3/L4/L4T;
- fases de `cronica` e famílias narrativas da extensão.
- consultas de regra, alvo prévio de rolagem e recibos de personagem/tempo da RM-10;

Desde o schema 3, chamada e resultado são correlacionados pelo `call_id` nativo quando possível, com FIFO apenas como fallback para rollouts antigos. Exit code, status explícito e respostas inequívocas permitem separar escrita tentada, concluída, falha e desconhecida.

`write_target_touches` e `canonical_write_target_touches` contam apenas alvos de escritas concluídas. `attempted_write_target_touches` preserva as tentativas. O mesmo princípio vale para leitura de transcrição.

## Leitura roteada versus leitura crua

Uma consulta L2 não esconde leitura direta no mesmo turno:

```text
contexto roteado = API operacional de contexto
leitura crua     = abertura/busca direta em arquivos
```

Se houver `contexto.py cena` seguido de `rg`/`sed`, o nível pode aparecer como `L2+RAW`. `fraction_turns_l0_l2` significa L0–L2 **limpo**; variantes `+RAW` não satisfazem a meta.

## Como um avanço narrativo é reconhecido

Há três rotas complementares:

1. prompt legado da baseline + heurística textual pequena;
2. writer legado `turno.py registrar`;
3. writers modernos `cronica concluir` / `cronica registrar`.

Chamadas com `--help` não contam como avanço nem escrita. Se a forma de pedir avanço mudar radicalmente, use `--narration-regex` no analisador/comparador.

## Métricas principais

### Input bruto por avanço

Meta técnica: redução de **75–85%**, com piso inicial de aprovação de **70%**.

### Inferências por avanço

Baseline antiga: aproximadamente 15,6. Meta: **até 5**.

### Tool calls por avanço

Baseline antiga: aproximadamente 23,5. Meta inicial: **até 8** sem sacrificar regra, agência ou continuidade.

### Orquestração por avanço

Contrato preferencial do turno unificado: **2 chamadas de orquestração**
(`preparar + concluir`) no turno comum. Esse número é diferente de tool calls
totais: uma rolagem necessária continua sendo uma chamada adicional legítima.

### Leitura roteada, crua e descoberta de schema

`routed_context_calls`, `raw_read_calls` e `schema_discovery_calls` localizam custo evitável sem confundir API operacional com investigação da infraestrutura.

### Alvos de escrita

O avanço comum pretende persistir apenas:

```text
sessoes/NNN/transcricao.md
runtime/eventos-pendentes.jsonl
```

Meta: **até 2 alvos concluídos** e zero escrita canônica concluída durante o turno comum.

### Leitura de transcrição

Transcrição é L4T/evidência bruta, não memória operacional. Meta comum: praticamente zero; a regra agregada tolera até 0,05 leitura concluída por avanço.

### Distribuição L0–L2 limpa

Meta: **ao menos 80%** dos avanços em L0–L2 limpo.

## Baseline pré-refatoração

`baseline/rollout-2026-08-15.json` combina contadores nativos com auditoria manual dos 13 avanços narrativos. Campos antigos sem precisão suficiente permanecem `n/d`; o comparador não inventa valores históricos.

A meta informal de economia efetiva não é convertida automaticamente em faturamento/quota. O comparador mostra separadamente input bruto, não-cache aproximado, inferências, tools e escrita.

## Momento recomendado para medir

Depois que a campanha estiver rodando:

1. jogar uma sessão real;
2. localizar o rollout correspondente;
3. executar analisador e comparador;
4. investigar outliers antes de alterar a arquitetura;
5. preferir 2–3 sessões para média mais estável.

Não medir depois de cada ação.

## Pacote padronizado por sessão

Quando a análise precisar produzir notas, atribuição de custo por módulo,
adjudicação semântica e feedback do jogador, seguir
`docs/agente/engenharia/avaliacao-desempenho-sessoes.md`. O gerador
`ferramentas/gerar-avaliacao-sessao.py` consome este relatório sem reinterpretar
o schema 3 e grava somente artefatos derivados em `evaluation/sessions/`.

## Privacidade e versionamento

Rollouts podem conter conversa, caminhos locais, prompts e outputs. O bruto não deve ser copiado automaticamente ao repo. Versione apenas relatórios derivados quando isso for deliberado e seguro. Nunca incluir credenciais, tokens ou arquivos de autenticação.

## Invariantes

- telemetria normal é pós-hoc;
- nenhuma tool call extra é necessária durante avanço apenas para medir;
- métricas ausentes permanecem ausentes;
- falha de writer não vira escrita efetiva;
- leitura crua não é mascarada por L1/L2 roteado;
- atribuição de sistema não equivale a fato canônico;
- uma chamada pode pertencer a múltiplos sistemas sem multiplicar `tool_calls`;
- elegibilidade observada não é inferida apenas da presença de marcador;
- gates neutros não são efeitos;
- custo fecha uma vez nos módulos pais; subcapacidades são exposição;
- adjudicação nunca sobrescreve a observação original;
- token traffic não é faturamento;
- rollout bruto permanece fora do repo por padrão;
- observabilidade nunca altera o cânone da campanha.
