# AGENTS.md — roteador operacional

Roteador global. Detalhes ficam em `docs/agente/` e só entram quando a tarefa exigir.

## 1. Fonte de verdade

O repositório é a memória canônica. Não depender só da conversa para fatos persistentes. Respeitar `campanha.yaml`, fontes autorizadas, ficha e estado. Texto novo usa português e UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são derivados. Em sessão ativa, `runtime/eventos-pendentes.jsonl` sobrepõe o último checkpoint. Estado/tempo descrevem o presente consolidado; relações/NPCs/conhecimento são fragmentados; transcrições são append-only para escrita e frias para leitura.

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

Antes de ler de novo, veja se o contexto basta. Após cada consulta: **Se for suficiente, pare.** Preferir portas públicas; não abrir implementação, pasta inteira, histórico ou transcrição “só para conferir”.

- **L0:** contexto atual;
- **L1:** `contexto.py status` — 4 KiB;
- **L2:** `cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra`, sessão atual — 8 KiB;
- **L3:** `buscar ... --apos L2 --motivo ...` — 8 KiB; 2–5 lacunas: `contexto-buscar-muitos.py`;
- **L4:** histórico estruturado — 12 KiB, sem transcrição;
- **L4T:** transcrição, somente após L4 — 16 KiB;
- **L5:** fonte oficial externa/autorizada se a memória interna não resolver.

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

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` dentro de ON = **RECALL**. OFF não avança nem é registrado; RECALL só completa fato que Ren legitimamente sabe, nunca vontade/emoção/estratégia/segredo.

Fluxo normal: `entrada → ON/OFF/RECALL → barreira → contexto necessário → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial.** `poetry run cronica preparar --cena-id <id-estavel> ...` → narrar → `poetry run cronica concluir --ticket <ticket>`. A saída de `preparar` contém o contrato JSON de conclusão e é autoritativa: **não chamar `--help`, não usar `sed`/`rg` para ler implementação e não abrir código-fonte para redescobrir sintaxe já fornecida**.

**Turno comum sem gatilho reativo:** `cronica preparar --cena-id <id-estavel>` é válido e emite ticket neutro. **Não inventar `--contexto-tag`, local ou NPC para satisfazer a CLI.** Tag só entra se uma tag tipada pertinente (`local:`, `assunto:`, `acao:`, `pessoa:`, `risco:`) já existir na situação. Gatilho local só existe ao **entrar/explorar** e usa o quarteto `--local ... --acao entrar|explorar --tier N --periculosidade ...`; não usar flags locais em mero deslocamento/retorno sem exploração.

**Barreira de pendências é pré-narração.** Antes de novo ON, ler `runtime/mundo-pendencias.yaml`. Se `bloqueado: true`, não narrar: usar `endpoints.py pendencias`. Se `tipo: reavaliar_agente_leve` e nada mudou, `agentes_leves.py concluir-noop <id>`; demais no-op: `barreira_mundo.py concluir <id> --nota ...`. Com mudança: transação `modo: mundo`, tag `resolver-pendencia-mundo:<id>`, checkpoint e conclusão. O writer repete a trava.

**Cena reativa:** `cronica preparar` recebe somente gatilhos reais; é read-only. Depois da narração aceita, `cronica concluir` revalida/confirma se a preparação for reativa e registra. Ticket neutro não fabrica confirmação. Cena abandonada não conclui; preparação reativa obsoleta exige novo preparo.

Primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` ficam para diagnóstico/reparo. Compatibilidade: writer legado usa stdin (`turno.py registrar <<'JSON'`); **não criar** `.turno-temporario.json` nem arquivo intermediário.

**Direção canônica é destino, nunca ação.** Se a cena apontar direção, usar `endpoints.py direcao <id>`; direção não escolhe executor, método, alvo, cena ou momento. `direcoes.py avancar` exige fonte canônica, evidência literal e nota.

Encontros simultâneos: resolver NPCs antes de mutar, colapsar aliases e ordenar por ID. Typo/ambiguidade falha antes de mapa/gate. `interacoes_mundo.py local|encontro` ficam para manutenção/acionamento deliberado.

**Antes de narrar** intenção que comprime tempo — dormir, esperar, vigiar horas, viajar/trabalhar por período prolongado — consultar uma vez `endpoints.py fronteira --data ... --hora ...`. Se `interromper`, narrar só até a fronteira, registrar/checkpointar, processar Mundo Vivo e continuar. Não chamar em turno curto.

Durante avanço comum:

- não atualizar diretamente estado, ficha, relações, conhecimento, consequências, relógios ou NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- concluir por stdin conforme `contrato_conclusao`; mecânica explícita na prosa usa linha própria `MECÂNICA — ...`;
- prosa completa fica na transcrição; JSONL recebe resumo/deltas/rolagens ocultas necessárias;
- instante muda com um único delta `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- reproduzir `rodape_canonico` verbatim como última linha visível.

