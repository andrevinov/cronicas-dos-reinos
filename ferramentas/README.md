# Ferramentas

Ferramentas locais de apoio para conduzir **Crônicas dos Reinos** com leitura e escrita econômicas.

## Rolador de dados

Usar `ferramentas/rolar-dados.py` para uma rolagem individual:

```bash
python3 ferramentas/rolar-dados.py rolar 2d6+3
python3 ferramentas/rolar-dados.py d20 --bonus 5 --cd 15 --label "Teste de Furtividade"
python3 ferramentas/rolar-dados.py ren pericia furtividade --cd 15
python3 ferramentas/rolar-dados.py ren salvaguarda destreza --cd 13
python3 ferramentas/rolar-dados.py ren iniciativa
python3 ferramentas/rolar-dados.py ren ataque wakizashi --ca 14
python3 ferramentas/rolar-dados.py npc d20 --nome "Guarda" --bonus 3 --cd 12 --label "Percepção"
```

Atalhos de Ren:

```bash
python3 ferramentas/rolar-dados.py ren listar
```

### Rolagens em lote

Quando duas ou mais rolagens independentes já forem necessárias antes de conhecer qualquer resultado, usar `rolar-lote.py`:

```bash
python3 ferramentas/rolar-lote.py <<'JSON'
[
  ["ren", "pericia", "furtividade", "--cd", "14"],
  ["npc", "d20", "--nome", "Guarda", "--bonus", "3", "--cd", "12"]
]
JSON
```

O lote usa o mesmo `rolar-dados.py`; não muda regras nem RNG. Não agrupar rolagem cuja necessidade depende de resultado anterior.

## Registrador transacional de turno

`ferramentas/turno.py` é a interface preferencial de **escrita durante narração ao vivo**.

```bash
python3 ferramentas/turno.py registrar <<'JSON'
{
  "jogador": "Ren avança sobre o alvo.",
  "narracao": "...",
  "resumo": "Ren alcança o alvo e gasta 1 Ki.",
  "modo": "combate",
  "deltas": [
    {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -1}
  ]
}
JSON
```

Por turno comum, altera somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

A transcrição é completa e append-only, mas **fria para leitura**. O JSONL recebe somente resumo curto, deltas e rolagens ocultas relevantes.

Segurança:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/turno.py status
```

O registro é idempotente. Se houver interrupção entre as duas escritas, repetir a mesma entrada repara apenas o lado ausente.

## Schema dos deltas

Operações: `set`, `inc`, `append`, `remove`, `registrar`.

Alvos suportados pela consolidação:

```text
estado
tempo
ficha
progressao
relacao:<id>
npc:<id>
conhecimento
consequencia
relogio:<id>
```

Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.pontos_de_vida.atuais","valor":-7}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04"}
{"alvo":"relacao:kethra_dunn","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
{"alvo":"consequencia","op":"registrar","valor":{"titulo":"Dívida aberta","descricao":"Pode voltar a importar."}}
```

`visibilidade: narrador` mantém conteúdo reservado fora de consultas públicas. O consolidador recusa um delta reservado destinado a domínio público.

## Checkpoint de cena e sessão

A porta operacional é `ferramentas/checkpoint.py`. Ela executa o motor canônico da Etapa 8 e depois atualiza a memória compacta da Etapa 9.

```bash
python3 ferramentas/checkpoint.py cena
python3 ferramentas/checkpoint.py sessao
python3 ferramentas/checkpoint.py status
python3 ferramentas/checkpoint.py check
```

Não usar depois de cada turno. O checkpoint deve ser muito menos frequente que o avanço narrativo.

### Fase canônica: `consolidar.py`

`ferramentas/consolidar.py` continua responsável pela parte atômica e idempotente:

- valida transações pendentes;
- calcula todos os documentos finais antes da primeira escrita;
- sincroniza PV, Ki, CA, dinheiro, nível e tempo entre representações espelhadas;
- atualiza apenas relações/NPCs realmente afetados e seus históricos;
- materializa conhecimento incremental sem modificar fragmentos legados;
- consolida consequência/progressão somente quando há delta explícito;
- mantém rolagens ocultas e relógios na área reservada;
- atualiza artefatos de sessão preservando texto manual fora de seções automáticas;
- instala o runtime do novo estado;
- remove do buffer as transações aplicadas **por último**.

Cada lote entra em `sessoes/NNN/consolidacoes.jsonl`, impedindo reaplicação de IDs já incorporados.

### Fase derivada: memória compacta

Depois do cânone instalado, `checkpoint.py` deriva:

```text
sessoes/NNN/handoff.yaml
sessoes/index.yaml
```

Esses arquivos são cache de leitura, não cânone. Se o processo cair depois da consolidação e antes do handoff, reconstruí-los não executa nenhum delta novamente.

### Recuperação

Se houver journal canônico:

```text
runtime/consolidacao-em-andamento.json
runtime/.consolidacao-stage/
```

não continuar o jogo. Usar:

```bash
python3 ferramentas/checkpoint.py recuperar
```

