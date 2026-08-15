# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler, o que escrever e quando consolidar**. A interface preferencial de leitura é `ferramentas/contexto.py`; durante narração ao vivo, a interface de escrita é `ferramentas/turno.py`. O protocolo profundo de consolidação fica em `docs/agente/consolidacao-transacional.md` e só deve ser lido quando esse trabalho for necessário.

## Regra principal de economia de contexto

Antes de qualquer consulta, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum. Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada consulta, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação já disponível e confiável.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados. `runtime/eventos-pendentes.jsonl` contém mudanças posteriores ao último checkpoint consolidado. `contexto.py` aplica essas pendências em memória e devolve o estado operacional efetivo.

Relações, medidores de NPC e conhecimento são fragmentados. A ferramenta resolve índices pequenos e abre somente o fragmento necessário. Monólitos em `historico/legado/` são material de auditoria.

## Interface única de consulta

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

A ferramenta possui orçamento padrão de 8 KiB e registra somente metadados opcionais em `runtime/consultas-contexto.jsonl`.

A busca genérica não inclui `narrador/`, `historico/` nem transcrições completas por padrão:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

`--reservado` e `--historico` são escaladas deliberadas, nunca opções de rotina.

## Escada de leitura

- **L0 — contexto já disponível:** nenhuma leitura.
- **L1 — estado quente efetivo:** `contexto.py status`.
- **L2 — consulta dirigida:** `cena`, `npc`, `relacao`, `conhecimento` ou `regra`.
- **L3 — descoberta limitada:** `buscar`, sem histórico frio/transcrições completas.
- **L4 — histórico profundo:** `buscar --historico`, histórico específico ou transcrição apontada por necessidade concreta.
- **L5 — fonte externa/autorizada:** livros oficiais ou pesquisa de material-base quando os resumos internos não bastarem.

Escalar apenas por necessidade identificável. Durante narração comum, o alvo é permanecer em L0–L2.

Nunca substituir uma consulta a uma relação por leitura de toda `estado/relacoes/`, nem uma consulta de conhecimento por abertura recursiva de `personagens/jogador/conhecimento/`.

## Estado base, pendente e efetivo

Três conceitos devem permanecer separados:

1. **estado consolidado** — arquivos canônicos em `estado/`, ficha, relações e conhecimento;
2. **deltas pendentes** — mudanças ocorridas depois do último checkpoint, em `runtime/eventos-pendentes.jsonl`;
3. **estado efetivo** — projeção do consolidado + deltas, devolvida por `contexto.py`.

Durante jogo ao vivo, consultar o estado efetivo. Não editar o consolidado apenas para fazer uma consulta seguinte enxergar uma mudança recém-ocorrida.

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

Não atualizar na mesma interação, por rotina: estado, tempo, ficha, fragmentos de relação/NPC, conhecimento consolidado, consequências, relógios ou arquivos separados de rolagens ocultas. Esses destinos pertencem à consolidação em lote.

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

## Consolidação — checkpoint, não turno

A consolidação deve ser **muito menos frequente que a narração**. Usar no fim de uma cena importante quando um checkpoint canônico for útil e obrigatoriamente antes de considerar a sessão encerrada:

```bash
python3 ferramentas/consolidar.py cena
python3 ferramentas/consolidar.py sessao
```

O consolidador usa os deltas já registrados; não precisa reconstituir mudanças vasculhando a campanha. Ele prepara todos os bytes finais antes da primeira escrita, atualiza somente os domínios afetados, instala o novo runtime no mesmo lote e remove as transações aplicadas do buffer por último.

Se houver `runtime/consolidacao-em-andamento.json`, a operação normal fica bloqueada. Não narrar nem consultar contexto. Recuperar:

```bash
python3 ferramentas/consolidar.py recuperar
```

A recuperação instala os bytes já preparados; não recalcula nem reaplica incrementos.

Detalhes de mirrors, relações/NPCs, conhecimento incremental, consequências, progressão, segredos, clocks, ledger e staging: `docs/agente/consolidacao-transacional.md`.

## Classificação da tarefa

Classificar mentalmente cada pedido em preparação, pesquisa, criação/progressão, sessão/narração, consolidação, manutenção, correção de continuidade ou revisão de material-base. A classificação escolhe fluxo/documento; não gera leitura extra por si só.

## Leitura por tipo de trabalho

### Narração ou início de sessão

