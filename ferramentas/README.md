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

### Núcleo mecânico interno

`dados` continua sendo a interface pública. A matemática compartilhada de d20, testes, salvaguardas, ataques, vantagem/desvantagem, críticos e dano fica em `mecanica_dnd_5_5e.py`; consumidores operacionais não devem chamar esse módulo diretamente. Durante a migração, isso não ativa 5.5e por si só: `campanha.yaml` continua sendo a autoridade do ruleset em uso.

### Mecânica vinculada ao turno

Quando um turno tiver consequência mecânica persistente, `cronica preparar` pode receber `--mecanica-json` com as regras e obrigações. A resposta devolve os IDs canônicos e congela tudo no mesmo ticket. Depois da rolagem com `dados`, `cronica concluir` recebe um bloco `mecanica.resolucoes`; o writer só vê a transação depois da validação causal.

Turnos puramente narrativos omitem esse argumento e não pagam leituras mecânicas adicionais. Gastos de Ki/Focus nunca devem ser enviados como delta isolado sem obrigação preparada.

Quando a mecânica foi preparada a partir de AD&D, o mesmo JSON acrescenta `proveniencia`. O gate exige edição de origem, destino moderno e fonte mecânica; números antigos literais são recusados antes do ticket. Uma adaptação 5.5e pode existir como preparação durante a migração, mas não entra no runtime enquanto 2014 estiver ativo.

Verificação do registro de adaptações antigas:

```bash
python3 ferramentas/gate_adnd.py check
```

Material AD&D puramente narrativo não precisa ser registrado. Uso AD&D→2014 é fallback explícito e precisa carregar motivo + decisão.

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

## Lifecycle unificado da campanha

Depois da Task 22, `cronica` também é a porta preferencial para sessão e level-up:

```bash
cronica sessao status
cronica sessao checkpoint
cronica sessao encerrar
cronica progressao status
cronica progressao aplicar < plano-nivel.yaml
cronica sessao iniciar
cronica sessao recuperar
```

`encerrar`, `checkpoint`, `iniciar` e `recuperar` delegam às mesmas autoridades anteriores (`checkpoint.py`/`sessoes.py`); não existe segundo lifecycle. Abertura continua criando somente N+1 e nunca copia a transcrição anterior.

Na faixa 8–17, `cronica progressao aplicar` exige o milestone correspondente já registrado pela Task 19. O plano mecânico informa alterações da ficha e o novo resumo de poderes, mas não pode escolher `identidade.nivel`; o lifecycle força exatamente o próximo nível desbloqueado. Ficha, espelhos, resumo, experiência, runtime, handoff e índice entram no mesmo journal recuperável.

As primitivas antigas continuam disponíveis para diagnóstico/manutenção.

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

`ferramentas/contexto.py` é a interface preferencial para leitura. `ferramentas/politica_acesso.py` aplica a escada e os tetos.

L1/L2:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py sessao atual
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
```

Busca L3:

```bash
python3 ferramentas/contexto.py buscar "ponte baixa" \
  --apos L2 --motivo "As consultas dirigidas não localizaram o domínio da pista."
```

Sessão histórica conhecida pode saltar busca ampla:

```bash
python3 ferramentas/contexto.py sessao 2 \
  --apos L2 --motivo "A pergunta aponta diretamente para a sessão 002 e seu resumo."
```

Semântica principal:

- `status`: L1, snapshot-base + deltas correntes;
- `retomada`: L2, runtime + cena + handoff atual + resumos pendentes, sem transcrição;
- `cena`: L2, contexto + cena com sobreposição;
- `sessao atual`: L2;
- `sessao N` histórica: L4 dirigido, sem transcrição;
- `npc`, `relacao`, `conhecimento`, `regra`: L2;
- `buscar`: L3 e exige escalada declarada.

### Histórico em dois degraus

Por padrão a busca exclui material reservado, `historico/` e transcrições.

L4:

```bash
python3 ferramentas/contexto.py buscar "frase exata" \
  --historico --apos L3 --motivo "A busca corrente não contém a origem histórica necessária."
```

`--historico` acrescenta histórico estruturado, handoffs/resumos/alterações e históricos específicos, **mas ainda não abre transcrições**.

Somente como L4T:

```bash
python3 ferramentas/contexto.py buscar "frase exata" \
  --historico --transcricoes --apos L4 \
  --motivo "O histórico estruturado não contém a formulação exata necessária."
```

`--transcricoes` sem `--historico` é recusado. `--reservado` também exige motivo concreto.

### Tetos de contexto

A política impõe:

```text
L1   4 KiB
L2   8 KiB
L3   8 KiB
L4  12 KiB
L4T 16 KiB
```

`--max-bytes` só reduz o teto. Pedir 16 KiB em `status` continua limitado a 4 KiB. Cada saída inclui `controle_acesso.pare_se_suficiente` para lembrar o agente de interromper a busca quando a lacuna estiver resolvida.

Detalhes: `docs/agente/escada-de-acesso.md`.

Telemetria local fica **desligada por padrão**. Para um diagnóstico pontual, use `--log-local`; o arquivo `runtime/consultas-contexto.jsonl` continua local/ignorado. A medição normal é pós-hoc pelo rollout nativo.

### Núcleo e porta pública

- `contexto_core.py`: mecanismo de índices/fragmentos herdado;
- `contexto.py`: porta pública com overlay, memória de sessão e política de acesso;
- `politica_acesso.py`: classificação, escalada, motivos e tetos;
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
- **Etapa 9:** handoff/índice, retomada sem transcript, histórico em dois degraus e transcrições frias;
- **Etapa 10:** escada executável, `--apos`/`--motivo`, saltos dirigidos e tetos por nível;
- **Etapa 11:** telemetria pós-hoc, comparação antes/depois, metas mensuráveis e zero logging local por padrão.

## Telemetria pós-hoc de rollouts

Não medir dentro do loop narrativo. Depois da sessão:

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

Comparação automática com a baseline de 15/08:

```bash
python3 ferramentas/comparar-rollouts.py ~/.codex/sessions/.../rollout-novo.jsonl
```

Várias sessões podem ser agregadas passando vários arquivos. O comparador normaliza por avanço narrativo e mostra input bruto, não-cache aproximado, inferências, tools, leituras/escritas, transcript e distribuição L0–L4T.

Arquivos de referência:

- `baseline/rollout-2026-08-15.json`;
- `baseline/metas-rollout-pos-refatoracao.json`;
- `baseline/telemetria-step-11.md`;
- `docs/agente/telemetria-rollouts.md`.

Redução de tokens é tratada como tráfego operacional, não como fórmula de cobrança/quota.