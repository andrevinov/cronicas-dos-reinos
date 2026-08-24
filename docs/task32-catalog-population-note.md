# Task 32 → Task 33 — nota de compatibilidade

A Task 32 foi entregue com `sidequests_canonicas.por_npc` vazio deliberadamente para separar engine de conteúdo. A Task 33 popula o mesmo roteador e os mesmos schemas, sem criar versão paralela do motor.

Testes sintéticos da Task 32 continuam preservados em `tests/sidequests_canonicas_task32_cases.py`; o wrapper público `tests/test_sidequests_canonicas.py` atualiza apenas os contratos de repositório que necessariamente mudaram quando o catálogo deixou de ser vazio.

Nenhum detalhe de quest é reproduzido nesta nota.
