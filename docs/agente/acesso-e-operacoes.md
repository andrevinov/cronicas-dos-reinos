# Acesso ao contexto e operações do agente

Este documento define como o agente decide **o que ler, quando parar de ler, o que escrever e quando consolidar**. A interface preferencial de leitura é `ferramentas/contexto.py`; durante narração ao vivo, a interface preferencial de escrita é `ferramentas/turno.py`.

## Regra principal de economia de contexto

Antes de qualquer consulta, perguntar: **a informação já presente no contexto é suficiente para executar a tarefa com segurança?**

Se sim, não ler arquivo algum.

Se não, buscar somente a menor fonte capaz de responder à lacuna concreta. Depois de cada consulta, perguntar novamente se já é suficiente. **Quando for suficiente, parar.**

Não ler o repositório inteiro, uma pasta inteira ou um arquivo grande apenas para "se situar". Não consultar livros oficiais preventivamente. Não reler informação já disponível e confiável.

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados. Desde a Etapa 7, `runtime/eventos-pendentes.jsonl` contém mudanças posteriores ao último checkpoint consolidado. `contexto.py` aplica essas pendências em memória e devolve o estado operacional efetivo.

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

Durante jogo ao vivo, consultar o **estado efetivo**. Não editar o consolidado apenas para fazer uma consulta seguinte enxergar uma mudança recém-ocorrida.

## Narração ao vivo — ciclo operacional

Fluxo obrigatório:

```text
ação do jogador
→ L0
→ consulta dirigida somente se faltar algo
→ rolagem(ns) necessária(s)
→ narração
→ turno.py registrar
→ fim da interação
```

A última etapa deve persistir a troca em uma única chamada de ferramenta:

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

O registrador escreve apenas:

- `sessoes/NNN/transcricao.md`;
- `runtime/eventos-pendentes.jsonl`.

Não atualizar na mesma interação, por rotina:

- `estado/estado-atual.yaml`;
- `estado/tempo.yaml`;
- ficha;
- fragmentos de relação;
- fragmentos de NPC;
- conhecimento consolidado;
- consequências;
- relógios;
- arquivos de rolagens ocultas.

Esses destinos são responsabilidade da consolidação posterior.

### O que vira delta

