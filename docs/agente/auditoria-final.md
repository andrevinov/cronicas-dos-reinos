# Auditoria final e retorno ao jogo

Este documento define a aceitação final da refatoração de economia de contexto. Ele é material de **manutenção**, não instrução para cada turno.

## Objetivo

A migração só pode ser considerada concluída quando quatro coisas forem verdadeiras ao mesmo tempo:

1. o cânone essencial capturado antes da refatoração continua preservado;
2. todas as proteções acumuladas das etapas 2–11 continuam verdes;
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

A auditoria exige a presença das portas e contratos criados durante a migração: contexto dirigido, turno transacional, checkpoint, consolidação, memória de sessões, política da escada, analyzer/comparador de rollout, baseline e metas.

Também falha imediatamente como gate se existir `runtime/consolidacao-em-andamento.json`. Nesse estado o repositório pode estar entre dois lados do mesmo commit lógico e a ação correta é:

```bash
python3 ferramentas/checkpoint.py recuperar
```

## Gate 2 — regressões e baseline original

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
integridade estrutural
baseline lógica de 15/08/2026
```

A baseline de 15/08 é deliberadamente histórica. Durante esta migração ela serve para provar que reorganizar arquivos e protocolos não alterou silenciosamente fatos do jogo.

Depois que a campanha voltar a avançar, essa baseline não deve ser reinterpretada como estado atual; ela continuará sendo evidência do ponto anterior à refatoração.

## Gate 3 — retomada apenas com a camada quente

Este é o teste mais importante da Etapa 12.

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

Em seguida executa `contexto.py retomada` apontando para esse repositório mínimo. O teste só passa se a ferramenta reconstruir sessão, personagem, recursos, data/hora, localização e resumo imediato de forma idêntica ao runtime real e dentro do teto L2 de 8 KiB.

Portanto o sucesso não significa apenas “o código diz que não lê a transcrição”. Significa que a retomada **funcionou em um ambiente onde a transcrição sequer existia**.

## Gate 4 — pausa com deltas ainda pendentes

Uma retomada também precisa funcionar se o processo morrer depois de um turno e antes do próximo checkpoint.

A auditoria cria outro sandbox quente, injeta ali um delta sintético de Ki usando o mesmo schema de `transacoes.py` e exige que `contexto.py retomada` devolva:

- o recurso efetivo com o delta aplicado;
- o resumo do evento pendente;
- nenhuma necessidade de estado canônico ou transcrição.

Nada é escrito no buffer real da campanha.

## Gate 5 — telemetria pós-hoc

A infraestrutura da Etapa 11 é exercitada com uma fixture de engenharia:

```bash
python3 ferramentas/analisar-rollout.py tests/fixtures/rollout-step11-mini.jsonl --json
python3 ferramentas/comparar-rollouts.py tests/fixtures/rollout-step11-mini.jsonl --json
```

Isso comprova que a medição está pronta. **Não existe ainda um número real pós-refatoração de economia**, porque o jogo foi suspenso durante a migração. Esse número só será legítimo depois que novos avanços narrativos gerarem rollout real.

Não executar analyzer/comparador no meio de um turno.

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

Quando `auditoria-final.py` e o CI final estiverem verdes, a migração pode ser considerada concluída.

Para a primeira interação depois da reforma:

1. não reler o repositório inteiro;
2. usar o contexto da conversa se suficiente;
3. se necessário, `contexto.py retomada`;
4. seguir a escada L0–L4T normalmente;
5. registrar o avanço com `turno.py registrar`;
6. medir o rollout somente depois, fora do loop.

A Etapa 12 não cria um novo protocolo de jogo. Ela prova que os protocolos criados nas etapas anteriores funcionam juntos.
