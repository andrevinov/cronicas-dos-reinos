# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler e qual fluxo executar**. Ele substitui a antiga prática de carregar um conjunto amplo de arquivos por precaução.

## Regra principal de economia de contexto

Antes de qualquer leitura, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum.

Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada leitura, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação que já está disponível e confiável no contexto atual.

Enquanto a camada `runtime/` ainda não existir, aplicar a mesma disciplina sobre os arquivos atuais usando buscas e faixas específicas sempre que possível. A criação do runtime é uma etapa posterior da refatoração.

## Escada transitória de leitura

Usar a menor camada que resolva a pergunta:

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — fonte operacional direta:** ficha, trecho de estado, trecho da sessão atual ou documento explicitamente apontado pela tarefa.
- **L2 — fragmento de domínio:** relação, NPC, regra, local, segredo ou conhecimento especificamente relacionado.
- **L3 — índice/resumo:** resumo de sessão, visão geral regional, decisão de regra ou documento de domínio mais amplo.
- **L4 — histórico profundo:** transcrição antiga, cronologia extensa ou múltiplos documentos para resolver contradição.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa de material-base quando os resumos internos não bastarem.

Escalar apenas por necessidade identificável. A existência de um nível mais profundo não é motivo para consultá-lo.

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

Usar apenas o necessário para a cena atual. Na arquitetura legada, as fontes possíveis incluem `campanha.yaml`, ficha, estado, tempo, relações, relógios, tramas, conhecimento do personagem, resumo anterior, região e segredos relacionados. **Esses itens deixaram de ser uma lista de leitura obrigatória integral:** consultar somente os que forem necessários para a abertura ou decisão concreta.

Na abertura, é aceitável um conjunto um pouco maior para reconstruir com segurança sessão, data, local, estado crítico, situação e segredos diretamente relacionados. Não carregar material remoto à cena apenas porque existe.

### Aplicação de regra

Consultar nesta ordem e parar quando resolvido:

1. resumo específico em `regras/`;
2. decisão anterior equivalente em `regras/decisoes.md`;
3. `regras/regras-da-casa.md`;
4. fonte oficial autorizada, se a dúvida continuar.

### Atualização da ficha

Consultar somente o que se relaciona à alteração: ficha atual, experiência/progressão pertinente, regra aplicável, fonte permitida e decisões de regra relevantes. Não reler criação e progressão completas se a alteração puder ser validada por um fragmento menor.

### Preparação de nova região

Consultar direção real da campanha, cronologia vigente relevante, consequências com alcance regional, relações/facções implicadas, material oficial da região, vizinhança necessária e planos ativos capazes de alcançá-la. Não preparar regiões sem utilidade previsível.

### Encerramento de sessão

Revisar transcrição ou registro bruto, estado inicial, rolagens importantes, decisões do jogador, recursos, relações, consequências, relógios e XP/marcos **na medida necessária para consolidar mudanças**. A futura arquitetura transacional fará essa consolidação em lote.

## Preparação inicial da campanha

Antes da primeira sessão devem estar definidos: edição, período histórico, região inicial, nível inicial, método de atributos, livros/suplementos autorizados, regras da casa, tom, limites, dificuldade, progressão, protocolo de rolagens e personagem inicial. Registrar em `campanha.yaml` ou arquivos diretamente referenciados.

Ravens Bluff é a base regional inicial e deve receber preparação suficiente para sustentar várias sessões antes da expansão. Priorizar The Living City, estrutura urbana, arredores imediatos, facções, NPCs recorrentes, ameaças, rumores e conexões vizinhas. Marcadores temporários só para detalhes menores que não afetem o jogo imediato.

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

Concluída quando resumo, estado, ficha, XP/marco, relações, consequências, tempo, localização e pendências estão suficientes para a próxima sessão começar sem reconstrução manual relevante.

## Prioridade corrente

Prioridades concretas de campanha devem vir de `campanha.yaml` e do estado atual, não de números de sessão hardcoded no manual do agente. A antiga instrução específica de priorizar `sessoes/001` era histórica e foi aposentada nesta refatoração.

Preserva-se o princípio que ela carregava: **não criar dezenas de documentos vazios para satisfazer uma árvore idealizada; criar arquivos quando houver conteúdo real e utilidade previsível.**
