# Perfis de execução da suíte de testes

Este documento define os perfis de teste usados durante desenvolvimento e diagnóstico.

A existência de perfis menores **não reduz o gate final**. A suíte completa continua obrigatória antes do merge, e o workflow `Integridade da campanha` continua sendo o dono da execução integral no GitHub Actions.

## `test-fast` — feedback rápido

```bash
poetry run test-fast
```

Use durante desenvolvimento para obter feedback curto sobre uma seleção explícita de testes rápidos e determinísticos, com foco em:

- unidades;
- contratos pequenos;
- mecânicas;
- parsers;
- validações;
- funções puras.

O perfil é uma allowlist curada em `ferramentas/testes.py`. Ele não tenta adivinhar velocidade pelo nome do teste e não substitui `test-full`.

Para apenas inspecionar quais arquivos fazem parte do perfil:

```bash
poetry run test-fast --list
```

## `test-domain` — diagnóstico relacionado à alteração

```bash
poetry run test-domain mecanica
poetry run test-domain cronica
poetry run test-domain sessoes
poetry run test-domain sidequests
poetry run test-domain mundo
poetry run test-domain runtime
```

As formas acentuadas em português também são aceitas, por exemplo:

```bash
poetry run test-domain mecânica
poetry run test-domain crônica
poetry run test-domain sessões
```

Mais de um domínio pode ser combinado; arquivos sobrepostos são executados uma única vez:

```bash
poetry run test-domain cronica mundo
```

O objetivo é investigação e feedback focado. Os domínios podem se sobrepor deliberadamente porque uma mesma regressão pode proteger mais de uma área.

A regressão histórica permanente de “Sete Nomes” pertence simultaneamente a
`sidequests`, `cronica`, `mundo` e `sessoes`. Ela usa `TemporaryDirectory` e um
snapshot em `tests/fixtures/historical/`; nenhum desses perfis escreve no estado
vivo do repositório.

Para listar os arquivos sem executar:

```bash
poetry run test-domain mundo --list
```

## `test-full` — suíte integral

```bash
poetry run test-full
```

Executa exatamente:

```text
python -m unittest discover -s tests -v
```

Esse é o perfil **obrigatório antes do merge** e corresponde à suíte integral mantida no workflow de Integridade.

O comando legado continua válido e é apenas um alias:

```bash
poetry run testes
```

Para listar os arquivos alcançados pelo padrão de discovery sem executar:

```bash
poetry run test-full --list
```

## `preflight` — gate local completo

```bash
poetry run preflight
```

`preflight` continua sendo o grande comando local de confiança. Ele executa a suíte completa e, depois, os gates estruturais, transacionais, de memória, runtime, integridade, baseline, auditoria e retomada.

No GitHub Actions, conforme a política da Task 4, a suíte completa é executada uma única vez por `Integridade`; o workflow de Preflight roda seus demais gates com `--sem-testes`.

## Fluxo recomendado

Durante uma alteração:

```text
mudança pequena
    ↓
test-fast
    ↓
test-domain <área afetada>
    ↓
test-full
    ↓
preflight
    ↓
PR / merge
```

Os dois primeiros passos aceleram feedback. Os dois últimos preservam a confiança final.

## Paralelização e sharding

Esta Task não divide a suíte da CI em shards. Os perfis de domínio são ferramentas de desenvolvimento e podem se sobrepor; portanto não constituem, por si só, prova de independência entre grupos.

Qualquer paralelização futura deve ser uma decisão separada, apoiada por telemetria e por evidência de que os grupos podem rodar independentemente sem reduzir cobertura ou permitir merge com algum grupo vermelho.
