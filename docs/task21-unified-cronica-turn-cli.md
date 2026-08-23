# Task 21 — Unified `cronica` Turn CLI

`cronica` é a porta operacional preferencial para o ciclo normal de um turno. Ela **não substitui** `endpoints.py`, `cena_mundo.py` nem `turno.py`; apenas reduz a orquestração necessária entre essas portas já estabilizadas.

## Fluxo normal: duas chamadas

### 1. Preparar

```bash
cronica preparar \
  --cena-id s013-porto \
  --local lower_trades \
  --acao entrar \
  --tier 2 \
  --periculosidade media
```

`preparar` chama o endpoint determinístico de cena uma única vez e devolve:

- IDs/gates/modificadores compactos da Task 10;
- o `preparacao_id` transacional;
- um `ticket` opaco com os parâmetros exatos da cena.

O ticket é JSON canônico comprimido + checksum SHA-256 truncado. Ele não é salvo em `runtime/` nem em qualquer outro arquivo. Abandonar uma preparação continua deixando **zero resíduo**.

Quando `--data/--hora` foram fornecidos, o ticket preserva o instante explícito. Quando não foram, ele preserva `null`: a conclusão volta a consultar o tempo canônico e, se o mundo mudou, o `preparacao_id` fica obsoleto como antes.

As três evidências da Task 20 (`preparacao`, `informacao`, `adequacao`) também viajam no ticket apenas para correlação/auditoria. Elas não alteram a confirmação da cena nem congelam RNG.

### 2. Narrar e concluir

Depois de produzir a narração aceita:

```bash
cronica concluir --ticket '<ticket>' <<'JSON'
{
  "jogador": "Ren avança pelo corredor lateral.",
  "narracao": "...",
  "resumo": "Ren entra sem alertar a patrulha.",
  "modo": "exploração",
  "deltas": []
}
JSON
```

`concluir` faz, dentro da mesma chamada:

1. **pré-validação read-only da transação** usando as mesmas funções do registrador;
2. **revalidação + confirmação da cena** usando `cena_mundo.confirm_scene`;
3. **registro do turno** usando `turno.register_transaction`;
4. emissão do rodapé canônico seguro.

A confirmação vem antes do registro porque `turno.register_transaction` pode disparar checkpoint temporal. Assim, uma passagem de horas ou amanhecer não altera o mundo entre a preparação narrada e a confirmação dessa própria cena.

## Portas explícitas de reparo

O fluxo normal deve preferir `concluir`, mas as fases continuam acessíveis:

```bash
cronica registrar --ticket '<ticket>' < turno.json
cronica confirmar --ticket '<ticket>'
```

`registrar` revalida o ticket antes de escrever. Se `concluir` já confirmou a cena e uma falha rara ocorreu depois, a mensagem de erro retorna `fase: falha_parcial`; nesse caso específico:

```bash
cronica registrar --ticket '<ticket>' --reparo-pos-confirmacao < turno.json
```

Esse modo não revalida a cena porque ela já foi confirmada; ele apenas reutiliza a idempotência de `turno.py` para terminar/reparar o registro.

## Compatibilidade

Continuam disponíveis e válidos:

- `endpoints.py cena`;
- `cena_mundo.py preparar|confirmar`;
- `turno.py registrar`;
- os respectivos atalhos Poetry existentes.

A Task 21 não cria um sexto endpoint, não move regras de recompensa/sidequest/mundo, não cria estado próprio e não muda o schema dos endpoints.

## Custo

O hot path preferencial passa a exigir **duas chamadas operacionais**: `preparar` e `concluir`. O ticket elimina a repetição de NPCs, local, ação, tier, risco, tags, instante e modificadores entre as fases.

A orquestração adiciona zero arquivos persistentes, zero schedulers, zero scans e zero semântica nova de turno. Qualquer ganho real de inferências/tokens deve ser medido depois em rollout; o contrato proíbe declarar redução percentual sem essa amostra.
