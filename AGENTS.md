# AGENTS.md — roteador operacional de Crônicas dos Reinos

Este arquivo contém apenas instruções que precisam estar disponíveis em praticamente qualquer tarefa. O detalhamento está em `docs/agente/` e deve ser lido **somente quando a tarefa exigir**.

## 1. Fonte de verdade

O repositório é a memória canônica da campanha. Não depender apenas da conversa para fatos persistentes.

Respeitar sistema, edição, período histórico, fontes autorizadas e configuração de `campanha.yaml` e `regras/fontes.md`. Não misturar silenciosamente regras de outras edições ou fontes não autorizadas. Todo texto novo usa português e UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados do último estado consolidado. Durante sessão ativa, `runtime/eventos-pendentes.jsonl` é a sobreposição transacional posterior ao checkpoint. `contexto.py` combina base + pendências e entrega o **estado operacional efetivo**.

Desde a Etapa 5, `estado/estado-atual.yaml` e `estado/tempo.yaml` descrevem somente o presente consolidado. Desde a Etapa 6, relações, medidores e conhecimento são fragmentados. Histórico frio não participa da leitura normal.

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

Runtime-base, índices e resultados de consulta não são cânone independente. Eventos pendentes têm precedência apenas temporal e deixam de existir como overlay depois de consolidados.

## 4. Economia de contexto — regra obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.**

Antes de chamar ferramenta ou abrir arquivo, pergunte se o contexto já disponível basta. Se bastar, não leia nada. Depois de cada consulta, pergunte novamente se já é suficiente. **Se for suficiente, pare.**

Preferir `ferramentas/contexto.py` a leitura integral de arquivos. Não abrir pasta inteira, histórico, transcrição antiga ou fonte oficial quando uma camada menor resolver.

Escada de leitura:

- **L0:** contexto atual, nenhuma leitura;
- **L1:** `python3 ferramentas/contexto.py status`;
- **L2:** `contexto.py cena`, `npc`, `relacao`, `conhecimento` ou `regra`;
- **L3:** `contexto.py buscar "termo"`;
- **L4:** `contexto.py buscar "termo" --historico`, histórico específico ou transcrição necessária;
- **L5:** fonte oficial externa/autorizada.

Material reservado só entra com `--reservado` por necessidade concreta. Fluxos detalhados: `docs/agente/acesso-e-operacoes.md`.

## 5. Roteamento por tarefa

Leia no máximo os documentos especializados necessários:

- fundamentos, autoridade, segredo, agência → `docs/agente/fundamentos.md`;
- acesso, preparação, protocolo transacional/consolidação → `docs/agente/acesso-e-operacoes.md`;
- regra, decisão, CD, rolagem → `docs/agente/regras-e-rolagens.md`;
- narração, NPC, facção, relógio, consequência, relação → `docs/agente/narracao-e-mundo.md`;
- ficha, progressão, inventário, recursos, tempo → `docs/agente/personagem-e-tempo.md`;
- pesquisa, região, retcon, edição, YAML, ferramentas, Git → `docs/agente/pesquisa-e-manutencao.md`.

Estilo: `narracao/guia-de-narrativa.md`. Sessões: `narracao/protocolo-de-sessao.md`. Limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional obrigatório

Fluxo normal:

`ação → contexto disponível → consulta se necessária → rolagens → narração → turno.py registrar → fim`.

Durante **cada avanço comum**:

- não atualizar diretamente estado, ficha, relações, conhecimento, consequências, relógios ou NPCs;
- não regenerar runtime;
- não executar `git status`, `git diff`, commit, auditoria ampla ou suíte global por rotina;
- registrar jogador + narrador + deltas em uma única chamada a `ferramentas/turno.py registrar`;
- essa chamada altera somente a transcrição e `runtime/eventos-pendentes.jsonl`;
- registrar apenas deltas persistentes realmente ocorridos;
- não copiar a narração inteira para o JSONL;
- rolagens ocultas relevantes ficam no registro transacional reservado até consolidação.

`contexto.py` enxerga as pendências. Pausa no meio da sessão não exige consolidação imediata.

Para rolagens independentes já conhecidas, preferir `ferramentas/rolar-lote.py`. Rolagens condicionais continuam separadas.

Meta: **duas escritas por avanço** — transcrição + buffer.

## 7. Consolidação de cena e sessão

Consolidar em **fronteira de cena importante**, quando um checkpoint canônico for útil, e sempre antes de considerar a sessão encerrada. Não consolidar automaticamente depois de cada turno.

```bash
python3 ferramentas/consolidar.py cena
python3 ferramentas/consolidar.py sessao
```

A consolidação aplica o lote pendente uma única vez, atualiza os domínios canônicos afetados, gera/atualiza artefatos da sessão, recalcula runtime e só então remove os eventos do buffer.

Se uma consolidação for interrompida, **não narrar, consultar contexto nem registrar novo turno**. Recuperar primeiro:

```bash
python3 ferramentas/consolidar.py recuperar
```

O journal e o staging preservam os bytes preparados; a recuperação não recalcula nem reaplica deltas. `consolidar.py sessao` não inventa fatos, não incrementa automaticamente a sessão e não escolhe progressão pelo jogador.

## 8. Regras, dados e segredos

Quando houver dúvida de regra, parar assim que resolvida. Preferir `contexto.py regra "assunto"`. Ordem conceitual: resumo interno → decisão anterior → regra da casa → fonte oficial.

Definir dificuldade/modificadores antes do dado. Nunca falsificar resultado. Usar `rolar-dados.py` e, para lotes independentes, `rolar-lote.py`.

`narrador/` é reservado. Busca padrão não inclui esse domínio. Deltas `visibilidade: narrador` não podem ser consolidados em arquivos públicos; rolagens ocultas e relógios reservados permanecem na área do narrador.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa. Não publicar o repositório nem mudar visibilidade sem pedido explícito.

Após alteração canônica **manual** fora do consolidador, regenerar runtime. O consolidador já prepara e instala o runtime correspondente ao novo cânone; não regenerá-lo de novo por rotina.

Verificações estruturais:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Essa suíte pertence a manutenção, consolidação e CI — nunca a cada ação de Ren.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico é documentada em `docs/agente/cobertura-agents-v1.yaml`. As 58 seções antigas possuem destino explícito.

Se faltar detalhe, consulte **apenas** o documento especializado correspondente. Não carregue todos os documentos de `docs/agente/`.
