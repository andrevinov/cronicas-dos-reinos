# Auditoria da suíte de testes

Esta auditoria implementa a etapa de inventário e telemetria da suíte sem
alterar testes existentes, cânone, estado vivo ou histórico.

## Baseline anterior à Task 1

No `main` em `fd132408` (`feat: activate D&D 5.5e ruleset (#103)`), o job de
Integridade concluiu a suíte padrão com:

- 1.254 testes;
- 69,081 s;
- resultado `OK`.

Essa medida é apenas o ponto de partida. Ela não informa em quais arquivos o
tempo está concentrado nem quais testes dependem do estado corrente da
campanha.

## Ferramenta

A auditoria está em:

```text
ferramentas/auditar-testes.py
```

O modo padrão é exclusivamente estático:

```bash
python ferramentas/auditar-testes.py
```

Para obter o relatório estruturado:

```bash
python ferramentas/auditar-testes.py --json
```

Para executar a mesma discovery usada pela suíte normal e medir cada teste:

```bash
python ferramentas/auditar-testes.py --medir
```

O relatório completo pode ser redirecionado para fora do repositório:

```bash
python ferramentas/auditar-testes.py --medir --json > /tmp/auditoria-testes.json
```

`--top N` controla quantos arquivos e testes aparecem no ranking resumido.

## Garantia de somente leitura

A ferramenta não possui operação de escrita nem argumento de saída para
arquivo. No modo estático ela apenas lê os fontes Python sob `tests/`.

`--medir` executa a suíte existente, portanto os próprios testes podem criar
arquivos em diretórios temporários como já fazem normalmente. A auditoria não
persiste artefatos no repositório.

O teste automatizado da ferramenta também verifica que duas execuções do
inventário estático produzem o mesmo resultado e não modificam o arquivo
analisado.

## O que é inventariado

O relatório separa:

- arquivos Python encontrados em `tests/`;
- arquivos incluídos no discovery padrão `test*.py`;
- auxiliares e smoke scripts que ficam fora desse padrão;
- quantidade de testes declarados identificada por AST;
- arquivos que fazem referência ao repositório real;
- arquivos que usam `TemporaryDirectory`, `tempfile` ou fixtures isoladas;
- leituras diretas reconhecíveis de estado vivo;
- assertions literais;
- classificações e candidatos de triagem.

As classificações são multi-rótulo. Um arquivo pode ser, por exemplo,
`integracao`, `contrato` e `task_historica` ao mesmo tempo.

As categorias disponíveis são:

```text
unitario
integracao
contrato
snapshot_historico
estado_vivo
regressao
smoke
performance
migracao
task_historica
```

## Estado vivo

A detecção de leitura direta procura operações como `open()`, `Path.open()`,
`read_text()` e `read_bytes()` sobre caminhos resolvíveis por AST.

São tratados como estado vivo, neste primeiro inventário:

```text
estado/**
runtime/**
personagens/jogador/ficha.yaml
sessoes/index.yaml
```

Referências a raízes usuais do repositório (`ROOT`, `REPO`, `REPO_ROOT` e
`ROOT_DIR`) também ajudam a identificar testes que usam o repositório real.

A distinção é intencional: um teste que chama um adaptador contra `REPO` pode
ser classificado como usuário do repositório real sem ser acusado de abrir
diretamente um arquivo de estado vivo.

## Candidatos de triagem

Os rótulos abaixo **não são vereditos** e nunca autorizam exclusão automática:

- `congelamento_suspeito`: leitura direta reconhecida de estado vivo combinada
  com assertion de igualdade contra literal;
- `congelamento_legitimo`: literal encontrado em teste que usa isolamento ou
  cenário de migração/snapshot, sem a combinação suspeita acima;
- `possivel_redundancia`: dois ou mais testes possuem corpo AST exatamente
  igual;
- `teste_transitorio`: arquivo/fonte associado a número histórico de Task;
- `teste_caro`: arquivo presente no ranking de custo da execução medida.

A Task 2 e a Task 3 devem revisar esses candidatos semanticamente. Em
particular, um falso positivo é preferível a apagar cobertura válida no escuro.

## Telemetria de duração

Com `--medir`, um `TextTestResult` instrumentado registra `perf_counter()` no
início e no fim de cada caso de teste. O relatório inclui:

- duração total;
- testes executados;
- falhas, erros e skips;
- duração por teste;
- duração agregada por arquivo;
- ranking dos arquivos mais caros;
- ranking dos testes mais caros.

A discovery é equivalente a:

```text
python -m unittest discover -s tests -v
```

Durações são naturalmente variáveis entre máquinas. O procedimento, o
conjunto medido e o formato do relatório são reproduzíveis; os números de
tempo não são tratados como snapshot rígido.

## Diagnóstico no GitHub Actions

O workflow `Auditoria da suíte de testes` executa a medição quando a própria
infraestrutura de auditoria é alterada e também pode ser disparado
manualmente. Ele não participa do fluxo normal de todos os PRs.

O relatório JSON completo é publicado como artifact do job. O log mostra um
resumo com as classificações, dependências de estado vivo, candidatos
suspeitos e rankings de custo.

## Limites conhecidos

A análise estática é deliberadamente conservadora. Ela não tenta executar
fluxo de dados completo nem adivinhar o que uma função chamada por um teste
abre internamente. Portanto:

- `estado_vivo` significa leitura direta detectável no teste;
- `repo_real` é uma categoria mais ampla;
- duplicidade significa igualdade estrutural do corpo, não equivalência
  semântica;
- classificações servem para organizar revisão humana.

Esses limites evitam que a ferramenta de inventário se transforme
acidentalmente em um mecanismo de alteração da suíte.
