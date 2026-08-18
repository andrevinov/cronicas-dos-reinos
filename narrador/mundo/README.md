# Motor reservado do Mundo Vivo

Esta pasta guarda somente o **controle determinístico** do mundo que continua em
movimento fora da presença de Ren. Ela não substitui agentes, agentes leves,
direções, entradas, sessões, relógios, relações ou qualquer outra fonte canônica.

## Arquivos

- `agenda.yaml`: cadências de reavaliação e agendamentos determinísticos futuros;
- `estado.yaml`: cursor até onde o motor já processou o tempo canônico e fila de
  decisões ainda pendentes.

`estado.yaml` é controle operacional reservado. Um item em `pendencias` significa
"o narrador precisa reconsiderar isto"; não significa que a ação já aconteceu.

## Comandos

```bash
python3 ferramentas/mundo.py status
python3 ferramentas/mundo.py pendentes
python3 ferramentas/mundo.py amanhecer
python3 ferramentas/mundo.py avancar
python3 ferramentas/mundo.py concluir <id>
python3 ferramentas/mundo.py check
```

`amanhecer` e `avancar` **não alteram `estado/tempo.yaml`**. Eles processam somente
o intervalo entre `estado.yaml -> processado_ate` e o tempo que a campanha já
alcançou em `estado/tempo.yaml`.

- `amanhecer` para no último amanhecer já alcançado;
- `avancar` vai até o instante canônico atual;
- `pendentes` lista somente decisões já disparadas;
- `concluir` deve ser usado depois que o narrador avaliou a pendência e registrou
  seu resultado, inclusive quando o resultado foi "nenhuma mudança";
- `check` é somente leitura e pertence a manutenção/CI.

## Checkpoints por passagem significativa de tempo

O fluxo normal sincroniza este motor em três situações:

1. todo `checkpoint.py cena` explícito;
2. todo `checkpoint.py sessao`;
3. automaticamente, quando `turno.py registrar` percebe que o tempo efetivo ficou
   **120 minutos ou mais** à frente do cursor do Mundo Vivo ou atravessou o
   amanhecer configurado em `agenda.yaml`.

A medida é acumulada desde `estado.yaml -> processado_ate`. Portanto quatro
avanços de 30 minutos promovem checkpoint quando o quarto completa duas horas;
não é necessário que uma única ação dure duas horas.

Passagens pequenas continuam baratas. Uma caminhada de cinco minutos escreve
somente transcrição + buffer, como antes. Descanso curto também não recebe
tratamento especial só por ter `modo: descanso`; um descanso realmente longo será
capturado pela passagem temporal. Quando uma exploração longa também muda
`localizacao.*`, o checkpoint é classificado como `viagem_longa` apenas para
explicar a causa operacional.

Fronteiras de cena importantes continuam usando `checkpoint.py cena` mesmo sem
salto temporal. O fechamento de sessão sempre usa `checkpoint.py sessao`; ambos
sincronizam o mundo depois da consolidação.

A ordem é obrigatória:

```text
turno persiste transcrição + delta
→ checkpoint consolida o novo tempo canônico
→ direções canônicas avaliam o intervalo sem avançar marcos
→ entradas elegíveis de aliados são filtradas sem fazer ninguém aparecer
→ se houve amanhecer, agentes leves vencidos passam pelo orçamento determinístico
→ mundo.py processa até esse tempo
→ handoff/índice são reconstruídos
```

Assim o motor nunca usa prosa, estimativa ou delta não consolidado como se já fosse
cânone.

## Idempotência entre turno e checkpoint

Como um checkpoint temporal pode limpar `runtime/eventos-pendentes.jsonl` dentro
da mesma execução de `turno.py`, retries precisam reconhecer transações já
instaladas. `turno.py` consulta `sessoes/NNN/consolidacoes.jsonl` somente no caminho
raro em que o marcador já existe na transcrição e o evento não está mais no
buffer. Se o ID já aparece no ledger, a operação é considerada consolidada e não
é reaplicada.

Pendências de direção, entrada e agentes leves usam IDs estáveis. Se houver falha
depois que uma delas foi criada e antes de seu controle reservado ser atualizado,
repetir o checkpoint não a duplica. A camada leve também repara
`proxima_avaliacao` ao reconhecer no Mundo Vivo um ID que já foi criado.

## Economia de contexto

O motor lê agenda, cursor e tempo. Quando nada vence, **não lê sequer o índice de
agentes**. Quando alguma pendência de agente estratégico vence, consulta no máximo
`narrador/agentes/index.yaml` para validar IDs e devolve apenas quem precisa de
reconsideração. Ele nunca abre automaticamente os fragmentos dos agentes.

A camada de direções, executada apenas em checkpoints, lê somente
`narrador/direcoes/index.yaml` + `estado.yaml`. **Não abre fragmento de direção nem
as fontes canônicas para decidir se uma avaliação venceu.** O fragmento só entra
depois, quando existe uma pendência concreta a resolver.

A camada de entradas segue a mesma regra: lê apenas índice, estado, nível atual e
tempo. Mantém **um único candidato normal por vez** e no máximo uma antecipação
extraordinária. O fragmento individual do aliado só é aberto depois que existe
`avaliar_entrada`.

A camada de agentes leves é ainda mais restritiva. Ela só é consultada quando o
intervalo do checkpoint **atravessa o amanhecer**. Um checkpoint de duas horas no
meio do dia não lê `narrador/agentes-leves/`. Mesmo no amanhecer, a seleção lê só
índice + estado + tempo + fila do Mundo Vivo; nenhum fragmento de NPC entra no
contexto antes de uma pendência concreta.

Exemplo de saída conceitual:

