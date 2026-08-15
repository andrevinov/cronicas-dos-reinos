# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler e qual fluxo executar**. Ele substitui a antiga prática de carregar um conjunto amplo de arquivos por precaução.

## Regra principal de economia de contexto

Antes de qualquer leitura, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum.

Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada leitura, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação que já está disponível e confiável no contexto atual.

A camada `runtime/` existe para concentrar o estado quente. Ela é derivada e descartável: serve para leitura rápida, mas não substitui as fontes canônicas. Divergência entre runtime e fonte canônica significa runtime desatualizado, não autorização para alterar o cânone a partir dele.

## Escada de leitura

Usar a menor camada que resolva a pergunta:

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — estado quente:** `runtime/contexto.yaml`.
- **L2 — cena ou fragmento específico:** `runtime/cena.yaml` ou um único arquivo apontado pelo runtime para NPC, relação, regra, lugar, segredo ou conhecimento.
- **L3 — índice/resumo:** resumo de sessão, visão geral regional, decisão de regra ou documento de domínio mais amplo.
- **L4 — histórico profundo:** estado acumulativo, transcrição antiga, cronologia extensa ou múltiplos documentos para resolver contradição.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa de material-base quando os resumos internos não bastarem.

Escalar apenas por necessidade identificável. A existência de um nível mais profundo não é motivo para consultá-lo.

Durante narração comum, o alvo é permanecer em L0–L2. L4 e L5 devem ser excepcionais.

## Classificação da tarefa

Classificar mentalmente cada pedido em uma ou mais categorias:

- preparação inicial;
- pesquisa de regra;
- pesquisa de cenário;
- criação de personagem;
- progressão;
- preparação de sessão;
- narração ao vivo;
- encerramento de sessão;
- manutenção de estado;
- correção de continuidade;
- criação de ferramenta;
- revisão do material-base.

A classificação serve para escolher o fluxo e os documentos especializados; não deve gerar leitura extra por si só.

## Leitura por tipo de trabalho

### Narração ou início de sessão

1. Tentar L0: contexto já carregado.
2. Se faltar estado operacional, ler `runtime/contexto.yaml`.
3. Se faltar situação imediata, ler `runtime/cena.yaml`.
4. Somente então seguir um ponteiro específico para relação, regra, segredo, conhecimento, estado completo ou histórico.

Na abertura de sessão é aceitável um conjunto um pouco maior, mas ainda deve começar pelo runtime. Não carregar material remoto à cena apenas porque existe.

Os arquivos `estado/estado-atual.yaml`, `estado/tempo.yaml`, `estado/relacoes.yaml`, `personagens/jogador/conhecimento.md` e transcrições não são mais fontes de primeira leitura para se situar. São camadas profundas acessadas quando a lacuna concreta exigir.

### Aplicação de regra

Consultar nesta ordem e parar quando resolvido:

1. resumo específico em `regras/`;
2. decisão anterior equivalente em `regras/decisoes.md`;
3. `regras/regras-da-casa.md`;
4. fonte oficial autorizada, se a dúvida continuar.

### Atualização da ficha

Consultar somente o que se relaciona à alteração: ficha atual, experiência/progressão pertinente, regra aplicável, fonte permitida e decisões de regra relevantes. Não reler criação e progressão completas se a alteração puder ser validada por um fragmento menor.

Depois de mudança canônica que altere recursos, nível, tempo, localização ou cena, regenerar `runtime/`.

### Preparação de nova região

Consultar direção real da campanha, cronologia vigente relevante, consequências com alcance regional, relações/facções implicadas, material oficial da região, vizinhança necessária e planos ativos capazes de alcançá-la. Não preparar regiões sem utilidade previsível.

### Encerramento de sessão

Revisar transcrição ou registro bruto, estado inicial, rolagens importantes, decisões do jogador, recursos, relações, consequências, relógios e XP/marcos **na medida necessária para consolidar mudanças**. A futura arquitetura transacional fará essa consolidação em lote.

Após consolidar as fontes canônicas, regenerar o runtime; nunca consolidar o cânone a partir do runtime como se ele fosse autoridade histórica.

