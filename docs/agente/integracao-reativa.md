# Integração reativa: contexto, locais, encontros, side quests e recompensas

Esta camada fecha o Mundo Vivo sem criar um novo scheduler. Ela só acorda quando
há um **gatilho real da cena**. Turnos comuns não consultam seus índices.

## 1. Porta preferencial: abertura de cena

Na narração ao vivo, a porta preferencial é uma única abertura reativa:

```bash
python3 ferramentas/cena_mundo.py abrir \
  --cena-id "sessao-009:bram-loja" \
  --local loja_bram_vask --acao entrar --tier 2 --periculosidade media \
  --npc bram_vask --npc noll
```

Ela recebe os gatilhos que realmente começaram naquela fronteira de cena e
encaminha cada um para a camada já existente:

```text
abertura de cena
├─ contexto concreto?     → candidatos contextuais para avaliação
├─ local entrou/explorou? → mapa de recompensas
└─ NPC(s) presentes?      → gate raro de sidequest por NPC elegível
```

A intenção é tornar difícil esquecer os mecanismos sem transformar a abertura em
scheduler. `local` e `encontro` continuam disponíveis em `interacoes_mundo.py`
como primitivas de baixo nível, mas o narrador ao vivo deve preferir
`cena_mundo.py abrir`.

### Descoberta contextual inversa

Quando uma cena começa ou muda materialmente e o contexto **já estabelecido**
contém propriedades relevantes, a mesma abertura pode receber até oito tags:

```bash
python3 ferramentas/cena_mundo.py abrir \
  --cena-id "sessao-009:escritorio" \
  --contexto-tag documentos \
  --contexto-tag escrituracao \
  --contexto-tag registros
```

As tags são rótulos explícitos do que o narrador já sabe sobre a cena. Não são
busca semântica e não autorizam ler o repositório para inventar tags. Caixa,
acentos e separadores são apenas normalizados para uma chave ASCII estável.

O roteador `narrador/mundo/contextos-cena.yaml` cruza essas tags com afinidades
curadas de três tipos: **presença**, **operação** e **direção**. Presença controlada
por arco declara `grupo_arco` (`antagonistas` ou `aliados`; `livre` é explícito).
Linhas operacionais só passam se existirem no contrato corrente. Direções só
passam se estiverem habilitadas no arco atual e ainda estiverem `ativas` em
`narrador/direcoes/estado.yaml`.

O filtro do arco acontece antes das fontes especializadas. Para presença de
antagonista, há uma **segunda trava**: `marcos_aparicao.py` exige nível mínimo e
estado `elegivel` ou `consumido` antes de abrir `narrador/agentes/index.yaml`.
Operação para nos controles do arco; direção consulta somente o estado compacto de
direções. **Nenhuma dessas três classes abre fragmento narrativo na pré-seleção.**

A Parte 1 já usa um **Contrato de Arco orquestrador**: Kurobane, Shizune,
Pan Chu e Chō entre os antagonistas; Shen e Jōen entre os aliados; Ponte de
Kozakura como direção habilitada; e Masao como agente do plano mestre. O contrato
não copia os detalhes dessas peças. `arcos.py resolver` consulta apenas o índice
especializado correspondente e devolve o caminho do fragmento que poderá ser
aberto depois. O plano mestre e os marcos dos antagonistas são referências
nomeadas para `narrador/masao/plano.md` e
`narrador/juppongatana/marcos-de-aparicao.md`.

A política é estrutural: qualquer peça controlada pelo arco e não listada fica
bloqueada. O Contrato de Arco não executa nada; responde **"esta peça pertence à
parte atual?"** e **"onde vive o detalhe, se eu realmente precisar dele?"**.
O Contrato de Arco já declara **linhas operacionais** compactas: necessidades
estratégicas + executores permitidos + referência ao plano mestre. A descoberta
contextual agora pode apontar uma dessas linhas diretamente quando as tags da cena
combinam, mas isso produz apenas `avaliar_linha_operacional`: nenhum executor,
método, alvo ou ação é escolhido. As traduções próprias de Kurobane, Shizune e
Pan Chu continuam sendo consultadas somente depois, por `arcos.py metodos`.
Detalhes: `narrador/arcos/README.md`.