```yaml
agentes_reconsiderar:
  - red_sail

direcoes_reconsiderar:
  - ponte_de_kozakura

entradas_reconsiderar:
  - shen_meihua

agentes_leves_reconsiderar:
  - luath
```

Só depois disso o narrador usa consultas dirigidas:

```bash
python3 ferramentas/agentes.py mostrar red_sail
python3 ferramentas/direcoes.py mostrar ponte_de_kozakura
python3 ferramentas/entradas.py mostrar shen_meihua
python3 ferramentas/agentes_leves.py mostrar luath
```

## Direções narrativas canônicas

Direção canônica não é agente nem relógio. Ela registra um destino de longo prazo
que deve existir na campanha sem prescrever **como, quando ou por quem** cada
marco será alcançado.

A fila usa dois tipos:

- `avaliar_direcao`: reexaminar se o marco atual já está sustentado pelos fatos;
- `ativar_direcao`: uma direção latente teve sua dependência satisfeita e pode
  começar, mas continua exigindo decisão explícita do narrador.

Nenhum desses tipos avança a história sozinho. Ao receber `avaliar_direcao`, ler
somente a direção indicada. Se os critérios ainda não estão sustentados, concluir
a pendência sem mudança. Se estão, registrar o fato que realmente ocorreu e então
usar `direcoes.py avancar` com origem e nota rastreáveis. `ativar_direcao` segue o
mesmo princípio com `direcoes.py ativar`.

A implementação inicial possui duas direções encadeadas:

- **Ponte de Kozakura**: ativa, começando por `coisas_plausiveis`;
- **Shin-Kozakura**: latente, só pode ser ativada depois de concluído o marco
  `perda_controle_exclusivo` da Ponte.

Detalhes e comandos ficam em `narrador/direcoes/README.md`.

## Entrada e aparição de aliados

`avaliar_entrada` significa somente que chegou uma janela razoável para consultar
um aliado futuro. **Não significa que ele chegou.** O narrador abre apenas o
fragmento indicado e compara seus gatilhos com os fatos já ocorridos.

O caminho padrão segue a ordem canônica Shen → Jōen → Jenilynn → Hotaru → Tadasu.
Só o primeiro ainda não presente fica agendado. O nível mínimo normal é uma
filtragem operacional derivada da janela preferencial de cada aliado; se ainda não
for suficiente, a avaliação é adiada automaticamente por três dias sem abrir o
fragmento.

A ordem continua sendo preferência, não trilho. Quando investigação, pedido de
ajuda, risco ou ação de antagonista justificarem furá-la, usar `entradas.py
antecipar <id> --origem ... --nota ...`. Só uma antecipação pode existir por vez e
ela será avaliada no próximo amanhecer. Nada disso produz entrada automática.

Depois que o aliado **realmente apareceu em cena**, usar `entradas.py confirmar`
com origem e nota. Isso marca a entrada como cumprida e agenda o próximo candidato
normal para o amanhecer seguinte. A pendência correspondente continua sendo
fechada por `mundo.py concluir`.

Detalhes: `narrador/entradas/README.md`.

## Agentes recorrentes leves

`reavaliar_agente_leve` existe para NPCs importantes que possuem emprego, rotina,
obrigações e vida própria, mas não precisam do peso operacional de Masao, uma
facção ou uma instituição. **Rotina é o resultado padrão.** Uma pendência leve não
obriga o NPC a fazer algo inesperado.

Ao receber uma pendência leve, consultar somente o NPC indicado:

```bash
python3 ferramentas/agentes_leves.py mostrar <id-ou-nome>
```

O fragmento traz rotina, objetivo atual, iniciativas possíveis e regra de
reavaliação. Se o estado atual não oferecer uma causa concreta para iniciativa,
concluir a pendência com nenhuma mudança extraordinária. Não inventar ação só
porque o scheduler chamou o NPC.

O orçamento atual é rígido:

- no máximo **1 nova reavaliação leve por checkpoint**;
- no máximo **2 pendências leves abertas simultaneamente**;
- seleção por **mais atrasado → maior prioridade → ID**;
- vencidos não selecionados continuam vencidos e serão reconsiderados depois;
- vários ciclos perdidos são condensados em uma única avaliação;
- checkpoints que não cruzam amanhecer nem carregam a camada.

A primeira população é deliberadamente pequena e escalonada: Luath a cada 3 dias,
Silva Elkwood a cada 4 e Maerra Thandrel a cada 5. Night Watch continua sendo
agente institucional estratégico; Luath é o indivíduo recorrente, portanto as duas
camadas não significam a mesma decisão.

Detalhes: `narrador/agentes-leves/README.md`.

## Cadência não é ação

Uma cadência de amanhecer significa **reavaliar**, não obrigar agente, direção,
entrada ou NPC leve a avançar nem garantir que Ren perceberá qualquer coisa. O
narrador ainda deve respeitar conhecimento, presença, mobilidade, recursos,
restrições, rotina e causalidade.

Cadências podem ser espaçadas conforme a escala: uma facção em busca ativa pode
ser reconsiderada diariamente; um antagonista estratégico, a cada vários dias;
um NPC recorrente, ainda mais espaçadamente; uma direção histórica ou uma entrada
futura, conforme sua própria escala.

## Agendamentos determinísticos

`agenda.yaml -> agendamentos` aceita três tipos nesta etapa:

- `reavaliar_agente`;
- `movimento`;
- `expiracao`.

Eles apenas criam pendências quando o horário chega. Um `movimento`, por exemplo,
não teletransporta nem altera sozinho `presenca`: ele informa que chegou a hora de
resolver aquele deslocamento. Isso permite que interrupções, fracassos ou eventos
posteriores ainda sejam considerados legitimamente pelo narrador.

Eventos aleatórios não pertencem a esta etapa e ainda não são sorteados por
`mundo.py`.
