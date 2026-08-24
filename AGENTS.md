# AGENTS.md — roteador operacional

## 1. Fonte de verdade

O repo é a memória canônica; não dependa só da conversa. Respeite `campanha.yaml`, ficha/estado e fontes autorizadas. Texto novo: português/UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são derivados; pendências sobrepõem checkpoint. Estado/tempo são consolidados; relações/NPCs/conhecimento fragmentados; transcrições frias append-only.

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

Em conflito: `AGENTS.md` → `campanha.yaml` → ficha/estado → pendências → sessões concluídas → `regras/decisoes.md` → regras da casa → resumos → fontes oficiais → possibilidades futuras.

Runtime, handoffs, índices e consultas são projeções, não cânone independente. Pendências têm precedência apenas temporal até consolidação.

## 4. Economia de contexto — obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.** **Economia de contexto não é economia de prosa.** Economize leitura, busca, inferências, tool calls e duplicação, não a experiência literária.

**Se for suficiente, pare.** Prefira portas públicas; não abra implementação, pastas, histórico ou transcrição “só para conferir”.

- **L0:** contexto atual;
- **L1:** `contexto.py status` — 4 KiB;
- **L2:** `cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra`, `reputacao`, sessão atual — 8 KiB;
- **L3:** `buscar ... --apos L2 --motivo ...` — 8 KiB; 2–5 lacunas: `contexto-buscar-muitos.py`;
- **L4:** histórico estruturado — 12 KiB, sem transcrição;
- **L4T:** transcrição, somente após L4 — 16 KiB;
- **L5:** fonte externa/autorizada se a memória interna não resolver.

Alvo histórico conhecido pode saltar busca ampla; reservado exige motivo. **Nunca abrir `transcricao.md` só para retomar sessão.**

## 5. Roteamento por tarefa

Leia no máximo o documento especializado necessário:

- autoridade/segredo/agência → `docs/agente/fundamentos.md`;
- ON/OFF/RECALL → `docs/agente/protocolo-de-entrada.md`;
- L0–L5/acesso → `docs/agente/escada-de-acesso.md`, `docs/agente/acesso-e-operacoes.md`;
- consolidação/checkpoint → `docs/agente/consolidacao-transacional.md`;
- retomada/lifecycle `cronica` → `docs/agente/memoria-de-sessoes.md`, `docs/task21-unified-cronica-turn-cli.md`, `docs/task22-unified-session-lifecycle.md`;
- fronteira/pendências/contratos → `docs/task23-batch-world-boundary-resolution.md`, `docs/task24-pending-gate-cronica-preparar.md`, `docs/task25-harden-operational-contracts.md`;
- NPC/diálogo/identidade/reputação/iniciativa → `docs/agente/narracao-e-mundo.md`, `docs/task27-relationship-aware-dialogue.md`, `docs/task28-identity-suspicion-recognition.md`, `docs/task29-public-reputation-ren.md`, `docs/task30-npc-social-initiative.md`;
- local/recompensa/side quest → `docs/agente/integracao-reativa-v2.md`, `docs/task31-retire-procedural-sidequest-gate.md`, `docs/task32-canonical-secret-quest-engine.md`;
- regras/rolagens/mecânica diegética → `docs/agente/regras-e-rolagens.md`, `docs/agente/mecanica-diegetica.md`;
- densidade literária → `docs/agente/densidade-narrativa.md`;
- ficha/recursos/tempo → `docs/agente/personagem-e-tempo.md`;
- pesquisa/Git/telemetria → `docs/agente/pesquisa-e-manutencao.md`, `docs/agente/telemetria-rollouts.md`.

