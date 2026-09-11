# NV-20 — Reconhecibilidade de persona e desafios causais

## Objetivo

A NV-20 torna apresentações públicas consequências sociais rastreáveis sem confundir fama de uma persona com reputação pública geral ou com conhecimento da identidade real. O primeiro caso de uso é Kage, mas o contrato é válido para qualquer persona registrada.

A implementação acrescenta duas peças estreitas:

1. um ledger compacto de reconhecibilidade por persona, audiência, localidade e marco público;
2. um tipo especializado de plano `desafio_persona`, executado pelo mesmo motor de planos já existente.

Não existe placar global no runtime, seleção de desafiante, scheduler ou fila novos.

## Ledger de reconhecibilidade

O estado canônico reside em `estado/estado-atual.yaml`, sob `reconhecibilidade_personas`. O ledger é append-only e limitado. Cada evento contém:

- `persona`;
- `audiencia` social já registrada no catálogo de públicos de Ravens Bluff;
- `localidade`;
- `marco_publico`;
- `tipo_marco`;
- `atribuicao` (`rumor`, `provavel`, `direta`);
- `confianca` (`baixa`, `media`, `alta`, `testemunhada`);
- fato público literal e fonte canônica compacta.

O ID do evento é derivado somente de `persona + audiência + localidade + marco`. Assim, repetir o mesmo marco para a mesma audiência não aumenta a fama e não permite trocar confiança/atribuição retroativamente.

### Medida útil sem placar global

`reconhecibilidade_persona.query` exige sempre `persona + audiência + localidade`. A função deriva apenas nessa consulta:

- quantidade de marcos distintos;
- índice dirigido, calculado da confiança e atribuição dos eventos daquela chave;
- nível qualitativo `desconhecida`, `ouvida`, `reconhecivel`, `conhecida` ou `notoria_local`.

Nada disso é projetado no contexto comum de cada turno. O ledger só é aberto quando uma reação/plano depende de reconhecimento ou quando uma consulta explícita é feita.

## Apresentação pública e atomicidade

Uma apresentação pública confirmada usa dois deltas no **mesmo writer**:

1. `consequencia/registrar` com `tipo: apresentacao_publica_confirmada`;
2. `estado/set` do ledger contendo exclusivamente os novos eventos de fama daquele marco.

`transacoes.validate_pending_record` exige pareamento exato entre os dois. Portanto:

- prosa sozinha não gera fama;
- passagem do tempo não gera fama;
- um marco de apresentação não pode ser registrado sem a consequência social correspondente;
- um evento de fama não pode aparecer sem o marco público que o causou.

A consolidação usa o journal multi-arquivo existente. O delta do ledger é um delta normal de `estado`, e `consolidar.py` apenas valida a transição append-only antes do stage e o estado resultante depois dele. Não há segundo writer.

`propose_public_performance` é o helper read-only para montar os dois deltas. Repetir o mesmo marco/audiência retorna `ja_registrado`, sem delta novo.

## Separação Ren / Shinta / Kage

O ledger só armazena a **persona percebida**. Ele não possui campo de identidade real e não lê o estado de suspeita de NPCs para fundir personas.

Um evento atribuído a Kage:

- aumenta somente a reconhecibilidade de `kage` naquela audiência/localidade;
- não altera `ren`;
- não altera `shinta`;
- não confirma que Kage é Ren;
- não converte suspeita em identidade confirmada.

A reputação pública da Task 29 continua sendo outro conceito: reputação mede posição/valência social de feitos públicos; NV-20 mede se uma persona é reconhecível e quão forte é essa atribuição naquele contexto.

## `desafio_persona`

Um desafio é um passo especializado de `planos_personagens`; não é um evento aleatório. O ator é explicitamente o `agente` do plano e precisa existir no sistema de agentes já instalado.

O passo acrescenta:

