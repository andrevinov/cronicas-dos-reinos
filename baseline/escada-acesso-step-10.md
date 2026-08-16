# Etapa 10 — baseline da escada formal de acesso

A Etapa 10 transforma a política de leitura em contrato executável. Ela não adiciona um ritual obrigatório de chamadas; pelo contrário, preserva a conclusão do rollout de que **round-trips custam caro** e permite saltos dirigidos quando o alvo já é conhecido.

## Escada efetiva

- L0 — contexto já presente: 0 ferramenta, 0 bytes do repositório;
- L1 — `status`: teto 4 KiB;
- L2 — consulta dirigida (`cena`, `retomada`, `npc`, `relacao`, `conhecimento`, `regra`, sessão atual): teto 8 KiB;
- L3 — busca limitada: teto 8 KiB, exige `--apos L2` + `--motivo`;
- L4 — histórico estruturado: teto 12 KiB, busca ampla exige `--apos L3` + `--motivo`;
- L4T — transcrição fria: teto 16 KiB, exige `--apos L4` + `--motivo`;
- L5 — fonte externa/autorizada: fora de `contexto.py`, somente após insuficiência da memória interna.

## Exceção econômica deliberada

Uma escada literal L0 → L1 → L2 → L3 → L4 em toda consulta aumentaria o número de inferências. Por isso um alvo conhecido pode evitar degrau amplo intermediário.

Exemplos:

- NPC conhecido → L2 direto;
- relação conhecida → L2 direto;
- sessão histórica conhecida → L4 direto, declarando `--apos L2` e a lacuna concreta;
- busca histórica sem alvo conhecido → L3 antes de L4;
- transcrição → sempre depois de L4 insuficiente.

`--apos` é uma declaração da decisão de escalada, não uma exigência de nova tool call. O ganho desejado é impedir busca especulativa sem criar chamadas artificiais.

## Orçamentos mecânicos

O orçamento solicitado pelo chamador é reduzido ao teto do nível:

```text
L1   4096 bytes
L2   8192 bytes
L3   8192 bytes
L4  12288 bytes
L4T 16384 bytes
```

Pedir `--max-bytes 16000 status` continua limitado a 4096 bytes.

## Motivo de escalada

L3, L4 e L4T exigem descrição concreta da informação ausente. Acesso `--reservado` também exige motivo.

Motivos genéricos como “só conferir” e “por precaução” são recusados. A ferramenta não tenta julgar semanticamente toda justificativa; a proteção combina schema, texto mínimo, degrau declarado, documentação e CI.

## Condição de parada dentro da própria saída

Cada resposta de `contexto.py` recebe `controle_acesso` com:

- nível efetivo;
- teto aplicado;
- `pare_se_suficiente: true`;
- condição de parada;
- próximo nível;
- `--apos` declarado;
- motivo, quando aplicável;
- marca de salto dirigido.

Isso serve como lembrete no próprio tool output, sem uma segunda chamada.

## Mapeamento da amostra pré-refatoração

Com base no rollout usado como baseline:

- continuação imediata de cena com dados já no contexto → alvo L0;
- falta apenas PV/Ki/hora/localização → L1;
- ação envolvendo NPC/relação/regra explicitamente identificada → L2;
- pista sem domínio conhecido → L3;
- origem de pista em sessões anteriores → L4;
- formulação exata perdida nos artefatos compactos → L4T;
- dúvida de Forgotten Realms/regra oficial não resolvida internamente → L5.

A expectativa é que **70–80% ou mais das interações normais morram em L0–L2**, mas a medição real será feita na Etapa 11 a partir dos rollouts nativos.

## Critérios permanentes de aprovação

- busca L3 sem `--apos L2` ou sem motivo falha;
- busca L4 ampla sem `--apos L3` falha;
- L4T sem `--apos L4` falha;
- sessão histórica conhecida pode usar salto L2 → L4;
- `--transcricoes` sem `--historico` falha;
- acesso reservado sem motivo falha;
- motivo explicitamente genérico falha;
- teto de bytes não pode ser ampliado pelo chamador;
- L1 retorna no máximo 4 KiB;
- L2/L3 retornam no máximo 8 KiB;
- a saída lembra o agente de parar quando suficiente;
- nenhum fato canônico é alterado por esta etapa.

## O que medir depois

No próximo rollout real, comparar com a baseline anterior:

- distribuição L0/L1/L2/L3/L4/L4T/L5;
- inferências por avanço narrativo;
- tool calls por avanço;
- bytes de saída por nível;
- número de escaladas L3+;
- quantidade de acessos a transcrição;
- consultas reservadas;
- escaladas rejeitadas/reescritas;
- proporção de saltos dirigidos que evitaram uma busca intermediária.
