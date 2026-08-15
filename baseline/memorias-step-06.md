# Etapa 6 — baseline estrutural das memórias fragmentadas

A Etapa 6 substituiu três depósitos acumulativos por roteadores, índices e fragmentos dirigidos.

## Antes

- `estado/relacoes.yaml`: 195.826 bytes
- `estado/medidores-npcs.yaml`: 28.689 bytes
- `personagens/jogador/conhecimento.md`: 274.271 bytes
- total dos três depósitos: 498.786 bytes

## Depois

- 34 relações possuem fragmento atual próprio e histórico completo próprio;
- 14 NPCs possuem fragmento de medidores próprio;
- o conhecimento de Ren foi dividido em 90 fragmentos literais;
- 56 blocos explicitamente marcados como Sessão 003 foram indexados separadamente;
- `conhecimento/ativo.yaml` aponta para a Sessão 003, a sessão corrente da campanha;
- os três arquivos antigos de entrada continuam existindo apenas como roteadores pequenos;
- cópias integrais pré-migração permanecem em `historico/legado/` com os blobs Git originais.

## Garantias

`ferramentas/migrar-memorias-fragmentadas.py --check` valida IDs, tamanhos, arquivos atuais, históricos e blobs legados.

`ferramentas/reindexar-conhecimento.py --check` concatena os 90 fragmentos na ordem registrada e exige igualdade byte a byte com o antigo `conhecimento.md`.

`tests/test_memorias_fragmentadas.py` testa também consultas reais de Kethra, Nera e conhecimento da Sessão 003, garantindo que `contexto.py` não reabra os monólitos.

Esta baseline registra arquitetura e contagens, não altera nenhum fato canônico da campanha.
