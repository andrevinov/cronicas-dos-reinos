# Task 21 — Unified `cronica` Turn CLI

`cronica` é a porta operacional preferencial para o ciclo normal de um turno. Ela **não substitui** `endpoints.py`, `cena_mundo.py` nem `turno.py`; reduz a orquestração entre essas autoridades.

## Fluxo normal: duas chamadas

### 1. Preparar

Todo turno pode começar apenas com um ID estável:

```bash
cronica preparar --cena-id s013-retorno-circo
```

Desde a Task 24, esta mesma porta começa pelo **Pending Gate**. O caminho livre segue exatamente o contrato abaixo; se houver pendências reais do Mundo Vivo, `preparar` retorna `fase: bloqueada_pendencias_mundo`, não emite ticket nem autoriza narração. A fila é resolvida pela Task 23 e então o mesmo `cronica preparar` é repetido. Detalhes: `docs/task24-pending-gate-cronica-preparar.md`.

Se **não existe gatilho reativo real**, essa chamada emite um **ticket neutro** read-only. Não chama endpoint de cena, não confirma cena inexistente e, sobretudo, não exige inventar tag/local/NPC para satisfazer a CLI.

Quando há entrada/exploração material de local, novo encontro de NPC ou tag contextual já pertinente, a mesma porta recebe os gatilhos reais. Exemplo local:

```bash
cronica preparar \
  --cena-id s013-porto \
  --local lower_trades \
  --acao entrar \
  --tier 2 \
  --periculosidade media
```

O quarteto local é atômico: `--local`, `--acao`, `--tier` e `--periculosidade` aparecem juntos ou são todos omitidos. Tier e risco não são inferidos silenciosamente pela CLI. Tags contextuais usam namespace `local:`, `assunto:`, `acao:`, `pessoa:` ou `risco:` e só devem ser fornecidas quando já forem pertinentes à situação.

Em preparação **reativa**, `preparar` chama o endpoint determinístico de cena uma única vez. Em preparação **neutra**, chama zero endpoints. Ambas devolvem:

- ticket autocontido com checksum;
- IDs/gates/modificadores compactos quando existirem;
- `reativa: true|false`;
- `contrato_conclusao`, com os cinco campos JSON exatos e a regra para mecânica explícita.

A saída de `preparar` é suficiente para a segunda fase. O hot path não precisa chamar `cronica concluir --help`, abrir documentação ou ler implementação para redescobrir a transação.

Quando `--data/--hora` foram fornecidos, o ticket preserva o instante explícito. Quando não foram, preserva `null`. As evidências da Task 20 (`preparacao`, `informacao`, `adequacao`) também viajam no ticket; no ticket neutro a rubrica continua pura e não exige cena artificial.

### 2. Narrar e concluir

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

Se a narração precisar exibir CD/CA/rolagem ou outra mecânica explícita, usar uma linha própria começando exatamente por:

```text
MECÂNICA — ...
```

Em ticket **reativo**, `concluir` executa:

1. pré-validação read-only da transação;
2. revalidação + confirmação da cena;
3. registro por `turno.register_transaction`;
4. rodapé canônico.

Em ticket **neutro**, não existe cena a confirmar: faz pré-validação → registro → rodapé. Isso preserva duas chamadas por turno sem fabricar mutação reativa.

A confirmação reativa continua antes do registro porque o registrador pode disparar checkpoint temporal. Assim uma passagem de horas/amanhecer não envelhece a preparação da própria cena.

## Portas explícitas de reparo

O fluxo normal prefere `concluir`, mas continuam disponíveis:

```bash
cronica registrar --ticket '<ticket>' < turno.json
cronica confirmar --ticket '<ticket>'
```

Para cena reativa já confirmada seguida de falha rara de registro:

```bash
cronica registrar --ticket '<ticket>' --reparo-pos-confirmacao < turno.json
```

Ticket neutro não produz `falha_parcial` de confirmação porque nenhuma confirmação ocorreu.

## Compatibilidade

Continuam disponíveis e válidos para manutenção/reparo:

- `endpoints.py cena`;
- `cena_mundo.py preparar|confirmar`;
- `turno.py registrar`;
- atalhos Poetry existentes.

Não há sexto endpoint, estado novo, scheduler, scan ou semântica paralela. O ticket neutro é apenas a representação explícita de “este turno não possui gatilho reativo”. O Pending Gate da Task 24 também não cria endpoint: reutiliza o marcador derivado e a semântica da barreira já existente.

## Rolagens comuns

Quando a perícia e a CD já estão definidas, a assinatura pública é estável:

```bash
poetry run rolar-dados ren pericia furtividade --cd 13 --label 'Furtividade de Ren'
```

Vantagem/desvantagem e evidências de abordagem são acrescentadas somente quando pertinentes. Não há razão para cascata de `--help` no hot path quando o roteador já forneceu a assinatura.

## Telemetria e custo

`cronica preparar` permanece read-only. No caminho livre, a Task 24 acrescenta somente a leitura do marcador minúsculo de pendências; não acrescenta endpoint nem altera o ticket/saída da Task 21. `concluir`/`registrar` continuam writers dos mesmos alvos operacionais do turno; `confirmar` só é mutante para ticket reativo. A preparação custa **0 ou 1 endpoint**, nunca mais de um; conclusão custa **0 ou 1 confirmação** e exatamente o registro necessário.

O alvo segue duas chamadas de orquestração por turno: `preparar` + `concluir`, além de rolagens/consultas materialmente necessárias. Ganho real continua sendo medido pós-hoc; nenhuma redução percentual é inferida sem rollout.