```yaml
desafio_persona:
  persona: kage
  reconhecimento:
    audiencia: circo_e_artes
    localidade: ravens_bluff
    marco_publico: <marco que causou o interesse>
    confianca_minima: media
    atribuicao_minima: provavel
  motivacao: <referência canônica do próprio ator>
  conhecimento_persona: <id de conhecimento do próprio ator>
  alcance:
    tipo: fisico
    local: <local do passo>
  interesse:
    tipo: marcial
    referencia: <referência canônica do próprio ator>
  stakes:
    descricao: ...
    se_aceito: ...
    se_recusado: ...
  protecoes:
    - <referência booleana que deve permanecer true>
```

Para canal, `alcance` usa `tipo: canal`, `persona` e `referencia`; o passo precisa reutilizar uma resolução `contato` e o mesmo canal. A motivação também é reutilizada como causa do contato.

### Gates obrigatórios

O plano só pode ser criado e continua executável se todos os itens abaixo forem verdadeiros:

1. **ator explícito e ativo** — não há busca por NPC no catálogo;
2. **motivação própria** — referência canônica pertencente ao ator;
3. **conhecimento suficiente da persona** — o conhecimento precisa ser do ator, nomear a persona-alvo e manter evidência literal em sua fonte;
4. **reconhecimento dirigido** — o marco indicado precisa existir para a persona, audiência e localidade com confiança/atribuição mínimas;
5. **alcance** — presença física válida no local ou canal canônico disponível;
6. **interesse marcial/social/misto** — comprovado em fonte do próprio ator;
7. **stakes explícitos** — aceitar e recusar não são inferidos pelo motor;
8. **proteções canônicas** — todas as referências declaradas precisam continuar compatíveis.

Esses gates são verificados na definição/replanejamento e novamente na tentativa/projeção. Um token antigo não congela fama, conhecimento, alcance ou proteção.

## O desafio não resolve o confronto

`desafio_persona` planeja **a abordagem**. O passo aceita somente resolução factual ou `contato`; não transforma um duelo, disputa social ou combate inteiro em um teste simples.

Aceitação, recusa e consequências posteriores continuam dependendo de fatos/decisões explícitos e dos motores apropriados. A NV-20 não decide por Ren/Kage.

## Integração com NV-19

Um evento de fama fornece uma referência canônica para `estado/estado-atual.yaml`. Essa referência pode alimentar `entrada_local.causa` da NV-19.

Assim, um rival pode, de forma causal:

1. conhecer um marco público de Kage;
2. ter motivação e conhecimento próprios;
3. planejar uma entrada local causada por esse marco;
4. chegar pelo lifecycle NV-19;
5. só então planejar/emitir o desafio se os demais gates continuarem válidos.

Nenhuma dessas etapas escolhe um rival aleatoriamente.

## Economia

- máximo de 48 eventos compactos de fama;
- estado total do ledger limitado a 28 KiB;
- no máximo 3 audiências novas por marco no helper de apresentação;
- query sempre dirigida por persona + audiência + localidade;
- projeção de query expõe no máximo 8 eventos recentes da chave;
- nenhum scan de NPCs/agentes para achar desafiante;
- `desafio_persona` abre somente o ator explicitamente definido pelo plano e as fontes dirigidas por seu contrato;
- nenhum RNG;
- nenhuma IA;
- nenhuma fila ou scheduler novo;
- o teto existente de planos continua autoritativo.

## Idempotência e segurança

- ID de fama é determinístico por marco/audiência/localidade/persona;
- eventos existentes são imutáveis;
- ledger é append-only;
- retry transacional continua usando o fingerprint/ledger existente;
- marca pública e fama são pareadas no mesmo writer;
- o mesmo ator não pode manter dois desafios ativos contra a mesma persona;
- reconhecimento não concede conhecimento individual ao NPC: o desafiante precisa possuir conhecimento próprio comprovado;
- fama não confirma identidade real;
- desafio não concede chegada, aceitação, vitória ou consequência sem o motor/fato correspondente.

## Limitações deliberadas

A NV-20 v1 automatiza eventos de reconhecibilidade a partir de `apresentacao_publica_confirmada`. Outros tipos de fama pública podem ser adicionados depois como novos tipos de marco, com contrato próprio; não são inferidos genericamente de qualquer consequência.

Também não existe propagação social automática entre audiências. Se um marco observado pelo circo chegar às redes informais, isso precisa ser outro fato causal explícito, não uma difusão implícita do ledger.
