# Motor reservado do Mundo Vivo

Esta pasta guarda o **controle determinístico** do mundo que continua em movimento
fora da presença de Ren. Ela não substitui agentes, agentes leves, direções,
entradas, relógios, eventos, rastros, relações ou conhecimento.

Princípio central: **existir no mundo não significa entrar no contexto nem no
conhecimento do personagem**. Python agenda, filtra, sorteia, roteia e deduplica;
o narrador abre somente o fragmento apontado por uma necessidade concreta.

## Arquivos centrais

- `agenda.yaml`: cadências e agendamentos determinísticos;
- `estado.yaml`: cursor do motor e fila de decisões pendentes;
- `ciclo-npcs.yaml`: registro terminal de NPCs mortos;
- `../eventos/`: baralho mundial e roteamento evento↔agentes;
- `../rastros/`: evidências observáveis separadas da verdade reservada.

`estado.yaml` é controle reservado. Uma pendência significa **“avaliar isto”**,
nunca “isto já aconteceu”.

## Checkpoints

O Mundo Vivo é sincronizado em `checkpoint.py cena`, `checkpoint.py sessao` e
automaticamente quando o tempo efetivo fica 120 minutos à frente do cursor ou
cruza o amanhecer. Passagens menores continuam no hot path de duas escritas.

```text
turno persiste transcrição + delta
→ checkpoint consolida o novo cânone
→ lifecycle desliga NPCs mortos
→ relógios sincronizam pressão → consequência
→ direções avaliam marcos
→ entradas de aliados são filtradas
→ agentes leves passam pelo orçamento no amanhecer
→ baralho mundial processa os amanheceres alcançados
→ mundo.py move o cursor e processa agenda determinística
→ handoff/índice são reconstruídos
```

Nenhuma camada usa prosa ou delta não consolidado como fato.

Quando uma cena contém descoberta de rastro, ela continua usando o **mesmo writer
de turno**. O par `conhecimento + rastro:estado` fica no buffer normal e entra no
mesmo staging/journal da consolidação; não há uma terceira escrita no turno.

## Economia de contexto

- agentes estratégicos: o motor nunca abre fragmentos automaticamente;
- direções: índice + estado;
- entradas: índice + estado + nível + tempo;
- agentes leves: somente ao cruzar amanhecer e com orçamento rígido;
- relógios: roteador derivado por agente;
- eventos: índice + estado; em dia `rotina` nem o roteador de interações é lido;
- rastros: `candidatos` usa só índice + localização canônica + tempo; o fragmento
  entra apenas depois que um ID relevante foi encontrado;
- transações sem `rastro:*`: delegam imediatamente ao consolidator legado, sem
  abrir índice ou fragmento de rastro.

Lookup dirigido:

```bash
python3 ferramentas/agentes.py mostrar red_sail
python3 ferramentas/direcoes.py mostrar ponte_de_kozakura
python3 ferramentas/entradas.py mostrar shen_meihua
python3 ferramentas/agentes_leves.py mostrar luath
python3 ferramentas/eventos_mundo.py mostrar acidente_no_porto
python3 ferramentas/rastros.py mostrar <id>
```

## Agentes, cadências e lifecycle

Cadência significa **reavaliar**, não agir. Presença, mobilidade, recursos,
conhecimento e restrições continuam mandando. `agenda.yaml` aceita
`reavaliar_agente`, `movimento` e `expiracao`; movimento vencido não teletransporta
ninguém.

Morte canônica (`npc:<id> -> vida.estado: morto`) é sincronizada antes dos
schedulers. O NPC perde agenda, atividade estratégica/leve, entrada futura e
pendências incompatíveis. `morto` é terminal. Detalhes: `CICLO-NPCS.md`.

## Relógios

Relógios não possuem agência:

```text
agente → operação → pressão → consequência
```

Passagem do tempo sozinha não incrementa pressão. Ao alcançar o limite, a pressão
vira consequência resolvida. Consulta barata:
`python3 ferramentas/relogios.py por-agente red_sail`.

## Direções e entradas

Direção é trajetória obrigatória de longo prazo sem cena, data ou executor
prescritos. A implementação inicial encadeia Ponte de Kozakura e Shin-Kozakura.
Detalhes: `../direcoes/README.md`.

`avaliar_entrada` apenas indica que um aliado futuro merece consulta. Caminho
normal: Shen → Jōen → Jenilynn → Hotaru → Tadasu. `antecipar` pode furar a ordem
com proveniência; `confirmar` só ocorre depois da aparição real. Detalhes:
`../entradas/README.md`.

## Agentes recorrentes leves

Rotina é o padrão. Há no máximo 1 nova reavaliação leve por checkpoint e 2 abertas;
seleção por mais atrasado → maior prioridade → ID. População inicial: Luath, Silva
Elkwood e Maerra Thandrel. Detalhes: `../agentes-leves/README.md`.

## Baralho e interação com agentes

Dois baralhos determinísticos sem reposição controlam o acaso. A urna de ocorrência
tem **7 `rotina` + 3 `evento`** por ciclo de dez amanheceres; o segundo baralho tem
dez cartas e só é consultado quando sai `evento`. A ordem é derivada por SHA-256;
não usa `random`, relógio do sistema ou entropia externa.

**Sorteio não é cânone.** Uma carta gera uma única pendência. Suas tags são cruzadas
com `narrador/eventos/interacoes.yaml`; no máximo **2 agentes estratégicos + 1
agente leve** são apontados como candidatos, por tags coincidentes → prioridade →
ID. Candidato não significa ação, conhecimento ou consequência.

Cartas não podem forçar aliados/Juppongatana, ativar a Ponte, matar NPC nomeado,
revelar segredo ou escolher autoria. Detalhes: `../eventos/README.md`.

## Verdade reservada → rastro → conhecimento

Os passos 7 e 8 fecham a barreira completa:

```text
fato canônico reservado
        ↓ pode deixar
rastro observável
        ↓ se Ren perceber/investigar
descoberta no turno
        ↓ mesma consolidação/journal
conhecimento de Ren + rastro marcado descoberto
```

Um fato off-screen **não cria conhecimento automaticamente**. O rastro registra
somente a manifestação observável; sua origem canônica permanece reservada e é
redigida por `rastros.py mostrar`.

`rastros.py candidatos` filtra por tempo, cidade/área/ponto, modo de acesso e tags
sem abrir fragmentos. Rastros de `investigacao` não aparecem na consulta automática.

Quando Ren efetivamente descobre um rastro, `preparar-descoberta` produz dois deltas
inseparáveis:

1. `conhecimento / registrar`, contendo exatamente `fato_observavel` e fonte pública
   `rastro:<id>`;
2. `rastro:<id> / set estado=descoberto`, reservado ao narrador.

O schema recusa pares incompletos **antes** das duas escritas do turno. No
checkpoint, o consolidator reabre somente o rastro descoberto, confirma que o texto
público não excede a evidência observável e inclui conhecimento + índice de rastros
no **mesmo plano staged e no mesmo journal**. Se houver queda durante a instalação,
a recuperação do journal termina exatamente o lote já preparado.

Depois da consolidação, o rastro deixa de aparecer em `candidatos`, mas seu
fragmento continua disponível para consulta explícita sem revelar a origem secreta.
O ledger do batch registra `rastros_descobertos`.

A instalação começou com índice vazio: nenhuma pista antiga foi recriada
retroativamente. Detalhes e comando `descobrir`: `../rastros/README.md`.