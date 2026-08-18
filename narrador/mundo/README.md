# Motor reservado do Mundo Vivo

Esta pasta guarda o **controle determinístico** do mundo que continua em movimento fora da presença de Ren. Ela não substitui agentes, agentes leves, direções, entradas, relógios, eventos, relações ou qualquer outra fonte canônica.

O princípio central é simples: **existir no mundo não significa entrar no contexto**. Python faz filtragem, agendamento, sorteio reprodutível e deduplicação; o narrador só abre o fragmento específico depois que surge uma pendência concreta.

## Arquivos centrais

- `agenda.yaml`: cadências de reavaliação e agendamentos determinísticos;
- `estado.yaml`: cursor do motor e fila de decisões pendentes;
- `ciclo-npcs.yaml`: registro terminal de NPCs mortos;
- `../eventos/`: baralho determinístico de acontecimentos mundiais.

`estado.yaml` é controle reservado. Um item em `pendencias` significa **“avaliar isto”**, nunca “isto já aconteceu”.

## Comandos do motor

```bash
python3 ferramentas/mundo.py status
python3 ferramentas/mundo.py pendentes
python3 ferramentas/mundo.py amanhecer
python3 ferramentas/mundo.py avancar
python3 ferramentas/mundo.py concluir <id>
python3 ferramentas/mundo.py check
```

`amanhecer` e `avancar` não alteram `estado/tempo.yaml`; processam somente o intervalo que a campanha já alcançou canonicamente.

## Checkpoints por passagem significativa de tempo

O Mundo Vivo é sincronizado em:

1. `checkpoint.py cena` explícito;
2. `checkpoint.py sessao`;
3. checkpoint automático quando o tempo efetivo fica **120 minutos ou mais** à frente do cursor ou cruza o amanhecer configurado.

A medida é acumulada. Quatro avanços de 30 minutos disparam no quarto; uma caminhada de cinco minutos continua no hot path de duas escritas.

A ordem operacional é:

```text
turno persiste transcrição + delta
→ checkpoint consolida o novo cânone
→ lifecycle desliga NPCs mortos
→ relógios sincronizam pressão → consequência
→ direções canônicas avaliam o intervalo
→ entradas de aliados são filtradas
→ agentes leves passam pelo orçamento quando houve amanhecer
→ baralho mundial processa os amanheceres alcançados
→ mundo.py move o cursor e processa agenda determinística
→ handoff/índice são reconstruídos
```

Nenhuma dessas camadas usa prosa ou delta não consolidado como fato.

## Idempotência

Retries reconhecem transações já consolidadas pelo ledger da sessão. Pendências de agentes, direções, entradas, agentes leves e eventos usam IDs estáveis.

O baralho grava a pendência do Mundo Vivo antes de avançar seu próprio cursor. Se o processo cair entre as duas escritas, o retry produz o mesmo sorteio, encontra o ID já existente e apenas repara o estado do baralho.

## Economia de contexto

O motor principal lê agenda, cursor e tempo. Quando nenhum agente estratégico vence, não abre seus fragmentos.

Direções usam apenas índice + estado para saber se há algo a reavaliar. Entradas usam índice + estado + nível + tempo. Agentes leves só entram no scheduler quando o intervalo cruza amanhecer e têm orçamento rígido. Relógios possuem roteador derivado por agente. O baralho mundial lê índice + estado + tempo + fila, **sem abrir nenhuma carta durante o sorteio**.

Exemplo de saída operacional:

```yaml
agentes_reconsiderar:
  - red_sail

direcoes_reconsiderar:
  - ponte_de_kozakura

entradas_reconsiderar:
  - shen_meihua

agentes_leves_reconsiderar:
  - luath

eventos_reconsiderar:
  - acidente_no_porto
```

Só então o narrador faz lookup dirigido:

```bash
python3 ferramentas/agentes.py mostrar red_sail
python3 ferramentas/direcoes.py mostrar ponte_de_kozakura
python3 ferramentas/entradas.py mostrar shen_meihua
python3 ferramentas/agentes_leves.py mostrar luath
python3 ferramentas/eventos_mundo.py mostrar acidente_no_porto
```

