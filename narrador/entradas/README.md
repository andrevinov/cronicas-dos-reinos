# Entradas e aparições de aliados

Camada reservada que controla **quando vale a pena avaliar** a entrada em cena de
um aliado futuro. Ela não decide a cena e não faz ninguém aparecer sozinha.

O cânone de `narrador/aliados/README.md` e `marcos-de-aparicao.md` continua sendo a
fonte narrativa. Esta pasta é apenas projeção operacional compacta.

## Princípios

- existe no máximo **um candidato normal**: o primeiro aliado ainda não presente
  na ordem preferencial canônica;
- o caminho normal respeita um nível mínimo derivado da janela preferencial;
- somente uma antecipação extraordinária pode furar a ordem por vez;
- `antecipar` exige `origem + nota` e agenda avaliação para o próximo amanhecer;
- antecipação também pode acelerar o candidato normal quando um gatilho forte
  aconteceu antes da avaliação periódica;
- `avaliar_entrada` significa apenas "agora vale consultar o fragmento";
- a entrada nunca é automática: o narrador pode concluir que ainda não é a hora;
- depois de cada avaliação vencida, a próxima fica três dias à frente, evitando
  reconsultas em todo checkpoint;
- `confirmar` só deve ser usado **depois** que a entrada realmente aconteceu em
  jogo. Ele então libera o próximo candidato normal para o amanhecer seguinte.

## Comandos

```bash
python3 ferramentas/entradas.py status
python3 ferramentas/entradas.py mostrar shen_meihua
python3 ferramentas/entradas.py antecipar dame_jenilynn_leyland \
  --origem "sessao:008" --nota "Ren pediu ajuda diretamente a Tyr"
python3 ferramentas/entradas.py confirmar shen_meihua \
  --origem "sessao:009" --nota "Shen cruzou Ren em cena e permaneceu em Ravens Bluff"
python3 ferramentas/entradas.py validar
```

Quando surgir uma pendência `avaliar_entrada`, usar `mostrar <id>` para abrir
somente índice + estado + fragmento daquele aliado. Depois da decisão, concluir a
pendência pela fila normal do mundo com `mundo.py concluir <id-da-pendencia>`.

## Economia de contexto

O checkpoint lê somente:

- `narrador/entradas/index.yaml`;
- `narrador/entradas/estado.yaml`;
- `runtime/contexto.yaml` para o nível atual;
- cursor/tempo do Mundo Vivo.

Ele **não abre `marcos-de-aparicao.md` nem fragmento de aliado**. Como há no
máximo um candidato em foco, um checkpoint nunca cria uma avalanche de cinco
possíveis aparições.
