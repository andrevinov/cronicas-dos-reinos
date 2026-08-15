# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler e qual fluxo executar**. A interface preferencial de leitura operacional é `ferramentas/contexto.py`.

## Regra principal de economia de contexto

Antes de qualquer consulta, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum.

Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada consulta, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação que já está disponível e confiável no contexto atual.

`runtime/` continua sendo derivado e descartável. `contexto.py` é apenas a porta de leitura mais econômica sobre runtime e fontes canônicas; a saída da ferramenta também não se torna cânone.

Relações, medidores de NPC e conhecimento são fragmentados. A ferramenta resolve índices pequenos e abre somente o fragmento necessário. Os antigos monólitos preservados em `historico/legado/` são material de auditoria, não memória operacional.

## Interface única de consulta

Usar preferencialmente:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

A ferramenta possui orçamento padrão de saída e compacta resultados antes de devolver conteúdo excessivo. Consultas locais registram apenas metadados em `runtime/consultas-contexto.jsonl`, arquivo ignorado pelo Git: comando, nível, número de fontes, bytes devolvidos e se houve truncamento. Nenhum conteúdo consultado é gravado nesse log.

A busca genérica não inclui `narrador/`, `historico/` nem transcrições completas por padrão. Quando necessário:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

`--reservado` é deliberado porque material de `narrador/` pode conter segredos. `--historico` é deliberado porque histórico frio e transcrições são camadas volumosas. Não usar essas opções preventivamente.

## Escada de leitura

Usar a menor camada que resolva a pergunta:

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — estado quente:** `contexto.py status`.
- **L2 — consulta dirigida:** `cena`, `npc`, `relacao`, `conhecimento` ou `regra`.
- **L3 — descoberta limitada:** `buscar`, sem histórico frio/transcrições completas.
- **L4 — histórico profundo:** `buscar --historico`, histórico específico de uma relação ou leitura de fonte histórica apontada por consulta anterior.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa de material-base quando os resumos internos não bastarem.

Escalar apenas por necessidade identificável. A existência de um nível mais profundo não é motivo para consultá-lo. Durante narração comum, o alvo é permanecer em L0–L2.

Leitura direta com `cat`, `sed`, `rg` ou abertura integral de arquivo canônico continua permitida quando a ferramenta apontar uma fonte específica e o fragmento retornado não bastar, ou durante tarefas estruturais de manutenção. Na narração comum, é exceção.

Nunca substituir uma consulta a uma relação por leitura de toda `estado/relacoes/`, nem uma consulta de conhecimento por abertura recursiva de `personagens/jogador/conhecimento/`. A fragmentação existe para que o acesso seja dirigido.

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

Começar em L0. Se faltar estado operacional, usar `contexto.py status`; se faltar o recorte imediato, usar `contexto.py cena`. Só consultar entidade, regra ou histórico quando a resposta atual depender disso.

Na abertura de sessão é aceitável consultar um pouco mais para reconstruir sessão, data, local, estado crítico, situação e segredos diretamente relacionados. Ainda assim, usar consultas dirigidas antes de arquivos completos.

### Aplicação de regra

Usar `contexto.py regra "assunto"`. A busca interna percorre os resumos de `regras/` e devolve apenas as seções mais relevantes.

Se ainda houver dúvida, seguir e parar assim que resolvido:

1. decisão anterior equivalente em `regras/decisoes.md`;
2. `regras/regras-da-casa.md`;
3. fonte oficial autorizada.

### Atualização da ficha

Consultar somente o que se relaciona à alteração: ficha atual, experiência/progressão pertinente, regra aplicável, fonte permitida e decisões de regra relevantes. Não reler criação e progressão completas se a alteração puder ser validada por um fragmento menor.

Depois de mudança canônica que altere recursos, nível, tempo, localização ou cena, regenerar `runtime/`.

### Preparação de nova região

Consultar direção real da campanha, cronologia vigente relevante, consequências com alcance regional, relações/facções implicadas, material oficial da região, vizinhança necessária e planos ativos capazes de alcançá-la. Não preparar regiões sem utilidade previsível.

### Encerramento de sessão

Revisar transcrição ou registro bruto, estado inicial, rolagens importantes, decisões do jogador, recursos, relações, consequências, relógios e XP/marcos **na medida necessária para consolidar mudanças**. A futura arquitetura transacional fará essa consolidação em lote.

Ao atualizar uma relação, escrever o estado corrente no fragmento da entidade; histórico cronológico pertence à camada histórica/sessão, não deve voltar a inflar o fragmento atual. Conhecimento adquirido deve entrar em fragmentos coerentes e manter os índices reconstruíveis.

Após consolidar as fontes canônicas, regenerar o runtime; nunca consolidar o cânone a partir do runtime como se ele fosse autoridade histórica.

## Semântica dos comandos de contexto

### `status`

Retorna somente `runtime/contexto.yaml`: sessão, personagem, recursos, tempo, localização e ponteiros. É a consulta operacional mais barata.

### `cena`

Retorna contexto quente e `runtime/cena.yaml`: resumo imediato, mecânica da cena e alertas/prazos. Não repetir se esses dados já estão no contexto da conversa.

### `npc`

Resolve `estado/npcs/index.yaml` e, quando necessário, `estado/relacoes/index.yaml`, abrindo no máximo os fragmentos correspondentes. Combina medidores do NPC e relação atual com Ren. Não carrega automaticamente histórico da relação nem segredos de `narrador/`.

### `relacao`

Resolve `estado/relacoes/index.yaml` e abre somente `estado/relacoes/<id>.yaml`. A resposta inclui um ponteiro para `historico/relacoes/<id>.yaml`, mas o histórico não é lido na consulta normal.

### `conhecimento`

Consulta `personagens/jogador/conhecimento/ativo.yaml`/`index.yaml` e pesquisa apenas os fragmentos Markdown pertinentes. Serve para responder **o que Ren sabe**, não o que é objetivamente verdadeiro nos bastidores. O arquivo `personagens/jogador/conhecimento.md` é apenas um roteador.

### `regra`

Busca seções nos resumos internos de `regras/`. Ausência de resultado não autoriza inventar regra; nesse caso, escalar segundo a hierarquia de fontes.

### `buscar`

É ferramenta de descoberta, não primeira escolha. Procura ocorrências pequenas nos domínios operacionais e nos resumos de sessão. Por padrão, não consulta `narrador/`, `historico/` nem `transcricao.md`; `--historico` inclui explicitamente as camadas frias.

## Runtime

`runtime/contexto.yaml` deve permanecer pequeno e conter somente estado operacional: sessão, personagem, recursos, tempo, localização e ponteiros.

`runtime/cena.yaml` deve conter um recorte ainda menor da situação imediata. `runtime/eventos-pendentes.jsonl` está reservado para a futura arquitetura transacional.

Comandos de geração:

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

Se `--check` falhar, não usar runtime desatualizado para narrar.

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

Concluída quando resumo, estado, ficha, XP/marco, relações, consequências, tempo, localização e pendências estão suficientes para a próxima sessão começar sem reconstrução manual relevante; o runtime foi regenerado a partir desse estado consolidado.

## Prioridade corrente

Prioridades concretas de campanha devem vir de `campanha.yaml`, do estado canônico e, para acesso rápido, de `runtime/`, não de números de sessão hardcoded no manual do agente.

Preserva-se o princípio: **não criar dezenas de documentos vazios para satisfazer uma árvore idealizada; criar arquivos quando houver conteúdo real e utilidade previsível.**
