# Direções narrativas canônicas

Esta pasta descreve destinos de longo prazo que **devem existir na campanha**, mas
não prescreve cenas, datas, protagonistas nem soluções.

Uma direção é diferente de:

- **agente**: alguém quer algo e age para obtê-lo;
- **evento mundial**: algo acontece por acaso ou pressão sistêmica;
- **direção canônica**: a campanha deve, em algum momento, atravessar certos
  marcos, mas o caminho concreto emerge do jogo.

## Arquivos

- `index.yaml`: roteador pequeno e cadência de avaliação;
- `estado.yaml`: progresso operacional reservado;
- `<direcao>.yaml`: marcos, critérios e guardrails derivados de material canônico.

## Uso

```bash
python3 ferramentas/direcoes.py status
python3 ferramentas/direcoes.py mostrar ponte_de_kozakura
python3 ferramentas/direcoes.py validar
python3 ferramentas/direcoes.py ativar shin_kozakura --origem "..." --nota "..."
python3 ferramentas/direcoes.py avancar ponte_de_kozakura --origem "..." --nota "..."
```

`mostrar` lê apenas índice + estado + fragmento alvo. `validar` percorre todas as
fontes e pertence a manutenção/CI.

`avancar` nunca deve ser chamado só porque o narrador deseja chegar logo ao
próximo arco. Ele exige origem e nota para deixar rastreável qual fato do mundo
justificou o avanço. O comando altera apenas `narrador/direcoes/estado.yaml`; não
cria conhecimento para Ren e não inventa retroativamente o acontecimento.

## Integração com Mundo Vivo

O motor do mundo cria pendências `avaliar_direcao` apenas na cadência definida no
índice e somente para direções ativas. Se uma direção latente tiver sua dependência
satisfeita, ele cria `ativar_direcao` em vez de ativá-la automaticamente.

Uma pendência significa **"reavaliar se o marco já está sustentado pelo mundo"**,
não "o marco aconteceu". O narrador consulta somente a direção indicada, decide
com base no cânone e então pode avançar ou simplesmente concluir a pendência sem
mudança.

Assim, Shin-Kozakura é inevitável como direção histórica depois da perda do
monopólio de Masao, mas sua data, agentes, crises, arquitetura concreta e caminho
político continuam pertencendo à campanha viva.
