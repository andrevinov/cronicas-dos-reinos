# Rastros observáveis

Esta camada separa **verdade do mundo** de **conhecimento de Ren** e, desde o passo 8, fecha a descoberta pelo mesmo pipeline transacional da narração.

```text
fato canônico reservado
        ↓ pode deixar
rastro observável
        ↓ Ren percebe/investiga
descoberta no turno
        ↓ mesma consolidação
conhecimento de Ren + rastro marcado como descoberto
```

Um fato off-screen não cria conhecimento automaticamente. Um rastro também não é conhecimento: ele é somente evidência disponível no mundo.

## Estrutura e custo

- `index.yaml`: roteador pequeno; filtra por tempo, lugar, acesso, tags e estado;
- `itens/<id>.yaml`: manifestação observável individual;
- `estado: ativo|descoberto` fica apenas no índice para impedir reapresentação automática;
- a causa verdadeira fica em `origem` e **não é exposta por `mostrar`**;
- o índice começa vazio: nenhuma pista antiga é reconstruída retroativamente.

`candidatos` usa somente índice + localização canônica + tempo. Não abre fragmentos:

```bash
python3 ferramentas/rastros.py candidatos
python3 ferramentas/rastros.py candidatos --acesso investigacao --tag lama
```

Depois de obter um ID relevante:

```bash
python3 ferramentas/rastros.py mostrar <id>
```

## Registro de um rastro

Só registrar depois que o fato que o originou já virou cânone. A fonte precisa existir e a evidência precisa aparecer literalmente nela. Controles operacionais, estado do baralho e cartas não resolvidas são rejeitados como origem.

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

## Descoberta transacional — passo 8

`preparar-descoberta` é somente leitura e devolve **dois deltas inseparáveis**:

1. `conhecimento / registrar` com exatamente o `fato_observavel`;
2. `rastro:<id> / set estado=descoberto` com visibilidade `narrador`.

```bash
python3 ferramentas/rastros.py preparar-descoberta <id>
```

O schema transacional rejeita um par incompleto antes das duas escritas de `turno.py`. Também rejeita duplicatas e qualquer mutação diferente de `estado=descoberto` para esse alvo reservado.

O caminho recomendado, quando a cena já resolveu a percepção/investigação, é registrar a descoberta diretamente pelo writer normal:

```bash
python3 ferramentas/rastros.py descobrir <id> <<'JSON'
{
  "jogador": "Ren examina as marcas junto à porta.",
  "narracao": "A lama é recente, mas não identifica quem passou por ali.",
  "resumo": "Ren percebe um rastro de lama azul.",
  "modo": "exploração"
}
JSON
```

`descobrir` apenas prepara o par e chama `turno.register_transaction`; portanto o hot path continua sendo **transcrição + buffer pendente**, as mesmas duas escritas de qualquer turno. O rastro ainda permanece `ativo` até o próximo checkpoint/consolidação.

Também é válido usar `turno.py registrar` diretamente, desde que os dois deltas produzidos por `preparar-descoberta` sejam incluídos juntos.

## Consolidação atômica

No checkpoint, `consolidar.py` valida novamente a descoberta:

- o rastro precisa existir e ainda estar `ativo`;
- o texto público precisa ser **idêntico** a `fato_observavel`;
- a fonte pública precisa ser somente `rastro:<id>`;
- a origem reservada nunca é copiada para conhecimento.

Depois disso, o conhecimento incremental e `narrador/rastros/index.yaml` entram no **mesmo plano de staging/journal**. Só então a instalação começa. Se houver queda no meio, o mecanismo de recuperação já existente instala ou repara exatamente o mesmo lote.

O ledger registra `rastros_descobertos` e inclui o índice de rastros em `arquivos_afetados`.

Depois de consolidado, um rastro `descoberto` deixa de aparecer em `candidatos`, evitando repetição de contexto. O fragmento continua consultável explicitamente para referência, sem expor a causa reservada.

## Escopos e acessos

Escopos: `cidade`, `area`, `ponto`.

Acessos:

- `automatico`: pode ser apresentado no escopo correto;
- `investigacao`: exige busca deliberada;
- `interacao`: exige contato/uso plausível;
- `rumor`: exige canal social plausível.

Filtragem é determinística; testes, perícias e interpretação narrativa continuam pertencendo à resolução da cena.
