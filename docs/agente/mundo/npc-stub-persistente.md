# Stub persistente automático de NPC

Esta camada resolve uma lacuna específica da abertura reativa: um personagem pode nascer na ficção com **nome próprio e possibilidade clara de reaparecer** antes de possuir relação, medidores, agenda, perfil de side quest ou agente do Mundo Vivo.

## Regra

Um NPC novo e nomeado recebe somente uma identidade canônica mínima:

```yaml
npc:
  nome: Tomas
  persistencia: persistente_sem_agenda
```

Isso significa apenas: **é a mesma pessoa se voltar a aparecer**.

Não significa:

- agente estratégico;
- agente leve;
- scheduler;
- quest giver;
- relação relevante com Ren;
- medidores sociais;
- presença automática em cenas futuras.

Qualquer promoção continua explícita e separada.

## Integração com a cena transacional

`cena_mundo.py preparar` continua read-only. Quando uma referência de NPC não existe, a porta tenta tratá-la como identidade nova somente se ela parecer um **nome próprio reutilizável e inequívoco**.

Exemplo:

```text
Tomas -> proposta determinística de npc_id: tomas
```

A preparação retorna o stub proposto, mas não escreve `estado/npcs/`.

Somente `cena_mundo.py confirmar`, depois de a cena ter sido aceita e registrada, materializa:

- `estado/npcs/<id>.yaml`;
- entrada mínima em `estado/npcs/index.yaml`;
- `historico/npcs/<id>.yaml` com a origem da identidade.

A escrita é idempotente. Fragmento e histórico usam bytes determinísticos; o índice é instalado por último, de modo que uma queda intermediária possa ser reparada por retry sem criar outra identidade.

## Homônimos, aliases e typos

A criação automática nunca usa fuzzy matching para escolher uma pessoa.

- alias que resolve para mais de um NPC falha;
- nome novo que colide com identidade existente falha;
- referência muito parecida com identidade conhecida é tratada como possível typo e exige desambiguação;
- um alias já resolvido por relações/perfis é conferido contra stubs existentes para não esconder homônimo posterior;
- o ID estável completo sempre vence a ambiguidade.

Assim, `Sella` não pode escolher arbitrariamente entre `sella_rove`, `velha_sella` ou outro homônimo futuro.

## Figurantes anônimos

Não criar stub para descritores como `guarda`, `mercador`, `homem`, `trabalhadora` etc. A criação automática exige referência com forma de nome próprio. Figurante continua figurante até receber identidade individualizável na ficção.

## Custo

A camada não roda como scheduler e não adiciona leitura ao turno comum.

- NPC já resolvido por ID/nome completo: custo anterior preservado;
- alias conhecido: pode consultar também o índice compacto de NPCs para detectar colisão;
- NPC novo: consulta dirigida aos índices de identidades e só escreve no `confirmar`;
- stub recém-criado não abre perfil de oportunidade e não sorteia side quest.

A classificação inicial `persistente_sem_agenda` deve ser alterada explicitamente se o NPC for promovido no futuro.
