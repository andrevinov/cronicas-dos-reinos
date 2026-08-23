# AGENTS.md — roteador operacional

Roteador global. Detalhes ficam em `docs/agente/` e só entram quando a tarefa exigir.

## 1. Fonte de verdade

O repositório é a memória canônica. Não depender só da conversa para fatos persistentes. Respeitar `campanha.yaml`, fontes autorizadas, ficha e estado. Texto novo usa português e UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são derivados. Em sessão ativa, `runtime/eventos-pendentes.jsonl` sobrepõe o último checkpoint; `contexto.py` combina base + pendências. Estado/tempo descrevem o presente consolidado; relações/NPCs/conhecimento são fragmentados; transcrições são append-only para escrita e frias para leitura.

## 2. Invariantes inegociáveis

1. O jogador controla Ren: decisões, falas, intenções, crenças, emoções definitivas e ações voluntárias.
2. O narrador controla mundo, NPCs, forças externas, regras e consequências.
3. Não garantir vitória nem alterar dificuldade/capacidade/resultado depois da rolagem.
4. O mundo continua fora da presença de Ren; NPCs e facções têm objetivos próprios.
5. Conhecimento do narrador, NPCs, facções, Ren e jogador são camadas diferentes.
6. Rumor não é fato; possibilidade futura não é cânone; segredo exige descoberta legítima.
7. Sessão concluída é histórico; correção relevante é explícita; efeito persistente continua rastreável.
8. Preparação serve ao jogo e nunca o substitui.

Detalhes: `docs/agente/fundamentos.md`.

## 3. Hierarquia de autoridade

Em conflito: `AGENTS.md` → `campanha.yaml` → ficha/estado consolidados → pendências correntes → sessões concluídas → `regras/decisoes.md` → regras da casa → resumos → fontes oficiais → possibilidades futuras.

Runtime, handoffs, índices e consultas são projeções/roteadores, não cânone independente. Pendências têm precedência apenas temporal até a consolidação.

## 4. Economia de contexto — obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.** **Economia de contexto não é economia de prosa.** Economize leitura, busca, inferências, tool calls e duplicação; não comprima a experiência literária.

Antes de ler de novo, veja se o contexto basta. Após cada consulta: **Se for suficiente, pare.** Preferir `ferramentas/contexto.py`; não abrir pasta inteira, histórico ou transcrição “só para conferir”.

- **L0:** contexto atual;
- **L1:** `contexto.py status` — 4 KiB;
- **L2:** `cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra`, sessão atual — 8 KiB;
- **L3:** `buscar ... --apos L2 --motivo ...` — 8 KiB; 2–5 lacunas: `contexto-buscar-muitos.py`;
- **L4:** histórico estruturado — 12 KiB, sem transcrição;
- **L4T:** transcrição, somente após L4 — 16 KiB;
- **L5:** fonte oficial externa/autorizada, só se a memória interna não resolver.

Alvo histórico conhecido pode saltar busca ampla; reservado exige motivo. **Nunca abrir `transcricao.md` para simplesmente retomar uma sessão.**

## 5. Roteamento por tarefa

Leia no máximo o documento especializado necessário:

- autoridade/segredo/agência → `docs/agente/fundamentos.md`;
- ON/OFF/RECALL → `docs/agente/protocolo-de-entrada.md`;
- L0–L5 → `docs/agente/escada-de-acesso.md`; acesso/operação → `docs/agente/acesso-e-operacoes.md`;
- consolidação/checkpoint → `docs/agente/consolidacao-transacional.md`;
- retomada/handoffs e lifecycle `cronica` → `docs/agente/memoria-de-sessoes.md`, `docs/task21-unified-cronica-turn-cli.md`, `docs/task22-unified-session-lifecycle.md`;
- regras/rolagens → `docs/agente/regras-e-rolagens.md`;
- NPC/facção/mundo → `docs/agente/narracao-e-mundo.md`; mecânica diegética → `docs/agente/mecanica-diegetica.md`;
- local/encontro/recompensa/side quest → `docs/agente/integracao-reativa-v2.md`;
- densidade literária → `docs/agente/densidade-narrativa.md`;
- ficha/recursos/tempo → `docs/agente/personagem-e-tempo.md`;
- pesquisa/Git → `docs/agente/pesquisa-e-manutencao.md`; telemetria → `docs/agente/telemetria-rollouts.md`.

Estilo: `narracao/guia-de-narrativa.md`. Sessões: `narracao/protocolo-de-sessao.md`. Limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` dentro de ON = **RECALL**. OFF não avança nem é registrado; RECALL só completa fato que Ren legitimamente sabe, nunca vontade/emoção/estratégia/segredo. Resolver antes do turno.

Fluxo normal: `entrada → ON/OFF/RECALL → barreira → contexto necessário → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial:** `poetry run cronica preparar ...` → narrar → `poetry run cronica concluir --ticket <ticket>`. Primitivas antigas ficam só para manutenção/reparo.

**Barreira de pendências é pré-narração.** Antes de novo ON, ler `runtime/mundo-pendencias.yaml`. Se `bloqueado: true`, não narrar a nova ação: usar `endpoints.py pendencias`. Pendência é avaliação, não fato. Se `tipo: reavaliar_agente_leve` e nada mudou, `agentes_leves.py concluir-noop <id>`; demais no-op: `barreira_mundo.py concluir <id> --nota ...`. Com mudança: transação `modo: mundo`, tag `resolver-pendencia-mundo:<id>`, checkpoint e conclusão. O writer repete a trava.