Começar em L0. Se faltar estado, `contexto.py status`; se faltar recorte imediato, `contexto.py cena`. Só consultar entidade, regra ou histórico quando a resposta atual depender disso.

### Aplicação de regra

Usar `contexto.py regra "assunto"`. Se ainda houver dúvida: decisão anterior equivalente → regra da casa → fonte oficial autorizada. Parar quando resolvido.

### Atualização da ficha

Durante jogo, dano, cura, Ki, moedas, munição e outros recursos entram como deltas; a ficha é sincronizada pela consolidação. Fora do loop narrativo, alteração canônica manual continua exigindo validação e regeneração do runtime quando aplicável.

Depois de `consolidar.py`, **não regenerar runtime por rotina**: o runtime correspondente ao novo cânone já foi calculado antes da instalação e faz parte do mesmo lote.

### Preparação de nova região

Consultar direção real, cronologia relevante, consequências de alcance regional, relações/facções implicadas, material oficial necessário e planos capazes de alcançar a região. Não preparar regiões sem utilidade previsível.

### Encerramento e consolidação

Usar transcrição + buffer como insumos principais. Antes de encerrar a sessão, executar `consolidar.py sessao` e verificar sucesso. Relações atuais permanecem em seus fragmentos; causas históricas vão para histórico específico. Conhecimento novo entra em fragmentos incrementais e seus índices.

A ferramenta não inventa fatos ausentes dos deltas, não incrementa a sessão automaticamente e não escolhe progressão pelo jogador.

## Semântica dos comandos de contexto

### `status`

Retorna `runtime/contexto.yaml` com deltas pendentes aplicados em memória.

### `cena`

Retorna contexto + `runtime/cena.yaml`, também com sobreposição pendente.

### `npc`

Resolve índices/fragmentos do NPC e relação e aplica deltas correspondentes ainda pendentes.

### `relacao`

Abre apenas o fragmento atual e aplica os deltas pendentes da entidade. Histórico frio não é lido automaticamente.

### `conhecimento`

Pesquisa conhecimento consolidado — incluindo fragmentos incrementais recentes — e descobertas ainda pendentes de alvo `conhecimento`.

### `regra`

Busca resumos internos. Ausência não autoriza inventar regra.

### `buscar`

Ferramenta de descoberta; material reservado só entra com `--reservado` e histórico frio somente com `--historico`.

## Runtime

`runtime/contexto.yaml` e `runtime/cena.yaml` devem permanecer pequenos. Durante turno, `contexto.py` projeta deltas sem regravá-los. `gerar-runtime.py` continua disponível para manutenção manual; o consolidador já produz o runtime do novo checkpoint.

## Comandos conceituais

- **"Preparar a campanha"**: completar configuração e documentos mínimos.
- **"Criar meu personagem"**: executar criação conforme edição e fontes.
- **"Preparar a próxima sessão"**: preparar abertura e possibilidades prováveis sem avançar indevidamente o mundo.
- **"Iniciar a sessão"**: carregar o mínimo seguro e narrar.
- **"Encerrar a sessão"**: executar `consolidar.py sessao`, validar e então encerrar.
- **"Conferir meu XP"**: recalcular histórico relevante e apontar divergências.
- **"Quais opções eu tenho para evoluir?"**: consultar ficha, fontes, pré-requisitos e caminhos registrados.
- **"Reavaliar o material-base"**: investigar lacunas e atualizar resumos.
- **"Preparar a região"**: criar apenas material necessário à área relevante.
- **"Conferir a continuidade"**: buscar contradições entre sessões, estado, ficha e registros.

## Critérios de conclusão

Uma regra está resumida quando pode ser aplicada sem consulta constante ao livro. Uma região está preparada quando sustenta decisões sem árvore rígida. Um personagem está criado quando escolhas/cálculos estão salvos. Uma sessão está preparada quando a abertura e agentes relevantes estão claros.

Uma sessão só está realmente encerrada quando `consolidar.py sessao` concluiu, o buffer não contém as transações aplicadas, os artefatos necessários foram atualizados e o novo runtime-base representa o estado consolidado.

## Prioridade corrente

Prioridades concretas vêm de `campanha.yaml`, estado consolidado e estado efetivo consultado por `contexto.py`, não de números hardcoded em documentação.

Preserva-se o princípio: **não criar arquivos vazios para satisfazer uma árvore idealizada; criar estrutura quando houver conteúdo real e utilidade previsível.**