Registrar somente mudança persistente ou necessária para continuidade. Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"estado","op":"set","caminho":"localizacao.ponto_exato","valor":"junto à cerca"}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04 de 7 Eleasis"}
{"alvo":"relacao:luath","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
```

Se nada persistente mudou, usar `deltas: []`. Não criar delta para cada frase descritiva.

### Operações disponíveis

- `set` — novo valor corrente;
- `inc` — variação numérica;
- `append` — acrescentar item;
- `remove` — retirar item/chave;
- `registrar` — fato que precisa chegar à consolidação sem alterar imediatamente um campo estruturado.

Deltas podem usar `visibilidade: narrador` quando o conteúdo não pode aparecer em consultas públicas.

### Idempotência

`turno.py` gera um ID estável e marca a transcrição com comentário HTML interno. Se o processo cair entre a escrita do JSONL e a transcrição, repetir a mesma entrada repara apenas o lado ausente.

Verificação barata:

```bash
python3 ferramentas/turno.py check
```

Não executar a suíte inteira de integridade depois de cada turno.

## Rolagens em lote

Quando duas ou mais rolagens são independentes e todas já são necessárias antes de conhecer qualquer resultado, usar uma única chamada:

```bash
python3 ferramentas/rolar-lote.py <<'JSON'
[
  ["ren", "pericia", "furtividade", "--cd", "14"],
  ["npc", "d20", "--nome", "Guarda", "--bonus", "3", "--cd", "12"]
]
JSON
```

Não agrupar uma rolagem cuja existência depende do resultado anterior.

## Classificação da tarefa

Classificar mentalmente cada pedido em uma ou mais categorias: preparação, pesquisa de regra/cenário, criação/progressão, preparação de sessão, narração ao vivo, encerramento, manutenção, correção de continuidade ou revisão de material-base.

A classificação escolhe fluxo/documento; não gera leitura extra por si só.

## Leitura por tipo de trabalho

### Narração ou início de sessão

Começar em L0. Se faltar estado, `contexto.py status`; se faltar recorte imediato, `contexto.py cena`. Só consultar entidade, regra ou histórico quando a resposta atual depender disso.

Na abertura de sessão é aceitável consultar um pouco mais para reconstruir estado crítico e segredos diretamente relacionados, ainda usando consultas dirigidas antes de arquivos completos.

### Aplicação de regra

Usar `contexto.py regra "assunto"`. Se ainda houver dúvida, parar assim que resolvido:

1. decisão anterior equivalente;
2. regra da casa;
3. fonte oficial autorizada.

### Atualização da ficha

Fora do loop narrativo, consultar apenas o que se relaciona à alteração. Durante jogo, dano, cura, Ki, moedas, munição e outros recursos entram como deltas; a ficha é sincronizada em consolidação.

Depois de consolidação canônica que altere recursos, nível, tempo, localização ou cena, regenerar `runtime/`.

### Preparação de nova região

Consultar direção real da campanha, cronologia relevante, consequências de alcance regional, relações/facções implicadas, material oficial necessário e planos capazes de alcançar a região. Não preparar regiões sem utilidade previsível.

### Encerramento e consolidação

A sessão deve usar transcrição + buffer pendente como insumos principais, complementados apenas pelo que for necessário. Não reconstruir todas as mudanças vasculhando o repositório se os deltas já as registram explicitamente.

Ao atualizar uma relação, gravar estado corrente no fragmento da entidade; história cronológica permanece na camada histórica. Conhecimento adquirido entra nos fragmentos/índices apropriados.

A Etapa 8 implementará a consolidação automática e idempotente. Até lá, não limpar o buffer pendente sem procedimento deliberado.

## Semântica dos comandos de contexto

### `status`

Retorna o snapshot de `runtime/contexto.yaml` **com deltas pendentes da sessão aplicados em memória**. É a consulta operacional mais barata.

### `cena`

Retorna contexto + `runtime/cena.yaml`, também com sobreposição pendente: recursos, hora, localização, modo e resumo imediato suportados.

### `npc`

Resolve índices e fragmentos do NPC/relação e aplica deltas `npc:<id>` e `relacao:<id>` ainda pendentes.

### `relacao`

Abre apenas `estado/relacoes/<id>.yaml` e aplica deltas pendentes daquela entidade. Histórico frio não é lido automaticamente.

### `conhecimento`

Pesquisa fragmentos consolidados e também descobertas pendentes de alvo `conhecimento`. Serve para responder **o que Ren sabe**.

### `regra`

Busca resumos internos de regras. Ausência não autoriza inventar regra.

### `buscar`

Ferramenta de descoberta. Além das fontes operacionais, considera resumos/deltas pendentes; material reservado só entra com `--reservado`, e histórico frio só com `--historico`.

## Runtime

`runtime/contexto.yaml` e `runtime/cena.yaml` devem permanecer pequenos. Eles não precisam ser regravados por turno; `contexto.py` projeta os deltas em memória.

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

`--check` valida o snapshot-base contra o último estado consolidado. A existência de eventos pendentes não torna o snapshot-base inválido.

## Comandos conceituais

- **"Preparar a campanha"**: completar configuração e documentos mínimos.
- **"Criar meu personagem"**: executar criação conforme edição e fontes.
- **"Preparar a próxima sessão"**: preparar abertura e possibilidades prováveis sem avançar indevidamente o mundo.
- **"Iniciar a sessão"**: carregar o mínimo seguro e narrar.
- **"Encerrar a sessão"**: consolidar registros, estado, XP, relações, consequências e pendências.
- **"Conferir meu XP"**: recalcular histórico relevante e apontar divergências.
- **"Quais opções eu tenho para evoluir?"**: consultar ficha, fontes, pré-requisitos e caminhos registrados.
- **"Reavaliar o material-base"**: investigar lacunas de regras/cenário e atualizar resumos.
- **"Preparar a região"**: criar apenas material necessário à área relevante.
- **"Conferir a continuidade"**: buscar contradições entre sessões, estado, ficha e registros.

## Critérios de conclusão

Uma regra está resumida quando pode ser aplicada sem consulta constante ao livro. Uma região está preparada quando sustenta as primeiras decisões sem árvore rígida. Um personagem está criado quando escolhas/cálculos estão salvos. Uma sessão está preparada quando a cena inicial e os agentes relevantes estão claros.

Uma sessão só está realmente encerrada quando a consolidação permite a próxima começar sem reconstrução manual substancial e o runtime-base foi regenerado a partir do estado consolidado.

## Prioridade corrente

Prioridades concretas vêm de `campanha.yaml`, estado consolidado e estado efetivo consultado por `contexto.py`, não de números de sessão hardcoded em documentação.

Preserva-se o princípio: **não criar arquivos vazios para satisfazer uma árvore idealizada; criar estrutura quando houver conteúdo real e utilidade previsível.**
