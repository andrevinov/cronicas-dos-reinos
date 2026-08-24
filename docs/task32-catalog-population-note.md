# Task 32 → Task 33 — nota de compatibilidade

A Task 32 foi entregue com `sidequests_canonicas.por_npc` vazio deliberadamente para separar engine de conteúdo. Ao popular 36 quests na Task 33, manter todas as refs inline faria `narrador/oportunidades/index.yaml` ultrapassar o orçamento quente já congelado.

A solução final preserva o motor da Task 32 e fragmenta apenas o armazenamento das refs em `narrador/sidequests-canonicas/roteadores/<npc_id>.yaml`. O índice quente declara `roteamento: fragmentado_por_npc_task33`; cada NPC catalogado abre no máximo seu próprio roteador dirigido, e NPC fora do catálogo não ganha leitura Task 33.

O engine original da Task 32 permanece preservado como core e continua aceitando o formato inline nos fixtures de compatibilidade. Os testes sintéticos anteriores seguem executados em `tests/sidequests_canonicas_task32_cases.py`; `tests/test_sidequests_canonicas.py` atualiza somente os contratos do repositório real que mudaram com a população/fragmentação.

Nenhum detalhe de quest é reproduzido nesta nota.
