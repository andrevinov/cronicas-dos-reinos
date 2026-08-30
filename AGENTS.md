# AGENTS.md — roteador operacional

## 1. Fonte de verdade

O repo é a memória canônica. Respeite `campanha.yaml`, ficha/estado e fontes autorizadas. Texto novo: português/UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são derivados; pendências prevalecem. Estado/tempo são consolidados; relações/NPCs/conhecimento fragmentados; transcrições frias append-only.

## 2. Invariantes inegociáveis

1. O jogador controla Ren: decisões, falas, intenções, crenças, emoções definitivas e ações voluntárias.
2. O narrador controla mundo, NPCs, forças externas, regras e consequências.
3. Não garantir vitória nem alterar dificuldade/capacidade/resultado depois da rolagem.
4. O mundo continua fora da presença de Ren; NPCs e facções têm objetivos próprios.
5. Conhecimento do narrador, NPCs, facções, Ren e jogador são camadas diferentes.
6. Rumor não é fato; possibilidade futura não é cânone; segredo exige descoberta legítima.
7. Sessão concluída é histórico; correção relevante é explícita; efeito persistente continua rastreável.
8. Preparação serve ao jogo e nunca o substitui.

## 3. Hierarquia de autoridade

Em conflito: `AGENTS.md` → `campanha.yaml` → ficha/estado → pendências → sessões concluídas → `regras/decisoes.md` → regras da casa → resumos → fontes oficiais → possibilidades futuras.

## 4. Economia de contexto — obrigatória

**Nunca leia por precaução.** **Economia de contexto não é economia de prosa.** **Se for suficiente, pare.** Leia só para lacuna concreta.

- **L0:** contexto atual;
- **L1:** `contexto.py status` — 4 KiB;
- **L2:** `cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra`, `reputacao`, sessão atual — 8 KiB;
- **L3:** `buscar ... --apos L2 --motivo ...` — 8 KiB; 2–5 lacunas: `contexto-buscar-muitos.py`;
- **L4:** histórico estruturado — 12 KiB, sem transcrição;
- **L4T:** transcrição, só após L4 — 16 KiB;
- **L5:** fonte externa/autorizada se necessário.

Alvo histórico conhecido pode saltar busca ampla; reservado exige motivo. **Nunca abrir `transcricao.md` só para retomar sessão.**

## 5. Roteamento por tarefa

- autoridade/segredo/agência → `docs/agente/fundamentos.md`;
- ON/OFF/RECALL → `docs/agente/protocolo-de-entrada.md`;
- L0–L5/acesso → `docs/agente/escada-de-acesso.md`, `docs/agente/acesso-e-operacoes.md`;
- consolidação/checkpoint → `docs/agente/consolidacao-transacional.md`;
- retomada/lifecycle `cronica` → `docs/agente/memoria-de-sessoes.md`, `docs/task21-unified-cronica-turn-cli.md`, `docs/task22-unified-session-lifecycle.md`;
- fronteira/pendências/contratos → `docs/task23-batch-world-boundary-resolution.md`, `docs/task24-pending-gate-cronica-preparar.md`, `docs/task25-harden-operational-contracts.md`;
- NPC/diálogo/identidade/reputação/iniciativa/condições → `docs/agente/narracao-e-mundo.md`, `docs/task27-relationship-aware-dialogue.md`, `docs/task28-identity-suspicion-recognition.md`, `docs/task29-public-reputation-ren.md`, `docs/task30-npc-social-initiative.md`, `docs/task34-persistent-world-conditions.md`;
- local/recompensa/side quest → `docs/agente/integracao-reativa-v2.md`, `docs/task40-emergent-sidequest-opportunity-boundary.md`, `docs/task41-emergent-sidequest-authoring-registry-v2.md`, `docs/task42-canon-bridge-rewriter.md`, `docs/task43-quest-rewards-discoveries-losses.md`, `docs/task44-adversarial-integrity-consequence-authority.md`;
- regras/rolagens/mecânica diegética → `docs/agente/regras-e-rolagens.md`, `docs/agente/mecanica-diegetica.md`;
- densidade literária → `docs/agente/densidade-narrativa.md`;
- ficha/recursos/tempo → `docs/agente/personagem-e-tempo.md`;
- pesquisa/Git/telemetria → `docs/agente/pesquisa-e-manutencao.md`, `docs/agente/telemetria-rollouts.md`.

