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

## Interação com agentes

As tags das cartas também ficam no índice pequeno. **Somente quando a urna realmente tira `evento`**, Python lê `interacoes.yaml` e os índices compactos de agentes estratégicos/leves. Nenhum fragmento individual é aberto nessa etapa.

`interacoes.yaml` registra sensibilidades operacionais por tag. O orçamento atual é rígido:

- no máximo **2 agentes estratégicos** por evento;
- no máximo **1 agente leve** por evento;
- seleção por **maior número de tags coincidentes → maior prioridade → ID**;
- agentes inativos são ignorados;
- agente físico sem presença local é ignorado;
- coletivo com presença apenas condicional não é acordado por evento genérico sem membro concreto em foco.

A pendência continua sendo **uma só**. Exemplo:

```yaml
tipo: evento_mundial
evento: inspecao_portuaria_reforcada
agentes_afetados:
  - red_sail
  - night_watch
agentes_leves_afetados:
  - luath
```

Essas listas significam **candidatos que merecem ser considerados na resolução**, não que já agiram, souberam do evento ou sofreram consequência. O narrador abre a carta e somente os agentes relevantes; se a manifestação realmente os afetar, qualquer plano, relógio, relação ou conhecimento novo entra pelo pipeline normal.

Se um NPC candidato morrer antes da resolução, o checkpoint seguinte o remove deterministicamente da pendência sem cancelar o evento.

## Economia

Em dia de `rotina`, a seleção lê apenas índice, estado dos baralhos, agenda, tempo e fila do Mundo Vivo. **Nem `interacoes.yaml` é aberto.**

Quando sai `evento`, entram apenas `interacoes.yaml` + índices compactos de agentes; cartas e fragmentos de NPC continuam fechados. O fragmento da carta só entra no contexto na resolução dirigida.

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
