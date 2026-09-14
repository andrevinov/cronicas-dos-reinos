# AGENTS.md — roteador operacional

## 1. Fonte de verdade

Memória canônica: `campanha.yaml`, ficha/estado e fontes autorizadas. Português/UTF-8. `runtime/contexto.yaml` e `runtime/cena.yaml`: derivados; pendências prevalecem. Estado/tempo consolidados; demais memórias fragmentadas; transcrições append-only.

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

Alvo histórico conhecido pode saltar busca ampla; reservado exige motivo. **Não abrir `transcricao.md` só para retomar.**

## 5. Roteamento por tarefa

- autoridade/segredo/agência → `docs/agente/fundamentos/fundamentos.md`;
- ON/OFF/RECALL → `docs/agente/fundamentos/protocolo-de-entrada.md`;
- L0–L5/acesso → `docs/agente/operacao/escada-de-acesso.md`, `docs/agente/operacao/acesso-e-operacoes.md`;
- consolidação/checkpoint → `docs/agente/operacao/consolidacao-transacional.md`;
- retomada/lifecycle → `docs/agente/memoria/memoria-de-sessoes.md`, `docs/agente/operacao/consolidacao-transacional.md`;
- fronteira/pendências/contratos → `docs/agente/mundo/modulos-mundo-causal-v2.md`, `docs/agente/mundo/compromissos-estruturados.md`;
- NPC/diálogo/identidade/reputação/iniciativa → `docs/agente/narrativa/modulo-continuidade-npc-v2.md`, `docs/agente/narrativa/narracao-e-mundo.md`, `docs/agente/memoria/memoria-de-cena.md`;
- local/incidente/permanência → `docs/agente/mundo/modulos-mundo-causal-v2.md`, `docs/agente/mundo/ecologia-local.md`;
- side quests → `docs/agente/mundo/modulos-sidequest-v2.md`, `docs/agente/mundo/sidequest-gate-v2.md`, `docs/agente/mundo/integracao-reativa-v2.md`;
- regras/dados → `docs/agente/regras/regras-e-rolagens.md`, `docs/agente/regras/mecanica-diegetica.md`;
- densidade → `docs/agente/narrativa/densidade-narrativa.md`; ficha/tempo → `docs/agente/regras/personagem-e-tempo.md`; manutenção/testes → `docs/agente/engenharia/pesquisa-e-manutencao.md`, `docs/agente/engenharia/telemetria-rollouts.md`, `docs/agente/engenharia/perfis-de-testes.md`, `docs/agente/engenharia/politica-de-testes.md`.

Estilo: `narracao/principios/guia-de-narrativa.md`; sessões: `narracao/operacao/protocolo-de-sessao.md`; limites: `narracao/principios/limites.md`.

## 6. Narração ao vivo — protocolo transacional

Texto normal = **ON**; bloco inteiro `[...]` = **OFF**; `{...}` em ON = **RECALL**. OFF não avança; RECALL só completa fato que Ren sabe, nunca vontade/emoção/estratégia/segredo.

Fluxo: `entrada → ON/OFF/RECALL → cronica preparar → rolagens → narração → cronica concluir → RODAPE_CANONICO → fim`.

**Porta operacional preferencial.** `poetry run cronica preparar --cena-id <id-estavel> ...` → narrar → `poetry run cronica concluir --ticket '<campo ticket>'`. Use `ticket:` completo, nunca `ticket_id`; a saída de `preparar` é autoritativa: **não chamar `--help`, `sed`/`rg` ou código-fonte para redescobrir sintaxe**.

**Contrato de oportunidade e progresso:** todo `cronica preparar` usa exatamente `--sem-oportunidade-sidequest` ou `--oportunidade-sidequest` + origem/tipo/âncora. Omissão/conflito falham. Negativa = sem âncora nova; causa vencida/alcançável continua; zero ativas só prioriza causa válida. Máx. 1 nova oportunidade/data+período, 2 ativas; só oferta narrada materializa.

**Turno comum sem gatilho:** `cronica preparar --cena-id <id-estavel> --sem-oportunidade-sidequest`; sidequest aceita é anexada pelo lifecycle. **Não inventar tag/local/NPC.** `--contexto-tag` (`--tag` alias): `local:`, `assunto:`, `acao:`, `pessoa:` ou `risco:`. Gatilho local com `--acao/--tier/--periculosidade` só ao **entrar/explorar**. Trânsito: `--transito-urbano ravens_bluff`, sem local/NPC/tag. **Permanência longa:** `--permanencia-local`; herda o local consolidado e `--local` só pode confirmá-lo. Não combinar com trânsito, NPC/tag ou gatilho de entrada.

