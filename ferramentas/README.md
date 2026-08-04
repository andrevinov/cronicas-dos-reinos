# Ferramentas

Ferramentas locais de apoio para conduzir **Crônicas dos Reinos**.

## Rolador de dados

Usar `ferramentas/rolar-dados.py` sempre que uma rolagem aberta ou oculta exigir dado durante a preparação ou narração.

Exemplos:

```bash
python3 ferramentas/rolar-dados.py rolar 2d6+3
python3 ferramentas/rolar-dados.py d20 --bonus 5 --cd 15 --label "Teste de Furtividade"
python3 ferramentas/rolar-dados.py ren pericia furtividade --cd 15
python3 ferramentas/rolar-dados.py ren salvaguarda destreza --cd 13
python3 ferramentas/rolar-dados.py ren iniciativa
python3 ferramentas/rolar-dados.py ren ataque wakizashi --ca 14
python3 ferramentas/rolar-dados.py ren dano wakizashi --critico
python3 ferramentas/rolar-dados.py npc d20 --nome "Guarda" --bonus 3 --cd 12 --label "Percepção"
python3 ferramentas/rolar-dados.py npc ataque --nome "Bandido" --arma "espada curta" --bonus-ataque 4 --dano 1d6+2 --tipo-dano perfurante --ca 16
```

Atalhos atuais de Ren:

```bash
python3 ferramentas/rolar-dados.py ren listar
```

Saídas públicas podem ser copiadas para a transcrição da sessão. Rolagens ocultas devem ser registradas apenas na área do narrador quando forem relevantes.
