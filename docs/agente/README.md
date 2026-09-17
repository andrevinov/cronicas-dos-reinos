# Manuais operacionais atuais

Índice da documentação que complementa o roteador curto `AGENTS.md`. Consulte
somente o domínio necessário para a tarefa.

## Fundamentos

- [`fundamentos/fundamentos.md`](fundamentos/fundamentos.md): autoridade, agência, segredo e cânone;
- [`fundamentos/protocolo-de-entrada.md`](fundamentos/protocolo-de-entrada.md): modos ON, OFF e RECALL.

## Operação

- [`operacao/escada-de-acesso.md`](operacao/escada-de-acesso.md): níveis L0–L5;
- [`operacao/acesso-e-operacoes.md`](operacao/acesso-e-operacoes.md): consultas e limites de acesso;
- [`operacao/endpoints-deterministicos.md`](operacao/endpoints-deterministicos.md): endpoints dirigidos;
- [`operacao/contratos-complementares-conclusao.md`](operacao/contratos-complementares-conclusao.md): referência dos contratos abreviados na conclusão;
- [`operacao/consolidacao-transacional.md`](operacao/consolidacao-transacional.md): preparo, conclusão, checkpoint e recovery.
- [`operacao/modulo-orquestracao-turno-e-sessao-v2.md`](operacao/modulo-orquestracao-turno-e-sessao-v2.md): control plane, recibos e correlação exactly-once.

## Memória

- [`memoria/modulo-contexto-e-memoria-v2.md`](memoria/modulo-contexto-e-memoria-v2.md): fachada de acesso econômico, retomada e persistência;
- [`memoria/memoria-de-cena.md`](memoria/memoria-de-cena.md): contexto do elenco e retomada;
- [`memoria/memoria-de-sessoes.md`](memoria/memoria-de-sessoes.md): lifecycle e histórico de sessão;
- [`memoria/memoria-duravel.md`](memoria/memoria-duravel.md): fatos persistentes;
- [`memoria/memoria-relevante.md`](memoria/memoria-relevante.md): seleção econômica de contexto;
- [`memoria/correcao-canonica.md`](memoria/correcao-canonica.md): correções explícitas sem reescrever história.

## Narrativa

- [`narrativa/modulo-entrega-narrativa-v2.md`](narrativa/modulo-entrega-narrativa-v2.md): recibo de entrega, avaliação semântica e percepção do jogador;
- [`narrativa/modulo-continuidade-npc-v2.md`](narrativa/modulo-continuidade-npc-v2.md): continuidade, conhecimento, identidade, reputação e iniciativa do elenco;
- [`narrativa/narracao-e-mundo.md`](narrativa/narracao-e-mundo.md): NPCs, relações, identidade e reputação;
- [`narrativa/densidade-narrativa.md`](narrativa/densidade-narrativa.md): densidade adequada ao turno;
- [`narrativa/papeis-conversacionais.md`](narrativa/papeis-conversacionais.md): papéis e diálogos;
- [`narrativa/personalidade-decisoria.md`](narrativa/personalidade-decisoria.md): decisões coerentes de NPCs.

## Regras e personagem

- [`regras/modulo-regras-e-estado-personagem-v2.md`](regras/modulo-regras-e-estado-personagem-v2.md): fachada de regras, rolagens e commit de ficha/tempo;
- [`regras/regras-e-rolagens.md`](regras/regras-e-rolagens.md): adjudicação, dados e recursos;
- [`regras/mecanica-diegetica.md`](regras/mecanica-diegetica.md): apresentação da mecânica;
- [`regras/personagem-e-tempo.md`](regras/personagem-e-tempo.md): ficha, estado e tempo.

## Mundo e side quests

