# Motor reservado do Mundo Vivo

Esta pasta guarda somente o **controle determinístico** do mundo que continua em
movimento fora da presença de Ren. Ela não substitui agentes, sessões, relógios,
relações ou qualquer outra fonte canônica.

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

O fluxo normal agora sincroniza este motor em três situações:

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

A ordem é obrigatória:

```text
turno persiste transcrição + delta
→ checkpoint consolida o novo tempo canônico
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

## Economia de contexto

O motor lê agenda, cursor e tempo. Quando nada vence, **não lê sequer o índice de
agentes**. Quando alguma pendência vence, consulta no máximo
`narrador/agentes/index.yaml` para validar IDs e devolve apenas os agentes que
precisam de reconsideração. Ele nunca abre automaticamente os fragmentos dos
agentes.

Exemplo de saída conceitual:

```yaml
agentes_reconsiderar:
  - red_sail
  - night_watch
```

Só depois disso o narrador pode usar uma consulta dirigida:

```bash
python3 ferramentas/agentes.py mostrar red_sail
```

## Cadência não é ação

Uma cadência de amanhecer significa **reavaliar o plano**, não obrigar o agente a
agir nem garantir que Ren perceberá qualquer coisa. O narrador ainda deve respeitar
conhecimento, presença, mobilidade, recursos, restrições e causalidade.

Cadências podem ser espaçadas conforme a escala: uma facção em busca ativa pode
ser reconsiderada diariamente, enquanto um antagonista estratégico pode ser
reconsiderado a cada vários dias.

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
