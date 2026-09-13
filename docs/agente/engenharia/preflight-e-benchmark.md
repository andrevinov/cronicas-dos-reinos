# Preflight e benchmark final

A Fase 7 fecha a reforma com dois gates diferentes. Eles não pertencem ao loop de narração ao vivo.

## 1. Preflight antes de push/merge

Com Poetry:

```bash
poetry run preflight
```

Ou diretamente:

```bash
python3 ferramentas/preflight.py
```

O preflight executa em sequência:

1. suíte unitária completa;
2. `turno.py check`;
3. `consolidar.py check`;
4. `sessoes.py check`;
5. `checkpoint.py check`;
6. migração/fragmentação/índice em modo `--check`;
7. `gerar-runtime.py --check`;
8. integridade estrutural/semântica;
9. preservação da baseline histórica;
10. auditoria final de retomada.

Ele não registra turno, não consolida, não abre sessão e não regenera runtime. Para depuração rápida é possível usar `--sem-testes`; para parar no primeiro erro, `--fail-fast`.

O GitHub Actions executa o mesmo `preflight.py` como gate de integração. Assim, passar no preflight local significa exercitar o mesmo orquestrador que será executado no CI.

## 2. Benchmark de rollouts reais

O comparador continua sendo diagnóstico:

```bash
poetry run rollout-comparar rollout-1.jsonl rollout-2.jsonl
```

O benchmark é um **gate de aceitação**:

```bash
poetry run rollout-benchmark rollout-1.jsonl rollout-2.jsonl
```

Ele lê `baseline/metas-benchmark-final.json` e exige, por padrão, pelo menos **5 avanços narrativos comuns** antes de emitir veredito. Menos que isso produz `AMOSTRA INSUFICIENTE`, não uma falsa aprovação/reprovação.

Critérios iniciais da Fase 7:

- redução de input bruto >= 70% contra a baseline pré-refatoração;
- média <= 5 inferências por avanço;
- média <= 5 tool calls por avanço;
- no máximo 1 writer bem-sucedido por avanço comum;
- no máximo 2 alvos efetivamente escritos por avanço comum;
- zero escrita canônica direta;
- zero tentativa/leitura de transcrição bruta;
- zero `.turno-temporario.json`;
- zero descoberta de schema/`--help` durante a narração;
- zero writer falho ou de resultado desconhecido;
- pelo menos 80% dos avanços em L0–L2 **limpo**, isto é, sem leitura RAW mascarada.

O benchmark retorna:

- exit `0`: `APROVADO`;
- exit `1`: amostra suficiente, mas uma ou mais metas falharam;
- exit `2`: `AMOSTRA INSUFICIENTE`.

`--min-turnos N` pode reduzir/aumentar o mínimo deliberadamente, principalmente para fixtures de engenharia. Não deve ser usado para transformar uma amostra real pequena em prova conclusiva.

## Escopo da medição

O gate final mede o **hot path de avanços narrativos comuns**. Fechamento/abertura de sessão, manutenção, auditoria e migração são operações raras e devem ser inspecionadas separadamente. Misturá-las deliberadamente à amostra para melhorar ou piorar a média destrói a utilidade da métrica.

Rollouts brutos continuam locais. Nenhum dos dois comandos copia JSONL do Codex para o repositório.
