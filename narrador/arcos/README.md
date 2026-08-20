# Contratos de Arco da Crônica

Esta camada fica **acima do Mundo Vivo**. Ela não decide quando alguma coisa
acontece; responde antes duas perguntas:

1. esta peça pertence à parte da história em que estamos?
2. se pertencer, **qual fonte especializada** deve ser consultada caso ela se torne relevante?

O Contrato de Arco é, portanto, um **orquestrador de referências**. Ele não é um
novo depósito narrativo.

```text
Contrato de Arco
       ↓ habilita/bloqueia + aponta fontes
índices especializados de agentes/entradas/direções
       ↓ resolvem ID → fragmento sem abri-lo
Mundo Vivo / contexto / entradas / direções
       ↓ avaliam oportunidade real
Narrador
       ↓ abre somente a fonte necessária e decide manifestação
Cânone
```

**Habilitado não significa ativo, presente ou acontecido.** Um antagonista pode
estar habilitado no arco e ainda ser bloqueado por presença, morte, marco de
aparição, falta de oportunidade ou restrição própria. O inverso é mais rígido:
uma peça controlada pelo arco e não listada está estruturalmente bloqueada.

## Estrutura

- `index.yaml`: ordem dos arcos, arquivo de cada contrato e única transição futura
  permitida (`proximo`);
- `estado.yaml`: ponteiro para o arco corrente e histórico curto de transições;
- `<arco>.yaml`: contrato **orquestrador** da parte da crônica;
- `ferramentas/arcos.py`: API única de leitura, elegibilidade, resolução de
  ponteiros, manifesto derivado, validação e transição.

## Contrato schema 4

Cada arco declara somente:

- **início**: marcador e fonte canônica que justificam a existência do arco;
- **término**: marcador e fonte que permitem encerrá-lo;
- **fontes orquestradas nomeadas**, como plano mestre e marcos de antagonistas;
- **plano mestre** como `agente + objetivo compacto + referência nomeada`;
- IDs de **antagonistas habilitados**;
- IDs de **aliados habilitados**;
- IDs de **direções habilitadas**;
- política obrigatória `nao_listados = bloqueados`;
- **linhas operacionais** compactas: necessidade estratégica + executores habilitados + referência estratégica.

O contrato **não pode** carregar `recursos`, `restricoes`, `presenca`,
`plano_atual`, listas de ações, descrição de personagem ou outra prosa que já
pertença às fontes especializadas. Uma linha operacional também não aceita `acao`,
`metodo` ou sequência de passos: ela descreve **o problema estratégico**, não como
um agente o resolve. O schema usa conjuntos de campos fechados e
teto de 8 KiB para impedir que o arquivo cresça até virar outro manual.

A Parte 1, por exemplo, não copia o plano de Masao. Ela registra:

```yaml
orquestracao:
  fontes:
    plano_mestre:
      arquivo: narrador/masao/plano.md
    marcos_antagonistas:
      arquivo: narrador/juppongatana/marcos-de-aparicao.md
  plano_mestre:
    agente: masao_hirasawa
    objetivo: preservar_consolidar_controle_exclusivo_ponte
    referencia: plano_mestre
```

Os antagonistas continuam sendo apenas IDs. Seus arquivos são descobertos pelo
índice `narrador/agentes/index.yaml`; aliados pelo índice de entradas; direções
pelo índice de direções. Assim mudar o conteúdo de Kurobane ou Shizune não exige
reescrever o contrato do arco.


## Linhas operacionais do arco

Uma linha operacional é uma necessidade estratégica ativa enquanto o arco está
corrente. Ela fica entre o plano mestre e os agentes:

```text
plano mestre de Masao
        ↓
linha operacional: impedir consolidação de provas
        ↓ executores permitidos
Kurobane / Shizune
        ↓ item 5
cada agente traduz a necessidade segundo seus métodos e restrições
```

Schema mínimo:

