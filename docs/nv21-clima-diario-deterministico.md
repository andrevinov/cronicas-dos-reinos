# NV-21 — Clima diário determinístico

## Objetivo

A NV-21 faz o clima existir como consequência do relógio do mundo, sem exigir autoria manual e sem transformar cada cena em uma nova rolagem. Na primeira sincronização de checkpoint após uma alvorada ainda não processada, cada região configurada recebe exatamente uma avaliação climática para aquela data.

O primeiro domínio instalado é `ravens_bluff`. A arquitetura permite outras regiões sem introduzir scheduler, fila ou chamada de IA.

## Autoridades

- configuração/decks: `narrador/mundo/clima-diario.yaml`;
- estado diário e candidatos congelados: `estado/clima-diario.yaml`;
- relógio: `estado/tempo.yaml`;
- alvorada: `narrador/mundo/agenda.yaml`;
- condição ambiental ativa: domínio já existente `condicoes_mundo` / `narrador/mundo/condicoes-persistentes.yaml`.

O campo legado livre `estado/tempo.yaml:clima` não é promovido a motor climático. Ele pode continuar existindo como texto histórico/compatível, mas NV-21 usa o estado estruturado acima.

## Deck sazonal auditável

Cada região declara explicitamente a estação de cada mês/festival de Harptos e um deck ordenado por estação. O slot é escolhido por:

`SHA256(semente + região + data + estação) mod tamanho_do_deck`

Não há `random`, `secrets`, RNG externo ou estado de gerador oculto. O registro diário persiste:

- data e região;
- estação;
- estado climático escolhido;
- índice do slot;
- hash da seleção;
- duração;
- intensidade;
- efeitos já congelados;
- fingerprint do resultado.

Os decks iniciais têm 32 slots. Cada estação reserva somente 2 para extremos, sendo 1 para vendaval. Assim tempestade/vendaval são possíveis, mas raros, enquanto chuva e vento comuns ocupam uma fração material do deck.

## Alvorada e idempotência

`checkpoint.sync_world` chama `clima_diario.sync_dawn` depois da sincronização normal do Mundo Vivo.

O estado guarda `avaliado_ate` por região. Uma data já avaliada nunca é sorteada de novo. Repetir checkpoint, recuperar processo ou abrir outra cena apenas reencontra o registro existente.

A instalação da NV-21 começa com Ravens Bluff avaliada até **21 Eleasis, 1372 DR**, o instante corrente da `main` de origem. Isso evita inventar retroativamente clima para uma alvorada já passada; o primeiro sorteio novo acontece a partir da alvorada seguinte.

Se o sistema atravessar dias sem checkpoint, as datas devidas são avaliadas deterministicamente. Resultados já expirados entram somente no histórico compacto; apenas a condição ainda temporalmente ativa é projetada/materializada.

## Estados comuns

Estados não extremos tornam-se ativos automaticamente na alvorada. Chuva pode, portanto, surgir sem nenhuma autoria manual.

Cada estado contém antes da narração:

- descrição ambiental;
- sinais sensoriais;
- multiplicador percentual de tempo de deslocamento;
- marcadores de deslocamento;
- disponibilidade de espaços exteriores/expostos;
- marcadores de incidentes;
- payload da condição persistente.

A duração máxima é inferior a 24 horas para evitar sobreposição acidental de dois resultados diários na alvorada seguinte.

## Extremos

`tempestade` e `vendaval` não se tornam fatos ativos apenas porque o hash os selecionou.

A seleção cria `candidato_extremo` com **todo o resultado já congelado**: intensidade, duração, sensorial, deslocamento, espaços, marcadores e condição persistente. Enquanto esse candidato não for confirmado:

- não há novo sorteio para a região;
- ele não muda em retries;
- ele não vira condição persistente;
- cenas não o tratam como clima ativo.

A confirmação usa `id + fingerprint`:

```bash
python ferramentas/clima_diario.py confirmar-extremo \
  --regiao ravens_bluff \
  --id clima-... \
  --fingerprint ...
```