Estilo: `narracao/guia-de-narrativa.md`; sessões: `narracao/protocolo-de-sessao.md`; limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` em ON = **RECALL**. OFF não avança; RECALL só completa fato que Ren sabe, nunca vontade/emoção/estratégia/segredo.

Fluxo: `entrada → ON/OFF/RECALL → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial.** `poetry run cronica preparar --cena-id <id-estavel> ...` → narrar → `poetry run cronica concluir --ticket '<campo ticket>'`. Use `ticket:` completo, nunca `ticket_id`; a saída de `preparar` é autoritativa: **não chamar `--help`, `sed`/`rg` ou código-fonte para redescobrir sintaxe**.

**Turno comum sem gatilho:** `cronica preparar --cena-id <id-estavel>` emite ticket neutro. **Não inventar tag, local ou NPC.** Tag: `--contexto-tag` (`--tag` é alias), namespace `local:`, `assunto:`, `acao:`, `pessoa:` ou `risco:`. Gatilho local só ao **entrar/explorar**: `--local ... --acao entrar|explorar --tier N --periculosidade ...`. Trânsito: `--transito-urbano ravens_bluff`, sem local/NPC/tag.

**Barreira de pendências vive dentro de `cronica preparar`.** Não leia marcador antes. Se `fase: bloqueada_pendencias_mundo`, **não narrar**: `resolver_fronteira.py preparar` → avaliar → `resolver_fronteira.py aplicar`; materializar só `requer_resolucao` e repetir `cronica preparar`. Evento canônico nunca é no-op. Reparo: `endpoints.py pendencias`; `tipo: reavaliar_agente_leve` → `agentes_leves.py concluir-noop <id>`; demais → `barreira_mundo.py concluir <id>`. O writer repete a trava.

**Cena reativa:** `cronica preparar` recebe só gatilhos reais e é read-only; após narração aceita, `cronica concluir` revalida/confirma/registra. Ticket neutro não fabrica confirmação; preparação obsoleta exige novo preparo.

Primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` são reparo. Writer legado usa stdin (`turno.py registrar <<'JSON'`); **não criar** `.turno-temporario.json`.

**Direção canônica é destino, nunca ação.** Use `endpoints.py direcao <id>`; `direcoes.py avancar` exige fonte canônica, evidência literal e nota.

Encontros simultâneos: resolver NPCs antes de mutar; colapsar aliases e ordenar por ID; ambiguidade falha antes de efeito.

**Fala de NPC:** `contexto.py npc` inclui `dialogo_relacional` e `iniciativa_social`; conselho exige gatilho. Iniciativa não cria presença, segredo, side quest ou ação de Ren.

**Identidades:** suspeita ≠ certeza. Pista concreta Ren/Shinta/Kage → `identidades.py evidencia`; Actor bem-sucedido bloqueia só pista `atuacao`. Confirmação exige fato canônico via `identidades.py confirmar`.

**Reputação:** ≠ fama/opinião. Fato público atribuído à persona → `reputacao_publica.py evento`; consulta rara → `contexto.py reputacao <persona>`. Nunca fundir Ren/Shinta/Kage automaticamente.

**Condição multi-dia:** cena espacial projeta automaticamente. Após fato canônico de início/fim, use `condicoes_mundo.py registrar|encerrar` com fonte+evidência literal.

**Antes de narrar** intenção que comprime tempo (dormir, esperar, vigiar horas, viajar/trabalhar), consultar uma vez `poetry run python ferramentas/endpoints.py fronteira --data '<data>' --hora HH:MM`. Se `interromper`, narrar até a fronteira; continuação volta por `cronica preparar`. **Não chamar** em turno curto.

Durante avanço comum:
- não atualizar diretamente estado/ficha/relações/conhecimento/consequências/relógios/NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- concluir conforme `contrato_conclusao`; mecânica explícita usa `MECÂNICA — ...`;
- prosa completa fica na transcrição; JSONL recebe só resumo/deltas/rolagens necessárias;
- instante: `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- `rodape_canonico` verbatim como última linha visível.

