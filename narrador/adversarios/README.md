# Adversários mecânicos

Esta camada reservada guarda a execução mecânica de NPCs e criaturas que exigem
mais do que um bloco improvisado. Ela não cria presença, conhecimento, objetivo
ou plano: essas autoridades continuam no estado, nos agentes e nas fontes
canônicas correspondentes.

`index.yaml` é o roteador. Cada entrada aponta para um bloco-base sob `fichas/` e
para um fragmento dirigido sob `especialidades/`. O contrato executável fica em
`contrato.yaml`.

Um bloco completo declara ruleset e proveniência, defesas, atributos, recursos,
traços, ações, ações bônus, reações, ações lendárias, táticas e retirada. Escala
lendária exige ao menos uma ação lendária. A especialidade separada
descreve procedimentos não combativos com resolução, sucesso, falha, limite e
contrajogo. Valores precisam existir antes da rolagem e não podem ser alterados
depois para corrigir dificuldade ou resultado.

## Consulta dirigida

```bash
python3 ferramentas/adversarios.py mostrar <id-ou-nome>
python3 ferramentas/adversarios.py especialidade <id-ou-nome> <especialidade-id>
```

Cada comando abre somente contrato, índice, ruleset de `campanha.yaml` e os
fragmentos do adversário pedido, com saída máxima de 8 KiB. Não abrir a pasta
inteira durante uma cena.

## Arquétipos reutilizáveis

Entradas com prefixo `arquetipo_` são blocos mecânicos, não pessoas nem espécies
automaticamente canônicas. O registro inclui um mestre de armas de referência 6,
um caçador de sombras de referência 7 e duas criaturas originais. Usar um modelo
exige vinculá-lo previamente a um ator ou criatura causalmente presente; o vínculo
define identidade e contexto, mas não permite mudar seus números depois da
preparação.

## Avaliação pré-rolagem

```bash
python3 ferramentas/ameacas.py avaliar <id-ou-nome> --ren --vetor combate
python3 ferramentas/ameacas.py avaliar <id-ou-nome> --nivel 7 --vetor especialidade
```

`contrato-ameacas.yaml` congela faixas e modificadores; `ameacas.yaml` guarda
patamares separados de combate e especialidade. A consulta é explícita e não roda
em turno comum. Quantidade, aliados já causais, recursos, terreno e iniciativa
precisam ser declarados antes da rolagem. Classificação letal ou esmagadora exige
saída observável, mas não garante que fugir, negociar ou intervir terá sucesso.

## Validação fria

```bash
python3 ferramentas/adversarios.py validar
```

O validador percorre o registro somente em manutenção/CI. Os dez membros da
Juppongatana possuem blocos originais 5.5e completos, vinculados por ID ao elenco
de `narrador/juppongatana/index.yaml`. Nível e classe nos perfis continuam sendo
referência de escala; os números executáveis vivem apenas neste registro.

```bash
python3 ferramentas/ameacas.py validar
```
