# Ecologia de trânsito urbano

## Objetivo

Deslocamentos materiais pela malha urbana de Ravens Bluff podem carregar pequena textura cotidiana sem transformar cada rua em local canônico e sem acrescentar uma terceira chamada ao hot path.

A porta continua sendo:

```bash
poetry run cronica preparar --cena-id <id-estavel> --transito-urbano ravens_bluff
# narrar
poetry run cronica concluir --ticket <ticket>
```

A flag é usada quando o **deslocamento em si** merece um turno curto de trânsito. Ela não deve ser adicionada a toda mudança de localização, teleportes, movimentos interiores ou transições que não ganham presença narrativa própria.

## Mesmo baralho, outro escopo

Não existe um segundo motor de microeventos. `ferramentas/microeventos_transito.py` reutiliza:

- `narrador/microeventos-locais/index.yaml`;
- `narrador/microeventos-locais/estado.yaml`;
- as mesmas fichas de ocorrência 3 `rotina` : 1 `microevento`;
- o mesmo ordenamento SHA-256;
- o mesmo consumo sem reposição;
- o mesmo writer de confirmação.

O escopo `ravens_bluff` vive fora de `locais:` no estado. Portanto `transito_ravens_bluff` nunca vira `local_id`, alias de lugar, mapa de recompensa ou âncora de NPC.

O estado do trânsito é inicializado **somente na primeira confirmação real**. Preparar/simular não modifica o repositório.

## Pressão de Ravens Bluff

As cinco frentes existentes são lidas pela porta oficial `pressao_ravens_bluff`:

- custo de vida;
- ocupação imobiliária;
- crime e milícias;
- desgaste da autoridade;
- presença oriental.

Nível 0 não acrescenta textura específica. Nível 1–4 acrescenta tags/canais ecológicos ao pool elegível. O valor do nível também pode graduar a manifestação narrada, mas **não altera a frequência 3:1**.

Exemplos de tradução de plausibilidade:

- custo de vida → comércio/abastecimento;
- ocupação → residência/vizinhança;
- crime/milícias → segurança;
- desgaste institucional → atendimento/institucional;
- presença oriental → carga.

Essa tradução não prova a causa. Um atraso, checagem, carga ou movimentação de rua pode possuir explicações banais; Ren não aprende automaticamente que Masao está por trás da pressão.

O trânsito é estritamente consumidor da pressão: **nunca chama avanço, nunca escreve o estado das frentes e nunca transforma passagem de tempo em nível novo**.

## Semântica da carta

`avaliar_microevento` continua significando somente obrigação de considerar uma perturbação curta e plausível.

A carta não cria automaticamente:

- NPC nomeado;
- combate ou dano;
- crime grave;
- side quest;
- recompensa;
- pista ou segredo;
- fato canônico sobre a origem da pressão.

Cânone forte, arco, cena aceita e pendências prevalecem. Se a carta não couber, a manifestação é descartada **sem rerroll de substituição**.

## Por que trânsito e cena reativa não usam o mesmo ticket

O baralho local e o escopo de trânsito compartilham `narrador/microeventos-locais/estado.yaml`. Confirmar um deles muda o fingerprint do arquivo usado pelo outro.

Para não introduzir um journal novo, segundo estado ou protocolo de reparo mais caro, o contrato é simples:

- `--transito-urbano` exige turno sem `--local`, `--npc` e `--contexto-tag`;
- o deslocamento pode terminar diegeticamente no destino;
- entrada/exploração/interação reativa, quando materialmente necessária, acontece no turno seguinte.

Isso preserva atomicidade e mantém a meta de duas chamadas de orquestração por turno.

## Custo

O trânsito abre no máximo quatro fontes já compactas:

1. catálogo compartilhado de microeventos;
2. estado compartilhado do baralho;
3. perfil de pressão de Ravens Bluff;
4. estado de pressão de Ravens Bluff.

Preparação: zero writes. Confirmação: no máximo um write, no arquivo de estado de microeventos já existente. Não há scheduler, scan global, fragmento narrativo, catálogo novo, endpoint novo ou RNG novo.

Contrato congelado: `baseline/urban-transit-ecology-orcamento.yaml`.
