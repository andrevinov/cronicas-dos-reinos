# Mecânica diegética: separação entre mundo e sistema

Esta camada impede que a linguagem do sistema vire conhecimento ou vocabulário natural dos personagens.

## Regra

A prosa de `narracao` e qualquer fala de NPC dentro dela são **diegéticas**. Não usar ali contagens ou rótulos de ficha como:

- PV / HP / pontos de vida;
- CA / AC / classe de armadura;
- CD / DC / classe de dificuldade;
- nível mecânico de personagem/classe;
- pontos ou contagem numérica de Ki;
- slots/espaços de magia;
- bônus ou modificadores numéricos de regra.

Em vez de “ele está com 3 PV”, narrar o que o mundo mostra: respiração curta, sangue, dificuldade de sustentar a guarda, perda de força etc. Em vez de um NPC dizer “minha CA é 18”, ele pode falar de armadura, treino, proteção ou confiança sem conhecer a abstração da ficha.

A palavra **ki** continua permitida como conceito diegético quando não é usada como contador mecânico. “Ren sente o ki se concentrar no baixo ventre” é válido; “Ren ainda tem 4 Ki” não é.

`nível` também continua palavra normal do idioma. “O nível da água subiu” é válido. O guardrail mira formas mecânicas como “nível 7”, “7º nível” ou “nível de personagem”.

## Camada mecânica explícita

Quando o jogador precisa receber uma instrução/regra numérica, use uma linha própria:

```text
MECÂNICA — Faça um teste de Furtividade, CD 15.
```

A linha inteira é OOC e não representa algo dito ou percebido literalmente pelos personagens. Não misturar a marca no meio de uma fala ou parágrafo diegético.

Exemplo:

```text
O guarda estreita os olhos e demora um segundo a mais no rosto de Shinta.

MECÂNICA — Teste de Enganação, CD 14.
```

## Onde mecânica continua permitida

O guardrail não transforma o sistema em segredo. Mecânica continua normal em:

- deltas transacionais;
- `resumo` operacional;
- ferramentas de rolagem e seus resultados;
- consultas de regra;
- ficha e runtime;
- `RODAPE_CANONICO`;
- uma linha explícita `MECÂNICA — ...` quando necessária ao jogador.

A separação é de **camada de linguagem**, não de informação.

## Escrita e custo

A validação ocorre dentro da construção transacional antes da transcrição e do buffer serem escritos. É somente regex sobre a string que já está na chamada de `turno.py registrar`:

- nenhuma leitura de arquivo;
- nenhuma busca;
- nenhuma inferência adicional;
- nenhuma escrita adicional;
- nenhuma varredura de transcrições históricas.

Se houver violação, a operação falha sem tocar transcrição ou `runtime/eventos-pendentes.jsonl` e informa que a frase deve ser reescrita diegeticamente ou movida para uma linha `MECÂNICA —`.

## Escopo

A Task 6 protege novas gravações. Ela não reescreve automaticamente transcrições antigas, porque isso alteraria um artefato histórico para resolver uma convenção introduzida depois.
