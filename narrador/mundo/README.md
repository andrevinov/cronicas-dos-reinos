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
