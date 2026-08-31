# Memória de sessões e transcrições frias

Este documento define como usar sessões antigas sem transformar centenas de quilobytes de transcrição em contexto operacional. A política formal de níveis, `--apos`, `--motivo` e tetos fica em `docs/agente/escada-de-acesso.md`.

## Princípio

A transcrição continua sendo o registro integral e append-only do que foi dito e narrado. Isso **não** significa que ela deva ser relida para retomar a campanha.

Existem quatro camadas:

1. `runtime/contexto.yaml` + `runtime/cena.yaml`: estado atual e cena imediata;
2. `runtime/eventos-pendentes.jsonl`: mudanças posteriores ao último checkpoint;
3. `sessoes/NNN/handoff.yaml` + `sessoes/index.yaml`: memória compacta de retomada;
4. `sessoes/NNN/transcricao.md`: arquivo frio, acessível apenas quando as camadas anteriores forem insuficientes.

A ordem é deliberada. **Não abrir a camada 4 por precaução.**

## Retomada normal

Use L2 diretamente quando a conversa não basta:

```bash
python3 ferramentas/contexto.py retomada
```

A consulta combina estado quente, cena, último handoff consolidado e os resumos dos eventos ainda pendentes. Ela deve bastar para reentrar na cena após pausa, compactação de conversa ou troca de processo.

Sessão atual também é L2:

```bash
python3 ferramentas/contexto.py sessao atual
```

Se a pergunta já identifica uma sessão histórica, a política permite um salto dirigido L2 → L4 em vez de pagar uma busca ampla L3:

```bash
python3 ferramentas/contexto.py sessao 2 \
  --apos L2 \
  --motivo "A pergunta aponta diretamente para a sessão 002 e exige seu resumo consolidado."
```

O comando lê `sessoes/index.yaml` e prefere `handoff.yaml`. Em sessões legadas sem handoff, usa resumo e alterações estruturadas quando existirem. **Não abre a transcrição.**

## Busca histórica em dois degraus

Histórico estruturado e transcrição bruta são níveis diferentes.

Primeiro L3, quando uma busca ampla corrente foi realmente necessária:

```bash
python3 ferramentas/contexto.py buscar "termo" \
  --apos L2 \
  --motivo "As consultas dirigidas não localizaram onde a informação está registrada."
```

Se a origem histórica ainda faltar, L4:

```bash
python3 ferramentas/contexto.py buscar "termo" \
  --historico --apos L3 \
  --motivo "A busca corrente não contém a origem histórica necessária para continuidade."
```

Isso inclui handoffs, resumos, alterações, consequências, experiência e `historico/`, mas mantém transcrições fora.

Somente se esse material não resolver a lacuna, L4T:

```bash
python3 ferramentas/contexto.py buscar "termo" \
  --historico --transcricoes --apos L4 \
  --motivo "O histórico estruturado não contém a formulação bruta necessária para resolver a continuidade."
```

`--transcricoes` é uma escalada explícita e não deve acompanhar toda busca histórica por hábito.

## Handoff

`handoff.yaml` é derivado de fontes já estruturadas. Ele contém:

- checkpoint mecânico e espacial pequeno;
- resumo imediato e prazos/alertas;
- últimos resumos transacionais consolidados;
- ponteiros para as fontes canônicas;
- indicação explícita de que a transcrição é fria.

Ele **não** contém blocos `**Jogador**` / `**Narrador**`, nem reconstrói prosa histórica.

O handoff é atualizado pela camada de checkpoint depois que a consolidação canônica termina. Há bootstrap para campanhas já em andamento:

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

A transcrição não deve repetir a cada turno um bloco como PV + CA + Focus + dinheiro + munição + hora + localização quando esses valores não mudaram e não são taticamente necessários.

Mencione mecânica quando ela:

- mudou naquele turno;
- altera a decisão imediata;
- precisa ficar clara em combate;
- resolve ambiguidade que o texto narrativo não resolve.

O estado completo já existe no runtime/deltas. Repeti-lo em toda resposta aumenta tanto a transcrição quanto o contexto da conversa sem acrescentar informação.

## Checkpoint

A porta operacional é:

```bash
python3 ferramentas/checkpoint.py cena
python3 ferramentas/checkpoint.py sessao
```

`consolidar.py` instala primeiro o novo cânone/runtime com journal/staging da Etapa 8. Depois, `checkpoint.py` deriva handoff e índice. Essa segunda fase é cache reconstruível: se falhar, repetir `checkpoint.py recuperar` ou reconstruir a memória compacta não reaplica deltas canônicos.

A transcrição não é reprocessada para criar o handoff; os resumos vêm do ledger transacional e a cena vem do runtime produzido pelo estado consolidado.

## Invariantes

- transcrição é completa, mas fria para leitura;
- nenhum handoff pode conter blocos de transcrição;
- nova sessão não copia trecho da anterior;
- `--historico` não implica transcrição;
- L3/L4/L4T exigem declaração de escalada e motivo;
- sessão histórica conhecida pode usar salto dirigido L2 → L4;
- `--transcricoes` exige L4 anterior insuficiente;
- `retomada` deve permanecer abaixo do teto L2;
- ausência de handoff em sessão legada não autoriza abrir automaticamente a transcrição;
- dados históricos não são apagados para economizar tokens; eles apenas deixam o caminho quente.