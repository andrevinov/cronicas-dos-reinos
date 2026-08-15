# Memória de sessões e transcrições frias

Este documento define como usar sessões antigas sem transformar centenas de quilobytes de transcrição em contexto operacional.

## Princípio

A transcrição continua sendo o registro integral e append-only do que foi dito e narrado. Isso **não** significa que ela deva ser relida para retomar a campanha.

A partir da Etapa 9 existem quatro camadas:

1. `runtime/contexto.yaml` + `runtime/cena.yaml`: estado atual e cena imediata;
2. `runtime/eventos-pendentes.jsonl`: mudanças posteriores ao último checkpoint;
3. `sessoes/NNN/handoff.yaml` + `sessoes/index.yaml`: memória compacta de retomada;
4. `sessoes/NNN/transcricao.md`: arquivo frio, acessível apenas quando as camadas anteriores forem insuficientes.

A ordem é deliberada. **Não abrir a camada 4 por precaução.**

## Retomada normal

Use:

```bash
python3 ferramentas/contexto.py retomada
```

A consulta combina estado quente, cena, último handoff consolidado e os resumos dos eventos ainda pendentes. Ela deve bastar para reentrar na cena após pausa, compactação de conversa ou troca de processo.

Se a pergunta for sobre uma sessão específica:

```bash
python3 ferramentas/contexto.py sessao 2
```

O comando lê `sessoes/index.yaml` e prefere `handoff.yaml`. Em sessões legadas sem handoff, usa resumo e alterações estruturadas quando existirem. **Não abre a transcrição.**

## Busca histórica em dois degraus

Histórico estruturado e transcrição bruta são níveis diferentes.

Primeiro:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico
```

Isso inclui handoffs, resumos, alterações, consequências, experiência e `historico/`, mas mantém transcrições fora.

Somente se esse material não resolver a lacuna:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico --transcricoes
```

`--transcricoes` é uma escalada explícita. Não deve ser usado junto a toda busca histórica por hábito.

## Handoff

`handoff.yaml` é derivado de fontes já estruturadas. Ele contém:

- checkpoint mecânico e espacial pequeno;
- resumo imediato e prazos/alertas;
- últimos resumos transacionais consolidados;
- ponteiros para as fontes canônicas;
- indicação explícita de que a transcrição é fria.

Ele **não** contém blocos `**Jogador**` / `**Narrador**`, nem reconstrói prosa histórica.

O handoff é atualizado pela consolidação de cena/sessão. A Etapa 9 também possui um bootstrap para campanhas já em andamento:

```bash
python3 ferramentas/sessoes.py bootstrap-atual
```

Esse bootstrap deriva o handoff apenas do runtime/cena correntes; não vasculha a transcrição para inventar uma recapitulação.

## Índice de sessões

`sessoes/index.yaml` registra, para cada sessão:

- natureza atual/histórica;
- handoff disponível;
- artefatos compactos existentes;
- ordem preferencial de leitura;
- caminho e tamanho da transcrição;
- classe da transcrição como arquivo frio para leitura.

Regeneração:

```bash
python3 ferramentas/sessoes.py reindexar
python3 ferramentas/sessoes.py check
```

O índice não contém prosa das sessões e não cresce na mesma escala das transcrições.

## Abertura de nova sessão

**Nunca copiar o último trecho da sessão anterior para a nova transcrição.**

A sessão nova começa com cabeçalho curto, recap narrativo necessário e nova cena. Para continuidade, usar `contexto.py retomada`, handoff da sessão anterior e, se necessário, seus artefatos compactos.

Sessões legadas até a 003 podem conter esse padrão antigo; ele é preservado por segurança histórica. O verificador rejeita a prática para sessões posteriores.

## Repetição de estado na prosa

A transcrição não deve repetir a cada turno um bloco como PV + CA + Ki + dinheiro + munição + hora + localização quando esses valores não mudaram e não são taticamente necessários.

Mencione mecânica quando ela:

- mudou naquele turno;
- altera a decisão imediata;
- precisa ficar clara em combate;
- resolve ambiguidade que o texto narrativo não resolve.

O estado completo já existe no runtime/deltas. Repeti-lo em toda resposta aumenta tanto a transcrição quanto o contexto da conversa sem acrescentar informação.

## Consolidação

`ferramentas/consolidar.py cena` e `sessao` atualizam o handoff e o índice no mesmo plano atômico que instala o novo estado/runtime. Assim, depois de um checkpoint, a campanha continua retomável mesmo com o buffer vazio.

A transcrição não é reprocessada para criar o handoff; os resumos vêm do ledger transacional e a cena vem do runtime produzido pelo estado consolidado.

## Invariantes

- transcrição é completa, mas fria para leitura;
- nenhum handoff pode conter blocos de transcrição;
- nova sessão não copia trecho da anterior;
- `--historico` não implica transcrição;
- `--transcricoes` exige escalada deliberada;
- `retomada` deve permanecer abaixo do orçamento normal de contexto;
- ausência de handoff em sessão legada não autoriza abrir automaticamente a transcrição;
- dados históricos não são apagados para economizar tokens; eles apenas deixam o caminho quente.