```yaml
linhas_operacionais:
  impedir_consolidacao_de_provas:
    objetivo: impedir_consolidacao_de_provas
    executores:
      - kurobane_jinzaburo
      - kajiwara_shizune
    referencia: plano_mestre
```

`executores` pode conter antagonistas habilitados no arco ou o próprio agente do
plano mestre. Isso permite Masao agir estrategicamente sem transformá-lo em NPC
habilitado para aparição. Um NPC habilitado no arco não ganha automaticamente
acesso a todas as linhas.

Na população jogável da Fase 11, a Parte 1 possui **11 linhas**. Além das
cinco iniciais, entram expansão da presença de Masao, ocupação urbana, desgaste
da autoridade, pressão por vínculos conhecidos de Ren, pressão sobre sua
identidade marcial e cobertura marítima. Chō e Pan Chu passam a ter funções
estratégicas próprias sem que isso os ative antes de seus marcos/presença.

Consultas baratas:

```bash
python3 ferramentas/arcos.py linhas
python3 ferramentas/arcos.py linha impedir_consolidacao_de_provas
python3 ferramentas/arcos.py linha impedir_consolidacao_de_provas --executor kurobane_jinzaburo
```

Esses comandos usam somente os três controles do arco e não abrem índice de
agentes nem fragmentos narrativos.


## Tradução operacional por agente

As linhas permanecem abstratas no contrato. O **como** fica no fragmento do
executor em `metodos_operacionais`:

```yaml
metodos_operacionais:
  impedir_consolidacao_de_provas:
    - id: interceptar_transito_documental
      abordagem: Interceptar fisicamente a circulação da prova antes do destino.
      modalidade: fisica
      tags: [documentos, prova, mensageiro]
```

O método é um **repertório de abordagem**, não uma ordem preparada. Por schema ele
não pode carregar `alvo`, `momento`, `acao` ou `resultado`; isso impede que
"Kurobane tende a interceptar documentos" vire "Kurobane rouba o documento X
amanhã" antes de a cena e o mundo sustentarem a decisão.

A mesma linha pode ser traduzida de maneiras diferentes. Em
`impedir_consolidacao_de_provas`, Kurobane possui repertório físico de
interceptação/substituição, enquanto Shizune possui repertório indireto de
invalidação e contradição administrativa. Pan Chu possui repertórios marítimos,
mas seu `estado: latente` e sua presença indeterminada continuam valendo: ter
métodos cadastrados **não o ativa**.

Consulta dirigida:

```bash
python3 ferramentas/arcos.py metodos impedir_consolidacao_de_provas \
  --executor kurobane_jinzaburo
```

A porta valida primeiro linha + executor usando somente os três controles do
arco. Executor não autorizado para ali, sem abrir índice ou fragmento. Executor
autorizado abre `narrador/agentes/index.yaml` + **um único fragmento de agente**
e devolve no máximo quatro métodos.

`ferramentas/metodos_agentes.py` contém apenas o schema/validador compacto dessa
tradução. A validação fria de `arcos.py validar` exige que cada executor declarado
por uma linha possua pelo menos uma tradução e rejeita método órfão ou atribuído a
agente que não seja executor daquela linha. IDs de linha são globalmente únicos
entre arcos.

## Marcos de aparição — segunda trava

O Contrato de Arco responde **quem pode pertencer à fase atual**, mas isso ainda não
é suficiente para uma primeira aparição. Antagonistas controlados pelo arco passam
por uma segunda trava compacta em:

- `marcos-aparicao.yaml`: índice mínimo derivado do documento longo de marcos;
- `estado-marcos-aparicao.yaml`: estado operacional `bloqueado | elegivel | consumido`;
- `ferramentas/marcos_aparicao.py`: gate, validação e mudanças explícitas de estado.

A lógica semântica é:

```text
Contrato de Arco permite?
        ↓
nível mínimo do marco foi alcançado?
        ↓
marco está elegível ou já consumido?
        ↓
contexto concreto da cena combina?
        ↓
avaliar aparição
```

