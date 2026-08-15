# Ferramentas

Ferramentas locais de apoio para conduzir **Crônicas dos Reinos**.

## Rolador de dados

Usar `ferramentas/rolar-dados.py` sempre que uma rolagem aberta ou oculta exigir dado durante a preparação ou narração.

Exemplos:

```bash
python3 ferramentas/rolar-dados.py rolar 2d6+3
python3 ferramentas/rolar-dados.py d20 --bonus 5 --cd 15 --label "Teste de Furtividade"
python3 ferramentas/rolar-dados.py ren pericia furtividade --cd 15
python3 ferramentas/rolar-dados.py ren salvaguarda destreza --cd 13
python3 ferramentas/rolar-dados.py ren iniciativa
python3 ferramentas/rolar-dados.py ren ataque wakizashi --ca 14
python3 ferramentas/rolar-dados.py ren dano wakizashi --critico
python3 ferramentas/rolar-dados.py npc d20 --nome "Guarda" --bonus 3 --cd 12 --label "Percepção"
python3 ferramentas/rolar-dados.py npc ataque --nome "Bandido" --arma "espada curta" --bonus-ataque 4 --dano 1d6+2 --tipo-dano perfurante --ca 16
```

Atalhos atuais de Ren:

```bash
python3 ferramentas/rolar-dados.py ren listar
```

Saídas públicas podem ser copiadas para a transcrição da sessão. Rolagens ocultas devem ser registradas apenas na área do narrador quando forem relevantes.

## Consulta única de contexto

`ferramentas/contexto.py` é a interface preferencial para leituras durante narração e preparação. Ela evita abrir arquivos acumulativos inteiros quando uma consulta específica basta.

Comandos principais:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py buscar "ponte baixa"
```

Desde a Etapa 6, `npc`, `relacao` e `conhecimento` não leem mais os antigos depósitos monolíticos. A ferramenta resolve internamente **índice → fragmento**:

- relações: `estado/relacoes/index.yaml` → `estado/relacoes/<id>.yaml`;
- medidores: `estado/npcs/index.yaml` → `estado/npcs/<id>.yaml`;
- conhecimento: `personagens/jogador/conhecimento/ativo.yaml`/`index.yaml` → fragmentos Markdown relevantes.

O histórico completo de uma relação permanece em `historico/relacoes/<id>.yaml`, mas não é lido por `relacao` ou `npc` normalmente. Para uma pergunta histórica, escalar deliberadamente.

A busca genérica exclui por padrão `narrador/`, `historico/` e transcrições completas. A escalada precisa ser deliberada:

```bash
python3 ferramentas/contexto.py buscar "sol apagado" --reservado
python3 ferramentas/contexto.py buscar "frase exata" --historico
```

A saída padrão é YAML e possui orçamento de 8 KiB. O teto técnico é 16 KiB; quando necessário, o resultado é compactado antes da impressão. Também é possível pedir JSON:

```bash
python3 ferramentas/contexto.py --json status
python3 ferramentas/contexto.py --max-bytes 4096 npc nera
```

Por padrão a ferramenta anexa **somente metadados** da consulta a `runtime/consultas-contexto.jsonl`: comando, termo, nível, quantidade de fontes, bytes devolvidos e se houve truncamento. Esse arquivo é ignorado pelo Git e não contém o conteúdo lido. Para testes ou uso sem telemetria local:

```bash
python3 ferramentas/contexto.py --sem-log status
```

Semântica rápida:

- `status`: somente `runtime/contexto.yaml`;
- `cena`: estado quente + `runtime/cena.yaml`;
- `npc`: um fragmento de medidores +, quando houver, um fragmento da relação atual;
- `relacao`: índice pequeno + um fragmento da relação atual; apenas aponta para o histórico;
- `conhecimento`: pesquisa os fragmentos do conhecimento de Ren e devolve os três trechos mais relevantes;
- `regra`: seções relevantes dos resumos internos de regras;
- `buscar`: descoberta limitada; com `--historico`, inclui histórico frio e transcrições.

## Estado quente (`runtime/`)

A camada operacional rápida é gerada deterministicamente a partir das fontes canônicas:

```bash
python3 ferramentas/gerar-runtime.py
```

Isso atualiza `runtime/contexto.yaml` e `runtime/cena.yaml`. Não altera `estado/`, ficha, sessões ou outros arquivos canônicos.

Para validar sem escrever:

```bash
python3 ferramentas/gerar-runtime.py --check
```

O CI executa esse modo automaticamente. Se o estado canônico mudar sem regeneração, a verificação falha em vez de permitir que o narrador use contexto quente obsoleto.

`runtime/eventos-pendentes.jsonl` já existe como reservatório para a futura arquitetura transacional, mas ainda não substitui a consolidação atual da campanha.

## Estado corrente e memória fragmentada

A Etapa 5 separou presente de cronologia em `estado/estado-atual.yaml` e `estado/tempo.yaml`. A Etapa 6 fez o mesmo com memórias acumulativas.

Verificações permanentes:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
```

`migrar-memorias-fragmentadas.py --check` comprova que:

- as cópias pré-migração de relações, medidores e conhecimento mantêm os blobs Git originais;
- todos os IDs de relações/NPCs continuam representados;
- cada fragmento atual respeita o limite de tamanho;
- o histórico completo de cada relação continua logicamente idêntico ao legado;
- a concatenação ordenada dos fragmentos de conhecimento reconstrói **byte a byte** o antigo `conhecimento.md`.

`reindexar-conhecimento.py --check` protege a divisão das descobertas por cabeçalhos `Sessão NNN` e garante que o recorte ativo acompanhe a sessão corrente quando ela possui entradas explícitas.

## Verificação de integridade

Durante a refatoração de economia de contexto, usar:

```bash
python3 -m pip install -r requirements-dev.txt
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
```

Para comparar o estado atual com a fotografia lógica criada antes da migração:

```bash
python3 ferramentas/verificar-integridade.py \
  --baseline baseline/estado-logico-2026-08-15.yaml
```

O verificador confere UTF-8, YAML sem chaves duplicadas, arquivos obrigatórios, referências de `campanha.yaml`, existência da sessão atual, consistência básica entre estado e ficha, limites de PV/Ki e coerência temporal.

As proteções acumuladas incluem:

- **Etapa 2:** `AGENTS.md` ≤ 12 KiB/180 linhas, seis documentos especializados e cobertura das 58 seções legadas;
- **Etapa 3:** runtime derivado ≤ 8 KiB e coerente com sessão, personagem, recursos, tempo e localização;
- **Etapa 4:** orçamento de saída, isolamento de material reservado/frio e consultas dirigidas;
- **Etapa 5:** estado/tempo correntes separados da cronologia e legado preservado;
- **Etapa 6:** relações, medidores e conhecimento fragmentados, reconstruíveis e consultáveis sem reabrir os monólitos.

## Análise de rollouts do Codex

Para medir o comportamento do Codex sem inserir telemetria dentro da narração:

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

A baseline pré-refatoração usada para comparação está em `baseline/rollout-2026-08-15.json`.