Rolagem: `poetry run dados ren pericia <nome> --cd <N> --label '<rótulo>'`; não redescobrir assinatura via `--help`. Rolagens independentes: `poetry run dados-lote`.

Rodapé é derivado. **medição é pós-hoc**: nunca `analisar-rollout.py`/`comparar-rollouts.py` durante jogo. Textura `contexto.py npc|local` só por lacuna.

Meta: **2 chamadas de orquestração por turno** (`cronica preparar` + `cronica concluir`), além do materialmente necessário.

### Recompensas e side quests

- Cena reativa segue `cronica preparar`/`cronica concluir`.
- `interacoes_mundo.py local <id> --acao entrar|explorar`: item existir ≠ Ren encontrar.
- **Task 40:** conversa comum/incidental = nenhuma chamada; com **âncora causal concreta**, `oportunidade_sidequest.py planejar`; saída read-only: só autoriza pensar, nunca criar/oferecer quest.
- **Task 41:** `sidequests_emergentes.py preparar` → narrar oferta → `cronica concluir` → materializar; sem oferta, não materializar. Nasce `oferecida` em `oportunidades.py`; rewards/stakes e cânone ficam só declarados.
- **Task 42:** quest emergente não lateral usa `canon_bridge_runtime.py`; aceitar só reserva causal e nunca move Ren. Convergência/transformação só suprimem realização padrão com evidência; `reconciliar` libera fallback. Integração automática fica para Task 46.
- **Task 43:** após materializar, registrar `contrato_recompensa` com `recompensas_sidequest.py` antes de resposta/lifecycle. Descoberta ≠ obtenção; sucesso/perda só materializam pelo writer transacional; perda exige contrato + evidência causal. Integração automática fica para Task 46.
- **Task 44:** preparar `contrato_adversarial` junto da Task41 antes da oferta; após materializar, `integridade_adversarial.py` materializa antes do lifecycle. Capacidade/conhecimento precisam ser reais; lateral mantém Protected Core, vínculo Task42 pode autorizar risco canônico; `obrigatoria_se_condicao` não amacia sem bloqueio causal. Execução terminal: Task45; integração quente: Task46.
- Pedido Task32 legado já narrado → `sidequests_canonicas.py oferecer <qsc-id> --npc <id>`; `endpoints.py sidequest <id>` preserva efeitos pós-cânone. Checkpoint não sorteia side quest nem loot.

## 7. Checkpoint de cena e sessão

Fronteira: `poetry run cronica sessao checkpoint`. Encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória.

Journal interrompido: não narrar; `poetry run cronica sessao recuperar` (`checkpoint.py recuperar` é fallback).

Ao pedido **“inicie uma sessão”**, **não pedir que ele rode CLI manualmente**: execute `poetry run cronica sessao status`; se `entre_sessoes`, `poetry run cronica sessao iniciar`. Use `recap_sessao_anterior`/`retomada`; não leia transcrição se bastar. Se `em_sessao`, use a retomada quente. Nunca pular sessão.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana registrado.

Primitivas: `checkpoint.py cena|sessao|recuperar`, `sessoes.py iniciar`.

## 8. Regras, dados e segredos

Dúvida de regra: prefira `contexto.py regra`. Defina CD/modificadores antes da rolagem; nunca falsifique resultado. Use `poetry run dados`/`poetry run dados-lote`.

`narrador/` é reservado; busca padrão não inclui esse domínio. Deltas reservados não vazam; rolagens ocultas/relógios permanecem reservados.

## 9. Alterações no repositório

Preservar UTF-8, histórico e formatos; não apagar fatos nem mudar visibilidade sem justificativa.

Manutenção/CI: `turno.py check`, `consolidar.py check`, `sessoes.py check`, `checkpoint.py check`, `resolver_fronteira.py check`, `recompensas.py check`, `recompensas_sidequest.py check`, `integridade_adversarial.py check`, `oportunidades.py check`, `canon_bridge_runtime.py check`, `sidequest_gate_v2.py check`, `condicoes_mundo.py check`, `interacoes_mundo.py check`, migrações `--check`, `gerar-runtime.py --check`, `verificar-integridade.py`.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico está em `docs/agente/cobertura-agents-v1.yaml`; as 58 seções antigas possuem destino explícito. Se faltar detalhe, consulte **apenas** o documento especializado correspondente.
