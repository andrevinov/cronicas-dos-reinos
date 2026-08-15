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

Quando duas ou mais rolagens independentes já forem necessárias antes de conhecer qualquer resultado, usar `rolar-lote.py` para reduzir ciclos modelo → ferramenta → modelo:

```bash
python3 ferramentas/rolar-lote.py <<'JSON'
[
  ["ren", "pericia", "furtividade", "--cd", "14"],
  ["npc", "d20", "--nome", "Guarda", "--bonus", "3", "--cd", "12"]
]
JSON
```

O lote usa o mesmo `rolar-dados.py`; não muda regras nem RNG. Não agrupar uma rolagem cuja necessidade depende do resultado anterior.

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
    {
      "alvo": "estado",
      "op": "inc",
      "caminho": "recursos.ki.atuais",
      "valor": -1
    }
  ]
}
JSON
```

Por turno comum, a ferramenta altera somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

Ela não atualiza diretamente ficha, estado, tempo, relações, conhecimento, consequências ou relógios. A prosa completa fica apenas na transcrição; o JSONL recebe resumo curto, deltas e rolagens ocultas relevantes.

Segurança:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/turno.py status
```

O registro é idempotente. Se houver interrupção entre as duas escritas, repetir exatamente a mesma entrada repara apenas o lado ausente.

## Schema dos deltas

Operações:

- `set`: substitui valor;
- `inc`: soma variação numérica;
- `append`: acrescenta item;
- `remove`: remove item/chave;
- `registrar`: guarda fato para consolidação sem alterar imediatamente um campo estruturado.

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

`visibilidade: narrador` mantém conteúdo reservado fora de consultas públicas. O consolidador recusa um delta reservado destinado a arquivos públicos.

## Consolidação automática de cena e sessão

`ferramentas/consolidar.py` transforma o buffer pendente em cânone **em lote**. Não usar depois de cada turno.

Checkpoint de cena importante:

```bash
python3 ferramentas/consolidar.py cena
```

Fechamento de sessão:

```bash
python3 ferramentas/consolidar.py sessao
```

Estado rápido:

```bash
python3 ferramentas/consolidar.py status
python3 ferramentas/consolidar.py check
```

O consolidador:

- valida as transações ainda pendentes;
- calcula em memória todos os documentos finais antes da primeira escrita;
- sincroniza representações espelhadas de PV, Ki, CA, dinheiro, nível e tempo;
- atualiza apenas relações/NPCs realmente afetados e registra a causa no histórico específico;
- materializa conhecimento novo em fragmentos incrementais sem modificar os fragmentos legados;
- consolida consequências/progressão somente quando há delta explícito;
- mantém rolagens ocultas e relógios na área reservada;
- atualiza os artefatos da sessão preservando texto manual fora das seções automáticas;
- prepara o novo runtime no mesmo lote;
- remove do buffer as transações aplicadas **por último**.

Cada lote entra em:

```text
sessoes/NNN/consolidacoes.jsonl
```

Esse ledger impede a reaplicação de IDs já incorporados.

### Segurança contra queda no meio da consolidação

Antes da instalação, os bytes finais ficam em staging e um journal registra hashes anteriores/finais:

```text
runtime/consolidacao-em-andamento.json
runtime/.consolidacao-stage/
```

Enquanto o journal existir, `contexto.py` e `turno.py` recusam operação normal. Não continue o jogo sobre um checkpoint parcialmente instalado.

Recuperação:

```bash
python3 ferramentas/consolidar.py recuperar
```

A recuperação instala os **mesmos bytes já preparados**; ela não recalcula o lote nem executa `inc` de novo. Se algum destino tiver sido editado externamente e possuir um terceiro hash, a ferramenta recusa sobrescrever silenciosamente.

Detalhamento: `docs/agente/consolidacao-transacional.md`.

## Consulta única de contexto

`ferramentas/contexto.py` é a interface preferencial para leitura durante narração e preparação.

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

Desde a Etapa 6, a consulta resolve índice → fragmento. Desde a Etapa 7, aplica também o buffer pendente sobre snapshots/fragmentos relevantes.

- `status`: snapshot-base + deltas correntes;
- `cena`: contexto + cena com sobreposição;
- `npc`: fragmentos de medidores/relação + deltas da entidade;
- `relacao`: um fragmento + deltas ainda pendentes;
- `conhecimento`: fragmentos consolidados — incluindo incrementais recentes — + descobertas pendentes;
- `regra`: resumos internos de regras;
- `buscar`: descoberta limitada.

A busca genérica exclui por padrão `narrador/`, `historico/` e transcrições completas:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

A saída padrão possui orçamento de 8 KiB e teto de 16 KiB:

```bash
python3 ferramentas/contexto.py --json status
python3 ferramentas/contexto.py --max-bytes 4096 npc nera
```

Telemetria opcional grava somente metadados em `runtime/consultas-contexto.jsonl`. Para desabilitar:

```bash
python3 ferramentas/contexto.py --sem-log status
```

### Núcleo e sobreposição

- `contexto_core.py`: mecanismo de índice/fragmento;
- `contexto.py`: porta pública com sobreposição transacional;
- `transacoes.py`: schema, aplicação e busca de deltas.

Não chamar `contexto_core.py` na narração normal, pois ele não aplica mudanças ainda pendentes.

## Estado quente (`runtime/`)

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base derivados do estado consolidado.

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

Eventos pendentes não tornam o snapshot-base obsoleto: `contexto.py` projeta a sobreposição em memória. Não regenerar a cada turno.

Depois de `consolidar.py`, o runtime correspondente ao novo checkpoint já foi calculado e instalado no mesmo lote; não regenerá-lo novamente por rotina.

## Estado corrente e memória fragmentada

Verificações permanentes:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
```

Elas protegem o estado atual contra retorno da cronologia, blobs legados, entidades históricas e reconstrução byte a byte do conhecimento pré-Etapa 6. Novas relações/NPCs e conhecimento incremental podem evoluir sem modificar o legado preservado.

## Verificação de integridade

Para manutenção/consolidação, não para cada turno:

```bash
python3 -m pip install -r requirements-dev.txt
python3 ferramentas/turno.py check
python3 ferramentas/consolidar.py check
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Baseline lógica:

```bash
python3 ferramentas/verificar-integridade.py \
  --baseline baseline/estado-logico-2026-08-15.yaml
```

Proteções acumuladas:

- **Etapa 2:** roteador `AGENTS.md` curto e cobertura normativa;
- **Etapa 3:** runtime-base pequeno e derivado;
- **Etapa 4:** consulta dirigida com orçamento rígido;
- **Etapa 5:** estado atual separado da cronologia;
- **Etapa 6:** relações/NPCs/conhecimento fragmentados e reconstruíveis;
- **Etapa 7:** escrita por turno limitada a transcrição + deltas, recuperação idempotente, estado efetivo por sobreposição e rolagens em lote;
- **Etapa 8:** consolidação em lote com ledger anti-reaplicação, mirrors consistentes, staging/journal recuperável e isolamento de material reservado.

## Análise de rollouts do Codex

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

A baseline pré-refatoração está em `baseline/rollout-2026-08-15.json`.
