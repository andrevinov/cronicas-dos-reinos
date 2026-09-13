# Oportunidades raras de side quest

Esta camada cria **oportunidades**, não missões automáticas. Ela fica ao redor do
Mundo Vivo e não entra no scheduler central.

Princípio:

```text
Ren encontra/interage com NPC
→ filtros baratos de orçamento/cooldown
→ NPC possui perfil ativo?
→ gate global sem reposição (8 nada / 2 oportunidade)
→ se nada: interação normal
→ se oportunidade: escolhe deterministicamente uma semente compatível
→ cria estado potencial
→ narrador avalia usando o estado canônico atual do NPC
→ descarta OU confirma a oferta
→ Ren aceita / adia / recusa
```

`potencial` **não significa** que o NPC pediu alguma coisa. A semente é explicitamente
não canônica até a avaliação do narrador. `oferecida` também não significa aceita.

## Por que os perfis são curados

Não existe fallback que varra os 35 NPCs ou invente semanticamente uma necessidade
genérica. NPC sem perfil ativo simplesmente não entra no gate.

A instalação inicial possui 12 perfis, todos ligados a relações atuais:

- Kethra Dunn;
- Bram Vask;
- Pell;
- Irmã Maerra Thandrel;
- Luath;
- Irmã Halessa Vorn;
- Silva Elkwood;
- Jack Mooney;
- Corven Dalm;
- Nera Vell;
- Brunna Torkel;
- Dessa Wren.

Os oito agentes leves atuais estão cobertos; Corven entra por já possuir agência
estratégica; Nera, Brunna e Dessa acrescentam necessidades pessoais, exploração e
trabalho profissional. NPCs representados por agente-pai não ganham perfil próprio
por padrão, evitando duplicar agência.

Cada perfil contém somente **sementes compatíveis** com função e vida do NPC.
Exemplo: Pell trabalha com entrega/informação; Maerra com vulneráveis e abrigo;
Jack com bastidores/circo. O narrador continua obrigado a descartar uma semente se
o estado canônico do encontro não a sustentar.

## Raridade e orçamento

O gate global é um baralho determinístico sem reposição:

```text
10 fichas por ciclo
8 = nada
2 = oportunidade
```

A ordem é SHA-256 de seed + ciclo + ficha. Não usa `random`, relógio do sistema ou
entropia externa.

Além do gate:

- cooldown global depois de uma **oferta real**: 2 ou 3 dias, escolhido
  deterministicamente;
- máximo de **2 side quests aceitas/ativas**;
- máximo de **3 em aberto** (`oferecida`, `aceita`, `adiada`);
- máximo de **1 pendência global de avaliação**;
- NPC com side quest em aberto não gera outra;
- semente descartada ou usada é consumida e não reaparece como missão duplicada;
- um `encontro_id` estável torna o gate idempotente: a mesma cena/NPC nunca sorteia duas vezes.

Recusas ficam registradas. Uma semente marcada `pode_reabrir: true` pode ser
reaberta explicitamente no futuro, preservando o mesmo ID em vez de criar cópia.

## Janelas

As sementes suportam:

```yaml
janela:
  tipo: a_qualquer_momento
```

```yaml
janela:
  tipo: temporal
  duracao_horas: 48
```

```yaml
janela:
  tipo: enquanto_condicao
  condicao: o problema ainda existir
```

Ao materializar uma oportunidade temporal, a duração vira um `expira_em` absoluto.
A expiração é verificada **reativamente** quando esta ferramenta volta a ser
chamada. Não existe despertador temporal novo.

Se uma missão temporal ainda não aceita vence, vira `expirada`. Se já estava
`aceita`, vira `falhada`. Isso altera somente o controle da side quest; qualquer
consequência real no mundo continua precisando de resolução narrativa/canônica.

## Estados

```text
potencial
  ↓ avaliação do narrador
oferecida
  ├─ aceita → concluida | falhada
  ├─ adiada → aceita | recusada | expirada
  └─ recusada → pode eventualmente reabrir, se permitido
```

Também existe `expirada` para ofertas/janelas que perderam o momento.

## Necessidade ≠ missão para Ren

Cada semente guarda `consequencia_sem_ren`, mas esse campo é somente uma
**possibilidade de resolução**. A ferramenta nunca executa automaticamente algo
como “outra pessoa foi contratada”, “o gato morreu” ou “o sequestrador chegou”.

Isso permite que o mundo continue tendo necessidades próprias sem transformar
toda necessidade em obrigação do jogador.

## Custo de contexto

A ordem é deliberadamente barata:

1. NPC sem perfil ativo → somente `index.yaml`;
2. cooldown, limite ou pendência global bloqueando → `index.yaml + estado.yaml`
   (e tempo, somente se o chamador não passar o instante já conhecido);
3. encontro elegível → abre **apenas o perfil daquele NPC**;
4. se sair oportunidade, a própria saída já contém a semente;
5. o narrador só precisa abrir `fonte_npc` se a avaliação realmente exigir
   contexto canônico adicional.

Não há scan de relações, agentes ou perfis durante um encontro.

A integração automática com o pipeline de encontro/lifecycle permanece para a
etapa final de integração. Hoje a porta explícita é:

```bash
python3 ferramentas/oportunidades.py encontro maerra_thandrel --encontro-id "sessao-009:cena-03:maerra"
python3 ferramentas/oportunidades.py avaliar sq-... oferecer --motivo "..."
python3 ferramentas/oportunidades.py responder sq-... aceitar
python3 ferramentas/oportunidades.py finalizar sq-... concluida --motivo "..."
python3 ferramentas/oportunidades.py mostrar sq-...
python3 ferramentas/oportunidades.py status
python3 ferramentas/oportunidades.py check
```
