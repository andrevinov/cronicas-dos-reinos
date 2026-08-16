# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler, o que escrever e quando fazer checkpoint**. A interface preferencial de leitura é `ferramentas/contexto.py`; durante narração ao vivo, a interface de escrita é `ferramentas/turno.py`. Consolidação profunda: `docs/agente/consolidacao-transacional.md`. Memória de sessões: `docs/agente/memoria-de-sessoes.md`.

## Regra principal de economia de contexto

Antes de qualquer consulta, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum. Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada consulta, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação já disponível e confiável.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados. `runtime/eventos-pendentes.jsonl` contém mudanças posteriores ao último checkpoint. `contexto.py` aplica essas pendências em memória e devolve o estado operacional efetivo.

Relações, medidores de NPC e conhecimento são fragmentados. `sessoes/NNN/handoff.yaml` é memória compacta de retomada. **Transcrições são preservadas integralmente, mas ficam fora da leitura normal.**

## Interface única de consulta

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py sessao 2
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

A ferramenta possui orçamento padrão de 8 KiB e registra somente metadados opcionais em `runtime/consultas-contexto.jsonl`.

Escaladas deliberadas:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
python3 ferramentas/contexto.py buscar "frase exata" --historico --transcricoes
```

`--historico` **não** implica mais transcrição. Ele inclui memória histórica estruturada. `--transcricoes` exige `--historico` e é a última escalada local antes de fonte externa.

## Escada de leitura

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — estado/retomada quente:** `contexto.py status` ou `contexto.py retomada`.
- **L2 — consulta dirigida:** `cena`, `npc`, `relacao`, `conhecimento`, `regra` ou `sessao N`.
- **L3 — descoberta limitada:** `buscar`, sem histórico frio nem transcrições.
- **L4 — histórico estruturado:** `buscar --historico`, handoffs, resumos, alterações e históricos específicos; transcrições continuam excluídas.
- **L4T — evidência bruta de sessão:** `buscar --historico --transcricoes`, somente quando L4 não resolver a lacuna.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa de material-base quando os resumos internos não bastarem.

Escalar apenas por necessidade identificável. Durante narração comum, o alvo é permanecer em L0–L2.

Nunca substituir consulta a uma relação por leitura de toda `estado/relacoes/`, consulta de conhecimento por abertura recursiva de todos os fragmentos, ou retomada por leitura da transcrição atual/anterior.

## Estado base, pendente e efetivo

Três conceitos devem permanecer separados:

1. **estado consolidado** — arquivos canônicos em `estado/`, ficha, relações e conhecimento;
2. **deltas pendentes** — mudanças posteriores ao último checkpoint, em `runtime/eventos-pendentes.jsonl`;
3. **estado efetivo** — projeção do consolidado + deltas, devolvida por `contexto.py`.

Handoff e índice de sessões são uma quarta categoria: **cache derivado de retomada**, não novo cânone.

Durante jogo ao vivo, consultar o estado efetivo. Não editar o consolidado apenas para a consulta seguinte enxergar uma mudança recém-ocorrida.

## Narração ao vivo — ciclo operacional

```text
ação do jogador
→ L0
→ consulta dirigida somente se faltar algo
→ rolagem(ns) necessária(s)
→ narração
→ turno.py registrar
→ fim da interação
```

Persistir a troca em uma única chamada:

```bash
python3 ferramentas/turno.py registrar <<'JSON'
{
  "jogador": "Ren ...",
  "narracao": "...",
  "resumo": "Mudança operacional curta.",
  "modo": "exploração",
  "deltas": []
}
JSON
```

O registrador escreve apenas `sessoes/NNN/transcricao.md` e `runtime/eventos-pendentes.jsonl`.

Não atualizar na mesma interação, por rotina: estado, tempo, ficha, fragmentos de relação/NPC, conhecimento consolidado, consequências, relógios, handoff, índice de sessões ou arquivos separados de rolagens ocultas. Esses destinos pertencem ao checkpoint.

Também não repetir em prosa o painel completo de PV/CA/Ki/dinheiro/hora/localização quando nada relevante mudou. Mostrar apenas mecânica necessária à decisão/resolução atual.

### O que vira delta

Registrar somente mudança persistente ou necessária para continuidade:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"estado","op":"set","caminho":"localizacao.ponto_exato","valor":"junto à cerca"}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04"}
{"alvo":"relacao:luath","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
```

