# AGENTS.md — roteador operacional

## 1. Fonte de verdade

Memória canônica: `campanha.yaml`, ficha/estado e fontes autorizadas. Português/UTF-8. `runtime/contexto.yaml` e `runtime/cena.yaml`: derivados; pendências prevalecem. Estado/tempo consolidados; relações/NPCs/conhecimento fragmentados; transcrições append-only.

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

`AGENTS.md` → `campanha.yaml` → ficha/estado → pendências → sessões concluídas → `regras/decisoes.md` → regras da casa → resumos → fontes oficiais → possibilidades futuras.

## 4. Economia de contexto — obrigatória

**Nunca leia por precaução.** **Economia de contexto não é economia de prosa.** **Se for suficiente, pare.**

- **L0:** contexto atual;
- **L1:** `contexto.py status` — 4 KiB;
- **L2:** consultas (`cena`, `retomada`, `npc`, `local`, `relacao`, `recurso`, `conhecimento`, `regra`/`reputacao`/`continuidade`, sessão) — 8 KiB;
- **L3:** `buscar ... --apos L2 --motivo ...` — 8 KiB; 2–5 lacunas: `contexto-buscar-muitos.py`;
- **L4:** histórico estruturado — 12 KiB, sem transcrição;
- **L4T:** transcrição, só após L4 — 16 KiB;
- **L5:** fonte externa/autorizada.

Alvo histórico conhecido pode saltar busca ampla; reservado exige motivo. **Nunca abrir `transcricao.md` só para retomar sessão.**

## 5. Roteamento por tarefa

- autoridade/segredo/agência → `docs/agente/fundamentos.md`;
- ON/OFF/RECALL → `docs/agente/protocolo-de-entrada.md`;
- L0–L5/acesso → `docs/agente/escada-de-acesso.md`, `docs/agente/acesso-e-operacoes.md`;
- consolidação/checkpoint → `docs/agente/consolidacao-transacional.md`;
- retomada/lifecycle → `docs/agente/memoria-de-sessoes.md`, `docs/task21-unified-cronica-turn-cli.md`, `docs/task22-unified-session-lifecycle.md`;
- fronteira/pendências/contratos → `docs/task23-batch-world-boundary-resolution.md`, `docs/task24-pending-gate-cronica-preparar.md`, `docs/task25-harden-operational-contracts.md`;
- NPC/diálogo/identidade/reputação/iniciativa/condições → `docs/agente/narracao-e-mundo.md`, Tasks 27–30 e 34;
- local/side quest/permanência → `docs/agente/integracao-reativa-v2.md`, Tasks 40–52 (`docs/task52-reactive-pressure-narrative-routing.md`) e `docs/nv15-permanencia-espacial-reativa.md`;
- regras/dados → `docs/agente/regras-e-rolagens.md`, `docs/agente/mecanica-diegetica.md`;
- densidade → `docs/agente/densidade-narrativa.md`; ficha/tempo → `docs/agente/personagem-e-tempo.md`; manutenção/testes → `docs/agente/pesquisa-e-manutencao.md`, `docs/agente/telemetria-rollouts.md`, `docs/agente/perfis-de-testes.md`, `docs/agente/politica-de-testes.md`.

Estilo: `narracao/guia-de-narrativa.md`; sessões: `narracao/protocolo-de-sessao.md`; limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` em ON = **RECALL**. OFF não avança; RECALL só completa fato que Ren sabe, nunca vontade/emoção/estratégia/segredo.

Fluxo: `entrada → ON/OFF/RECALL → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial.** `poetry run cronica preparar --cena-id <id-estavel> ...` → narrar → `poetry run cronica concluir --ticket '<campo ticket>'`. Use `ticket:` completo, nunca `ticket_id`; a saída de `preparar` é autoritativa: **não chamar `--help`, `sed`/`rg` ou código-fonte para redescobrir sintaxe**.

**Tasks47–49:** todo `cronica preparar` usa exatamente `--sem-oportunidade-sidequest` ou `--oportunidade-sidequest` + origem/tipo/âncora. Omissão/conflito falham. A negativa só bloqueia oferta nova; missão `aceita` é projetada e exige decisão factual no `cronica concluir`.

