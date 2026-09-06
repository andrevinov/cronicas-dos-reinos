# NV-09 — Da iniciativa social ao contato efetivo

## O que muda

Um aliado com intenção registrada pode procurar Ren, enviar recado, fazer convite,
pedir ajuda ou retomar assunto importante **sem Ren procurá-lo primeiro**. O passo
pertence ao plano NV-08: definição não é tentativa; envio não é chegada; entrega
não é aceite, cumprimento da necessidade ou sucesso do objetivo maior.

`contatos_sociais.py` conecta o plano ao `iniciativa_social.project` e à prioridade
social de `pressao_narrativa.py`. Não existe scheduler, chamada de IA por NPC,
catálogo paralelo de missões ou arquivo canônico de contatos. O jogador não ganha
uma obrigação por ouvir um pedido. Convivência e convites sem missão são casos
normais. Não há implantação retroativa em personagens nem alteração do save.

## Causa, canal e oportunidade

A causa aponta um fato estabelecido em `npc.necessidades.<id>` do próprio remetente.
O canal vem de `npc.canais_contato.<id>` no mesmo fragmento indexado. São referências
NV-08 completas (`arquivo`, `caminho`, `valor`): ausência, divergência ou fonte fora
do repositório não é permissão. O objetivo continua pertencendo ao perfil existente.

O piloto oferece dois meios: presencial e mensageiro. O remetente precisa conhecer
o canal/destino, com um ID do próprio conhecimento e evidência ainda presente na
fonte; a identidade relacional deve ser Ren, não um alias fundido por conveniência.
Canal e referências declaram a ligação causal: a validação estrutural não interpreta
sozinha a veracidade ou adequação semântica da evidência.

No envio, presença, recursos, condições e conhecimento passam pelos gates NV-08.
Mensageiro exige portador identificado e disponível na origem. A duração mínima
é declarada antes da tentativa; transporte exige tempo positivo. A ferramenta
**não calcula rotas nem executa deslocamento**: uma chegada precisa ser registrada
pelos writers existentes, respeitando as regras de viagem. Tempo transcorrido
sozinho não teletransporta ninguém. Mudanças legítimas continuam acionando a NV-07;
essas pendências causais são resolvidas no lote, não silenciadas pelo contato.

Na entrega, Ren e o interlocutor ou portador precisam estar no destino declarado,
com presença estruturada e sem deslocamento em curso. O remetente de um recado não
precisa continuar na origem e não aparece fisicamente junto do mensageiro.

## Exemplo isolado de passo

Este exemplo não descreve a campanha instalada. Supõe que os fatos referenciados
já existam para `escriba_fixture`, inclusive o conhecimento `endereco_ren` com fonte
e evidência. É o valor de `passo` de um delta `plano:<id>` da NV-08, não um arquivo
novo a preencher automaticamente. `fato` da definição/tentativa também deve estar
na narração correspondente.

```yaml
id: convidar_para_cha
acao: Procurar Ren para convidá-lo a tomar chá.
em: {data: '7 Eleasis, 1372 DR', hora: '08:03'}
duracao_minutos: 5
local: Circo
condicoes: []
recursos: []
conhecimento: [endereco_ren]
resolucao:
  tipo: contato
  modalidade: convite
  mensagem: Venha tomar chá comigo quando tiver um momento.
  causa:
    arquivo: estado/npcs/escriba_fixture.yaml
    caminho: npc.necessidades.companhia
    valor: Deseja companhia para o chá.
  canal:
    arquivo: estado/npcs/escriba_fixture.yaml
    caminho: npc.canais_contato.circo
    valor:
      meio: presencial
      origem: Circo
      destino: Circo
      portador: null
      duracao_minima_minutos: 0
      conhecimento_id: endereco_ren
      disponivel: true
```

Modalidades: `procurar`, `recado`, `convite`, `pedir_ajuda`, `retomar_assunto`.
Para mensageiro, usar `meio: mensageiro`, um `portador` canônico diferente de Ren e
`duracao_minima_minutos` positiva. Seu estado indexado deve provar origem e chegada.

## Fluxo operacional e entrega

1. Registrar intenção no `cronica concluir` pertinente; `tentar` pelo lote da
   fronteira, com custos cobrados uma vez. A agenda da NV-08 guarda o prazo.
2. Depois de tentado e devido, `cronica preparar` reconhece contatos em andamento.
   Outras classes de pendência continuam bloqueantes. Operações comprometidas
   permanecem no ticket com suas decisões obrigatórias e precedência.