Uma confirmação repetida do mesmo candidato é idempotente. Fingerprint divergente falha fechado; nunca dispara reroll.

## Condições persistentes

Ao ativar clima comum — ou confirmar um extremo — NV-21 registra `tipo: clima` no mecanismo Task 34 já existente.

A fonte da evidência é o próprio estado canônico `estado/clima-diario.yaml`. O `fato_canonico` diário é curto e literal, permitindo que `condicoes_mundo` mantenha suas regras de proveniência.

A ordem de persistência é deliberadamente recuperável:

1. o resultado climático congelado é escrito no estado canônico;
2. a condição Task 34 é garantida a partir desse registro.

Se o processo cair entre as duas etapas, repetir `sync_dawn` não rerrola: ele repara somente a condição ausente a partir do mesmo resultado. Não foi criado um segundo journal apenas para clima.

## Cenas e descrição sensorial

`permanencia_espacial.prepare` chama somente a leitura `clima_diario.for_scene`. Essa função não abre o deck e não sorteia nada; lê apenas o estado ativo e, quando necessário, o relógio para validar a janela temporal.

A projeção entrega descrição, sinais sensoriais e disponibilidade de espaços antes da prosa. Assim a narração pode refletir chuva, vento, piso molhado ou necessidade de abrigo sem inventar consequências depois do texto.

Fixtures/repositórios sem a configuração NV-21 continuam delegando byte-logicamente às camadas anteriores.

## Deslocamento

`microeventos_transito` continua usando o mesmo deck urbano, estado e writer. A NV-21 apenas acrescenta uma leitura dirigida do clima ativo.

O clima de trânsito é incluído no fingerprint de preparação. Se o estado climático mudar entre `preparar` e `concluir`, o ticket fica obsoleto em vez de narrar com efeitos antigos.

A projeção fornece `tempo_percentual` e marcadores já congelados. Nenhum segundo baralho de trânsito é criado e a frequência 3:1 dos microeventos permanece intocada.

O teto de fontes do trânsito sobe de 4 para 6 apenas para acomodar `estado/clima-diario.yaml` e, quando há estado ativo, `estado/tempo.yaml`. Não há escrita adicional em `preparar`.

## Disponibilidade de espaços

O clima não fecha locais canônicos por adivinhação. Em vez disso, a projeção estruturada distingue:

- `exteriores`;
- `expostos`;
- marcadores como `abrigo_recomendado`, `abrigo_necessario`, `vento_extremo`.

Isso alimenta a decisão de disponibilidade antes da narração sem alterar cadastro de locais ou fabricar geometria.

## Incidentes locais

A Task 35 já aceita condições persistentes como filtro de cartas e converte seus marcadores em tokens de elegibilidade. Como NV-21 materializa o clima no domínio Task 34, essa integração é direta e não cria uma segunda ponte.

Exemplo já existente: a carta `queda_em_piso_molhado` exige `chuva_forte`. Chuva forte/tempestade NV-21 carregam esse marcador; portanto podem tornar a carta elegível sem aumentar a frequência do baralho de incidentes.

## Economia

- uma avaliação pequena por data/região;
- zero IA;
- zero scheduler novo;
- zero fila nova;
- zero scan de população;
- cenas não abrem deck climático;
- seed e slots são auditáveis;
- estado guarda somente ativo, um candidato extremo e histórico curto;
- trânsito reutiliza o fingerprint e writer existentes;
- incidentes reutilizam os tokens de condição existentes.

O orçamento está congelado em `baseline/clima-diario-nv21-orcamento.yaml`.

## Limitações deliberadas

- NV-21 não simula pressão atmosférica, temperatura contínua ou células meteorológicas móveis.
- A região inicial é Ravens Bluff; microclimas de bairro não são inferidos.
- Disponibilidade espacial é classificada por exposição, não por uma lista automática de locais fechados.
- Um extremo exige confirmação explícita; a NV-21 não decide sozinha que uma tempestade candidata virou fato narrativo.
- O sistema não reescreve retroativamente o texto livre de clima legado em `estado/tempo.yaml`.