Se nada persistente mudou, usar `deltas: []`. Não criar delta para cada frase descritiva.

Operações: `set`, `inc`, `append`, `remove`, `registrar`. Deltas podem usar `visibilidade: narrador` quando o conteúdo não pode aparecer em consultas públicas.

### Idempotência do turno

`turno.py` gera ID estável e marca a transcrição. Se o processo cair entre as duas escritas, repetir a mesma entrada repara somente o lado ausente.

```bash
python3 ferramentas/turno.py check
```

Não executar a suíte inteira de integridade depois de cada turno.

## Rolagens em lote

Quando duas ou mais rolagens são independentes e todas já são necessárias antes de conhecer qualquer resultado, usar uma única chamada a `rolar-lote.py`. Não agrupar rolagem cuja existência dependa do resultado anterior.

## Checkpoint — muito menos frequente que turno

Fazer checkpoint no fim de cena importante quando um estado canônico for útil e obrigatoriamente antes de considerar a sessão encerrada:

```bash
python3 ferramentas/checkpoint.py cena
python3 ferramentas/checkpoint.py sessao
```

O fluxo separa duas responsabilidades:

1. `consolidar.py` é o motor canônico: journal/staging, aplicação única dos deltas, runtime novo e limpeza do buffer por último;
2. `checkpoint.py` deriva depois `handoff.yaml` e `sessoes/index.yaml` do estado já instalado.

Essa separação evita contaminar a transação canônica com cache de leitura. Se a segunda fase falhar, regenerar a memória compacta não reaplica deltas.

Se houver `runtime/consolidacao-em-andamento.json`, a operação normal fica bloqueada. Não narrar nem consultar contexto. Recuperar:

```bash
python3 ferramentas/checkpoint.py recuperar
```

Detalhes de mirrors, relações/NPCs, conhecimento incremental, consequências, progressão, segredos, clocks, ledger e staging: `docs/agente/consolidacao-transacional.md`.

## Classificação da tarefa

Classificar mentalmente cada pedido em preparação, pesquisa, criação/progressão, sessão/narração, checkpoint/consolidação, manutenção, correção de continuidade ou revisão de material-base. A classificação escolhe fluxo/documento; não gera leitura extra por si só.

## Leitura por tipo de trabalho

### Retomada ou início de sessão

Começar em L0. Se a continuidade não estiver suficientemente presente, usar **primeiro**:

```bash
python3 ferramentas/contexto.py retomada
```

Isso combina runtime, cena, handoff consolidado e resumos das transações ainda pendentes. Só depois consultar entidade/regra específica.

Ao abrir uma nova sessão, não copiar o último trecho da anterior. Se precisar dela, usar `contexto.py sessao N`, depois L4; transcrição só em L4T.

### Aplicação de regra

Usar `contexto.py regra "assunto"`. Se ainda houver dúvida: decisão anterior equivalente → regra da casa → fonte oficial autorizada. Parar quando resolvido.

### Atualização da ficha

Durante jogo, dano, cura, Ki, moedas, munição e outros recursos entram como deltas; a ficha é sincronizada pela consolidação. Fora do loop narrativo, alteração canônica manual continua exigindo validação e regeneração do runtime quando aplicável.

Depois de `checkpoint.py`, não regenerar runtime/handoff por rotina: o fluxo já os deixa coerentes.

### Preparação de nova região

Consultar direção real, cronologia relevante, consequências de alcance regional, relações/facções implicadas, material oficial necessário e planos capazes de alcançar a região. Não preparar regiões sem utilidade previsível.

### Encerramento e checkpoint

