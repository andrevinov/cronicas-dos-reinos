# Task 19 — Juppongatana Milestone Progression

A faixa de **níveis 8 a 17** de Ren passa a ter uma espinha explícita: cada membro único da Juppongatana neutralizado de forma **canônica e durável** desbloqueia exatamente um nível.

A ordem é livre. O primeiro membro neutralizado leva ao nível 8; o segundo ao 9; …; o décimo ao 17. Isso não transforma a ordem de aparição em trilho e não exige que o Círculo Externo inteiro caia antes do Meio ou Interno.

## O que conta

Neutralização não é sinônimo de morte. Contam resultados persistentes como morte confirmada, prisão/confinamento estável, incapacitação durável, ruptura definitiva com Masao ou expulsão/exílio operacional.

Não contam derrota temporária, fuga, objetivo frustrado, ferimento recuperável, exposição, primeiro contato ou simplesmente sobreviver a um duelo.

Kurobane já havia sido frustrado antes da instalação desta task, mas isso não foi uma neutralização durável. O ledger começa em **0/10**, sem crédito retroativo.

## Fonte e evidência

Cada milestone precisa apontar para uma fonte canônica persistida sob `sessoes/`, `estado/` ou `historico/` e fornecer evidência literal presente nessa fonte. O registro não aceita a própria política como prova e não faz busca ampla no repositório.

## Transação

`progressao_juppongatana.py preparar` é read-only e calcula um fingerprint sobre política, estado, ficha e fonte. `confirmar` revalida o mesmo conjunto antes de acrescentar uma única entrada ao ledger.

O gate altera somente `narrador/juppongatana/estado-progressao.yaml`. Ele **não atualiza `nivel` na ficha automaticamente**, porque subir de nível exige também PV, ki, habilidades e eventuais escolhas. Depois do milestone, a aplicação mecânica segue `regras/progressao.md`.

## Retornos

Se um membro neutralizado retornar mais tarde por uma reversão canônica extraordinária, o nível já conquistado não é perdido. O mesmo membro também não pode conceder um segundo milestone.

Depois do décimo milestone e do nível 17, a progressão volta ao regime geral de marcos narrativos.