## Agentes e cadências

Cadência significa **reavaliar**, não agir. Presença, mobilidade, recursos, conhecimento e restrições continuam mandando. Uma facção em busca ativa pode vencer diariamente; um antagonista estratégico, em dias alternados; um NPC recorrente, bem menos frequentemente.

Agendamentos determinísticos em `agenda.yaml` continuam aceitando:

- `reavaliar_agente`;
- `movimento`;
- `expiracao`.

Um `movimento` vencido não teletransporta ninguém: cria apenas uma decisão a resolver.

## Lifecycle de NPCs

Morte canônica (`npc:<id> -> vida.estado: morto`) é sincronizada antes dos schedulers. O NPC é desligado de agenda, agentes estratégicos/leves, entradas futuras e pendências incompatíveis. `morto` é terminal; ausência posterior do campo não ressuscita ninguém.

Detalhes: `CICLO-NPCS.md`.

## Relógios como pressão de agentes

Relógios não possuem agência. A cadeia é:

```text
agente → operação → pressão → consequência
```

Uma pressão ativa que alcança o limite vira consequência resolvida e sai da lista de pressões vivas. A passagem do tempo, sozinha, não incrementa relógios.

Consulta barata por agente:

```bash
python3 ferramentas/relogios.py por-agente red_sail
```

## Direções narrativas canônicas

Direção é trajetória obrigatória de longo prazo sem cena, data ou executor prescritos. A fila usa `avaliar_direcao` e `ativar_direcao`; nenhuma das duas avança a história automaticamente.

A implementação inicial encadeia **Ponte de Kozakura** e **Shin-Kozakura**. Detalhes: `../direcoes/README.md`.

## Entrada e aparição de aliados

`avaliar_entrada` significa apenas que a janela de um aliado futuro merece consulta. O caminho normal é Shen → Jōen → Jenilynn → Hotaru → Tadasu; somente um candidato normal fica em foco. Ordem e nível filtram barato, mas não tornam a aparição automática.

`antecipar` pode furar a ordem com origem/nota rastreáveis; `confirmar` só é usado depois que a aparição realmente ocorreu. Detalhes: `../entradas/README.md`.

## Agentes recorrentes leves

NPC leve tem **rotina como padrão**. O orçamento atual permite no máximo 1 nova reavaliação leve por checkpoint e 2 pendências leves abertas. Seleção: mais atrasado → maior prioridade → ID. Ciclos perdidos são condensados em uma única avaliação.

A população inicial é Luath, Silva Elkwood e Maerra Thandrel. Detalhes: `../agentes-leves/README.md`.

## Baralho de eventos mundiais

O acaso do mundo é implementado por **dois baralhos determinísticos sem reposição** em `narrador/eventos/`.

A urna de ocorrência possui 10 fichas por ciclo: **7 `rotina` e 3 `evento`**. Portanto, cada bloco de dez amanheceres contém exatamente três oportunidades de evento, em ordem pseudoaleatória reprodutível. Só quando sai `evento` o segundo baralho fornece uma carta concreta.

O baralho de cartas possui inicialmente dez moldes. Uma carta não volta antes que todas as outras tenham sido consumidas. A ordem de cada ciclo é calculada por SHA-256 a partir de semente persistente + nome do baralho + número do ciclo + ID; não há `random`, relógio do sistema ou entropia externa.

**Sorteio não é cânone.** Ele gera `evento_mundial` com ID, categoria e escala. O narrador abre somente aquela carta e resolve sua manifestação no estado atual; a resolução pode ser apenas textura. Apenas fatos posteriormente registrados pelo pipeline transacional tornam-se canônicos.

As cartas não podem, por si só, forçar entrada de aliado/Juppongatana, ativar a Ponte de Kozakura, matar NPC nomeado, revelar segredo ou escolher autoria. Interação entre eventos e agentes pertence à etapa seguinte do Mundo Vivo.

O estado inicial é retroativamente neutro: a camada começa a produzir sorteios somente a partir do primeiro amanhecer futuro alcançado após sua instalação.

Detalhes e comandos: `../eventos/README.md`.
