# Rastros observáveis

Esta camada separa **verdade do mundo** de **conhecimento de Ren**.

```text
fato canônico reservado
        ↓ pode deixar
rastro observável
        ↓ se Ren realmente perceber/investigar
descoberta
        ↓ pelo pipeline transacional
conhecimento de Ren
```

Um fato off-screen não cria conhecimento automaticamente. Um rastro também não é
conhecimento: ele é somente uma evidência disponível no mundo.

## Estrutura

- `index.yaml`: roteador compacto dos rastros ativos; contém apenas metadados
  suficientes para filtrar por tempo, lugar, acesso e tags;
- `itens/<id>.yaml`: fragmento individual com a manifestação observável;
- a causa verdadeira fica em `origem`, com fonte/evidência canônicas, e **não é
  exposta por `mostrar`**.

O índice começa vazio. A instalação não reconstrói rastros retroativamente a partir
das sessões já jogadas.

## Registro

Depois que uma ação, consequência ou acontecimento realmente virou cânone e deixou
uma evidência, registrar por stdin:

```bash
cat <<'YAML' | python3 ferramentas/rastros.py registrar
nome: Pegadas com lama azul
tipo: fisico
manifestacao: Há respingos de lama azul perto da porta.
fato_observavel: Alguém passou recentemente pela porta trazendo lama azul nas botas.
localizacao:
  escopo: area
  cidade: Ravens Bluff
  area: Ponte Baixa
acesso: investigacao
persistencia:
  disponivel_de:
    data: 11 Eleasis, 1372 DR
    hora: '06:00'
  expira_em: null
tags: [lama, passagem]
origem:
  estatuto: fato_canonico
  fonte: sessoes/009/fatos.yaml
  evidencia: Um mensageiro deixou lama azul junto à porta dos fundos.
  referencia: mensageiro_desconhecido
YAML
```

A origem precisa existir e a evidência precisa aparecer literalmente nela. Controles
operacionais e moldes não resolvidos (`narrador/mundo/estado.yaml`,
`narrador/eventos/estado.yaml`, cartas do baralho) são rejeitados como fonte.

## Descoberta barata

Ao entrar numa área, consultar primeiro somente o índice:

```bash
python3 ferramentas/rastros.py candidatos
```

Por padrão aparecem apenas rastros de acesso `automatico`. Uma busca deliberada usa:

```bash
python3 ferramentas/rastros.py candidatos --acesso investigacao --tag lama
```

Essa filtragem usa localização canônica + tempo + índice. **Não abre fragmentos.**
Se houver um ID relevante, só então:

```bash
python3 ferramentas/rastros.py mostrar <id>
```

`mostrar` expõe apenas a evidência observável; a causa reservada é redigida.

## Conhecimento

```bash
python3 ferramentas/rastros.py preparar-descoberta <id>
```

Esse comando é somente leitura. Ele produz um `delta_sugerido` para
`alvo: conhecimento`, mas **não o instala** e não marca o rastro como descoberto.
A integração atômica entre descoberta, transação do turno e encerramento/consumo do
rastro pertence ao passo 8.

Portanto, nesta etapa:

- fato ≠ rastro;
- rastro ≠ conhecimento;
- presença no mesmo lugar ≠ descoberta para rastros de `investigacao`;
- abrir um rastro não revela sua causa verdadeira;
- nenhuma operação desta camada escreve em `personagens/jogador/conhecimento/`.

## Escopos e acessos

Escopos: `cidade`, `area`, `ponto`.

Acessos:

- `automatico`: pode ser apresentado quando Ren está no escopo correto;
- `investigacao`: só entra após busca deliberada;
- `interacao`: exige contato/uso do objeto ou pessoa;
- `rumor`: exige um canal social plausível.

A filtragem é determinística; testes, perícias e interpretação narrativa continuam
pertencendo à resolução da cena.