**Iniciativa do elenco:** `--participante <id>` seleciona memória/elenco prospectivo; não prova por si presença física no mesmo preparo. `--interlocutor <id>` é o subconjunto que recebe decisão de iniciativa, mas só fica elegível com presença já consolidada no elenco corrente ou canal de contato validado. Interlocutor não cria presença, encontro ou side quest. No máximo uma abertura por janela; silêncio/adiamento/inelegibilidade ficam explícitos.

**Barreira de pendências vive dentro de `cronica preparar`.** Não leia marcador antes. Se `fase: bloqueada_pendencias_mundo`, **não narrar**: `world_boundary_resolution.py preparar` → avaliar → `world_boundary_resolution.py aplicar`; materializar só `requer_resolucao` e repetir `cronica preparar`. Evento canônico nunca é no-op. Reparo: `endpoints.py pendencias`; `tipo: reavaliar_agente_leve` → `agentes_leves.py concluir-noop <id>`; planos → eventos explícitos no lote, nunca no-op; demais → `barreira_mundo.py concluir <id>`. O writer repete a trava.

**Planos/contatos/operações:** `plano:<id>` no concluir; `planos` no lote. Ver `docs/agente/mundo/compromissos-estruturados.md`.

**Cena reativa:** `preparar` recebe só gatilhos reais e é read-only; `concluir` revalida/confirma/registra. Ticket neutro não confirma; preparo obsoleto exige outro. **Reserva de permanência:** `--permanencia-local` reserva sorteios não-canônicos e um recibo por `local+data+período` no primeiro preparo. Não cria fato; impede reroll em retry/novo `scene_id`.

Primitivas `endpoints.py cena`, `cena_mundo.py confirmar`, `turno.py registrar` são reparo. Writer legado usa stdin (`turno.py registrar <<'JSON'`); **não criar** `.turno-temporario.json`.

**Direção canônica é destino, nunca ação.** `endpoints.py direcao <id>`; `direcoes.py avancar` exige fonte canônica, evidência literal e nota. Encontros simultâneos: resolver NPCs antes de mutar; aliases colapsados/ordenados; ambiguidade falha antes de efeito.

**Memória de cena:** usar `memoria_cena` do preparar/retomada antes de `contexto.py npc`; aprofundar só lacuna indicada. Elenco completo: `--participante <id>` repetido ou `--sem-participantes`; mesma cena reutiliza o salvo. Recibo só com base ainda no contexto, nunca só no disco; retomada fria é completa. Contrato: `docs/agente/memoria/memoria-de-cena.md`. Conselho exige gatilho; `dialogo_relacional`/`iniciativa_social` não criam presença, segredo, side quest ou ação de Ren.

**Identidades:** suspeita ≠ certeza. Pista Ren/Shinta/Kage → `identidades.py evidencia`; Actor bem-sucedido bloqueia só pista `atuacao`; confirmação exige fato canônico. **Reputação:** fato público atribuído à persona → `reputacao_publica.py evento`; consulta rara → `contexto.py reputacao <persona>`; nunca fundir personas automaticamente.

**Condição multi-dia:** cena espacial projeta automaticamente; fato canônico de início/fim → `condicoes_mundo.py registrar|encerrar`.

**Antes de narrar** intenção que comprime tempo (dormir, esperar, vigiar horas, viajar/trabalhar), consultar uma vez `poetry run python ferramentas/endpoints.py fronteira --data '<data>' --hora HH:MM`. Se `interromper`, narrar até a fronteira; continuação volta por `cronica preparar`. **Não chamar** em turno curto. Se a compressão for permanência no mesmo local, cada janela volta por `cronica preparar ... --permanencia-local`; declare `--interlocutor` apenas para quem já está presente/contactável. A projeção espacial avalia uma vez por local/data/período e a iniciativa social usa a mesma identidade para não repetir abertura.

