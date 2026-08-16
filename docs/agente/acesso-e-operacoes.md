# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler, o que escrever e quando fazer checkpoint**. A interface preferencial de leitura é `ferramentas/contexto.py`; durante narração ao vivo, a interface de escrita é `ferramentas/turno.py`. Política formal de níveis e orçamentos: `docs/agente/escada-de-acesso.md`. Consolidação profunda: `docs/agente/consolidacao-transacional.md`. Memória de sessões: `docs/agente/memoria-de-sessoes.md`. Telemetria pós-hoc: `docs/agente/telemetria-rollouts.md`.

## Regra principal de economia de contexto

Antes de qualquer consulta, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum. Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada consulta, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação já disponível e confiável.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados. `runtime/eventos-pendentes.jsonl` contém mudanças posteriores ao último checkpoint. `contexto.py` aplica essas pendências em memória e devolve o estado operacional efetivo.

Relações, medidores de NPC e conhecimento são fragmentados. `sessoes/NNN/handoff.yaml` é memória compacta de retomada. **Transcrições são preservadas integralmente, mas ficam fora da leitura normal.**

## Interface única de consulta

Consultas L1/L2 não exigem declaração de escalada:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py sessao atual
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
```

Busca ampla e histórico exigem declarar qual nível foi insuficiente e a lacuna concreta:

```bash
python3 ferramentas/contexto.py buscar "ponte baixa" \
  --apos L2 --motivo "As consultas dirigidas não localizaram em qual domínio a pista foi registrada."

python3 ferramentas/contexto.py buscar "frase exata" \
  --historico --apos L3 --motivo "A busca corrente não localizou a origem histórica necessária."

python3 ferramentas/contexto.py buscar "frase exata" \
  --historico --transcricoes --apos L4 \
  --motivo "O histórico estruturado não contém a formulação exata necessária."
```

Se a sessão histórica já é conhecida, evitar uma busca L3 artificial:

```bash
python3 ferramentas/contexto.py sessao 2 \
  --apos L2 --motivo "A pergunta aponta diretamente para a sessão 002 e exige seu resumo consolidado."
```

A ferramenta aplica tetos mecânicos por nível: L1 4 KiB; L2/L3 8 KiB; L4 12 KiB; L4T 16 KiB. `--max-bytes` pode reduzir o teto, nunca aumentá-lo.

`--historico` **não** implica transcrição. `--transcricoes` exige `--historico`, `--apos L4` e motivo. `--reservado` também exige motivo concreto.

## Escada de leitura

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — estado quente:** `contexto.py status`.
- **L2 — consulta dirigida:** `cena`, `retomada`, `npc`, `relacao`, `conhecimento`, `regra` ou sessão atual.
- **L3 — descoberta limitada:** `buscar`, com `--apos L2 --motivo`.
- **L4 — histórico estruturado:** `buscar --historico --apos L3 --motivo`; sessão histórica conhecida pode saltar diretamente de L2 para L4.
- **L4T — evidência bruta:** `buscar --historico --transcricoes --apos L4 --motivo`.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa material-base quando a memória interna não bastar.

A escada **não obriga a executar cada degrau**. Uma entidade conhecida pode ir direto a L2; uma sessão histórica conhecida pode saltar L3. Isso evita round-trips inúteis. O que exige sequência explícita é a ampliação de escopo: busca ampla → histórico → transcrição.

Durante narração comum, o alvo é permanecer em L0–L2. Toda saída de `contexto.py` traz `controle_acesso.pare_se_suficiente: true` e a condição de parada do nível.

Observabilidade não cria trabalho no turno: `contexto.py` não grava telemetria local por padrão e os rollouts são analisados somente depois da sessão. Para diagnóstico explícito, `--log-local` habilita o pequeno log local.

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

Ao abrir uma nova sessão, não copiar o último trecho da anterior. Se a pergunta já nomear uma sessão antiga, use o salto dirigido `sessao N --apos L2 --motivo "..."`; transcrição só em L4T.

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

L1. Retorna `runtime/contexto.yaml` com deltas pendentes aplicados em memória. Teto 4 KiB.

### `retomada`

L2. Retorna runtime + cena + memória compacta consolidada da sessão atual + resumos das pendências recentes. **Não abre transcrição.** É a porta padrão depois de pausa, compactação ou processo novo.

### `cena`

L2. Retorna contexto + `runtime/cena.yaml`, também com sobreposição pendente.

### `sessao N`

Sessão atual é L2. Sessão histórica é L4 por alvo dirigido e exige `--apos L2 --motivo`; não paga uma busca L3 desnecessária. Consulta índice/handoff/resumo estruturado sem abrir transcrição.

### `npc`

L2. Resolve índices/fragmentos do NPC e relação e aplica deltas correspondentes ainda pendentes.

### `relacao`

L2. Abre apenas o fragmento atual e aplica os deltas pendentes da entidade. Histórico frio não é lido automaticamente.

### `conhecimento`

L2. Pesquisa conhecimento consolidado — incluindo fragmentos incrementais recentes — e descobertas ainda pendentes de alvo `conhecimento`.

### `regra`

L2. Busca resumos internos. Ausência não autoriza inventar regra.

### `buscar`

L3 sem flags históricas. Exige `--apos L2 --motivo`. `--reservado` acrescenta material do narrador e também exige motivo. `--historico` sobe para L4 e exige `--apos L3`. Apenas `--historico --transcricoes` sobe para L4T e exige `--apos L4`.

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