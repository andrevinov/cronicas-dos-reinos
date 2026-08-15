# AGENTS.md — roteador operacional de Crônicas dos Reinos

Este arquivo contém apenas instruções que precisam estar disponíveis em praticamente qualquer tarefa. O detalhamento está em `docs/agente/` e deve ser lido **somente quando a tarefa exigir**.

## 1. Fonte de verdade

O repositório é a memória canônica da campanha. Não depender apenas da conversa para fatos persistentes.

Respeitar sistema, edição, período histórico, fontes autorizadas e configuração de `campanha.yaml` e `regras/fontes.md`. Não misturar silenciosamente regras de outras edições ou fontes não autorizadas.

Todo texto novo deve usar português e UTF-8.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados do último estado consolidado. Durante sessão ativa, `runtime/eventos-pendentes.jsonl` é a sobreposição transacional ainda não consolidada. A saída de `ferramentas/contexto.py` combina base + pendências e representa o **estado operacional efetivo**, mas não substitui o cânone consolidado.

Desde a Etapa 5, `estado/estado-atual.yaml` e `estado/tempo.yaml` descrevem **somente o presente consolidado**. Cronologia pertence a `sessoes/`; `historico/legado/` preserva depósitos antigos para auditoria e recuperação excepcional.

Desde a Etapa 6, relações, medidores de NPC e conhecimento são fragmentados. `estado/relacoes.yaml`, `estado/medidores-npcs.yaml` e `personagens/jogador/conhecimento.md` são roteadores. Presente detalhado vive nos fragmentos; históricos frios ficam fora da leitura normal.

## 2. Invariantes inegociáveis

1. O jogador controla Ren: decisões, falas, intenções, crenças, emoções definitivas e ações voluntárias.
2. O narrador controla mundo, NPCs, forças externas, regras e consequências.
3. Não garantir vitória nem alterar dificuldade, capacidades ou resultado depois de conhecer uma rolagem.
4. O mundo continua agindo fora da presença de Ren; NPCs e facções têm objetivos próprios.
5. Conhecimento do narrador, de NPCs, de facções, de Ren e do jogador são camadas diferentes.
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
4. eventos transacionais pendentes da sessão atual, apenas para mudanças posteriores à consolidação;
5. sessões concluídas;
6. `regras/decisoes.md`;
7. regras da casa;
8. resumos internos;
9. fontes oficiais autorizadas;
10. possibilidades futuras.

Runtime-base, índices e resultados de consulta não são cânone independente. Eventos pendentes só têm precedência temporal sobre o estado consolidado para a sessão em curso; a consolidação posterior precisa incorporá-los sem duplicação.

Erro conhecido não deve ser preservado apenas por estar em fonte de alta autoridade: identificar o conflito, verificar mudança posterior e corrigir explicitamente.

## 4. Economia de contexto — regra obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.**

Antes de chamar ferramenta ou abrir arquivo, pergunte se o contexto já disponível basta. Se bastar, não leia nada.

Depois de cada consulta, pergunte novamente se já é suficiente. **Se for suficiente, pare.**

Durante operação normal, preferir `ferramentas/contexto.py` a `cat`, `sed`, `rg` ou abertura integral de arquivos canônicos. A ferramenta resolve índice → fragmento e também aplica deltas pendentes relevantes.

Não:

- ler o repositório inteiro para se situar;
- abrir pasta inteira quando uma entidade específica basta;
- reler informação confiável já presente no contexto;
- abrir todos os fragmentos preventivamente;
- abrir histórico de relação para responder ao estado atual dela;
- abrir transcrição antiga antes de tentar runtime, consulta dirigida ou resumo;
- consultar `historico/legado/` para uma pergunta normal;
- consultar livro oficial se resumo ou decisão interna já resolver;
- continuar pesquisando apenas para confirmar algo já estabelecido com segurança.

Escada de leitura:

- **L0:** contexto atual, nenhuma leitura;
- **L1:** `python3 ferramentas/contexto.py status`;
- **L2:** `contexto.py cena`, `npc`, `relacao`, `conhecimento` ou `regra`;
- **L3:** `contexto.py buscar "termo"`, sem histórico frio;
- **L4:** `contexto.py buscar "termo" --historico`, histórico específico ou transcrição necessária;
- **L5:** fonte oficial externa/autorizada.

