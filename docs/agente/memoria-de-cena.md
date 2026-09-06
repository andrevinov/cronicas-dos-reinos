# Memória na preparação e na retomada — NV-05

## Escopo e autoridade

`cronica preparar` reúne a memória dos participantes efetivos, sobre as fontes
existentes e seus deltas pendentes. `cronica sessao status`, `cronica sessao iniciar`,
`retomada_cronica.current_snapshot` e `contexto.py retomada` entregam a mesma
projeção completa. Não há avaliador de IA, scheduler, varredura de todos os NPCs,
novo banco de memórias ou terceira chamada ritual.

A NV-03 continua classificando campos e oferecendo aprofundamento dirigido; a
NV-04 continua registrando acontecimentos anotados. O pacote distingue dados de
cada NPC e compartilha compromissos uma única vez. Informação atribuída a alguém
não passa automaticamente a Ren nem aos demais participantes. Paletas e papéis
conversacionais continuam sugestões interpretativas, não fatos novos.

## Declarar participantes sem fabricar encontros

Na primeira preparação de uma cena, ou quando o elenco mudar, o narrador declara
os NPCs cuja participação **já foi estabelecida na ficção**:

```sh
poetry run cronica preparar --cena-id conversa-no-circo \
  --sem-oportunidade-sidequest --participante silva_elkwood
```

Repetir `--participante` fornece o elenco completo, substituindo o anterior.
`--sem-participantes` declara uma cena sem NPCs. O jogador não executa esses
comandos; continuam sendo parte do trabalho do narrador.

Sem essas flags, a mesma `cena-id`, no mesmo local, recupera o elenco salvo.
Os `--npc` de um gatilho real também podem acrescentar participantes conhecidos;
`--participante` é diferente: só informa memória, **não abre um encontro**, não
cria stub, não avalia presença incidental e não acorda sidequest.

Uma pessoa apenas mencionada em tags, resumos, relações, promessas ou planos não
entra no elenco por inferência. Nomes e aliases precisam resolver inequivocamente
nos índices existentes. NPC ainda não registrado recebe lacuna explícita, não
biografia inventada. O limite é seis NPCs; Ren não entra nessa lista.

O estado legado pode não possuir elenco estruturado. Nesse caso o pacote informa
`participantes: null` e `aprofundamento_necessario: true`. Não há migração inventando
quem estava presente. A próxima declaração factual pelo narrador estabelece o
registro prospectivamente. Uma lista vazia é diferente de elenco desconhecido.

## Persistência e mudanças durante o turno

O preparo é read-only. Seu ticket guarda apenas o elenco, o elenco anterior e o
local de origem, nunca a memória completa. No `cronica concluir`, a mudança de
elenco é compilada para um delta comum de `estado_narrativo.elenco_cena`, antes dos
writers e da captura NV-04. O mesmo buffer, histórico e checkpoint mantêm a única
fonte canônica. Sem mudança, não há delta extra; repetir a transação não duplica
nem ressuscita um elenco antigo.

Cena nova, entrada em local ou trânsito não herdam automaticamente o elenco.
Deslocamento narrado que altera área/ponto exato invalida a presença anterior.
Quando a própria narração estabelece quem chegou/saiu/seguiu junto, o concluir
pode transportar um único `set` operacional do registro completo, coerente com
a localização resultante do mesmo turno:

```json
{"alvo":"estado","op":"set","caminho":"estado_narrativo.elenco_cena",
 "valor":{"versao":1,"cena_id":"conversa-no-circo",
          "local":{"area":"Circo","ponto_exato":"junto à carroça"},
          "participantes":["silva_elkwood"]}}
```

Os nomes de local acima são exemplos, não alterações da campanha. A lista final
exige IDs existentes; não se aceitam subcampos concorrentes ou registro apontando
para outra cena/local. `valor: null` registra ausência de elenco conhecido.
Ticket com elenco usa a conclusão unificada; um reparo repete o mesmo concluir,
não separa confirmar/registrar.

## Reutilização depende do contexto, não de um arquivo

O padrão é `modo: completa`. O pacote inclui `recibo` com versão, escopo e digests
dos itens efetivamente entregues. A preparação seguinte pode receber
`--memoria-base-em-contexto '<JSON exato de recibo>'` **somente quando todos aqueles
itens ainda estiverem disponíveis no contexto ativo do narrador**.

Com essa declaração, `modo: delta` contém somente substituições integrais dos
itens alterados e uma lista `removidos`. Aplicar as substituições sobre a base,
remover as chaves indicadas e guardar o novo recibo. `base` identifica o digest
do recibo anterior. O escopo inclui versão, sessão, cena e local; mudança de
escopo devolve o pacote completo. Digests representam a projeção selecionada,
não o arquivo inteiro nem a presença presumida da informação na IA.

Depois de compactação/perda do contexto, **omitir o recibo**, mesmo que haja um
cache no disco. A retomada não aceita recibo e sempre entrega memória completa.
A ferramenta não consegue verificar a janela interna de uma IA: a declaração é
responsabilidade de seu chamador. Não se trata de comprovação de cache nativo de
provedor. Não há cache persistente; a memoização de leituras dura uma chamada.

## Orçamento e lacunas

Há um teto conjunto de **4 KiB** para a memória, não um teto por NPC. Cabe dentro
do envelope existente: 8 KiB no preparar comum e na retomada, ou dos limites já
existentes dos fluxos de sidequest/pressão. Ticket, instruções e política de
acesso entram na medição do envelope; nenhum desses limites é aumentado.

Os índices são lidos uma vez por montagem e só os fragmentos dos participantes
são abertos. Estado efetivo precede seleção; compromissos são classificados com
a hora efetiva sem serem executados. Dados, vínculo, informações e marcos têm
precedência sobre orientações interpretativas longas. Fatos indivisíveis não são
cortados no meio; ausência de espaço produz `aprofundamento_necessario`, ponteiro
do campo e consulta dirigida. Ausência de um domínio é identificada separadamente.
O pacote não afirma que essa classificação estrutural compreende toda a cena.

O narrador não repete `contexto.py npc` quando o pacote já resolve a interação.
Quando um campo indispensável faltar, usa a consulta NV-03 indicada, sem busca
ampla. Um envelope impossível falha explicitamente; não elimina silenciosamente
a memória para aparentar que o orçamento foi cumprido.

## Evidência e limites

Testes isolados cobrem o preparo, o registro NV-04, pendências antes do checkpoint,
retomada em outro processo, aliases, ausência de transferência de conhecimento,
repetição, mudança de cena/local, recibos e orçamento agregado. As entradas são
fixtures sintéticas; não constituem novos episódios produzidos por uma IA.

A economia esperada vem da supressão de consultas separadas e retransmissões
redundantes. Estado/índices e metadados de elenco têm custo explícito; nenhuma
redução de tokens nativos ou melhoria literária é declarada sem o benchmark de
episódios equivalentes da NV-02. Os dados da campanha não são fixtures desses
testes e não são alterados para instalar esta funcionalidade.
