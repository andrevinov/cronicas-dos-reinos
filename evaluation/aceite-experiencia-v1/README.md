# Aceite antecipado do avaliador — AMV-14

Natureza: episódios sintéticos isolados e revisão pós-hoc em 2026-10-06.
Não são sessões da campanha nem execução dos módulos de jogo modificados.

O gabarito registra propriedades antes da medição. O pedido entregue ao revisor
contém apenas fontes, critérios e instruções; não contém gabarito, diagnóstico
esperado ou indicação de qual variante é defeituosa. Os comandos e resultados
de execução bem-sucedidos são iguais dentro de cada par, salvo o conteúdo factual
de estado que a propriedade compara.

A revisão semântica é executada pelo agente que avalia a sessão. Replay dos
pareceres congela essa execução para testar o pipeline; não é um leitor semântico
automático nem uma segunda execução independente de julgamento. Autoria de casos
e revisão nesta entrega não constitui validação cega por terceiro. O resultado
publicará divergências, cobertura por propriedade e limites, sem nota global.

`episodios.json` contém entradas nativas; `gabarito.json` fica fora dos pedidos.
Não alterar esses dois arquivos para acompanhar a implementação. Correção de
referência exige versão nova, motivo e preservação da referência anterior.

**Correção explícita da fonte:** `episodios-v2.json` inclui o marcador nativo de
início de turno antes da entrada. A v1 não o incluía e o scanner corretamente
perdia a intenção. V1, manifesto e gabarito permanecem preservados; expectativas
não mudaram. O manifesto seleciona a v2 e verifica hashes das duas fontes.

## Resultado e reprodução

[Revisão executada](resultado-revisao-executada.json): **24 casos, 168/168
verificações**, incluindo o conjunto reservado de processo. [Pareceres](pareceres-executados.json)
registram as decisões reais dessa leitura pelo agente. Código não lê o gabarito
para produzi-las; o verificador usa a referência somente para medir o resultado.

```bash
poetry run python ferramentas/verificar_revisao_experiencia.py preparar \
  --trabalho /tmp/aceite-revisao
# Nova execução semântica: agente lê pedidos e escreve decisões das fontes.
# Replay abaixo reutiliza os pareceres históricos, sem alegar julgamento novo.
poetry run python ferramentas/verificar_revisao_experiencia.py medir \
  --trabalho /tmp/aceite-revisao --pareceres evaluation/aceite-experiencia-v1/pareceres-executados.json \
  --replay --saida /tmp/resultado-replay.json
poetry run python -m unittest tests.test_revisao_sessao tests.test_filas_prioridade_avaliacao
```

Os testes reprovam uma aprovação indiscriminada de todos os casos. Também
exercitam publicação real, falta de decisão, falsificação de citações, fonte
alterada, guardrail com nota nula, fonte insuficiente, expurgo e retry.