Para material reservado, só usar `--reservado` quando existir lacuna concreta de bastidor. Só subir quando o nível anterior não responder à pergunta necessária.

Fluxos detalhados: `docs/agente/acesso-e-operacoes.md`.

## 5. Roteamento por tarefa

Leia **no máximo os documentos especializados necessários**:

- fundamentos, autoridade, segredo, agência, proibições → `docs/agente/fundamentos.md`;
- acesso, preparação, operação, protocolo transacional → `docs/agente/acesso-e-operacoes.md`;
- regra, decisão, CD, teste, rolagem → `docs/agente/regras-e-rolagens.md`;
- narração, NPC, facção, relógio, consequência, relação, memória → `docs/agente/narracao-e-mundo.md`;
- ficha, progressão, inventário, recursos, tempo/viagem → `docs/agente/personagem-e-tempo.md`;
- pesquisa, região, retcon, edição, YAML, ferramentas, Git → `docs/agente/pesquisa-e-manutencao.md`.

Estilo: `narracao/guia-de-narrativa.md`. Fluxo de sessão: `narracao/protocolo-de-sessao.md`. Limites: `narracao/limites.md`.

## 6. Narração ao vivo — protocolo transacional obrigatório

Fluxo normal:

`ação do jogador → contexto já disponível → consulta somente se faltar algo → rolagens necessárias → narração → turno.py registrar → fim`.

Durante **cada avanço narrativo comum**:

- não atualizar `estado/`, ficha, relações, conhecimento, consequências, relógios ou arquivos de NPC diretamente;
- não regenerar `runtime/contexto.yaml` ou `runtime/cena.yaml` por causa do turno;
- não executar auditoria ampla, `git diff`, `git status`, commit ou validação global por rotina;
- registrar a fala/ação do jogador e a resposta do narrador junto com os deltas em **uma única chamada** a `ferramentas/turno.py registrar`;
- o registrador deve alterar somente a transcrição atual e `runtime/eventos-pendentes.jsonl`;
- registrar deltas mínimos de recursos, tempo, localização, modo de cena, relação, conhecimento, consequência ou outro efeito persistente realmente alterado;
- não copiar a narração para o JSONL: nele entram apenas resumo curto e deltas;
- rolagens ocultas relevantes podem ficar no registro transacional reservado até consolidação, sem terceira escrita durante o turno.

O `contexto.py` enxerga as pendências e devolve o estado efetivo. Portanto uma pausa no meio da sessão **não exige consolidação imediata**.

Se duas ou mais rolagens independentes já forem conhecidas antes da chamada, preferir `ferramentas/rolar-lote.py` para executá-las em uma única rodada de ferramenta. Não agrupar artificialmente rolagens cuja necessidade depende do resultado anterior.

O objetivo operacional é **duas escritas por avanço**: transcrição + buffer de deltas. Consolidação canônica acontece em lote, não a cada troca.

## 7. Regras e dados

Quando houver dúvida, parar assim que estiver resolvida. Preferir `python3 ferramentas/contexto.py regra "assunto"`.

A ordem conceitual continua: resumo interno → decisão anterior → regra da casa → fonte oficial.

Rolagem só quando houver incerteza real e consequência relevante. Definir dificuldade/modificadores antes do dado. Nunca falsificar ou corrigir resultado depois.

Usar `ferramentas/rolar-dados.py`; para rolagens independentes em lote, `ferramentas/rolar-lote.py`.

## 8. Segredos

`narrador/` é reservado. Não revelar conteúdo, nomes secretos, caminhos ou inferências de bastidor sem descoberta legítima. Ao justificar decisão, explicar apenas o que Ren poderia perceber.

Busca padrão não inclui `narrador/`. Deltas com `visibilidade: narrador` e `rolagens_ocultas` não entram em consultas públicas normais.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa. Não publicar o repositório nem mudar visibilidade sem pedido explícito.

Fora da narração ao vivo, após alteração canônica consolidada que mude a situação atual, regenerar `runtime/`.

Verificações estruturais:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Não execute essa suíte inteira depois de cada ação de Ren. Ela pertence a manutenção, consolidação e CI.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico é documentada em `docs/agente/cobertura-agents-v1.yaml`. As 58 seções antigas possuem destino explícito.

Se uma tarefa exigir detalhe que não esteja neste roteador, consulte **apenas** o documento especializado correspondente. Não carregue todos os documentos de `docs/agente/`.
