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
python3 ferramentas/rolar-dados.py ren dano wakizashi --critico
python3 ferramentas/rolar-dados.py npc d20 --nome "Guarda" --bonus 3 --cd 12 --label "Percepção"
```

Atalhos atuais de Ren:

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

O lote apenas chama o mesmo `rolar-dados.py`; não muda regras nem RNG. Não agrupar uma rolagem cuja necessidade depende do resultado da anterior.

## Registrador transacional de turno

`ferramentas/turno.py` é a interface preferencial de **escrita durante narração ao vivo**.

Uma chamada registra simultaneamente a troca na transcrição e os deltas mínimos no buffer pendente:

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

Ela **não** atualiza ficha, estado, tempo, relações, conhecimento, consequências ou relógios. Esses destinos serão tratados pela consolidação da Etapa 8.

A prosa completa fica apenas na transcrição; o JSONL recebe resumo curto, deltas e rolagens ocultas relevantes.

Comandos de segurança:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/turno.py status
```

O registro é idempotente. Se houver interrupção entre as duas escritas, repetir exatamente a mesma entrada repara apenas o lado ausente.

## Schema dos deltas

Operações:

- `set`: substitui um valor;
- `inc`: soma variação numérica;
- `append`: acrescenta item;
- `remove`: remove item/chave;
- `registrar`: guarda fato para consolidação sem alterar imediatamente um campo estruturado.

Alvos usuais:

```text
estado
tempo
relacao:<id>
npc:<id>
conhecimento
consequencia
relogio:<id>
```

Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.pontos_de_vida.atuais","valor":-7}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04 de 7 Eleasis"}
{"alvo":"relacao:kethra_dunn","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
```

`visibilidade: narrador` impede que um delta reservado entre em consultas públicas normais. `rolagens_ocultas` pode ser incluído no registro da transação e será consolidado depois em área reservada.

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

Desde a Etapa 6, a consulta resolve índice → fragmento. Desde a Etapa 7, ela também aplica `runtime/eventos-pendentes.jsonl` sobre os fragmentos/snapshots relevantes.

Portanto:

- `status`: snapshot-base + deltas correntes de recursos/tempo/localização/modo;
- `cena`: contexto + cena com a mesma sobreposição;
- `npc`: fragmento de medidores/relação + deltas `npc:<id>`/`relacao:<id>`;
- `relacao`: um fragmento + deltas ainda pendentes daquela entidade;
- `conhecimento`: fragmentos consolidados + descobertas pendentes;
- `regra`: resumos internos de regras;
- `buscar`: fontes operacionais + resumos de eventos pendentes.

A busca genérica exclui por padrão `narrador/`, `historico/` e transcrições completas:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

A saída padrão é YAML com orçamento de 8 KiB e teto técnico de 16 KiB:

```bash
python3 ferramentas/contexto.py --json status
python3 ferramentas/contexto.py --max-bytes 4096 npc nera
```

A telemetria opcional de consultas grava somente metadados em `runtime/consultas-contexto.jsonl`. Para não registrar:

```bash
python3 ferramentas/contexto.py --sem-log status
```

### Núcleo e sobreposição

A implementação foi separada em:

- `contexto_core.py`: mecanismo de índice/fragmento da Etapa 6;
- `contexto.py`: porta pública que acrescenta a sobreposição transacional;
- `transacoes.py`: schema, aplicação e busca de deltas pendentes.

Não chamar `contexto_core.py` durante narração normal, pois ele não aplica mudanças ainda pendentes.

## Estado quente (`runtime/`)

`runtime/contexto.yaml` e `runtime/cena.yaml` são snapshots-base gerados deterministicamente a partir do estado consolidado:

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

A existência de eventos pendentes não torna esses arquivos obsoletos: `contexto.py` aplica a sobreposição em memória. Não regenerar os snapshots a cada turno.

`runtime/eventos-pendentes.jsonl` agora é buffer transacional ativo, não reservatório futuro.

## Estado corrente e memória fragmentada

Verificações permanentes:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
```

Elas protegem blobs legados, IDs, fragmentos atuais, histórico de relações e reconstrução byte a byte do antigo conhecimento acumulado.

## Verificação de integridade

Para manutenção/consolidação, não para cada turno:

```bash
python3 -m pip install -r requirements-dev.txt
python3 ferramentas/turno.py check
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
- **Etapa 7:** escrita de turno limitada a transcrição + deltas, recuperação idempotente, estado efetivo por sobreposição e rolagens em lote.

## Análise de rollouts do Codex

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

A baseline pré-refatoração está em `baseline/rollout-2026-08-15.json`.