Rolagem comum de perícia já conhecida: `poetry run rolar-dados ren pericia <nome> --cd <N> --label '<rótulo>'` (acrescente vantagem/desvantagem ou abordagem apenas quando pertinente); não descobrir a assinatura via cascata de `--help`.

Rodapé é derivado, não cânone. Telemetria: **medição é pós-hoc**; nunca `analisar-rollout.py`/`comparar-rollouts.py` durante jogo. Textura de NPC/local: `contexto.py npc|local` só por lacuna. Rolagens independentes: `rolar-lote.py`.

Meta: **2 chamadas de orquestração por turno** (`cronica preparar` + `cronica concluir`), além das rolagens/consultas materialmente necessárias. Não decompor em primitivas sem reparo real.

### Recompensas e side quests

- Cena reativa segue `cronica preparar`/`cronica concluir`; primitivas abaixo são manutenção/teste.
- `interacoes_mundo.py local <id> --acao entrar|explorar`: item existir ≠ Ren encontrar.
- `interacoes_mundo.py encontro <npc> --encontro-id <id>`: potencial ≠ oferta; oferta/aceite/recusa ficam em `oportunidades.py`.
- `endpoints.py sidequest <id>` separa deltas e efeitos pós-cânone; rastro/recompensa só materializam após fato-base.
- Agente novo passa pela classificação NPC v2; checkpoint não sorteia side quest nem loot.

## 7. Checkpoint de cena e sessão

Fronteira importante: `poetry run cronica sessao checkpoint`. Encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória.

Journal interrompido: não narrar; `poetry run cronica sessao recuperar` (`checkpoint.py recuperar` é fallback).

Ao pedido **“inicie uma sessão”**, o narrador executa `poetry run cronica sessao status`; se `entre_sessoes`, executa `poetry run cronica sessao iniciar`. **Use o bloco `recap_sessao_anterior`/`retomada` devolvido pela própria CLI** para recapitular e abrir; não chamar `contexto.py retomada`, ler handoff cru ou abrir transcrição se esse bloco bastar. Se já `em_sessao`, `cronica sessao status` já devolve a retomada quente e a sessão apenas continua. Nunca pedir CLI manual ao jogador, pular sessão ou copiar transcrição anterior.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana registrado.

Primitivas equivalentes seguem disponíveis para manutenção: `checkpoint.py cena`, `checkpoint.py sessao`, `sessoes.py iniciar`, `checkpoint.py recuperar`.

## 8. Regras, dados e segredos

Dúvida de regra: parar quando resolvida; preferir `contexto.py regra`. Definir CD/modificadores antes da rolagem; nunca falsificar resultado. Usar `rolar-dados.py`/`rolar-lote.py`.

`narrador/` é reservado. Busca padrão não inclui esse domínio. Deltas reservados não vazam para domínio público; rolagens ocultas e relógios mecânicos permanecem reservados.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa nem mudar visibilidade sem pedido. Após alteração canônica manual, regenerar runtime/memória só se a retomada mudou; checkpoint normal já faz isso.

Manutenção/CI, nunca por turno: `turno.py check`, `consolidar.py check`, `sessoes.py check`, `checkpoint.py check`, `recompensas.py check`, `oportunidades.py check`, `interacoes_mundo.py check`, migrações `--check`, `gerar-runtime.py --check`, `verificar-integridade.py`.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico está em `docs/agente/cobertura-agents-v1.yaml`; as 58 seções antigas possuem destino explícito. Se faltar detalhe, consulte **apenas** o documento especializado correspondente.
