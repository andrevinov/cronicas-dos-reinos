# Resolução de ações

Resumo operacional para conduzir ações durante as sessões.

A base é **D&D 5e**, com simplificação prática quando a regra completa interromper o ritmo sem acrescentar risco ou escolha.

---

## Quando rolar

Pedir rolagem quando houver:

* incerteza real;
* risco ou custo;
* oposição;
* consequência interessante em caso de fracasso;
* capacidade do personagem realmente relevante para o resultado.

Não pedir rolagem para:

* ações triviais;
* ações impossíveis;
* tarefas seguras que podem ser repetidas até funcionar;
* informação que Ren saberia automaticamente;
* escolhas puramente interpretativas.

---

## Fórmula básica

Para testes:

```text
d20 + modificador apropriado contra CD
```

Para ataques:

```text
d20 + bônus de ataque contra CA
```

Para salvaguardas:

```text
d20 + bônus da salvaguarda contra CD do efeito
```

Sempre que possível, usar:

```bash
python3 ferramentas/rolar-dados.py
```

---

## CDs rápidas

Usar como referência inicial:

| CD | Dificuldade |
| --- | --- |
| 10 | fácil sob pressão |
| 12 | moderada baixa |
| 15 | moderada séria |
| 18 | difícil |
| 20 | muito difícil |

A CD deve ser definida antes da rolagem.

Não aumentar ou reduzir CD depois de ver o dado, salvo se uma característica usada legitimamente após a rolagem mudar o resultado.

---

## Vantagem e desvantagem

Usar vantagem quando a situação favorecer claramente Ren:

* boa preparação;
* ferramenta adequada;
* ajuda efetiva;
* posição superior;
* distração bem criada;
* alvo descuidado.

Usar desvantagem quando a situação prejudicar claramente:

* pressa extrema;
* pouca luz sem compensação;
* barulho;
* ferimento, exaustão ou condição relevante;
* ferramenta improvisada;
* risco de ser observado.

Se vantagem e desvantagem coexistirem, elas se cancelam.

---

## Testes resistidos

Quando uma criatura se opõe diretamente a outra, usar teste resistido.

Exemplos:

* Furtividade de Ren contra Percepção de vigia;
* Enganação de NPC contra Intuição de Ren;
* Atletismo contra Acrobacia em agarrão ou empurrão, quando aplicável.

Se revelar o teste resistido entregaria segredo, fazer rolagem oculta e registrar na área do narrador quando for importante.

---

## Sucesso com custo

Quando uma falha simples travaria a cena, considerar sucesso com custo.

Custos possíveis:

* tempo perdido;
* barulho;
* gasto de recurso;
* pista incompleta;
* testemunha assustada;
* avanço de relógio;
* condição temporária;
* reputação afetada.

Não usar sucesso com custo para anular risco importante, combate ou decisão ruim.

---

## Ajuda de NPCs

NPCs podem ajudar quando:

* estão presentes;
* entendem a tarefa;
* possuem capacidade real de contribuir;
* têm motivo para colaborar.

A ajuda pode conceder vantagem, reduzir CD ou apenas permitir a tentativa.

NPCs não devem resolver a aventura no lugar de Ren.

---

## Campanha solo

Como Ren atua sozinho, aplicar risco com clareza.

O narrador deve:

* apresentar sinais de ameaça forte;
* permitir fuga, negociação e infiltração;
* evitar encontros feitos apenas para gastar PV;
* lembrar que inimigos podem fugir, render-se, negociar ou chamar reforços;
* preservar consequência real quando Ren escolher confronto direto.

Campanha solo não significa proteção automática.

---

## Gasto de recursos de classe

Todo gasto mecânico de recurso de classe precisa ser decidido antes de persistir a consequência. O turno só pode reduzir o recurso se o ticket preparado registrar a obrigação, o valor disponível naquele instante for suficiente e a resolução do turno confirmar o gasto.

O recurso de classe ativo de Ren é **Focus**. O writer nunca pode aceitar um gasto que deixe Focus abaixo de zero. `ki` permanece apenas em registros históricos anteriores ao cutover.

`cronica` valida a causalidade e a disponibilidade, mas não implementa a regra de D&D nem rola dados: resoluções de teste, salvaguarda e ataque são verificadas pelas primitivas do núcleo mecânico.
