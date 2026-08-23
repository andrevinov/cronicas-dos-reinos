# Task 20 — Approach Quality Modifier

Approach Quality Modifier é uma house rule **pré-rolagem** para testes de habilidade do jogador. Ela existe para que um plano excelente não tenha exatamente a mesma chance que uma tentativa genérica quando a ficção realmente favorece o teste.

## Rubrica 0/+1/+2/+3

Cada dimensão vale no máximo `+1` e precisa favorecer **este teste específico**:

1. **Preparação** — Ren criou antes uma condição útil: recurso, ferramenta, posição, ensaio, tempo investido ou outro preparo concreto.
2. **Informação** — o plano usa algo relevante que Ren já descobriu sobre alvo, rotina, ambiente, fraqueza ou procedimento.
3. **Adequação** — o método escolhido se encaixa particularmente bem no obstáculo, em vez de ser apenas “eu tento”.

Nenhuma dimensão válida = `+0`; as três = `+3`. A mesma justificativa não pode pontuar duas dimensões.

## Momento da decisão

A rubrica é resolvida **antes do RNG**. Depois que o dado aparece, o bônus não pode ser inventado, aumentado ou usado para rerrolar.

O bônus da ficha continua independente. Vantagem/desvantagem e outros modificadores circunstanciais também continuam independentes, mas uma mesma circunstância ficcional não pode ser cobrada duas vezes em mecânicas diferentes.

## Escopo

A implementação inicial aceita o modificador apenas em:

- `dados d20` — teste genérico do jogador;
- `dados ren pericia` — perícia de Ren.

Ataques, salvaguardas, iniciativa, dano e rolagens de NPC ficam fora. Isso evita alterar bounded accuracy ou transformar uma regra de qualidade da **abordagem** em bônus universal.

## Impossibilidade continua impossibilidade

A rubrica só é aplicada depois que o narrador determinou que existe um teste legítimo. Um plano brilhante pode melhorar a chance de algo difícil; não permite rolar para uma ação impossível e não altera a CD para fingir que ela se tornou possível.

## Endpoints

A Task 10 já reservou `modificadores`. Quando uma cena recebe evidências de abordagem, `endpoints.py cena` acrescenta ali um único objeto `qualidade_abordagem`. Nenhum endpoint novo é criado e o schema permanece `1`. Sem evidências, o snapshot antigo permanece idêntico.

## Custo

A rubrica é uma função pura: zero leitura, zero escrita, zero scheduler, zero estado e zero RNG adicional. O rolador público valida as evidências, soma o bônus ao modificador apropriado e chama uma única vez o motor de dados preservado em `_rolar_dados_core.py`. O lote continua usando a mesma porta pública, sem segundo motor de rolagem.
