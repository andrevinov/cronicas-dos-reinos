# Baralho de eventos mundiais

Esta camada acrescenta acaso **reprodutível e sem reposição** ao Mundo Vivo sem transformar acaso em cânone automático.

## Dois baralhos

Cada amanhecer alcançado passa primeiro pela urna de ocorrência: **7 fichas `rotina` e 3 fichas `evento`**. As dez são consumidas sem reposição. Ao esgotar, o ciclo seguinte é reordenado deterministicamente por SHA-256 a partir da semente persistente.

Somente quando sai `evento` o segundo baralho é consultado. Ele contém cartas mundiais únicas e também é consumido sem reposição; uma carta não volta antes de todas as outras terem sido sorteadas.

Não se usa `random`, relógio do sistema ou entropia externa. A mesma semente, ciclo e catálogo produzem a mesma ordem.

## Cânone

Sorteio não é acontecimento. Uma carta sorteada cria somente uma pendência `evento_mundial` em `narrador/mundo/estado.yaml`. Ao resolver:

```bash
python3 ferramentas/eventos_mundo.py mostrar <id>
```

O narrador decide como a premissa se manifesta no estado atual. Pode resultar em textura sem efeito durável. Só fatos explicitamente registrados pelo pipeline transacional viram cânone. A carta não cria conhecimento para Ren.

## Economia

A seleção diária lê apenas índice, estado dos baralhos, agenda, tempo e fila do Mundo Vivo. **Nenhum fragmento de carta é aberto durante o sorteio.** Dias de rotina criam zero pendências narrativas. O fragmento entra no contexto somente na resolução dirigida.

O estado começa processado no amanhecer de 10 Eleasis, 1372 DR; portanto a instalação não sorteia eventos retroativos para dias já jogados.

## Retry

O checkpoint grava primeiro a pendência do Mundo Vivo e só depois avança o estado dos baralhos. Se houver queda entre essas duas escritas, o retry sorteia a mesma ficha/carta, encontra o ID estável já presente e apenas repara o estado sem duplicar o evento.

## Catálogo inicial

Dez moldes genéricos: incêndio localizado; inspeção portuária; chuva/alagamento; procissão; acidente no porto; disputa de ofícios; escassez; viajantes incomuns; doença leve; e boato que move multidão.

Nenhuma carta pode forçar a entrada de aliado ou antagonista, ativar a Ponte de Kozakura, escolher NPC nomeado como vítima ou atribuir autoria secreta. Essas decisões pertencem às outras camadas.

## Comandos

```bash
python3 ferramentas/eventos_mundo.py status
python3 ferramentas/eventos_mundo.py mostrar <id>
python3 ferramentas/eventos_mundo.py processar
python3 ferramentas/eventos_mundo.py validar
```

`processar` é chamado automaticamente pelo checkpoint de baixa frequência.
