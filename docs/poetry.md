# Ambiente Python com Poetry

O repositório usa Poetry para manter as dependências isoladas e oferecer atalhos para as ferramentas mais usadas.

## Primeira instalação

Na raiz do repositório:

```bash
poetry install
```

O arquivo `poetry.toml` força o ambiente para:

```text
.venv/
```

A pasta já é ignorada pelo Git.

Para ativar o ambiente no shell:

```bash
source .venv/bin/activate
```

No Poetry 2 também é possível usar:

```bash
eval "$(poetry env activate)"
```

Não é obrigatório ativar o ambiente. Você pode executar qualquer comando com `poetry run`.

## Comandos principais

```bash
# Retomar/consultar a campanha sem reler transcrições.
poetry run contexto retomada
poetry run contexto status
poetry run contexto cena

# Registrar um avanço narrativo transacional.
poetry run turno registrar

# Consolidar em uma fronteira importante de cena ou sessão.
poetry run checkpoint cena
poetry run checkpoint sessao
poetry run checkpoint recuperar

# Verificações.
poetry run integridade
poetry run auditoria
poetry run testes

# Runtime quente.
poetry run runtime --check

# Dados.
poetry run dados d20 --bonus 5
poetry run dados-lote

# Telemetria pós-hoc.
poetry run rollout /caminho/para/rollout.jsonl
poetry run rollout-comparar /caminho/para/rollout.jsonl
```

## Atalhos disponíveis

Os comentários no próprio `pyproject.toml` são a referência rápida de cada comando:

- `contexto`: consulta estado efetivo e memória dirigida;
- `turno`: registra transcrição + deltas pendentes;
- `checkpoint`: consolida e atualiza handoff/índice;
- `consolidar`: motor de baixo nível do checkpoint;
- `auditoria`: auditoria completa de retomada;
- `integridade`: validação estrutural e semântica;
- `runtime`: gera/valida `runtime/`;
- `sessoes`: memória compacta de sessões;
- `dados` e `dados-lote`: rolagens;
- `rollout` e `rollout-comparar`: telemetria depois da sessão;
- `testes`: suíte unitária completa.

## Lock file

Na primeira execução, se ainda não existir `poetry.lock`, o Poetry resolve as dependências e o cria. Como este repositório funciona como uma aplicação, vale versionar o `poetry.lock` depois de gerado para tornar reinstalações reproduzíveis.
