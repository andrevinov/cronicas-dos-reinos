# AGENTS.md — roteador operacional de Crônicas dos Reinos

Este arquivo contém apenas instruções que precisam estar disponíveis em praticamente qualquer tarefa. O detalhamento está em `docs/agente/` e deve ser lido **somente quando a tarefa exigir**.

## 1. Fonte de verdade

O repositório é a memória canônica da campanha. Não depender apenas da conversa para fatos persistentes.

Respeitar sistema, edição, período histórico, fontes autorizadas e configuração de `campanha.yaml` e `regras/fontes.md`. Não misturar silenciosamente regras de outras edições ou fontes não autorizadas. Todo texto novo usa português e UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados do último estado consolidado. Durante sessão ativa, `runtime/eventos-pendentes.jsonl` é a sobreposição transacional posterior ao checkpoint. `contexto.py` combina base + pendências e entrega o **estado operacional efetivo**.

Desde a Etapa 5, `estado/estado-atual.yaml` e `estado/tempo.yaml` descrevem somente o presente consolidado. Desde a Etapa 6, relações, medidores e conhecimento são fragmentados. Desde a Etapa 9, transcrições são **append-only para escrita, frias para leitura**; retomada usa runtime + handoff + pendências.

## 2. Invariantes inegociáveis

1. O jogador controla Ren: decisões, falas, intenções, crenças, emoções definitivas e ações voluntárias.
2. O narrador controla mundo, NPCs, forças externas, regras e consequências.
3. Não garantir vitória nem alterar dificuldade, capacidades ou resultado depois de conhecer uma rolagem.
4. O mundo continua agindo fora da presença de Ren; NPCs e facções têm objetivos próprios.
5. Conhecimento do narrador, NPCs, facções, Ren e jogador são camadas diferentes.
6. Rumor não é fato; possibilidade futura não é cânone.
7. Segredos só podem ser revelados por descoberta legítima.
8. Sessão concluída é registro histórico; correções relevantes são explícitas, nunca silenciosas.
9. Decisões com efeitos persistentes devem continuar rastreáveis.
10. Preparação serve ao jogo e nunca deve substituí-lo.

Detalhes: `docs/agente/fundamentos.md`.

## 3. Hierarquia de autoridade

Em conflito, usar como ordem inicial:

1. este `AGENTS.md` para operação global;
2. `campanha.yaml`;
3. ficha e estado canônicos consolidados;
4. eventos pendentes da sessão atual, somente para mudanças posteriores à consolidação;
5. sessões concluídas;
6. `regras/decisoes.md`;
7. regras da casa;
8. resumos internos;
9. fontes oficiais autorizadas;
10. possibilidades futuras.

Runtime, handoffs, índices e resultados de consulta são projeções/roteadores, não cânone independente. Eventos pendentes têm precedência apenas temporal e deixam de existir como overlay depois de consolidados.

## 4. Economia de contexto — regra obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.**

**Economia de contexto não é economia de prosa.** Economize leitura, busca, inferências, tool calls, arquivos quentes, duplicação e reescritas; não comprima a experiência literária do jogador apenas para produzir menos texto. A transcrição é fria para leitura futura e pode conter prosa rica. Detalhes: `docs/agente/densidade-narrativa.md`.

Antes de chamar ferramenta ou abrir arquivo, pergunte se o contexto já disponível basta. Se bastar, não leia nada. Depois de cada consulta, pergunte novamente se já é suficiente. **Se for suficiente, pare de buscar.** Isso não significa encerrar a narração assim que os fatos mínimos forem conhecidos.

A escada é um controle de escalada, **não uma checklist obrigatória**. Se o alvo já é conhecido, ir direto à consulta dirigida evita round-trips inúteis. O proibido é subir para busca ampla, histórico ou transcrição “só para conferir”.

Preferir `ferramentas/contexto.py` a leitura integral de arquivos. Não abrir pasta inteira, histórico, transcrição ou fonte oficial quando uma camada menor resolver.

Escada de leitura:

- **L0:** contexto atual, nenhuma leitura;
- **L1:** `contexto.py status` — teto 4 KiB;
- **L2:** `cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra` ou sessão atual — teto 8 KiB;
- **L3:** `buscar "termo" --apos L2 --motivo "lacuna concreta"` — teto 8 KiB;
- **L4:** `buscar ... --historico --apos L3 --motivo "lacuna"` — teto 12 KiB, ainda sem transcrições;
- **L4T:** `buscar ... --historico --transcricoes --apos L4 --motivo "lacuna"` — teto 16 KiB;
- **L5:** fonte oficial externa/autorizada, somente se a memória interna não resolver.

Se **2–5 lacunas concretas pertencem à mesma decisão**, não faça vários `contexto.py buscar`. Agrupe em uma única chamada a `python3 ferramentas/contexto-buscar-muitos.py "termo 1" "termo 2" ... --apos L2 --motivo "lacuna/decisão concreta"`. O lote usa o mesmo degrau L3/L4/L4T e **um único orçamento global de saída**. Não agrupar curiosidades ou perguntas independentes apenas para economizar chamadas.

Alvo histórico já conhecido pode saltar busca ampla: `contexto.py sessao 2 --apos L2 --motivo "..."`. Isso economiza uma inferência/tool round; não autoriza busca especulativa.

Material reservado só entra com `--reservado` e motivo concreto. **Nunca abrir `transcricao.md` para simplesmente retomar uma sessão.** Política completa: `docs/agente/escada-de-acesso.md`.

## 5. Roteamento por tarefa

Leia no máximo os documentos especializados necessários:

- fundamentos, autoridade, segredo, agência → `docs/agente/fundamentos.md`;
- ON/OFF/RECALL e parser da janela → `docs/agente/protocolo-de-entrada.md`;
- escada L0–L5, tetos, `--apos`, `--motivo` → `docs/agente/escada-de-acesso.md`;
- acesso, preparação, operação transacional → `docs/agente/acesso-e-operacoes.md`;
- consolidação, checkpoint canônico, ledger, staging, recuperação → `docs/agente/consolidacao-transacional.md`;
- retomada, sessões antigas, handoff, índice, transcrições frias → `docs/agente/memoria-de-sessoes.md`;
- regra, decisão, CD, rolagem → `docs/agente/regras-e-rolagens.md`;
- narração, NPC, facção, relógio, consequência, relação → `docs/agente/narracao-e-mundo.md`;
- densidade literária, diálogo, ambientação e textura compacta → `docs/agente/densidade-narrativa.md`;
- ficha, progressão, inventário, recursos, tempo → `docs/agente/personagem-e-tempo.md`;
- pesquisa, região, retcon, edição, YAML, ferramentas, Git → `docs/agente/pesquisa-e-manutencao.md`;
- telemetria, rollout, benchmark e economia medida → `docs/agente/telemetria-rollouts.md`.

Estilo: `narracao/guia-de-narrativa.md`. Sessões: `narracao/protocolo-de-sessao.md`. Limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional obrigatório