- [`mundo/integracao-reativa-v2.md`](mundo/integracao-reativa-v2.md): contrato integrado de cena reativa;
- [`mundo/acionamentos-causais.md`](mundo/acionamentos-causais.md): acionamentos causais;
- [`mundo/compromissos-estruturados.md`](mundo/compromissos-estruturados.md): planos, contatos e operações;
- [`mundo/modulo-operacoes-adversariais-v2.md`](mundo/modulo-operacoes-adversariais-v2.md): contrato, concorrência e guardrails adversariais;
- [`mundo/direcoes-como-destino.md`](mundo/direcoes-como-destino.md): direção sem ação prescrita;
- [`mundo/ecologia-local.md`](mundo/ecologia-local.md): incidentes locais;
- [`mundo/ecologia-transito-urbano.md`](mundo/ecologia-transito-urbano.md): trânsito urbano;
- [`mundo/microeventos-locais.md`](mundo/microeventos-locais.md): microeventos e permanência;
- [`mundo/modulos-mundo-causal-v2.md`](mundo/modulos-mundo-causal-v2.md): fachadas de projeção espacial, fronteira e roteamento causal;
- [`mundo/modulos-sidequest-v2.md`](mundo/modulos-sidequest-v2.md): fachadas públicas de autoria, lifecycle e integração canônica;
- [`mundo/sidequest-gate-v2.md`](mundo/sidequest-gate-v2.md): oportunidade, autoria e lifecycle;
- [`mundo/adventure-drought-pressure.md`](mundo/adventure-drought-pressure.md): pressão por ausência de aventura;
- [`mundo/mundo-vivo-noop-compaction.md`](mundo/mundo-vivo-noop-compaction.md): compactação de no-op;
- [`mundo/npc-stub-persistente.md`](mundo/npc-stub-persistente.md): persistência mínima de NPC.

## Engenharia e avaliação

- [`engenharia/pesquisa-e-manutencao.md`](engenharia/pesquisa-e-manutencao.md): pesquisa e alterações no repositório;
- [`engenharia/politica-de-testes.md`](engenharia/politica-de-testes.md): propriedade e política de testes;
- [`engenharia/perfis-de-testes.md`](engenharia/perfis-de-testes.md): seleção de suítes;
- [`engenharia/preflight-e-benchmark.md`](engenharia/preflight-e-benchmark.md): gates antes de entrega;
- [`engenharia/auditoria-final.md`](engenharia/auditoria-final.md): auditoria estrutural;
- [`engenharia/benchmark-narrativo.md`](engenharia/benchmark-narrativo.md): protocolo de benchmark;
- [`engenharia/telemetria-rollouts.md`](engenharia/telemetria-rollouts.md): telemetria pós-hoc;
- [`engenharia/avaliacao-desempenho-sessoes.md`](engenharia/avaliacao-desempenho-sessoes.md): avaliação uniforme por sessão;
- [`engenharia/contrato-entrada-medicao.md`](engenharia/contrato-entrada-medicao.md): entrada congelada e unidades de medição;
- [`engenharia/corpus-regressao-avaliacao.md`](engenharia/corpus-regressao-avaliacao.md): corpus independente e expectativas do avaliador;
- [`engenharia/operacoes-executadas-rollout.md`](engenharia/operacoes-executadas-rollout.md): separação entre chamadas e operações executadas;
- [`engenharia/classificacao-resultados-rollout.md`](engenharia/classificacao-resultados-rollout.md): estados terminais observáveis das operações;
- [`engenharia/ledger-atividades-modulares.md`](engenharia/ledger-atividades-modulares.md): atribuição de atividades aos módulos;
- [`engenharia/agregacao-fail-closed.md`](engenharia/agregacao-fail-closed.md): bloqueio de agregação quando a medição é inválida;
- [`engenharia/qualidade-por-interacao.md`](engenharia/qualidade-por-interacao.md): adjudicação de qualidade separada da conformidade;
- [`engenharia/filas-prioridade-e-custo.md`](engenharia/filas-prioridade-e-custo.md): filas independentes e custo contábil;
- [`engenharia/reprodutibilidade-pacote-avaliacao.md`](engenharia/reprodutibilidade-pacote-avaliacao.md): proveniência e reprodução byte a byte;
- [`engenharia/validacao-externa-e-aceite.md`](engenharia/validacao-externa-e-aceite.md): amostra externa e aceite final fail-closed.