Antes de encerrar a sessão, executar `checkpoint.py sessao` e verificar sucesso. Relações atuais permanecem em seus fragmentos; causas históricas vão para histórico específico. Conhecimento novo entra em fragmentos incrementais e seus índices.

O motor não inventa fatos ausentes dos deltas, não incrementa a sessão automaticamente e não escolhe progressão pelo jogador.

## Semântica dos comandos de contexto

### `status`

Retorna `runtime/contexto.yaml` com deltas pendentes aplicados em memória.

### `retomada`

Retorna runtime + cena + memória compacta consolidada da sessão atual + resumos das pendências recentes. **Não abre transcrição.** É a porta padrão depois de pausa, compactação ou processo novo.

### `cena`

Retorna contexto + `runtime/cena.yaml`, também com sobreposição pendente.

### `sessao N`

Consulta `sessoes/index.yaml` e prefere `handoff.yaml`. Para sessões legadas sem handoff, usa resumo/alterações compactas disponíveis. Não abre transcrição automaticamente.

### `npc`

Resolve índices/fragmentos do NPC e relação e aplica deltas correspondentes ainda pendentes.

### `relacao`

Abre apenas o fragmento atual e aplica os deltas pendentes da entidade. Histórico frio não é lido automaticamente.

### `conhecimento`

Pesquisa conhecimento consolidado — incluindo fragmentos incrementais recentes — e descobertas ainda pendentes de alvo `conhecimento`.

### `regra`

Busca resumos internos. Ausência não autoriza inventar regra.

### `buscar`

Sem flags, é descoberta limitada. `--reservado` acrescenta material do narrador. `--historico` acrescenta histórico estruturado. Apenas `--historico --transcricoes` acrescenta transcrições brutas.

## Runtime e memória de sessões

`runtime/contexto.yaml` e `runtime/cena.yaml` permanecem pequenos. Durante turno, `contexto.py` projeta deltas sem regravá-los.

`sessoes/index.yaml` contém metadados/ponteiros, não prosa acumulada. `handoff.yaml` tem teto de 8 KiB e é derivado de runtime/cena + ledger, não da transcrição. A transcrição continua crescendo como registro histórico, mas não como contexto operacional.

## Comandos conceituais

- **"Preparar a campanha"**: completar configuração e documentos mínimos.
- **"Criar meu personagem"**: executar criação conforme edição e fontes.
- **"Preparar a próxima sessão"**: preparar abertura e possibilidades prováveis sem avançar indevidamente o mundo.
- **"Iniciar/retomar a sessão"**: usar `contexto.py retomada` e narrar com o mínimo seguro.
- **"Encerrar a sessão"**: executar `checkpoint.py sessao`, validar e então encerrar.
- **"Conferir meu XP"**: recalcular histórico relevante e apontar divergências.
- **"Quais opções eu tenho para evoluir?"**: consultar ficha, fontes, pré-requisitos e caminhos registrados.
- **"Reavaliar o material-base"**: investigar lacunas e atualizar resumos.
- **"Preparar a região"**: criar apenas material necessário à área relevante.
- **"Conferir a continuidade"**: começar por memória compacta e escalar só se necessário.

## Critérios de conclusão

Uma regra está resumida quando pode ser aplicada sem consulta constante ao livro. Uma região está preparada quando sustenta decisões sem árvore rígida. Um personagem está criado quando escolhas/cálculos estão salvos. Uma sessão está preparada quando a abertura e agentes relevantes estão claros.

Uma sessão só está realmente encerrada quando o checkpoint canônico concluiu, o buffer não contém as transações aplicadas, os artefatos necessários foram atualizados e handoff/índice representam o novo ponto de retomada.

## Prioridade corrente

Prioridades concretas vêm de `campanha.yaml`, estado consolidado e estado efetivo consultado por `contexto.py`, não de números hardcoded em documentação.

Preserva-se o princípio: **não criar arquivos vazios para satisfazer uma árvore idealizada; criar estrutura quando houver conteúdo real e utilidade previsível.**