A saída possui no máximo quatro `candidatos_contextuais`, com subtetos de duas
presenças, duas operações e uma direção. A ordenação é:

```text
mais coincidências → maior prioridade → tipo → ID estável
```

**Candidato contextual não é fato.** Além disso, afinidade contextual não supera
o arco nem o marco de aparição: uma peça proibida na Parte atual ou cujo primeiro
marco ainda esteja bloqueado não é exibida como candidata. O retorno
`contexto_arco` mostra apenas o arco aplicado e a quantidade bloqueada, sem expor
NPCs futuros ao narrador. Para candidatos permitidos, o campo `modo_avaliacao`
explicita o limite:

- `presenca_confirmada`: o índice já permite considerar uma interseção física;
- `avaliar_estabelecimento_presenca`: a presença ainda é indeterminada e o marco
  mínimo já permitiu avaliação; o narrador pode consultar **no máximo um** fragmento
  dirigido e decidir se o cânone realmente sustenta estabelecer essa presença agora;
- `atuacao_por_rede` / `estrutura_local`: a avaliação pode ocorrer sem presumir
  uma aparição física individual.
- `avaliar_linha_operacional`: a cena pode oferecer uma janela para uma necessidade
  estratégica ativa; executor e método ainda não foram escolhidos;
- `avaliar_marco_atual`: a cena pode sustentar o marco atual de uma direção ativa;
  a direção continua inalterada até resolução explícita.

`avaliar_estabelecimento_presenca` nunca autoriza simplesmente mudar
`presenca.estado`. Qualquer estabelecimento de presença concreta continua
exigindo fonte/evidência e o pipeline canônico normal. Se a cena não sustentar o
candidato, a avaliação termina sem mudança.

Agente inativo, físico `fora_da_area`/`em_viagem`, coletivo dependente de membros
sem membro concreto e NPC já incluído no elenco da própria abertura são
pré-filtrados. Repetir a mesma `cena_id` com as mesmas tags devolve a mesma seleção
e o mesmo `avaliacao_id`; não há sorteio nem mutação.

A descoberta contextual só roda em **abertura ou mudança material de cena**. Não
reexecutar a cada fala de Ren.

### `cena_id` e idempotência

`cena_id` é um identificador ASCII estável e único daquela cena narrativa. Não
criar um novo ID a cada fala.

A mesma abertura pode ser repetida com segurança. Para cada NPC, a porta deriva:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Para cada candidato contextual, deriva:

```text
scene:<cena_id>:contexto:presenca:<agente_id>
scene:<cena_id>:contexto:operacao:<linha_id>
scene:<cena_id>:contexto:direcao:<direcao_id>
```

Se o mesmo NPC já foi processado naquela cena, o gate não roda novamente. A
seleção contextual é somente leitura e permanece determinística.

Quando um NPC novo entra numa cena que já está em andamento, chamar novamente a
porta com o **mesmo `cena_id`** e o elenco atualizado é seguro: NPCs antigos viram
`encontro_ja_processado`; somente o recém-chegado pode consumir novo gate.

### Vários NPCs simultâneos

Todos os IDs, a configuração contextual e o contrato mínimo do arco corrente são
validados antes de qualquer mutação. Se houver typo, ambiguidade, binding contextual
quebrado ou arco corrente inexistente/inválido, a abertura falha antes de gerar mapa
ou consumir gate.

Referências duplicadas que apontam para o mesmo NPC são colapsadas. Encontros que
começam simultaneamente são ordenados pelo **ID canônico**, não pela ordem dos
argumentos do CLI. Assim a distribuição do baralho 8/2 não depende de uma ordem
acidental de escrita.

A abertura aceita no máximo 12 referências de NPC por chamada. O gate global
continua permitindo no máximo uma pendência de avaliação; portanto uma abertura
pode expor no máximo um perfil narrativo de oportunidade.