3. O preparo escolhe no máximo um contato elegível. Combate, perigo, contrato
   mecânico, ação social solicitada, oportunidade ou outra pressão superior adiam
   sua apresentação. Uma entrega por cena/sessão; os demais contatos permanecem
   pendentes, sem novas avaliações independentes de IA.
4. O retorno `contato_social` traz remetente, meio, portador, mensagem, causa e modo
   social. O concluir decide entrega ou adiamento. Sem escolha explícita, falha
   antes da escrita. O ticket e a revisão conferem os dados novamente.

```yaml
# Bloco dentro da transação normal enviada a cronica concluir:
contato_social:
  plano_id: convite_da_escriba
  resultado: entregue
  evidencia: A escriba se aproximou e fez seu convite.
```

A evidência **e a mensagem inteira** precisam aparecer em `narracao`. O compilador
produz um evento de plano e um registro de conhecimento atribuído ao remetente.
Assim, ouvir uma afirmação não a promove a verdade objetiva. Remetente/portador,
causa, canal e localização são revalidados antes de escrever. O mesmo lote não
pode invalidá-los e ainda entregar com base na versão antiga.

A entrega inclui o interlocutor físico no elenco conhecido; em recados, somente
o portador, nunca o remetente remoto. Não substitui um elenco desconhecido por uma
lista supostamente completa. A NV-05 recupera o elenco/memória persistidos no preparo
seguinte. Nenhuma promessa, aceitação ou missão é criada por esse evento.

```yaml
contato_social:
  plano_id: convite_da_escriba
  resultado: adiado
  evidencia: A conversa presente ainda exigia atenção.
  motivo: Não há oportunidade para interromper essa conversa.
  retomar_em: {data: '7 Eleasis, 1372 DR', hora: '08:20'}
```

Adiamento exige instante futuro e conserva a tentativa; não entrega conhecimento.
Quando nenhuma iniciativa pode entrar, `contatos_adiados` informa o motivo sem
repetir a mensagem. Local errado não paralisa Ren: o plano permanece inteiro, e o
lote de fronteira permite diagnosticar impossibilidade e registrar sua consequência.
Não usar `sem_mudanca` ou sucesso factual para apagar ou entregar esse contato.

## Depois da entrega e recuperação

O plano fica em `aguarda_resposta`, sem pendência ou agendamento de cobrança. Sua
última tentativa registra `contato_entregue` e `resposta_de_ren: nao_presumida`.
Uma conduta posterior usa replanejamento/desistência explícitos da NV-08; a resposta
do jogador e outros fatos continuam nos contratos existentes, incluindo NV-04.

Recibos compactos em `contatos_sociais_entregues`, dentro do **estado do mundo
existente**, impedem repetir a mesma causa, inclusive com outro ID de plano ou
mensagem reformulada. Chaves causais devem permanecer estáveis; uma causa
materialmente nova pode originar outro contato. A deduplicação é estrutural, não
um detector semântico de pedidos equivalentes escritos com novas chaves.

Plano, recibo, conhecimento, elenco, agenda, barreira e ledger são instalados pelo
mesmo journal de consolidação. A conclusão força o checkpoint na mesma chamada.
Interrupção antes do checkpoint bloqueia novo preparo; repetir o mesmo concluir
repara o registro. Journal aberto exige `cronica sessao recuperar` antes de
continuar. Replays consolidados conferem o fingerprint NV-08, não reaplicam custos,
não reenviam mensagens nem restauram presenças antigas. `confirmar` e `registrar`
isolados não aceitam esse ticket integrado.

## Orçamento e alcance da evidência

Sem contato pendente, a extensão não faz leituras nem altera a saída do preparo.
Não varre perfis do mundo: considera somente planos devidos já registrados, até o
limite existente de oito planos. Uma pressão superior evita abrir os aliados. O
preparo é read-only; as fontes dirigidas são revalidadas na conclusão.

Preservados: 4 KiB conjuntos da memória NV-05, 8 KiB do preparo comum e envelopes
anteriores de pressão/sidequest, sem promovê-los por causa de um contato. Projeção
do contato: até 2 KiB. Passo/contexto/controle mantêm os tetos NV-08. Recibos:
até 64 e 12 KiB; exceder falha explicitamente, não descarta a proteção antirrepetição.
O ledger mantém o histórico completo. Não existe terceira chamada ritual de turno.

Os testes usam episódios anotados em diretórios temporários, writers/CLI reais,
recuperação de journal, dois contatos e filas mistas de operações. Medem bytes de
argumentos, ticket e saída; isso não comprova economia de tokens nativos nem melhora
literária em partidas. Essas avaliações continuam dependentes dos episódios NV-02
com uma IA narrando, não apenas de campos estruturados corretos.