## Preparação inicial da campanha

Antes da primeira sessão devem estar definidos: edição, período histórico, região inicial, nível inicial, método de atributos, livros/suplementos autorizados, regras da casa, tom, limites, dificuldade, progressão, protocolo de rolagens e personagem inicial. Registrar em `campanha.yaml` ou arquivos diretamente referenciados.

Ravens Bluff é a base regional inicial e deve receber preparação suficiente para sustentar várias sessões antes da expansão. Priorizar The Living City, estrutura urbana, arredores imediatos, facções, NPCs recorrentes, ameaças, rumores e conexões vizinhas. Marcadores temporários só para detalhes menores que não afetem o jogo imediato.

## Runtime

`runtime/contexto.yaml` deve permanecer pequeno e conter somente estado operacional: sessão, personagem, recursos, tempo, localização e ponteiros.

`runtime/cena.yaml` deve conter um recorte ainda menor da situação imediata. O resumo de cena é derivado do final cronológico de `localizacao.descricao_operacional`; ele existe para evitar a leitura integral do estado acumulativo.

`runtime/eventos-pendentes.jsonl` está reservado para a futura arquitetura transacional. Enquanto ela não for implantada, a existência do arquivo não muda as obrigações atuais de consolidação.

Comandos:

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

O modo `--check` deve fazer parte dos testes de integridade. Se falhar, não usar runtime desatualizado para narrar.

## Comandos conceituais

Interpretar pedidos informais conforme a intenção operacional:

- **"Preparar a campanha"**: completar configuração e documentos mínimos.
- **"Criar meu personagem"**: executar criação conforme edição e fontes.
- **"Preparar a próxima sessão"**: preparar abertura e possibilidades prováveis sem avançar indevidamente o mundo.
- **"Iniciar a sessão"**: carregar o mínimo seguro, abrir registro e narrar.
- **"Encerrar a sessão"**: consolidar registros, estado, XP, relações, consequências e pendências.
- **"Conferir meu XP"**: recalcular histórico relevante e apontar divergências.
- **"Quais opções eu tenho para evoluir?"**: consultar ficha, fontes, pré-requisitos e caminhos registrados.
- **"Reavaliar o material-base"**: investigar lacunas de regras/cenário e atualizar resumos.
- **"Preparar a região"**: criar apenas o material necessário para a área relevante.
- **"Conferir a continuidade"**: buscar contradições entre sessões, estado, ficha e registros.

## Critérios de conclusão

### Resumo de regra

Concluído quando identifica edição/fonte, explica procedimento, registra exceções, distingue oficial/adaptação e pode ser usado sem consulta constante ao livro.

### Região preparada

Concluída quando há visão geral suficiente, locais principais, NPCs/facções com objetivos, conflitos, rumores/ameaças, segredos necessários, consequências incorporadas e material suficiente para improvisar as primeiras decisões do jogador.

### Personagem criado

Concluído quando escolhas obrigatórias estão feitas, cálculos conferidos, ficha salva, histórico inicial registrado, recursos definidos, progressão inicial documentada e vínculo com o cenário coerente.

### Sessão preparada

Concluída quando o estado necessário foi revisado, a cena inicial está clara, NPCs relevantes têm objetivos, regras prováveis estão acessíveis, consequências/relógios necessários foram considerados, segredos pertinentes estão disponíveis e a preparação não depende de uma escolha específica do jogador.

### Sessão encerrada

Concluída quando resumo, estado, ficha, XP/marco, relações, consequências, tempo, localização e pendências estão suficientes para a próxima sessão começar sem reconstrução manual relevante; o runtime foi regenerado a partir desse estado consolidado.

## Prioridade corrente

Prioridades concretas de campanha devem vir de `campanha.yaml`, do estado canônico e, para acesso rápido, de `runtime/`, não de números de sessão hardcoded no manual do agente.

Preserva-se o princípio de não criar dezenas de documentos vazios para satisfazer uma árvore idealizada; criar arquivos quando houver conteúdo real e utilidade previsível.