**Turno comum sem gatilho:** `cronica preparar --cena-id <id-estavel> --sem-oportunidade-sidequest`; sidequest aceita é anexada pela Task48. **Não inventar tag/local/NPC.** `--contexto-tag` (`--tag` alias): `local:`, `assunto:`, `acao:`, `pessoa:` ou `risco:`. Gatilho local com `--acao/--tier/--periculosidade` só ao **entrar/explorar**. Trânsito: `--transito-urbano ravens_bluff`, sem local/NPC/tag. **Permanência longa no mesmo local:** `--permanencia-local`; herda o `local_id` consolidado e aceita `--local` apenas como confirmação do mesmo local. Não combinar permanência com trânsito, NPC/tag ou gatilho de entrada; elenco conhecido usa `--participante`.

**Barreira de pendências vive dentro de `cronica preparar`.** Não leia marcador antes. Se `fase: bloqueada_pendencias_mundo`, **não narrar**: `resolver_fronteira.py preparar` → avaliar → `resolver_fronteira.py aplicar`; materializar só `requer_resolucao` e repetir `cronica preparar`. Evento canônico nunca é no-op. Reparo: `endpoints.py pendencias`; `tipo: reavaliar_agente_leve` → `agentes_leves.py concluir-noop <id>`; planos → eventos explícitos no lote, nunca no-op; demais → `barreira_mundo.py concluir <id>`. O writer repete a trava.

**Planos/contatos/operações:** `plano:<id>` no concluir; `planos` no lote. Ver `docs/nv08-planos-personagens.md`.

**Cena reativa:** `cronica preparar` recebe só gatilhos reais e é read-only; `cronica concluir` revalida/confirma/registra. Ticket neutro não fabrica confirmação; preparação obsoleta exige novo preparo. **Exceção NV-15 deliberada:** `--permanencia-local` reserva somente sorteios não-canônicos de microevento/incidente e um recibo espacial por `local+data+período` no primeiro preparo. Isso não cria fato narrativo; é a trava que impede reroll em retry/novo `scene_id`.

Primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` são reparo. Writer legado usa stdin (`turno.py registrar <<'JSON'`); **não criar** `.turno-temporario.json`.

**Direção canônica é destino, nunca ação.** `endpoints.py direcao <id>`; `direcoes.py avancar` exige fonte canônica, evidência literal e nota. Encontros simultâneos: resolver NPCs antes de mutar; aliases colapsados/ordenados; ambiguidade falha antes de efeito.

**Memória de cena:** usar `memoria_cena` do preparar/retomada antes de `contexto.py npc`; aprofundar só lacuna indicada. Elenco completo: `--participante <id>` repetido ou `--sem-participantes`; mesma cena reutiliza o salvo. Recibo só com base ainda no contexto, nunca só no disco; retomada fria é completa. Contrato: `docs/agente/memoria-de-cena.md`. Conselho exige gatilho; `dialogo_relacional`/`iniciativa_social` não criam presença, segredo, side quest ou ação de Ren.

**Identidades:** suspeita ≠ certeza. Pista Ren/Shinta/Kage → `identidades.py evidencia`; Actor bem-sucedido bloqueia só pista `atuacao`; confirmação exige fato canônico. **Reputação:** fato público atribuído à persona → `reputacao_publica.py evento`; consulta rara → `contexto.py reputacao <persona>`; nunca fundir personas automaticamente.

**Condição multi-dia:** cena espacial projeta automaticamente; fato canônico de início/fim → `condicoes_mundo.py registrar|encerrar`.

**Antes de narrar** intenção que comprime tempo (dormir, esperar, vigiar horas, viajar/trabalhar), consultar uma vez `poetry run python ferramentas/endpoints.py fronteira --data '<data>' --hora HH:MM`. Se `interromper`, narrar até a fronteira; continuação volta por `cronica preparar`. **Não chamar** em turno curto. Se a compressão for **permanência no mesmo local** (esperar, trabalhar, observar, conviver), cada janela alcançada volta por `cronica preparar ... --permanencia-local`; a NV-15 herda o local consolidado e avalia ecologia/presença/microevento/incidente/condições no máximo uma vez por local/data/período.

Durante avanço comum:
- não atualizar diretamente estado/ficha/relações/conhecimento/consequências/relógios/NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- concluir conforme `contrato_conclusao`; mecânica explícita usa `MECÂNICA — ...`;
- gasto persistente de Focus precisa ser pré-comprometido no próprio ticket. Atalho comum: `cronica preparar ... --gasto-focus <N>`; caminho completo: `--mecanica-json '<json>'`. Nunca enviar apenas delta negativo. No `concluir`, confirmar a obrigação em `mecanica.resolucoes` e usar `{"alvo":"estado","op":"inc","caminho":"recursos.focus.atuais","valor":-N}`. Exemplo completo e schema: `docs/agente/regras-e-rolagens.md`;
- prosa completa fica na transcrição; JSONL só resumo/deltas/rolagens necessárias;
- promessa, informação transmitida, mudança relacional ou marco novo: registrar `memoria={versao:1,fatos:[...]}` no mesmo concluir, com participantes e evidência literal. Schema: `docs/agente/memoria-duravel.md`. Sem fato novo, omitir; não duplicar os deltas compilados;
- instante: `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- `rodape_canonico` verbatim como última linha visível.