Linguagem da janela: texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` dentro de ON = **RECALL**. OFF é meta, não avança nem é registrado; responder OFF também entre colchetes. RECALL só completa fato que Ren legitimamente sabe, nunca vontade/emoção/estratégia/segredo, e deve ser substituído antes do turno. Se não puder ser resolvido, parar sem rolar nem avançar. Em mensagem mista, somente ON resolvido entra em `jogador`. Detalhes: `docs/agente/protocolo-de-entrada.md`.

Fluxo normal:

`entrada → separar ON/OFF/RECALL → resolver RECALL → ação ON → contexto necessário → rolagens → narração → turno.py registrar → fim`.

Durante **cada avanço comum**:

- não atualizar diretamente estado, ficha, relações, conhecimento, consequências, relógios ou NPCs;
- não regenerar runtime nem handoff;
- não executar `git status`, `git diff`, commit, auditoria ampla ou suíte global por rotina;
- não executar `analisar-rollout.py`, `comparar-rollouts.py` ou criar telemetria durante o avanço; medição é pós-hoc;
- registrar jogador + narrador + deltas por stdin numa única chamada: `python3 ferramentas/turno.py registrar <<'JSON'` → JSON com `jogador`, `narracao`, `resumo`, `modo`, `deltas` → `JSON`; não abrir TTY, não criar `.turno-temporario.json`, não usar `--arquivo` nem consultar `--help` no avanço;
- essa chamada altera somente a transcrição atual e `runtime/eventos-pendentes.jsonl`;
- **`narracao` é a cena completa para o jogador; `resumo` é compressão operacional; `deltas` são apenas mudanças persistentes**;
- não encurtar `narracao` para fazê-la caber no tamanho desejado do resumo ou do buffer;
- registrar apenas deltas persistentes realmente ocorridos; efeito temporário usa `set efeitos_temporarios.<id>` e, ao consumir/expirar, `remove` no mesmo caminho;
- não copiar a narração inteira para o JSONL;
- não repetir bloco completo de PV/CA/Ki/dinheiro/hora/localização quando nada relevante mudou;
- rolagens ocultas relevantes ficam no registro transacional reservado até consolidação.

Quando um NPC ou local presente precisar de matéria-prima descritiva e o contexto atual não bastar, preferir a mesma consulta dirigida: `contexto.py npc "Nome"` pode trazer textura compacta e `contexto.py local "Lugar"` consulta paleta de ambiente. Não consultar paleta a cada turno nem usar textura como fonte de segredo/cânone novo.

`contexto.py` enxerga as pendências. Para retomar após pausa/compactação, usar `contexto.py retomada`, **não reler a transcrição**.

Para rolagens independentes já conhecidas, preferir `ferramentas/rolar-lote.py`. Rolagens condicionais continuam separadas.

Meta: **duas escritas por avanço** — transcrição + buffer.

## 7. Checkpoint de cena e sessão

Fazer checkpoint em **fronteira de cena importante**, quando um estado consolidado for útil, e sempre antes de considerar a sessão encerrada. Não fazer depois de cada turno.

```bash
python3 ferramentas/checkpoint.py cena
python3 ferramentas/checkpoint.py sessao
```

`checkpoint.py` chama o motor canônico `consolidar.py` e, depois da instalação atômica, reconstrói `sessoes/NNN/handoff.yaml` e `sessoes/index.yaml`. Handoff/índice são cache derivado: falha na segunda fase não reaplica deltas.

Se uma consolidação for interrompida, **não narrar, consultar contexto nem registrar novo turno**. Recuperar primeiro:

```bash
python3 ferramentas/checkpoint.py recuperar
```

`consolidar.py` continua sendo o motor de baixo nível do journal/staging e não inventa fatos, não incrementa sessão e não escolhe progressão pelo jogador.

Ao abrir uma sessão nova, **nunca copiar o último trecho da sessão anterior**. Use `contexto.py retomada`, handoff e artefatos compactos.

Detalhes: `docs/agente/consolidacao-transacional.md` e `docs/agente/memoria-de-sessoes.md`.

## 8. Regras, dados e segredos

Quando houver dúvida de regra, parar assim que resolvida. Preferir `contexto.py regra "assunto"`. Ordem conceitual: resumo interno → decisão anterior → regra da casa → fonte oficial.

Definir dificuldade/modificadores antes do dado. Nunca falsificar resultado. Usar `rolar-dados.py` e, para lotes independentes, `rolar-lote.py`.

`narrador/` é reservado. Busca padrão não inclui esse domínio. Deltas `visibilidade: narrador` não podem ser consolidados em arquivos públicos; rolagens ocultas e relógios reservados permanecem na área do narrador.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa. Não publicar o repositório nem mudar visibilidade sem pedido explícito.

Após alteração canônica manual, regenerar runtime e reconstruir memória compacta se a situação de retomada mudou. O fluxo normal de checkpoint já faz isso.

Verificações estruturais:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/sessoes.py check
python3 ferramentas/checkpoint.py check
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Essa suíte pertence a manutenção, checkpoint e CI — nunca a cada ação de Ren.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico é documentada em `docs/agente/cobertura-agents-v1.yaml`. As 58 seções antigas possuem destino explícito.

Se faltar detalhe, consulte **apenas** o documento especializado correspondente. Não carregue todos os documentos de `docs/agente/`.