A recuperação instala os mesmos bytes staged sem recalcular `inc` e depois reconstrói a memória compacta. Sem journal, o comando também pode reparar apenas handoff/índice.

Detalhes canônicos: `docs/agente/consolidacao-transacional.md`. Memória: `docs/agente/memoria-de-sessoes.md`.

## Memória fria de sessões

`ferramentas/sessoes.py` mantém a camada de retomada sem reler transcrições.

```bash
python3 ferramentas/sessoes.py status
python3 ferramentas/sessoes.py sessao 2
python3 ferramentas/sessoes.py check
python3 ferramentas/sessoes.py reindexar
python3 ferramentas/sessoes.py bootstrap-atual
```

- `sessoes/index.yaml`: índice pequeno de sessões e artefatos compactos;
- `sessoes/NNN/handoff.yaml`: checkpoint de retomada com teto de 8 KiB;
- `transcricao.md`: registro completo, mas classificado como arquivo frio para leitura.

O handoff é construído de runtime/cena + resumos do ledger. Ele **não lê nem copia prosa da transcrição**.

Sessões legadas podem não possuir handoff. Nesse caso `sessoes.py sessao N` prefere resumo e alterações estruturadas disponíveis e continua sem abrir a transcrição.

## Consulta única de contexto

`ferramentas/contexto.py` é a interface preferencial para leitura.

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py sessao 2
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

Semântica principal:

- `status`: snapshot-base + deltas correntes;
- `retomada`: runtime + cena + handoff atual + resumos de eventos pendentes recentes, sem transcrição;
- `cena`: contexto + cena com sobreposição;
- `sessao N`: handoff ou fallback compacto de uma sessão, sem transcrição;
- `npc`: fragmentos de medidores/relação + deltas da entidade;
- `relacao`: um fragmento + deltas pendentes;
- `conhecimento`: fragmentos consolidados + incrementais recentes + descobertas pendentes;
- `regra`: resumos internos;
- `buscar`: descoberta limitada.

### Histórico em dois degraus

Por padrão a busca exclui material reservado, `historico/` e transcrições.

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

`--historico` acrescenta histórico estruturado, handoffs/resumos/alterações e históricos específicos, **mas ainda não abre transcrições**.

Somente como última escalada local:

```bash
python3 ferramentas/contexto.py buscar "frase exata" --historico --transcricoes
```

`--transcricoes` sem `--historico` é recusado.

A saída padrão possui orçamento de 8 KiB e teto de 16 KiB:

```bash
python3 ferramentas/contexto.py --json status
python3 ferramentas/contexto.py --max-bytes 4096 npc nera
```

Telemetria opcional grava somente metadados em `runtime/consultas-contexto.jsonl`; desabilitar com `--sem-log`.

### Núcleo e porta pública

- `contexto_core.py`: mecanismo de índices/fragmentos herdado;
- `contexto.py`: porta pública com sobreposição, memória de sessão e política de transcrições frias;
- `transacoes.py`: schema/aplicação/busca de deltas;
- `sessoes.py`: handoff e índice de sessões.

Não chamar `contexto_core.py` na narração normal.

## Estado quente (`runtime/`)

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados do estado consolidado.

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

Eventos pendentes não tornam o snapshot-base obsoleto: `contexto.py` projeta a sobreposição em memória. Não regenerar a cada turno.

No runtime v2, a transcrição aparece apenas como `transcricao_fria`; os ponteiros operacionais são `retomada`, `handoff_atual` e `indice_sessoes`.

## Estado corrente e memória fragmentada

Verificações permanentes:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
```

Elas protegem o estado atual contra retorno da cronologia, blobs legados, entidades históricas e reconstrução byte a byte do conhecimento pré-Etapa 6. Novas relações/NPCs e conhecimento incremental podem evoluir sem modificar o legado preservado.

## Verificação de integridade

Para manutenção/checkpoint, não para cada turno:

```bash
python3 -m pip install -r requirements-dev.txt
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/sessoes.py check
python3 ferramentas/checkpoint.py check
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Baseline lógica:

```bash
python3 ferramentas/verificar-integridade.py --baseline baseline/estado-logico-2026-08-15.yaml
```

Proteções acumuladas:

- **Etapa 2:** `AGENTS.md` curto e cobertura normativa;
- **Etapa 3:** runtime-base pequeno e derivado;
- **Etapa 4:** consulta dirigida com orçamento rígido;
- **Etapa 5:** estado atual separado da cronologia;
- **Etapa 6:** relações/NPCs/conhecimento fragmentados e reconstruíveis;
- **Etapa 7:** turno limitado a transcrição + deltas, recuperação idempotente, overlay e rolagens em lote;
- **Etapa 8:** consolidação em lote com ledger, mirrors, staging/journal e isolamento reservado;
- **Etapa 9:** handoff/índice de sessão, retomada sem transcript, busca histórica em dois degraus e transcrições frias para leitura.

## Análise de rollouts do Codex

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

A baseline pré-refatoração está em `baseline/rollout-2026-08-15.json`; a baseline específica da memória fria está em `baseline/memoria-sessoes-step-09.md`.