**Cena reativa:** `cronica preparar` recebe `cena_id` estável e só local/NPC/tags pertinentes; é read-only. Sem gatilho, não inventar dados nem consultar recompensa. Após narração aceita, `cronica concluir --ticket <ticket>` revalida/confirma e registra. Cena abandonada não conclui; ticket obsoleto exige novo preparo.

As primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` continuam disponíveis para diagnóstico/reparo. Para compatibilidade de manutenção, o writer legado usa stdin (`turno.py registrar <<'JSON'`); nunca crie arquivo intermediário.

**Direção canônica é destino, nunca ação.** Se a cena apontar direção, usar `endpoints.py direcao <id>`; direção não escolhe executor, método, alvo, cena ou momento. `direcoes.py avancar` exige fonte canônica, evidência literal e nota.

Encontros simultâneos: resolver NPCs antes de mutar, colapsar aliases e ordenar por ID. Typo/ambiguidade falha antes de mapa/gate. `interacoes_mundo.py local|encontro` ficam para manutenção/acionamento deliberado.

Antes de comprimir tempo — dormir, esperar, vigiar horas, viajar/trabalhar por período prolongado — consultar uma vez `endpoints.py fronteira --data ... --hora ...`. Se `interromper`, narrar só até a fronteira, registrar/checkpointar, processar Mundo Vivo e depois continuar. Não chamar em turno curto.

Durante avanço comum:

- não atualizar diretamente estado, ficha, relações, conhecimento, consequências, relógios ou NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- enviar jogador+narrador+deltas por stdin para `poetry run cronica concluir --ticket <ticket> <<'JSON'`; **não criar** `.turno-temporario.json` nem outro arquivo temporário;
- prosa completa fica na transcrição; JSONL recebe resumo/deltas/rolagens ocultas necessárias;
- instante muda com um único delta `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- o valor `rodape_canonico` de `cronica concluir` deve ser reproduzido verbatim como última linha visível.

Rodapé é derivado, não cânone. Telemetria é **pós-hoc**; nunca `analisar-rollout.py`/`comparar-rollouts.py` durante avanço ao vivo. Textura de NPC/local: `contexto.py npc|local`, só quando houver lacuna. Rolagens independentes: `rolar-lote.py`; condicionais ficam separadas.

Meta: **2 chamadas por turno** (`cronica preparar` + `cronica concluir`); não decompor sem necessidade de reparo.

### Recompensas e side quests

- Cena reativa segue `cronica preparar`/`cronica concluir`; primitivas abaixo são manutenção/teste.
- `interacoes_mundo.py local <id> --acao entrar|explorar`: item existir ≠ Ren encontrar.
- `interacoes_mundo.py encontro <npc> --encontro-id <id>`: potencial ≠ oferta; oferta/aceite/recusa ficam explícitos em `oportunidades.py`.
- `endpoints.py sidequest <id>` separa deltas de turno e efeitos pós-cânone; rastro/recompensa só materializam após fato-base canônico.
- Agente novo passa pela classificação NPC v2; checkpoint não sorteia side quest nem loot.

## 7. Checkpoint de cena e sessão

Fronteira importante: `poetry run cronica sessao checkpoint`. Encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória; pendência aberta bloqueia próximo avanço.

Journal interrompido: não narrar; `poetry run cronica sessao recuperar` (`checkpoint.py recuperar` é fallback).

Ao pedido **“inicie uma sessão”**, **não pedir que ele rode CLI manualmente**: o narrador executa `poetry run cronica sessao status`; se `entre_sessoes`, executa `poetry run cronica sessao iniciar` e recapitula via `contexto.py retomada`/handoff. Se já `em_sessao`, apenas retoma. Nunca pular sessão nem copiar transcrição anterior.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana já registrado.

Primitivas equivalentes continuam disponíveis para manutenção: `checkpoint.py cena`, `checkpoint.py sessao`, `sessoes.py iniciar`, `checkpoint.py recuperar`.

## 8. Regras, dados e segredos

Dúvida de regra: parar quando resolvida; preferir `contexto.py regra`. Definir CD/modificadores antes da rolagem; nunca falsificar resultado. Usar `rolar-dados.py`/`rolar-lote.py`.

`narrador/` é reservado. Busca padrão não inclui esse domínio. Deltas reservados não vazam para domínio público; rolagens ocultas e relógios mecânicos permanecem reservados.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa nem mudar visibilidade sem pedido. Após alteração canônica manual, regenerar runtime/memória só se a retomada mudou; checkpoint normal já faz isso.

Manutenção/CI, nunca por turno: `turno.py check`, `consolidar.py check`, `sessoes.py check`, `checkpoint.py check`, `recompensas.py check`, `oportunidades.py check`, `interacoes_mundo.py check`, migrações `--check`, `gerar-runtime.py --check`, `verificar-integridade.py`.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico está em `docs/agente/cobertura-agents-v1.yaml`; as 58 seções antigas possuem destino explícito. Se faltar detalhe, consulte **apenas** o documento especializado correspondente.
