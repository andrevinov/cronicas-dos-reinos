# Auditoria final e retorno ao jogo

Este documento define a aceitação final da refatoração de economia de contexto. Ele é material de **manutenção**, não instrução para cada turno.

## Objetivo

A migração só pode ser considerada concluída quando quatro coisas forem verdadeiras ao mesmo tempo:

1. a evidência histórica capturada antes da refatoração continua preservada;
2. todas as proteções acumuladas continuam verdes sobre o estado vivo da campanha;
3. um processo limpo consegue reconstruir a cena atual sem transcrição, histórico legado ou estado completo;
4. a própria auditoria não altera nenhum arquivo da campanha.

A porta única é:

```bash
python3 ferramentas/auditoria-final.py
```

Para relatório estruturado:

```bash
python3 ferramentas/auditoria-final.py --json
```

O comando deve terminar com **PRONTO PARA RETOMAR**. Qualquer gate falho produz **BLOQUEADO** e retorno não zero.

## Gate 1 — infraestrutura acumulada

A auditoria exige a presença das portas e contratos criados durante a migração: contexto dirigido, turno transacional, checkpoint, consolidação, memória de sessões, política da escada, textura narrativa dirigida, analyzer/comparador de rollout, baseline e metas.

Também falha imediatamente como gate se existir `runtime/consolidacao-em-andamento.json`. Nesse estado o repositório pode estar entre dois lados do mesmo commit lógico e a ação correta é:

```bash
python3 ferramentas/checkpoint.py recuperar
```

## Gate 2 — regressões e baseline histórica

A auditoria executa a suíte unitária completa e os verificadores acumulados:

```text
unittest completo
estado atual separado do histórico
memórias fragmentadas
reindexação de conhecimento
turno transacional
consolidação
memória fria/checkpoint
runtime derivado
integridade estrutural do estado vivo
imutabilidade da baseline lógica de 15/08/2026
```

A baseline de 15/08 é deliberadamente histórica. Durante a migração congelada, suas assertions também serviram para provar que reorganizar arquivos e protocolos não alterou silenciosamente fatos do jogo.

**Depois que a campanha voltou a avançar, a baseline não é mais um estado esperado do presente.** Exigir para sempre `08:03`, `resgate_rural` etc. transformaria a proteção em impedimento ao próprio jogo.

O gate permanente agora prova duas coisas separadas:

1. o estado vivo passa pelas verificações estruturais, transacionais e de consistência atuais;
2. `baseline/estado-logico-2026-08-15.yaml` permanece byte a byte igual ao artefato pré-refatoração.

A comparação antiga continua disponível deliberadamente com:

```bash
python3 ferramentas/verificar-integridade.py \
  --baseline baseline/estado-logico-2026-08-15.yaml
```

Usá-la somente quando a intenção explícita for comparar contra aquele instante histórico — por exemplo numa migração congelada — e não como gate normal depois de jogar.

Para verificar apenas a evidência histórica:

```bash
python3 ferramentas/verificar-integridade.py --verificar-baseline-historica
```

## Gate 3 — retomada apenas com a camada quente

A auditoria cria um diretório temporário contendo **somente**:

```text
runtime/contexto.yaml
runtime/cena.yaml
runtime/eventos-pendentes.jsonl
sessoes/index.yaml
sessoes/NNN/handoff.yaml
```

Ela não copia:

```text
sessoes/NNN/transcricao.md
estado/estado-atual.yaml
personagens/jogador/ficha.yaml
historico/
```

Em seguida executa `contexto.py retomada` apontando para esse repositório mínimo. O teste só passa se a ferramenta reconstruir sessão, personagem, recursos, data/hora, localização e resumo imediato de forma idêntica ao **estado efetivo atual (checkpoint + eventos pendentes)** e dentro do teto L2 de 8 KiB.

Portanto o sucesso não significa apenas “o código diz que não lê a transcrição”. Significa que a retomada **funcionou em um ambiente onde a transcrição sequer existia**.

## Gate 4 — pausa com deltas ainda pendentes

Uma retomada também precisa funcionar se o processo morrer depois de um turno e antes do próximo checkpoint.

A auditoria cria outro sandbox quente, injeta ali um delta sintético de Ki usando o mesmo schema de `transacoes.py` e exige que `contexto.py retomada` devolva:

- o recurso efetivo com o delta aplicado;
- o resumo do evento pendente;
- nenhuma necessidade de estado canônico ou transcrição.

Nada é escrito no buffer real da campanha. A presença de transações reais pendentes na campanha também é válida: a auditoria compara a retomada quente contra a projeção efetiva, não apenas contra o snapshot do último checkpoint.

## Gate 5 — telemetria pós-hoc

A infraestrutura de telemetria é exercitada com uma fixture de engenharia:

```bash
python3 ferramentas/analisar-rollout.py tests/fixtures/rollout-step11-mini.jsonl --json
python3 ferramentas/comparar-rollouts.py tests/fixtures/rollout-step11-mini.jsonl --json
```

Isso comprova que a medição está pronta. Números reais pós-refatoração só são legítimos quando vierem de avanços narrativos reais; não executar analyzer/comparador no meio de um turno.

## Gate 6 — privacidade dos rollouts

`git ls-files` é usado para garantir que nenhum `rollout-*.jsonl` bruto foi versionado fora de `tests/fixtures/`.

A regra permanece: não commitar `~/.codex`, sessões brutas ou arquivos que possam carregar contexto privado/secrets.

## Gate 7 — auditoria sem mutação

Antes do primeiro gate, a ferramenta calcula um digest de árvore das áreas de campanha:

```text
campanha.yaml
estado/
personagens/jogador/
sessoes/
narrador/
regras/
cenario/
runtime/
```

Ao final calcula novamente. Os hashes e a quantidade de arquivos precisam ser idênticos.

A auditoria é, portanto, também um teste de que **testar a campanha não muda a campanha**.

## Critério de retorno ao jogo

Quando `auditoria-final.py` e o CI estiverem verdes, a arquitetura está pronta para continuar a campanha.

Para uma interação normal:

1. não reler o repositório inteiro;
2. usar o contexto da conversa se suficiente;
3. se necessário, `contexto.py retomada`;
4. seguir a escada L0–L4T normalmente;
5. quando NPC/local precisarem de presença e o contexto não bastar, usar textura dirigida L2;
6. narrar com densidade apropriada — economia de contexto não é economia de prosa;
7. registrar o avanço com `turno.py registrar`;
8. medir o rollout somente depois, fora do loop.