Durante avanço comum:
- não atualizar diretamente estado/ficha/relações/conhecimento/consequências/relógios/NPCs;
- não regenerar runtime/handoff nem rodar Git, testes ou telemetria;
- concluir conforme `contrato_conclusao`; mecânica explícita usa `MECÂNICA — ...`;
- gasto persistente de Focus precisa ser pré-comprometido no próprio ticket. Atalho comum: `cronica preparar ... --gasto-focus <N>`; caminho completo: `--mecanica-json '<json>'`. Nunca enviar apenas delta negativo. No `concluir`, confirmar a obrigação em `mecanica.resolucoes` e usar `{"alvo":"estado","op":"inc","caminho":"recursos.focus.atuais","valor":-N}`. Exemplo completo e schema: `docs/agente/regras/regras-e-rolagens.md`;
- prosa completa fica na transcrição; JSONL só resumo/deltas/rolagens necessárias;
- promessa, informação transmitida, mudança relacional ou marco novo: registrar `memoria={versao:1,fatos:[...]}` no mesmo concluir, com participantes e evidência literal. Schema: `docs/agente/memoria/memoria-duravel.md`. Sem fato novo, omitir; não duplicar os deltas compilados;
- instante: `{"alvo":"tempo","op":"instante","valor":{"data":"<data>","hora":"HH:MM"}}`;
- `rodape_canonico` verbatim como última linha visível.

Rolagem: `poetry run dados ren pericia <nome> --cd <N> --label '<rótulo>'`; não redescobrir assinatura via `--help`. Independentes: `poetry run dados-lote`. Rodapé é derivado. **medição é pós-hoc**: nunca `analisar-rollout.py`/`comparar-rollouts.py` durante jogo.

Meta: **2 chamadas de orquestração por turno** (`cronica preparar` + `cronica concluir`), além do materialmente necessário.

### Recompensas e side quests

- **Autoria e contratos:** conversa incidental não acorda autoria; âncora concreta percorre oportunidade → autoria → contratos → lifecycle no mesmo `preparar/concluir`. Só oferta narrada materializa; recompensa, risco e progresso ficam congelados. A ponte canônica não move Ren; integridade adversarial preserva o núcleo protegido; terminal nunca é no-op.
- **Lifecycle:** negativa não oculta causa vencida/alcançável. Missões aceitas (máx. 2) exigem no `concluir` negativa factual ou fatos com evidência literal. Retry repete `concluir`; consulta: `endpoints.py sidequest <id>` ou `sidequest_lifecycle.py status <id>`.
- **Reações e operações:** exigem causalidade e gates aplicáveis; compromisso precede narração/rolagem; direção não autoriza ação. Migração legada não inventa terminal/reação. Oferta canônica já narrada usa `canonical_quest_integration.py oferecer <qsc-id> --npc <id>`; checkpoint não sorteia side quest/loot.

## 7. Checkpoint de cena e sessão

`poetry run cronica sessao checkpoint`; encerramento: `poetry run cronica sessao encerrar`. Ordem: cânone → Mundo Vivo/lifecycle → barreira → memória. Journal interrompido: não narrar; `poetry run cronica sessao recuperar`.

Ao pedido **“inicie uma sessão”**, **não pedir que ele rode CLI manualmente**: `poetry run cronica sessao status`; se `entre_sessoes`, `poetry run cronica sessao iniciar`. Use recap/retomada; não leia transcrição se bastar. Nunca pular sessão.

Level-up entre sessões: `poetry run cronica progressao status` e `poetry run cronica progressao aplicar`; níveis 8–17 exigem milestone Juppongatana registrado.

## 8. Regras, dados e segredos

Dúvida: `contexto.py regra`. Defina CD/modificadores antes da rolagem; nunca falsifique resultado. Use `poetry run dados`/`poetry run dados-lote`. `narrador/` é reservado; busca padrão não inclui esse domínio. Deltas reservados não vazam.

## 9. Alterações no repositório

Preservar UTF-8, histórico e visibilidade. Testes: `docs/agente/engenharia/politica-de-testes.md`.

- estado vivo → invariantes/relações;
- absoluto mutável → **fixtures/snapshots/cenários temporários/histórico imutável**;
- **snapshot histórico** → natureza+motivo;
- permanente → **nome de domínio**, não `test_taskNN_*`;
- remoção → **propriedade protegida** + destino;
- `ROOT`: preferir `TemporaryDirectory` se isolável.

`auditar-testes.py`: heurística read-only; suspeito exige revisão. Índice: `docs/agente/README.md`.
