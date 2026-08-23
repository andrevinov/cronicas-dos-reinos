# Task 18 — Reward Budget v2

Reward Budget v2 governa somente **novos mapas procedurais**. Todo mapa já persistido continua imutável e é reutilizado byte a byte; a task não reequilibra retrospectivamente recompensas já materializadas.

## Quatro eixos

A v2 combina quatro restrições independentes:

1. **Local** — a família ecológica limita categorias plausíveis e o teto-base de valor.
2. **Tier** — fornece os pontos-base do orçamento e o máximo de slots.
3. **Risco** — adiciona pontos e, em `alta|letal`, pode elevar em um nível o teto de valor do local.
4. **Importância** — itens `especial` custam mais pontos que itens `comum`; `arco` continua proibido para procedural.

O custo de um item é `custo_valor + custo_importancia`. A seleção é um ranking SHA-256 único sobre os candidatos plausíveis; itens que não cabem no saldo não são rerrolados. O algoritmo percorre a ordem determinística e encerra quando não existe candidato novo que caiba no orçamento.

## Plausibilidade espacial

A ecologia já carregada pela cena fornece `familia`. O perfil v2 da família define categorias permitidas, modificador de pontos e teto-base de valor. O `check` frio exige perfil explícito para toda família ecológica canônica do repositório e falha se uma nova família real ficar descoberta. Ecologias sintéticas de fixtures antigas podem continuar no gerador v1 para preservar regressões legadas.

## Compatibilidade

Fixtures antigas sem a camada ecológica continuam exercitando o gerador v1. Produção usa v2 para qualquer novo local canônico com ecologia. Mapas v1 existentes permanecem válidos e nunca são regenerados.

Recompensas planejadas (`quest`, `direcao_canonica`, `autoral`) continuam separadas do orçamento procedural. Elas ainda respeitam o teto total do mapa e a regra de que existir não significa ter sido encontrada.

## Custo

As regras v2 ficam em `narrador/recompensas/tabelas.yaml`, que já é lido somente na criação inicial do mapa. Quando a cena já trouxe a ecologia, a v2 adiciona **zero fontes**. Uma chamada direta de geração pode abrir `cenario/locais/ecologia.yaml` uma única vez. Consulta de mapa existente continua lendo somente índice + mapa.