Estilo: `narracao/guia-de-narrativa.md`. Sessões: `narracao/protocolo-de-sessao.md`. Limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` dentro de ON = **RECALL**. OFF não avança nem é registrado; RECALL só completa fato que Ren legitimamente sabe, nunca vontade/emoção/estratégia/segredo.

Fluxo: `entrada → ON/OFF/RECALL → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial.** `poetry run cronica preparar --cena-id <id-estavel> ...` → narrar → `poetry run cronica concluir --ticket '<campo ticket>'`. Use `ticket:` completo, nunca `ticket_id`. Se `preparar` emitir ticket, sua saída é autoritativa: **não chamar `--help`, `sed`/`rg` ou código-fonte para redescobrir sintaxe**.

**Turno comum sem gatilho:** `cronica preparar --cena-id <id-estavel>` emite ticket neutro. **Não inventar tag, local ou NPC.** Tag pertinente usa `--contexto-tag` (`--tag` é alias) e namespace `local:`, `assunto:`, `acao:`, `pessoa:` ou `risco:`. Gatilho local só existe ao **entrar/explorar** e usa `--local ... --acao entrar|explorar --tier N --periculosidade ...`. Deslocamento urbano material usa `--transito-urbano ravens_bluff`; não combinar trânsito com local/NPC/tag.

**Barreira de pendências vive dentro de `cronica preparar`.** Não leia o marcador antes do turno. Se `fase: bloqueada_pendencias_mundo`, **não narrar**: `resolver_fronteira.py preparar` → avaliar lote → `resolver_fronteira.py aplicar`; materializar só `requer_resolucao` e repetir `cronica preparar`. Evento canônico nunca é no-op; candidato autônomo exige bloqueio canônico concreto. Reparo: `endpoints.py pendencias`; `tipo: reavaliar_agente_leve` → `agentes_leves.py concluir-noop <id>`; demais → `barreira_mundo.py concluir <id>`. O writer repete a trava.

**Cena reativa:** `cronica preparar` recebe só gatilhos reais e é read-only. Após narração aceita, `cronica concluir` revalida/confirma se reativa e registra. Ticket neutro não fabrica confirmação; cena abandonada não conclui; preparação obsoleta exige novo preparo.

Primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` ficam para diagnóstico/reparo. Writer legado usa stdin (`turno.py registrar <<'JSON'`); **não criar** `.turno-temporario.json` nem intermediário.

**Direção canônica é destino, nunca ação.** Se a cena apontar direção, usar `endpoints.py direcao <id>`; direção não escolhe executor, método, alvo, cena ou momento. `direcoes.py avancar` exige fonte canônica, evidência literal e nota.

Encontros simultâneos: resolver NPCs antes de mutar, colapsar aliases e ordenar por ID. Typo/ambiguidade falha antes de qualquer efeito. `interacoes_mundo.py` fica para manutenção/efeitos deliberados.

**Fala de NPC:** `contexto.py npc` já inclui `dialogo_relacional` e `iniciativa_social`; conselho exige gatilho. Iniciativa social nunca cria presença, segredo, side quest ou ação de Ren.

**Identidades:** suspeita ≠ certeza. Não testar reconhecimento por rotina. Se surgir pista concreta ligando Ren/Shinta/Kage, `identidades.py evidencia` prepara o delta; Actor bem-sucedido bloqueia só pista `atuacao`, nunca física/contextual/testemunho. Confirmação exige fato canônico explícito via `identidades.py confirmar`.

**Reputação:** ≠ fama/opinião; não testar por rotina. Fato público relevante atribuído à persona → `reputacao_publica.py evento`; consulta rara → `contexto.py reputacao <persona>`. Nunca fundir Ren/Shinta/Kage automaticamente.

**Antes de narrar** intenção que comprime tempo — dormir, esperar, vigiar horas, viajar/trabalhar por período prolongado — consultar uma vez `poetry run python ferramentas/endpoints.py fronteira --data '<data>' --hora HH:MM`. Aceita Harptos canônico, `AAAA-MM-DD` (mês = índice de Harptos) ou `DD/MM/AAAA`. Se `interromper`, narrar até a fronteira e checkpointar; a continuação volta por `cronica preparar`. Não chamar em turno curto.

Durante avanço comum:

- não atualizar diretamente estado, ficha, relações, conhecimento, consequências, relógios ou NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- concluir por stdin conforme `contrato_conclusao`; mecânica explícita usa linha própria `MECÂNICA — ...`;
- prosa completa fica na transcrição; JSONL recebe resumo/deltas/rolagens ocultas necessárias;
- instante muda com `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- reproduzir `rodape_canonico` verbatim como última linha visível.

