# Task 25 — Harden Operational Contracts

## Problema observado

Os rollouts pós-refatoração mostraram que o hot path já estava barato quando os
contratos eram seguidos, mas pequenas divergências de representação ainda podiam
criar retries desnecessários:

- copiar `ticket_id` no lugar do `ticket` completo;
- usar uma data inequívoca como `1372-08-17` ou `17/08/1372` e cair no parser
  estrito de Harptos;
- usar `--tag` para uma flag cujo nome canônico é `--contexto-tag`;
- chamar `poetry run rolar-dados` embora o Poetry já possuísse a forma instalada
  e estável `poetry run dados`.

A Task 25 corrige essas bordas sem alterar qualquer regra narrativa ou mecânica.

## Tickets

O ticket continua autocontido, comprimido, assinado e validado por checksum.
Whitespace acidental no corpo base64 continua tolerado; corrupção real continua
falhando.

`ticket_id` permanece somente como checksum/identificador diagnóstico. Ele não
contém informação suficiente para reconstruir o ticket. Se for fornecido em
`--ticket`, a CLI agora falha com instrução autoritativa para reutilizar exatamente
o campo `ticket:` completo da saída de `cronica preparar`, em vez do erro genérico
de prefixo que incentivava `--help` e leitura de implementação.

O `contrato_conclusao.disciplina` também explicita preventivamente essa distinção.

## Datas operacionais

O formato persistido continua sendo Harptos canônico, por exemplo:

```text
17 Eleasis, 1372 DR
```

Na borda operacional são aceitos aliases inequívocos:

```text
17 Eleasis 1372 DR
17 eleasis 1372
1372-08-17
17/08/1372
17-08-1372
```

Nos formatos numéricos, o número do mês é o índice do mês de Harptos; portanto
`08 = Eleasis`. Isso **não** cria calendário gregoriano dentro da campanha.
Entradas vagas como “amanhã de manhã” não são adivinhadas.

`cronica preparar --data ... --hora ...` usa essa normalização. Para compressão
de tempo, a porta tolerante é executada pelo Python que já existe no ambiente do
Poetry, sem exigir reinstalação do projeto:

```bash
poetry run python ferramentas/fronteira_operacional.py --data '1372-08-17' --hora 06:00
```

Ela normaliza a data e delega ao mesmo endpoint `mundo.fronteira` já existente.
`endpoints.py fronteira` permanece disponível como primitiva/fallback estrito.

## Tags contextuais

O nome canônico permanece:

```text
--contexto-tag
```

`cronica preparar` aceita também `--tag` como alias de compatibilidade. Ambos
alimentam exatamente o mesmo `contexto_tag`, portanto namespace, validação,
ordenamento e semântica da Task 8 continuam iguais. Nenhuma nova classe de tag é
criada.

## Rolagens

A forma autoritativa passa a ser exatamente a que já está instalada no `.venv`:

```text
poetry run dados
poetry run dados-lote
```

Esses wrappers continuam executando `rolar-dados.py` e `rolar-lote.py`; não existe
segundo motor de RNG e nenhum `poetry install` adicional é necessário para a Task 25.

## Custo e escopo

Contrato: `baseline/harden-operational-contracts-orcamento.yaml`.

- zero chamada operacional extra no turno livre;
- zero endpoint novo;
- zero scheduler/estado/scan;
- aliases aceitos são resolvidos na borda antes das mesmas autoridades existentes;
- nenhuma redução de custo é inventada sem novo rollout.

A finalidade é remover retries, `--help`, leitura de código e tentativas de sintaxe
alternativa — não mudar a frequência ou o conteúdo de qualquer sistema narrativo.