Rolagem: `poetry run dados ren pericia <nome> --cd <N> --label '<rótulo>'`; não redescobrir assinatura via `--help`. Independentes: `poetry run dados-lote`. Rodapé é derivado. **medição é pós-hoc**: nunca `analisar-rollout.py`/`comparar-rollouts.py` durante jogo.

Meta: **2 chamadas de orquestração por turno** (`cronica preparar` + `cronica concluir`), além do materialmente necessário.

### Recompensas e side quests

- **Tasks 40–46:** conversa incidental não acorda autoria; âncora concreta percorre oportunidade → autoria → contratos → lifecycle no mesmo `preparar/concluir`. Só oferta narrada materializa; recompensa/risco/progresso ficam congelados. Task42 não move Ren; Task44 preserva Protected Core; Task45 terminal nunca é no-op.
- **Tasks 47–49:** todo `preparar` decide oportunidade; negativa só bloqueia oferta nova. Missões aceitas (máx. 2) exigem no `concluir` negativa factual ou fatos com evidência literal. Retry repete `concluir`; consulta: `endpoints.py sidequest <id>` ou `sidequests_ativas.py status <id>`.
- **Tasks 50–53/legado:** reações/operações exigem causalidade e gates aplicáveis; compromisso precede narração/rolagem; direção não autoriza ação. Migração Sete Nomes não inventa terminal/reação. Task32 já narrada usa `sidequests_canonicas.py oferecer <qsc-id> --npc <id>`; checkpoint não sorteia side quest/loot.

## 7. Checkpoint de cena e sessão

`poetry run cronica sessao checkpoint`; encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória. Journal interrompido: não narrar; `poetry run cronica sessao recuperar`.

Ao pedido **“inicie uma sessão”**, **não pedir que ele rode CLI manualmente**: `poetry run cronica sessao status`; se `entre_sessoes`, `poetry run cronica sessao iniciar`. Use recap/retomada; não leia transcrição se bastar. Nunca pular sessão.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana registrado.

## 8. Regras, dados e segredos

Dúvida: `contexto.py regra`. Defina CD/modificadores antes da rolagem; nunca falsifique resultado. Use `poetry run dados`/`poetry run dados-lote`. `narrador/` é reservado; busca padrão não inclui esse domínio. Deltas reservados não vazam.

## 9. Alterações no repositório

Preservar UTF-8, histórico e visibilidade. Testes: `docs/agente/politica-de-testes.md`.

- estado vivo → invariantes/relações;
- absoluto mutável → **fixtures/snapshots/cenários temporários/histórico imutável**;
- **snapshot histórico** → natureza+motivo;
- permanente → **nome de domínio**, não `test_taskNN_*`;
- remoção → **propriedade protegida** + destino;
- `ROOT`: preferir `TemporaryDirectory` se isolável.

`auditar-testes.py`: heurística read-only; suspeito requer revisão, não veredito.

## 10. Cobertura do manual anterior

As 58 seções anteriores estão em `docs/agente/cobertura-agents-v1.yaml`. Consulte **apenas** o documento do detalhe faltante.
