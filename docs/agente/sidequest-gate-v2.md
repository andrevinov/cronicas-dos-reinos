# Side Quest Gate v2

A Task 14 mantém side quests raras e reativas, mas deixa o gate sensível à
`Adventure Drought Pressure` da Task 13.

A pressão nunca cria missão. Ela só pode transformar a **ficha-base já sorteada**
`nada` em `oportunidade` quando Ren já está em um encontro elegível com um NPC.
`oportunidade` continua significando somente `avaliar_sidequest`.

## Baralho-base preservado

O catálogo continua exatamente:

```text
8 × nada
2 × oportunidade
```

A ordem continua sendo o mesmo baralho SHA-256 sem reposição e a seed existente
não muda. A Task 14 não reinicializa `narrador/oportunidades/estado.yaml`, não
reordena `restantes` e não infere seca retroativa.

## Pressão

Somente quando a ficha-base é `nada`, o gate consulta a pressão da Task 13.

A quantidade de fichas `nada` promovíveis por ciclo é:

| nível | pressão | `nada` promovíveis | oportunidades efetivas máximas / 10 |
| ---: | --- | ---: | ---: |
| 0 | normal | 0 | 2 |
| 1 | leve | 1 | 3 |
| 2 | alta | 2 | 4 |
| 3 | crítica | 3 | 5 |

As fichas promovíveis são escolhidas deterministicamente por SHA-256 da seed do
gate + identidade da ficha. Os conjuntos são prefixos: subir a pressão só amplia
o conjunto; nunca troca uma ficha promovida por outra.

Mesmo em nível crítico, metade do ciclo continua sendo `nada`. Sidequest continua
rara porque o gate só roda em encontro elegível e ainda respeita orçamento,
cooldown, necessidade disponível e avaliação canônica posterior.

## Ordem dos bloqueios

A pressão não é sequer consultada enquanto uma destas travas já resolver o encontro:

1. NPC sem perfil ativo;
2. encontro já processado;
3. pendência de avaliação aberta;
4. limite de sidequests ativas;
5. limite de sidequests em aberto;
6. cooldown global de oferta.

Depois disso o sistema consome **uma única ficha-base**. Se ela já for
`oportunidade`, a pressão também não é lida porque não pode alterar o resultado.
Somente `nada` chega à consulta de pressão.

## Potencial continua não sendo oferta

Uma promoção produz, no máximo:

```text
nada (base)
  ↓ pressão
avaliar_sidequest
  ↓ avaliação explícita contra o cânone
oferecer OU descartar
  ↓ decisão de Ren, se oferecida
aceitar / adiar / recusar
```

Pressão não pode:

- inventar necessidade do NPC;
- criar NPC nomeado;
- criar combate;
- criar recompensa;
- criar pista ou segredo;
- furar cooldown ou limites globais;
- oferecer automaticamente;
- aceitar automaticamente;
- rerrolar uma ficha ou necessidade descartada.

## Proveniência

A resposta do gate v2 carrega `gate_v2` com:

- versão;
- ficha-base;
- resultado-base;
- resultado efetivo;
- se houve promoção;
- pressão usada, quando consultada.

Quando a pressão foi decisiva, o encontro retorna
`motivo: gate_v2_promovido_por_pressao`; oportunidade-base usa
`gate_oportunidade_base`. A pendência continua com o schema v1 existente: a
proveniência operacional não cria um novo fato canônico dentro da missão.

## Integração sem duplicação

O hot path continua sendo:

```bash
python3 ferramentas/endpoints.py cena ...
```

`cena_mundo.py` continua baseado em `cena_mundo_v4`. Ele apenas instala o
adaptador v2 na porta dirigida de encontro. O adaptador intercepta temporariamente
`oportunidades.draw_gate`, chama o **mesmo** `interacoes_mundo.encounter_event`
existente e restaura o sorteador em `finally`.

Assim, bloqueios, resolução de NPC, abertura de perfil, escolha de necessidade,
persistência e orçamento continuam com uma única implementação. A Task 14 não
cria `cena_mundo_v5` nem uma segunda orquestração de encontros.

A CLI de manutenção explicitamente v2 é:

```bash
python3 ferramentas/sidequest_gate_v2.py encontro <npc> --encontro-id <id>
python3 ferramentas/sidequest_gate_v2.py check
```

## Hot path e custo

A consulta de pressão lê somente `narrador/microeventos-locais/estado.yaml` e é
cacheada por versão do arquivo durante o processo. Em fixtures antigos sem a
camada inteira de microeventos, o nível efetivo é zero. Configuração parcial
falha fechada.

Não há scheduler, scan global, reroll ou escrita adicional. A única escrita do
encontro continua sendo o mesmo `narrador/oportunidades/estado.yaml` já usado
pelo v1. A fonte de pressão entra em `fontes_lidas`, logo também participa do
fingerprint transacional da preparação de cena.

Contrato de regressão: `baseline/sidequest-gate-v2-orcamento.yaml`.