O roteador de cena pode fazer uma pré-filtragem barata por tags antes de abrir os
controles, mas **nenhum candidato é exposto** sem satisfazer todas as travas acima.

`elegivel` não é presença e não é aparição. Significa apenas que uma cena adequada
pode justificar consulta dirigida ao NPC. `consumido` significa que a primeira
aparição já ocorreu; a partir daí o marco deixa de bloquear reaparições, que continuam
sujeitas a presença, mobilidade, contexto e demais regras.

A fonte narrativa longa continua sendo
`narrador/juppongatana/marcos-de-aparicao.md`. O índice compacto guarda somente
ID, arco, nível mínimo, seção da fonte e um identificador curto da condição. O texto
longo não entra no hot path.

Mudanças são explícitas:

```bash
python3 ferramentas/marcos_aparicao.py marcar-elegivel <npc>   --origem "..." --nota "..."
python3 ferramentas/marcos_aparicao.py consumir <npc>   --origem "..." --nota "..."
```

Um marco `bloqueado` não pode ser consumido diretamente. Passagem de tempo, afinidade
de tags ou habilitação no arco **não promovem** o estado por conta própria.

## Parte 1 — Uma Ponte para Kozakura

A população jogável da Parte 1 fixa:

- antagonistas habilitados: Kurobane, Shizune, Pan Chu e Chō;
- aliados habilitados: Shen e Jōen;
- direções habilitadas: **Ponte de Kozakura** e **Golden Lily em Ravens Bluff**;
- plano mestre: domínio gradual de Ravens Bluff e preservação do valor
  estratégico da Ponte;
- 11 linhas operacionais e autonomia própria dos quatro Juppongatana;
- cinco frentes de pressão urbana, que só mudam com fato canônico + evidência;
- qualquer antagonista/aliado/direção não listado continua bloqueado.

Anji e os demais membros posteriores continuam existindo no cânone, mas não são
peças autônomas da Parte 1. A chegada do Golden Lily é destino temporal canônico;
bombardeio, sequestros, intervenção de Cormyr e outras escaladas permanecem
condicionais.

## API

```bash
python3 ferramentas/arcos.py status
python3 ferramentas/arcos.py checar antagonistas kajiwara_shizune
python3 ferramentas/arcos.py resolver antagonistas kajiwara_shizune
python3 ferramentas/arcos.py resolver aliados shen_meihua
python3 ferramentas/arcos.py manifesto
python3 ferramentas/arcos.py linhas
python3 ferramentas/arcos.py linha <id> [--executor <agente>]
python3 ferramentas/arcos.py metodos <id> --executor <agente>
python3 ferramentas/arcos.py validar
```

- `checar`: somente habilitado/bloqueado; lê apenas controles do arco;
- `resolver`: se bloqueado, para ali; se habilitado, lê **um índice** e devolve o
  caminho do fragmento, sem abrir o fragmento;
- `manifesto`: ferramenta fria que materializa o mapa completo `ID → nome →
  arquivo` do arco corrente a partir dos índices existentes; não abre nenhum
  fragmento narrativo;
- `linhas`: lista as necessidades estratégicas e seus executores;
- `linha`: resolve uma linha específica e, opcionalmente, checa um executor sem
  abrir índice ou fragmento;
- `metodos`: após linha + executor autorizados, abre somente o índice de agentes e
  um fragmento dirigido para devolver o repertório daquele executor;
- `validar`: manutenção/CI; confere que IDs e arquivos apontados realmente existem.

O manifesto é derivado e nunca vira fonte de verdade adicional.

## Transição

Transição de arco nunca acontece por relógio nem por desejo do narrador. Ela
precisa:

1. seguir exatamente o `proximo` declarado no índice;
2. apresentar exatamente o marcador de término do arco corrente;
3. registrar origem e nota rastreáveis.