### Economia

A porta não cria scan novo:

- turno comum → não chama a descoberta contextual;
- abertura sem tags → não lê o roteador contextual;
- tags sem afinidade → lê somente `contextos-cena.yaml`;
- afinidade toda bloqueada pelo arco → roteador + controles do arco, sem fonte especializada;
- presença antagonista permitida → controles do marco + runtime de nível e só
  depois o índice resumido de agentes;
- operação permitida → não abre agente nem método;
- direção permitida → acrescenta somente `narrador/direcoes/estado.yaml`;
- combinação máxima das três classes → até 9 fontes pequenas, 0 fragmentos;
- no máximo 8 tags e 4 candidatos agregados (2 presença / 2 operação / 1 direção);
- cena só com local → não lê oportunidades nem tempo;
- NPC canônico sem perfil → não lê tempo;
- ID exato de perfil → resolução custa só o índice de oportunidades;
- alias/typo → no máximo índice de oportunidades + índice de relações;
- nenhum fragmento é aberto para resolver identidade.

## 2. Primitiva local: entrada/exploração

Quando Ren efetivamente entra ou começa a explorar uma área/setor com identidade
operacional estável, a abertura de cena pode despachar o local. A primitiva
continua disponível para manutenção/teste:

```bash
python3 ferramentas/interacoes_mundo.py local sarbreen_setor_a \
  --acao entrar --tier 2 --periculosidade alta
```

Se o mapa já existe, lê somente índice + mapa e o reutiliza. Se não existe, a
geração determinística acontece uma vez. Mudanças posteriores de tier/perigo não
rerrolam a área.

O retorno oferece candidatos/condições ao narrador. **Item existir no mapa não
significa que Ren o encontrou.** Fragmento de item só deve ser aberto quando sua
condição se tornar relevante.

## 3. Primitiva de encontro com NPC

A abertura de cena despacha encontros elegíveis com IDs estáveis. A primitiva
continua disponível quando for necessário acionar somente um encontro:

```bash
python3 ferramentas/interacoes_mundo.py encontro maerra_thandrel \
  --encontro-id "sessao-009:cena-03:maerra"
```

O `encontro_id` identifica a conversa inteira. Não gerar um novo ID a cada fala.

### Resolução do NPC

Preferir sempre o **ID estável completo**. Esse é o caminho mais barato: um ID de
perfil exato é reconhecido somente com `narrador/oportunidades/index.yaml`.

A porta tolera nome/alias humano sem criar identidade paralela:

```text
nera       -> nera_vell
Nera Vell  -> nera_vell
```

Nome completo normalizado pode ser resolvido no próprio índice de oportunidades.
Alias parcial consulta no máximo o índice canônico `estado/relacoes/index.yaml`
para provar que a referência é **globalmente unívoca**, sem abrir fragmentos.

Por isso:

```text
dunn  -> ERRO: colm_dunn ou kethra_dunn
nrea  -> ERRO: NPC desconhecido; sugestão nera_vell
```

Um NPC canônico realmente conhecido, mas sem perfil de oportunidade, continua
retornando `npc_sem_perfil_ativo`. Um identificador desconhecido **nunca** recebe
essa resposta. Ambiguidade ou typo falham antes de consumir o gate e pedem o ID
estável. O resultado usa sempre o ID canônico resolvido em cooldown, idempotência,
necessidades e missões.

A ordem barata é:

```text
resolver ID/nome do NPC
→ perfil existe no índice?
→ orçamento/cooldown permitem?
→ encontro já foi processado?
→ gate global 8 nada / 2 oportunidade
   → nada: fim, sem abrir perfil
   → oportunidade: abre exatamente 1 perfil dirigido
                  → escolhe 1 necessidade ainda disponível
                  → cria apenas potencial
```

`potencial` não é oferta. O narrador decide `oferecer` ou `descartar` com
`oportunidades.py`; Ren decide aceitar, adiar ou recusar.

## 4. Efeitos de side quest

Uma side quest aceita pode tocar estruturas já existentes sem bypassar seus
contratos. Antes de registrar o turno que materializa o efeito:

