# NV-11 — Sidequests nascidas da vida dos personagens

## Fonte e autoridade

Uma oportunidade pode nascer de uma necessidade, conflito ou impedimento de um
personagem antes de Ren falar com ele. A causa fica declarada no passo do plano
NV-08, que já conserva responsável, objetivo, estado e continuidade. A NV-11 não
varre perfis, não cria scheduler, catálogo de missões, chamada de IA por NPC ou
outro estado persistente.

A declaração não é uma oferta. `cronica preparar` projeta a causa para a Task40;
a Task46 só registra uma missão `oferecida` se o pedido for narrado no mesmo
turno. Aceitar, adiar e recusar continuam no lifecycle de `oportunidades.py`. A
falta de resposta ou a mera existência da necessidade nunca decide por Ren.

## Contrato no plano

O campo opcional `oportunidade_sidequest` pertence ao `passo` NV-08:

```yaml
oportunidade_sidequest:
  versao: 1
  tipo: necessidade # necessidade | conflito | impedimento
  causa:
    arquivo: estado/npcs/escriba_fixture.yaml
    caminho: npc.necessidades.documentos_ameacados
    valor: Os documentos precisam chegar antes que a rota seja fechada.
  situacao: >-
    A entrega documental está presa a uma janela concreta e a rota pode deixar
    de existir antes da chegada.
  motivo_envolver_ren: >-
    A escriba pede a ajuda de Ren porque ele conhece a região e pode escolher se
    quer intervir na rota ameaçada.
  consequencias:
    agir: >-
      A entrega pode alcançar um caminho seguro, sujeita aos riscos e à resolução
      mecânica da tentativa.
    nao_agir: >-
      A rota pode fechar e obrigar a escriba a abandonar a entrega sem que isso
      imponha punição artificial a Ren.
```

A referência deve apontar o estado indexado do próprio responsável. Cada tipo
usa seu domínio: `npc.necessidades.<id>`, `npc.conflitos.<id>` ou
`npc.impedimentos.<id>`. O valor precisa existir e coincidir no registro e em
cada preparo. Um impedimento só fica elegível enquanto o plano estiver
`bloqueado`; intenção de dificuldade futura não basta.

Situação, motivo e consequências são projeções condicionais. `agir` não garante
sucesso, e `nao_agir` não executa efeito. A autoria Task41 precisa preservar o
personagem interessado como `quest_giver`, a situação como premissa do pedido e
a consequência de não agir no contrato de stakes. Recompensas, oposição,
capacidade, conhecimento e resultado continuam nas Tasks43–45 e 50–52.

## Fluxo operacional

Quando a causa se tornou materialmente relevante, usar a porta normal:

```text
poetry run cronica preparar --cena-id <id-estavel> \
  --oportunidade-sidequest --sidequest-plano <plano-id>
```

`--sidequest-plano` substitui os campos manuais `--sidequest-origem-*`,
`--sidequest-ancora-*` e `--sidequest-npc`. Local, periculosidade e tier continuam
os da cena. A saída inclui `causa_personagem`, com interessado, situação, motivo,
consequências possíveis e fonte canônica. O pacote e seu digest entram no mesmo
ticket Task46, sem terceira chamada de orquestração.

Se houver uma oferta narrada, o bloco `sidequest_emergente` do concluir continua
usando os contratos das Tasks41, 43, 44 e 45. A missão nasce `oferecida`. A decisão
posterior usa a porta Task42 existente:

```text
poetry run python ferramentas/canon_bridge_runtime.py responder <missao-id> aceitar
poetry run python ferramentas/canon_bridge_runtime.py responder <missao-id> recusar
```

Recusa é terminal para causas NV-11. A missão guarda um recibo causal derivado do
personagem, tipo e referência; uma nova revisão ou outro ID de plano não faz a
mesma necessidade reaparecer. Uma causa materialmente nova precisa de outra
referência canônica. Recusar não agenda consequência, perda ou reação.

Uma missão aceita pode ser abandonada explicitamente:

```text
poetry run python ferramentas/canon_bridge_runtime.py abandonar <missao-id> \
  --motivo '<fato que encerrou a participação>'
```

O estado passa a `abandonada`, sai das missões ativas e libera eventual reserva
Task42. O abandono não conclui objetivo, concede recompensa ou aplica punição. O
mundo pode continuar por acontecimentos canônicos independentes, sujeitos aos
contratos adversariais e aos writers normais.

## Orçamento e regressão

Planos continuam limitados a oito e o passo completo a 2.400 bytes. A projeção
abre apenas o plano indicado, seu NPC e a referência declarada; a única coleção
percorrida é o lifecycle de missões existente para localizar um recibo da mesma
causa. O pacote final conserva o teto Task40 de 8 KiB. Turnos com decisão negativa
mantêm zero leitura da NV-11.

As fixtures de `test_sidequests_personagens.py` cobrem nascimento antes da
conversa, causa de terceiro, impedimento, ticket Task46, preservação autoral,
recusa sem punição/reoferta e abandono depois do aceite. Os testes usam campanha
temporária e não alteram o save vivo.