```bash
python3 ferramentas/arcos.py transicionar \
  --para <proximo_arco> \
  --marco <marco_de_termino> \
  --origem "..." \
  --nota "..."
```

A Parte 1 ainda não declara `proximo`: não inventamos a Parte 2 antes de
estruturá-la. Em testes sintéticos, a transição prova que a mudança de arco muda
a elegibilidade de forma determinística e não permite pular ou voltar partes.

## Descoberta contextual

A descoberta inversa usa o Contrato de Arco como filtro, nunca o manifesto
completo. Desde as fases 6 e 9, ela trabalha em quatro classes:

```text
tags concretas da cena
→ afinidade contextual
→ Contrato de Arco permite?
   ├─ presença  → marco de aparição permite? → estado/presença resumidos → avaliar
   ├─ operação  → linha operacional ativa             → avaliar
   ├─ direção   → direção habilitada + ativa           → avaliar marco atual
   └─ entrada   → arco + ordem/janela + contexto forte → avaliar aliado
```

Se todos os matches forem bloqueados pelo arco, o processo para antes da fonte
especializada. Operação não abre agente nem métodos; direção abre apenas o estado
compacto de direções. Nenhuma das quatro classes abre fragmento narrativo na
pré-seleção. `resolver`/`metodos`/`direcoes.py mostrar` continuam sendo passos
posteriores, somente quando uma lacuna concreta justificar detalhe.

## Estado após a Fase 11

As peças previstas para este ciclo já estão integradas: filtro de arco nos
schedulers, marcos de aparição, entrada contextual de aliados, direções como
restrições de destino e população jogável da Parte 1. A evolução futura deve
acrescentar novos fatos/arcos sem transformar esses controles em um roteiro de
cenas obrigatórias.

## Guardrail do Mundo Vivo — fase 7

`ferramentas/arco_mundo.py` é a única tradução do Contrato de Arco para os
schedulers. Ele não agenda nada: recebe uma peça que outra camada já pretendia
reavaliar e pode barrá-la antes da criação da pendência.

O roteador `controle-mundo.yaml` lista somente agentes estratégicos cuja autonomia
é controlada pelo arco. Agentes ausentes (Night Watch, Red Sail, Casa de Tyr,
agentes leves etc.) continuam livres. Para os controlados:

```text
reavaliação/evento
→ arco habilita o agente?
→ agente é o plano mestre OU possui ao menos uma linha operacional?
→ somente então pode virar candidato de avaliação
```

Movimento/presença exigem habilitação no arco, mas ação autônoma também respeita
o estado real do agente. Na Fase 11 Chō e Pan Chu já possuem linhas/repertórios,
mas permanecem inertes enquanto `estado: latente`; isso permite cadastrar
reavaliações futuras sem fazê-los agir antes da primeira aparição canônica.

O mesmo guardrail cobre:

- `mundo.py`: reavaliações e movimentos de agentes estratégicos;
- `direcoes_mundo.py`: avaliação/ativação de direções e limpeza de pendências antigas;
- `entradas.py`: avaliação e mutação de entradas de aliados;
- `eventos_mundo.py`: evento continua existindo, mas candidatos estratégicos bloqueados são removidos;
- `fronteira_mundo.py`: uma peça bloqueada não interrompe salto temporal.

Pendência incompatível com o arco é **cancelada como avaliação**, nunca registrada
como acontecimento. Evento mundial não é apagado: somente sua lista de agentes
estratégicos candidatos é podada. Essa distinção impede o Contrato de Arco de
reescrever a história ou engolir o Mundo Vivo.


## Entradas de aliados e arco

O contrato lista quais aliados pertencem ao arco, mas não duplica ordem, nível,
janela ou gatilhos. Esses dados continuam em `narrador/entradas/`. A Fase 9 usa
`ferramentas/aliados_contextuais.py` para combinar o contrato com a camada de
entradas e com tags fortes de cena. Assim **habilitado no arco** continua sendo
necessário, mas não suficiente para aparecer.
