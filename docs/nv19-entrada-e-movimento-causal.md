# NV-19 — Entrada e movimento causal de personagens

## Objetivo

A NV-19 permite que um personagem já conhecido pelo sistema chegue a um local por causa própria sem transformar o cadastro de NPCs em urna de cameos. A autoridade continua sendo o plano de personagem da NV-08 e a agenda do Mundo Vivo. Não existe scheduler, fila ou estado ficcional paralelo.

Uma entrada é sempre consequência de um plano `entrada_local`. A permanência espacial apenas pergunta se há uma entrada já vencida dirigida ao local atual e projeta no máximo uma. Ela nunca procura personagens no catálogo.

## Contrato `entrada_local`

`entrada_local` é um passo especializado de um plano existente. O registro continua usando `plano:<id>` e o lifecycle `definir -> tentar -> resolver`, mas o passo acrescenta:

```yaml
entrada_local:
  causa:
    arquivo: estado/ou/narrador/fonte.yaml
    caminho: fato.dirigido
    valor: <fato esperado>
  origem: <local canônico>
  destino: <local canônico>
  janela:
    inicio: {data: <Harptos>, hora: HH:MM}
    fim: {data: <Harptos>, hora: HH:MM}
  duracao_esperada_minutos: <permanência esperada após a chegada>
  conhecimento_necessario: [<ids>]
  disponibilidade:
    arquivo: <fonte canônica>
    caminho: <campo booleano>
    valor: true
  recursos_necessarios:
    - {caminho: recursos.<id>, quantidade: <n>}
  motivo_presenca: <por que o personagem vai estar ali>
```

O passo genérico mantém `em`, `duracao_minutos`, `local`, `conhecimento`, `recursos` e `resolucao`. A NV-19 exige consistência entre as duas camadas:

- `local == entrada_local.destino`;
- `conhecimento == conhecimento_necessario`;
- `recursos == recursos_necessarios`;
- resolução `factual.sem_oposicao` usa exatamente a referência de `disponibilidade`;
- `duracao_minutos` é o deslocamento e precisa fazer a chegada cair dentro da janela;
- `duracao_esperada_minutos` é quanto a presença resultante permanece causalmente válida;
- origem e destino precisam ser distintos.

A causa precisa ser uma referência canônica dirigida. Ela pode ser um fato produzido por agenda, outro plano ou evento causal, mas não pode ser inferida do mero cadastro do personagem.

## Lifecycle e atomicidade

### Definição

`definir` registra somente intenção. Não move o personagem e não cria presença.

### Início do deslocamento

`tentar` só passa quando:

- a origem ainda contém presença física válida do ator;
- a janela ainda permite chegar;
- causa, disponibilidade, condições, conhecimento e recursos continuam válidos;
- o plano continua coerente com a intenção canônica do ator;
- regras de arco/adversário continuam permitindo esse caminho.

A mesma transação que registra `tentar` precisa substituir `npc:<id>.presenca` por uma presença `em_deslocamento` com origem, destino, plano, início e chegada prevista. Recursos do passo são consumidos pelo mecanismo NV-08 já existente na mesma transação.

### Chegada

Quando o prazo da tentativa vence, a pendência do próprio plano reaparece. `resolver` só materializa uma entrada com `resultado: sucesso` e `seguimento: concluir`. Na mesma transação, `npc:<id>.presenca` passa para o destino, com `chegou_em`, `motivo_presenca`, `plano_entrada` e `expira_em`.

A prova factual do resultado é o próprio valor de `npc.presenca` produzido pelo lote. Assim, passagem do tempo ou prosa não concedem chegada.

### Adiamento

Antes do deslocamento, `bloquear` pode reagendar a entrada para um instante futuro. Isso não altera presença e não conclui o plano. Depois que o deslocamento começou, omitir a resolução mantém a chegada pendente: a tentativa não é apagada nem convertida em no-op.

## Permanência espacial

`permanencia_espacial.prepare` consulta entradas somente quando o estado do Mundo Vivo possui planos `entrada_local`. A consulta:

1. abre o controle compacto de planos;
2. filtra por `destino == local atual` e por pendência já aberta;
3. ordena deterministicamente por instante vencido + ID;
4. abre perfil/estado apenas do candidato escolhido;
5. retorna no máximo uma `entrada_causal`.

A projeção não entra no recibo aleatório/espacial da NV-15 e não rerrola nada. Ela é observabilidade de uma causa já existente.

A porta `cronica` expõe a mesma entrada em `ids.entradas_contextuais`, em um gate `entrada_local` e em `entrada_local`. O efeito continua sendo materializado pelo lote do Mundo Vivo, nunca pelo preparo da cena.

## Cadastro não cria cameo

Nenhum caminho NV-19 lê `estado/npcs/index.yaml` ou `narrador/agentes/index.yaml` para escolher quem pode aparecer. O índice de NPC é aberto apenas depois que um plano dirigido já selecionou seu próprio ator, para localizar o fragmento transacional daquele ator.

A presença incidental da NV-15 não muda: continua limitada às rotinas e vínculos já ancorados. NV-19 é a via explícita para uma entrada nova causada por agenda/plano/evento.

## Emissários

Emissários não ganham subsistema. Um mensageiro que precisa se deslocar recebe o mesmo plano `entrada_local`; quando sua presença causal chega ao destino, `contatos_sociais` consulta a mesma função `presence_at`. O contato continua responsável pela mensagem, pelo canal e pela memória; NV-19 responde apenas pelo movimento/presença.

## Expiração e movimento posterior

A presença materializada contém `expira_em`. `effective_presence` e `presence_at` tratam a presença como expirada após esse instante sem destruir o registro bruto da chegada. O rastro canônico continua auditável e um plano posterior pode substituir a presença por outro movimento.

Essa expiração derivada evita um segundo scheduler apenas para remover presença. Ela também impede que contato/mensageiro use presença causal já vencida.

## Economia

- máximo existente de 8 planos ativos; nenhum teto foi ampliado;
- no máximo uma entrada local projetada por permanência;
- nenhum scan da população cadastrada;
- somente planos com destino igual ao local atual entram na seleção;
- somente o ator selecionado abre perfil e estado NPC;
- nenhuma chamada de IA ou RNG;
- nenhuma nova fila ou scheduler;
- agenda e pendência do plano NV-08 continuam autoritativas;
- movimento/presença e evento do plano viajam no mesmo registro transacional;
- replay continua usando fingerprint e journal existentes.

## Compatibilidade e segurança

Planos sem `entrada_local` seguem o código NV-18 congelado byte a byte em `_planos_personagens_nv18.py`. `planos_personagens.py` executa essa implementação no mesmo namespace e só especializa o novo tipo.

A NV-19 não contorna agentes adversariais protegidos pelo arco, não decide por Ren, não cria NPC, não inventa conhecimento, não presume disponibilidade e não transforma chegada prevista em chegada realizada.

## Limitação deliberada

A NV-19 movimenta o **estado NPC transacional** (`estado/npcs/<id>.yaml`), porque é a autoridade que pode participar atomicamente do journal. Fragmentos estratégicos reservados continuam descrevendo intenção/capacidade e não são reescritos como efeito colateral de uma chegada. Um agente estratégico controlado pelo arco continua sujeito aos gates existentes e não pode usar `entrada_local` para furar operação, presença protegida ou marco narrativo.