Rolagem comum conhecida: `poetry run dados ren pericia <nome> --cd <N> --label '<rótulo>'` (vantagem/desvantagem ou abordagem só quando pertinente); não redescobrir assinatura via `--help`.

Rodapé é derivado. **Medição é pós-hoc**: nunca `analisar-rollout.py`/`comparar-rollouts.py` durante jogo. Textura: `contexto.py npc|local` só por lacuna; rolagens independentes: `poetry run dados-lote`.

Meta: **2 chamadas de orquestração por turno** (`cronica preparar` + `cronica concluir`), além do materialmente necessário. Não decompor em primitivas sem reparo real.

### Recompensas e side quests

- Cena reativa segue `cronica preparar`/`cronica concluir`.
- `interacoes_mundo.py local <id> --acao entrar|explorar`: item existir ≠ Ren encontrar.
- **Task 31:** encontro não sorteia side quest; perfis procedurais ficam inativos.
- **Task 32:** só NPC explícito fornece refs canônicas; disponibilidade ≠ oferta ≠ aceite. Presença incidental não aciona. Se o pedido entrou na narração aceita, após `cronica concluir`: `sidequests_canonicas.py oferecer <qsc-id> --npc <id>`; Ren responde pelo lifecycle existente.
- `endpoints.py sidequest <id>` preserva efeitos/pós-cânone após fato-base. Checkpoint não sorteia side quest nem loot.

## 7. Checkpoint de cena e sessão

Fronteira importante: `poetry run cronica sessao checkpoint`. Encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória.

Journal interrompido: não narrar; `poetry run cronica sessao recuperar` (`checkpoint.py recuperar` é fallback).

Ao pedido **“inicie uma sessão”**, **não pedir que ele rode CLI manualmente**: o narrador executa `poetry run cronica sessao status`; se `entre_sessoes`, executa `poetry run cronica sessao iniciar`. Use o `recap_sessao_anterior`/`retomada` devolvido; não leia handoff cru/transcrição se bastar. Se já `em_sessao`, o status traz a retomada quente. Nunca pular sessão nem copiar transcrição anterior.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana registrado.

Primitivas de manutenção: `checkpoint.py cena|sessao|recuperar`, `sessoes.py iniciar`.

## 8. Regras, dados e segredos

Dúvida de regra: parar quando resolvida; preferir `contexto.py regra`. Definir CD/modificadores antes da rolagem; nunca falsificar resultado. Use `poetry run dados`/`poetry run dados-lote`.

`narrador/` é reservado. Busca padrão não inclui esse domínio. Deltas reservados não vazam ao público; rolagens ocultas e relógios mecânicos permanecem reservados.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa nem mudar visibilidade sem pedido. Após alteração canônica manual, regenerar runtime/memória só se a retomada mudou; checkpoint normal já faz isso.

Manutenção/CI, nunca por turno: `turno.py check`, `consolidar.py check`, `sessoes.py check`, `checkpoint.py check`, `resolver_fronteira.py check`, `recompensas.py check`, `oportunidades.py check`, `sidequest_gate_v2.py check`, `interacoes_mundo.py check`, migrações `--check`, `gerar-runtime.py --check`, `verificar-integridade.py`.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico está em `docs/agente/cobertura-agents-v1.yaml`; as 58 seções antigas possuem destino explícito. Se faltar detalhe, consulte **apenas** o documento especializado correspondente.