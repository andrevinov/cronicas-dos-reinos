# Task 26 — NPC Relationship State v1

## Problema

As relações já possuíam prosa rica (`atitude_para_ren`, `confianca`, `respeito`),
mas essa nuance não era um contrato operacional uniforme. Ao mesmo tempo, uma
camada numérica antiga já existia para parte do elenco com `vinculo`, `confianca`
e `risco_percebido`.

Criar uma segunda “barra de amizade” duplicaria fonte de verdade. A Task 26 faz o
oposto: **generaliza a camada que já existe** e dá semântica explícita aos dois
eixos centrais.

## Dois eixos centrais

O estado físico permanece em `estado/npcs/<id>.yaml`:

- **afinidade** = `medidores.vinculo`;
- **confiança** = `medidores.confianca`.

Ambos usam 0–10 ou `null` quando o cânone ainda não permite inferência segura.
`risco_percebido` continua sendo um terceiro contexto útil, mas não é afinidade nem
confiança.

A prosa detalhada em `estado/relacoes/<id>.yaml` continua canônica e preserva as
nuances que dois números não podem representar. Um NPC pode, por exemplo, confiar
na competência de Ren sem gostar dele, ou gostar dele e ainda desconfiar de suas
promessas.

## Bootstrap

Todos os **36 relacionamentos atuais** de `estado/relacoes/index.yaml` agora possuem
medidores tipados em `estado/npcs/`. O índice de NPCs possui 37 entradas porque o
homem de mãos limpas permanece como registro histórico extra apesar de não possuir
relação corrente.

Os valores antigos foram preservados onde já existiam. Para relações antes sem
medidor, o bootstrap usa somente o estado canônico atual. Ausência real de evidência
vira `null`, não uma personalidade inventada. Rusk Cinza, por exemplo, continua com
afinidade desconhecida até existir encontro suficiente.

A identidade pela qual a relação existe pode ser registrada sem revelar outra
identidade ao NPC. Sella da Galeria, por exemplo, relaciona-se operacionalmente com
**Shinta**; isso não afirma que ela conhece Ren por trás da identidade.

## Mutação

Afinidade/confiança **não sobem porque uma conversa foi simpática** e não caem
porque um NPC deu uma bronca. Um teste social isolado também não altera medidor.

Para eixo já conhecido, a forma normal é um delta incremental:

```json
{
  "alvo": "npc:jack_mooney",
  "op": "inc",
  "caminho": "medidores.confianca",
  "valor": 1,
  "fato_canonico": "Jack viu Ren cumprir um compromisso importante sem expor o circo.",
  "fonte": "sessoes/NNN/transcricao.md"
}
```

Regras:

- somente `+1` ou `-1` por fato normal;
- `fato_canonico` concreto e `fonte` são obrigatórios;
- `set` não pode sobrescrever eixo conhecido;
- um eixo `null` pode ser inicializado uma vez com `set`, `inicializacao: true`,
  valor 0–10, fato e fonte.

O schema transacional recusa a forma errada antes do buffer. No checkpoint, todos
os deltas relacionais do lote são simulados contra o estado consolidado antes do
stage: incremento de `null`, reinicialização, overflow acima de 10 e underflow
abaixo de 0 falham sem instalar estado parcial.

## Hot path

Nenhuma chamada nova é necessária. `contexto npc <nome>` já lia o índice de
medidores, um fragmento NPC, o índice de relações e no máximo um fragmento de
relação; isso continua igual. O contrato `relacionamento-v1.yaml` é manutenção,
não leitura ritualística por turno.

Task 27 poderá usar esses mesmos números para modular diálogo e Task 30 para
iniciativa social sem abrir outra camada de estado.

## Custo

Contrato: `baseline/npc-relationship-state-v1-orcamento.yaml`.

- 0 chamadas extras por turno;
- 0 scheduler;
- 0 RNG;
- 0 armazenamento relacional paralelo;
- índice NPC <= 24 KiB;
- fragmento NPC <= 12 KiB;
- mudanças relacionais só pagam validação dirigida quando realmente existem.
