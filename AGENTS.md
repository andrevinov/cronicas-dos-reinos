# AGENTS.md — roteador operacional de Crônicas dos Reinos

Este arquivo contém apenas instruções que precisam estar disponíveis em praticamente qualquer tarefa. O detalhamento foi movido para `docs/agente/` e deve ser lido **somente quando a tarefa exigir**.

## 1. Fonte de verdade

O repositório é a memória canônica da campanha. Não depender apenas da conversa para fatos persistentes.

Respeitar sistema, edição, período histórico, fontes autorizadas e configuração de `campanha.yaml` e `regras/fontes.md`. Não misturar silenciosamente regras de outras edições ou fontes não autorizadas.

Todo texto novo deve usar português e UTF-8.

`runtime/` é uma camada derivada e descartável de acesso rápido; **não é fonte canônica**. Se divergir das fontes, regenerar o runtime a partir delas.

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
3. ficha atual;
4. estado atual;
5. sessões concluídas;
6. `regras/decisoes.md`;
7. regras da casa;
8. resumos internos;
9. fontes oficiais autorizadas;
10. possibilidades futuras.

`runtime/` não entra nessa hierarquia porque é projeção operacional das fontes acima.

Erro conhecido não deve ser preservado apenas por estar em fonte de alta autoridade: identificar o conflito, verificar mudança posterior e corrigir explicitamente.

## 4. Economia de contexto — regra obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.**

Antes de chamar ferramenta ou abrir arquivo, pergunte se o contexto já disponível basta. Se bastar, não leia nada.

Depois de cada leitura, pergunte novamente se já é suficiente. **Se for suficiente, pare.**

Não:

- ler o repositório inteiro para se situar;
- abrir pasta inteira quando uma entidade específica basta;
- reler informação confiável já presente no contexto;
- abrir estado canônico gigante quando `runtime/` responder;
- abrir transcrição antiga antes de tentar runtime/resumo/estado;
- consultar livro oficial se resumo ou decisão interna já resolver;
- continuar pesquisando apenas para confirmar algo já estabelecido com segurança.

Escada de leitura:

- **L0:** contexto atual, nenhuma leitura;
- **L1:** `runtime/contexto.yaml`;
- **L2:** `runtime/cena.yaml` ou fragmento específico apontado pelo runtime;
- **L3:** índice, resumo ou documento de domínio mais amplo;
- **L4:** estado histórico profundo, transcrição ou múltiplas fontes para resolver conflito;
- **L5:** fonte oficial externa/autorizada.

Só subir quando o nível anterior não responder à pergunta necessária.

Fluxos detalhados: `docs/agente/acesso-e-operacoes.md`.

## 5. Roteamento por tarefa

Leia **no máximo os documentos especializados necessários**:

- fundamentos, autoridade, segredo, agência, proibições → `docs/agente/fundamentos.md`;
- escolha de arquivos, preparação, comandos conceituais, critérios de conclusão → `docs/agente/acesso-e-operacoes.md`;
- regra, decisão, CD, teste, rolagem aberta/oculta → `docs/agente/regras-e-rolagens.md`;
- narração, NPC, facção, relógio, consequência, relação, memória de sessão → `docs/agente/narracao-e-mundo.md`;
- ficha, criação, progressão, inventário, recursos, tempo/viagem → `docs/agente/personagem-e-tempo.md`;
- pesquisa, região, fonte, retcon, edição de arquivos, YAML, ferramentas, Git → `docs/agente/pesquisa-e-manutencao.md`.

O estilo narrativo continua em `narracao/guia-de-narrativa.md`; o fluxo de sessão em `narracao/protocolo-de-sessao.md`; limites em `narracao/limites.md`.

## 6. Narração ao vivo

Durante narração:

- usar primeiro o contexto já carregado;
- se faltar estado operacional, ler `runtime/contexto.yaml`;
- se faltar situação imediata da cena, ler `runtime/cena.yaml`;
- seguir ponteiro para arquivo canônico somente quando o runtime não resolver a lacuna;
- consultar somente fatos que afetem a resposta atual;
- não transformar escolhas em menu rígido;
- não revelar bastidores;
- não repetir estado mecânico inteiro se nada relevante mudou;
- manter registro suficiente para consolidação posterior sem interromper a cena.

`runtime/eventos-pendentes.jsonl` já existe, mas a arquitetura transacional de escrita será implantada em etapa posterior. Até lá, evitar duplicação documental desnecessária sem deixar estado crítico inconsistente.

## 7. Regras e dados

Quando houver dúvida, parar assim que estiver resolvida: resumo interno → decisão anterior → regra da casa → fonte oficial.

Rolagem só quando houver incerteza real e consequência relevante. Definir dificuldade/modificadores antes do dado. Nunca falsificar ou corrigir resultado depois.

Usar `ferramentas/rolar-dados.py` quando aplicável.

## 8. Segredos

`narrador/` é reservado. Não revelar conteúdo, nomes secretos, caminhos ou inferências de bastidor sem descoberta legítima. Ao justificar uma decisão, explicar apenas o que Ren poderia perceber.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa. Não publicar o repositório nem mudar visibilidade sem pedido explícito.

Após alteração canônica que mude a situação atual, regenerar:

```bash
python3 ferramentas/gerar-runtime.py
```

Após mudança estrutural ou migração, executar:

```bash
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
python3 ferramentas/verificar-integridade.py --baseline baseline/estado-logico-2026-08-15.yaml
```

Durante a refatoração, a baseline protege os fatos essenciais enquanto a estrutura muda.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico é documentada em `docs/agente/cobertura-agents-v1.yaml`. As 58 seções antigas possuem destino explícito; adaptações intencionais estão registradas ali.

Se uma tarefa exigir detalhe que não esteja neste roteador, consulte **apenas** o documento especializado correspondente. Não use o tamanho reduzido deste arquivo como motivo para carregar todos os documentos de `docs/agente/`.