```bash
python3 ferramentas/interacoes_mundo.py preparar-sidequest sq-... <<'YAML'
- tipo: operacao
  operacao: red_sail_reconstruir_cadeia_colm
- tipo: pressao
  relogio: rastro_fraco_no_pomar
- tipo: consequencia
  valor:
    titulo: Um custo persistente
    descricao: O resultado da missão criou uma consequência.
YAML
```

- `agente`: referencia agente existente; agente novo é devolvido para
  **classificação NPC v2**, nunca criado silenciosamente;
- `operacao`: valida vínculo no roteador compacto;
- `pressao`: produz delta `relogio:<id>` para o mesmo `turno.py registrar`;
- `consequencia`: produz delta `consequencia/registrar`;
- `rastro` e `recompensa`: ficam em `pos_canonico`.

No máximo 6 efeitos por decisão. A preparação não abre fragmento de relógio.

## 5. Pós-canônico

Depois que o fato-base foi consolidado:

```bash
python3 ferramentas/interacoes_mundo.py pos-sidequest sq-... <<'YAML'
- tipo: rastro
  especificacao:
    ...
- tipo: recompensa
  local_id: sarbreen_setor_a
  especificacao:
    ...
YAML
```

Rastros continuam exigindo fonte canônica + evidência literal. Recompensa de quest
entra como `origem: quest`. Se o mapa ainda não existe, fica planejada para ele;
se já existe, é anexada sem rerrolar o núcleo procedural nem trocar a chave de
geração. Retry com o mesmo ID é idempotente; conteúdo divergente falha.

## 6. Lifecycle

No checkpoint, após o cânone estar instalado, quest giver morto é propagado para a
camada de oportunidades:

- perfil → `inativo`;
- potencial → descartado/inviável;
- `oferecida` ou `adiada` → `expirada`;
- `aceita` → `falhada`;
- estados terminais permanecem históricos.

Isso não sorteia oportunidade, não cria consequência e não abre side quest nova.


## Linhas do arco e métodos do agente

Quando uma necessidade concreta já apontar uma linha operacional do arco, não
inventar diretamente uma ação para o executor. Resolver em duas etapas:

```text
arcos.py linha <linha> --executor <agente>
→ confirma que a necessidade e o executor pertencem ao arco

arcos.py metodos <linha> --executor <agente>
→ abre somente o fragmento daquele agente
→ devolve repertórios próprios de abordagem
```

Método continua sendo candidato de comportamento, não acontecimento. Presença,
mobilidade, conhecimento, restrições e o contexto atual ainda precisam sustentar
a manifestação. Em especial, um agente latente pode possuir métodos futuros sem
ficar elegível para agir agora.

A tradução fica no fragmento do agente, nunca no Contrato de Arco. Isso permite
que Kurobane e Shizune sirvam à mesma linha estratégica de maneiras diferentes
sem duplicar seus comportamentos no orquestrador.

## 7. Orçamento

Contrato: `baseline/mundo-vivo-integracao-orcamento.yaml`.

Invariantes:

- zero scan de recompensas/NPCs por turno comum;
- abertura de cena é a porta preferencial única para gatilhos reativos ao vivo;
- descoberta contextual é somente por tags explícitas, sem scan semântico;
- no máximo 8 tags e 4 candidatos contextuais agregados (2 presença / 2 operação / 1 direção);
- presença antagonista é filtrada por arco + marco de aparição + nível antes do índice de agentes;
- operação contextual para no Contrato de Arco e não escolhe executor;
- direção contextual exige direção habilitada + ativa e não avança marco;
- combinação máxima abre até 9 fontes compactas e 0 fragmentos;
- candidato contextual não é cânone e candidato fora do arco não é exposto;
- no máximo 12 referências de NPC por abertura;
- identidades e bindings contextuais são validados antes de qualquer mutação;
- encontros simultâneos são ordenados por ID canônico;
- cena só com local não lê oportunidades/tempo;
- NPC sem perfil não lê tempo;
- gate de side quest somente no início de encontro elegível;
- ID exato de perfil não abre o índice canônico de relações;
- alias/typo abre no máximo oportunidades + índice de relações, nunca fragmento;
- ficha `nada` abre zero perfis;
- ficha `oportunidade` abre no máximo um perfil;
- mapa existente nunca relê tabelas nem rerrola;
- mapa novo é gerado uma vez;
- no máximo um fragmento dirigido por decisão;
- tradução de linha por agente abre no máximo 1 fragmento e 4 métodos;
- executor recusado para linha não abre índice nem fragmento de agente;
- método operacional é repertório e não cria ação/cânone;
- lifecycle de checkpoint expõe zero fragmentos narrativos;
- turno comum continua com duas escritas.

