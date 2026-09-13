# Dungeons preparadas

Esta camada guarda estruturas exploráveis completas sem transformar preparação em
acontecimento. Uma entrada no índice não significa que Ren encontrou acesso, que
os encontros estão presentes ou que qualquer recompensa foi descoberta.

Consulta dirigida:

```bash
python3 ferramentas/dungeons.py mostrar sarbreen_poroes_secos
python3 ferramentas/dungeons.py nivel sarbreen_poroes_secos 2
python3 ferramentas/dungeons.py validar
```

`mostrar` abre contrato, índice e manifesto. `nivel` acrescenta exatamente um
fragmento de nível e devolve IDs de adversários; fichas e avaliações continuam nas
portas próprias `adversarios.py` e `ameacas.py`. Nunca abrir os outros níveis por
precaução.

O progresso factual continua no turno transacional, em sessões e nos lifecycles já
existentes. Esta camada não possui scheduler, RNG, estado de salas ou writer. Um
checkpoint não povoa dungeon, não move criaturas e não concede recompensa.

O piloto `sarbreen_poroes_secos` é um trecho delimitado da cidade anã quebrada,
não “Sarbreen inteira”. Seu manifesto preserva a incursão histórica da Balança
Velha e não determina onde está a Ponte de Kozakura.
