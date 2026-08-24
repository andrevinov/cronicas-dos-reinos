# Task 29 — Public Reputation of Ren

## Problema

Ren pode tornar-se conhecido em Ravens Bluff por motivos muito diferentes: estrangeiro, vigilante, colaborador útil,
protetor, herói local ou figura controversa. Isso não é o mesmo que **fama**, não é a opinião de um NPC específico e
não pode revelar automaticamente que Ren, Shinta e Kage são a mesma pessoa.

A Task 29 introduz uma camada compacta de **reputação pública**: a posição social produzida por fatos canônicos que
foram realmente públicos, socialmente relevantes e atribuídos a uma persona percebida.

## Quatro camadas que não se confundem

1. **verdade canônica** — o que realmente aconteceu;
2. **suspeita/ reconhecimento individual** — o que um NPC liga entre Ren, Shinta e Kage (Task 28);
3. **fama/recognizability** — quão conhecido é um nome, rosto ou artista;
4. **reputação pública** — como uma esfera social tende a posicionar-se diante daquela persona por feitos públicos.

Aplauso, popularidade ou uma boa rolagem social não criam reputação cívica sozinhos. O espetáculo de Kage pode torná-lo
mais conhecido como artista sem transformá-lo em protetor ou herói local.

## Públicos sociais

O registro `cenario/regioes/ravens-bluff/publicos-reputacao.yaml` deriva da estrutura social já documentada em
`cenario/regioes/ravens-bluff/faccoes.md` e mantém apenas seis públicos amplos:

- `populacao_geral`;
- `autoridades_civicas`;
- `porto_e_comercio`;
- `templos_e_comunidade`;
- `circo_e_artes`;
- `redes_informais`.

Um público não é uma mente coletiva. Luath, um guarda anônimo e um magistrado continuam podendo pensar coisas distintas.
A camada registra apenas uma posição social ampla; relações e crenças individuais continuam nas camadas de NPC.

## Estado

Não existe arquivo de estado paralelo. A reputação, quando surgir, ocupa o campo opcional
`reputacao_publica_ren` dentro de `estado/estado-atual.yaml`:

```yaml
reputacao_publica_ren:
  schema_reputacao_publica_ren: 1
  cidade: ravens_bluff
  registros:
    populacao_geral:
      ren:
        estado: protetor
        marcos: [resgate_publico]
        evidencias:
          resgate_publico:
            id: rep-...
            fonte: sessao:...
```

Ausência do campo significa que a Task 29 ainda não registrou posição pública consolidada. A implementação não percorre o
histórico para atribuir reputação retroativa.

## Persona percebida

Todo registro pertence ao par `público × persona percebida`.

- um feito conhecido como **Kage** altera Kage;
- um feito conhecido como **Shinta** altera Shinta;
- um feito publicamente atribuído a **Ren** altera Ren.

Nenhuma confirmação privada da Task 28 copia reputação entre personas. Mesmo que Kethra descubra `Kage = Ren`, a cidade
não passa a saber disso. Fundir reputações exige um fato canônico de **atribuição pública** e um evento registrado para a
persona que o público passou a reconhecer.

## Marcos qualitativos

Não há pontos nem score. A v1 possui cinco marcos ativos possíveis:

- `resgate_publico`;
- `derrota_criminosos`;
- `colaboracao_institucional`;
- `consequencia_positiva_visivel`;
- `consequencia_negativa_visivel`.

O mesmo tipo de marco só pode estar ativo uma vez por público/persona. Repetir cinco resgates não soma cinco pontos: o
estado já sabe que aquele público viu essa persona como alguém que resgata. Isso impede grind artificial e mantém o
payload pequeno.

Cada fato pode alterar no máximo **um marco por público** e pode alcançar no máximo três públicos explicitamente
atingidos no mesmo evento.

## Estados derivados

O rótulo nunca é escrito por decisão livre do narrador; ele é derivado deterministicamente dos marcos:

- nenhum marco → `estrangeiro_desconhecido`;
- só consequência negativa → `pessoa_perigosa`;
- negativo + qualquer positivo → `figura_controversa`;
- todos os quatro marcos positivos → `heroi_local`;
- resgate público → `protetor`;
- colaboração institucional ou consequência positiva → `pessoa_util`;
- derrota pública de criminosos → `vigilante`.

A ordem acima é deliberada. `heroi_local` exige **amplitude de evidência**, não repetição do mesmo feito.

## Esclarecimento público

`esclarecimento_publico` não é um marco positivo. Ele existe para resolver uma consequência negativa que tenha sido
publicamente corrigida ou esclarecida. A evidência negativa permanece compactamente registrada como origem histórica,
mas deixa de ser um marco ativo; o estado é então recalculado pelos marcos restantes.

## Porta read-only rara

Quando a ficção produzir um fato realmente público e socialmente relevante:

```bash
poetry run python ferramentas/reputacao_publica.py evento ren \
  --publico populacao_geral \
  --publico templos_e_comunidade \
  --tipo resgate_publico \
  --fato '<fato público concreto>' \
  --fonte '<fonte canônica compacta>'
```

A ferramenta **não escreve**. Ela devolve um ou mais deltas `estado` para a transação normal do turno.

Consulta dirigida:

```bash
poetry run python ferramentas/contexto.py reputacao ren
```

ou, para um público específico:

```bash
poetry run python ferramentas/contexto.py reputacao kage --publico circo_e_artes
```

Não consultar reputação por rotina. A porta só é necessária quando a reação social ampla daquela cena é uma lacuna real.

## Transação e checkpoint

O delta persiste somente o registro do par afetado:

```json
{
  "alvo": "estado",
  "op": "set",
  "caminho": "reputacao_publica_ren.registros.populacao_geral.ren",
  "valor": {"estado":"protetor","marcos":["resgate_publico"],"evidencias":{}},
  "motivo_reputacao": "evento_publico",
  "tipo_reputacao": "resgate_publico",
  "publico_reputacao": "populacao_geral",
  "identidade_publica": "ren",
  "atribuicao_publica": true,
  "origem_reputacao": "fato_publico",
  "fato_canonico": "...",
  "fonte": "..."
}
```

O writer recusa mutação direta do domínio, público/persona desconhecidos, atribuição não pública e estado que não seja o
derivado correto. O checkpoint simula o lote contra o estado anterior e impede salto de vários marcos, reescrita de outra
evidência e grind do mesmo tipo de feito.

Eventos pendentes da própria Task 29 são aplicados à projeção antes do checkpoint, permitindo dois fatos públicos
consecutivos sem perder o primeiro.

## Leitura da cidade

`contexto.py reputacao` projeta todos os públicos e deriva uma leitura compacta, sem persistir um score global:

- `sem_posicao_publica`;
- `reputacao_fragmentada`;
- `apoio_crescente`;
- `apoio_amplo`;
- `reputacao_adversa`;
- `cidade_dividida`.

Essa leitura serve à narrativa; não substitui os registros por público.

## Custo

Contrato: `baseline/public-reputation-ren-orcamento.yaml`.

O caminho comum ganha:

- 0 chamadas extras;
- 0 scheduler;
- 0 RNG;
- 0 arquivo de estado paralelo;
- 0 scan de histórico;
- 0 fusão automática de identidades.

A Task 29 deve ajudar Ren a **construir posição na cidade** ao longo de feitos públicos, sem transformar cada turno numa
pesquisa de opinião ou cada aplauso numa barra de fama.