Regressões específicas:

- `tests/fixtures/mundo-vivo/integracao-v1.yaml`;
- `tests/test_cena_mundo.py`;
- `tests/test_contexto_cena.py`.

## 8. Contrato de Arco acima do Mundo Vivo

A descoberta contextual e os schedulers não possuem autoridade para contornar a
parte corrente da crônica. `ferramentas/arco_mundo.py` centraliza o guardrail:

- agente estratégico controlado pelo arco precisa estar habilitado;
- reavaliação/evento também exige ao menos uma linha operacional do arco, salvo o agente do plano mestre;
- movimento/presença exigem habilitação, mas não linha;
- aliado/direção não listados não geram avaliação;
- evento mundial continua existindo quando um candidato é bloqueado;
- pendência antiga incompatível é removida como **avaliação cancelada**, nunca como fato desfeito;
- fronteira temporal não interrompe a intenção por peça que o arco não permite processar.

Agentes não controlados pelo arco continuam usando as regras normais do Mundo Vivo.
O guardrail roda em checkpoint/evento/fronteira, não em turno comum, e expõe zero
fragmentos narrativos.


## 9. Entradas contextuais de aliados

Aliados futuros usam o mesmo princípio de descoberta inversa, mas **reutilizam**
`narrador/entradas/index.yaml` e `narrador/entradas/estado.yaml`; não existe uma
segunda fila nem uma segunda ordem de aparição.

Fluxo:

```text
arco habilita aliado
→ aliado é o candidato em foco da ordem (ou antecipado explicitamente)
→ cadência já abriu a janela contextual
→ nível mínimo permite (salvo antecipação explícita)
→ tags fortes da cena combinam
→ avaliar entrada orgânica
```

A cadência não cria mais `avaliar_entrada` como pendência bloqueante. Ao vencer,
`entradas.py process_checkpoint` torna `proxima_avaliacao: null` para o candidato
em foco e registra `abrir_janela_contextual`; isso significa **disponível para uma
cena adequada**, não "aparecer agora". A fronteira temporal ainda pode parar no
instante em que a janela abre, mas, depois do checkpoint, não existe pendência do
Mundo Vivo obrigando uma aparição.

`contexto_cena.py` expõe no máximo 1 candidato do tipo `entrada`. A pré-seleção
abre somente Contrato de Arco + índice/estado de entradas + nível do runtime; o
fragmento `narrador/entradas/<aliado>.yaml` só entra depois de a cena já ter
produzido candidato concreto.

Bindings iniciais usam apenas sinais fortes derivados das fontes já existentes:

- Shen: `pressao_shizune`, `ferimento_grave`, `anomalia_ponte`,
  `ordem_falsa_oriental`;
- Jōen: `derrota_grave`, `limite_getsuei_ryu`, `meihua_rastro_mestre`.

Shen continuar latente bloqueia Jōen pela ordem preferencial, mesmo que uma cena
combine com Jōen. Confirmar Shen faz a camada de entradas promover Jōen ao foco
normal e agendar sua futura janela. `entrada` contextual continua sendo somente
**obrigação de avaliar**, nunca confirmação de presença.

Consulta barata:

```bash
python3 ferramentas/aliados_contextuais.py status
python3 ferramentas/aliados_contextuais.py gate shen_meihua
```
