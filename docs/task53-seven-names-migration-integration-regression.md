# Task 53 — Seven Names Migration, Integration & Regression

## Status e dependências

**Implementada em 2026-09-01.** É a etapa final de integração das Tasks 48–52.

Esta Task não altera o passado narrado nem decide retroativamente qual reação Masao executará. Ela migra o estado operacional, prova o fluxo ponta a ponta e atualiza os contratos/documentação somente depois que a implementação estiver verde.

## Problema

“Sete Nomes Antes do Amanhecer” é o caso real que revelou as lacunas:

- missão aceita ausente do hot path;
- fatos posteriores à calaria não incorporados ao progresso;
- verificador substituto não reconhecido;
- terminal ainda `null` apesar de forte progresso factual;
- contrato adversarial original estreito demais para repercussões posteriores;
- nenhuma reavaliação de reação após captura de agente e apreensão de provas;
- ausência de cobertura end-to-end que atravesse oportunidade, aceite, progresso emergente, sucesso e reação.

## Objetivo

Migrar a sidequest atual sem retcon, criar uma regressão histórica isolada e provar que o sistema novo:

1. projeta a missão ativa;
2. reconhece fatos canônicos já existentes;
3. aceita Luath como substituto institucional quando a evidência sustentar;
4. encerra a missão somente quando todas as condições estiverem satisfeitas;
5. avalia reação de Masao em contrato separado;
6. pode preparar pressões simultâneas sem garanti-las;
7. mantém suíte, estado vivo e orçamentos limpos.

## Implementação

### Migração idempotente

Adicionar uma migração de domínio com dry-run obrigatório. Ela deve:

- localizar a missão por `mission_id` ou `quest_id`;
- validar Tasks 41/43/44/45 e respectivos digests;
- preservar byte a byte o contrato adversarial original;
- indexar a missão aceita para a Task48;
- importar somente fatos com fonte e evidência literal canônica;
- registrar substituição de ator apenas quando presença, competência e atuação estiverem provadas;
- recalcular condições sem presumir o próximo turno;
- marcar `necessita_reavaliacao_reacao` quando houver fato causal suficiente;
- não materializar ataque, encontro, morte, soltura ou invasão durante a migração.

Se a evidência consolidada ainda não satisfizer formalmente a verificação institucional, a missão permanece aceita e o próximo turno recebe a fase aberta. A migração não completa a frase que Luath ainda não disse.

### Reação sucessora de “Sete Nomes”

Depois do fato terminal ou do marco excepcional apropriado, a avaliação poderá considerar, sem garantir:

- vigilância ou ataque à Casa da Aurora Menor;
- emboscada à transferência da cativa e das provas;
- especialista tentando tomar matriz/documentos durante distração;
- fraude institucional para libertação;
- extração furtiva ou invasão da custódia;
- tentativa de silenciar a testemunha;
- operações simultâneas contra comitiva e Casa.

Cada alternativa depende do estado canônico de conhecimento, capacidades, presença e recursos de Masao, Kurobane e demais agentes. A migração não adiciona automaticamente nenhum desses fatos aos antagonistas.

### Snapshot histórico controlado

Criar, se necessário, fixture sob nome de domínio, por exemplo:

```text
tests/fixtures/historical/seven-names-session-017-end.yaml
```

O arquivo deve declarar:

- `natureza: snapshot_historico_isolado`;
- instante: fim da Sessão 017;
- motivo: reproduzir a regressão que deixou sidequest aceita atrás da ficção;
- aviso de que não representa o estado vivo futuro.

O snapshot conterá apenas os fragmentos mínimos: oportunidade/missão, quest, progresso, stakes, fatos estruturados necessários, tempo e atores relevantes. Não copiará transcrição integral.

### Atualização operacional após implementação

Somente depois da migração e da suíte verde:

- atualizar `AGENTS.md` para distinguir nova oportunidade de missão ativa;
- atualizar Tasks 45–47 com a integração posterior;
- atualizar documentação de Mundo Vivo e narração;
- atualizar perfis de teste apenas com arquivos de domínio permanentes;
- registrar rollout e limites medidos, sem estimar economia.

## O que esta Task resolve

- Corrige o caso real sem esconder a falha histórica.
- Prova que um caminho muito diferente do planejamento continua resolvendo a missão.
- Mantém a missão original encerrável e as repercussões em contrato separado.
- Fornece regressão end-to-end reutilizável.
- Impede que testes novos se acoplem ao estado vivo ou a números de Task.
- Fecha documentação, telemetria, migração e rollout em uma única etapa final.

## Estratégia de testes

### Arquivos permanentes de domínio

Os testes novos devem usar nomes como:

- `test_active_sidequest_projection.py`;
- `test_transactional_sidequest_progress.py`;
- `test_sidequest_success_reactions.py`;
- `test_concurrent_world_operations.py`;
- `test_reactive_pressure_routing.py`;
- `test_seven_names_sidequest_regression.py`.

Não criar `test_task48_*`, `test_task49_*` etc.

### Cenário end-to-end

O teste de “Sete Nomes” deve provar em repositório temporário:

1. oferta e aceite existentes;
2. exame da ordem e mensageiro já resolvidos;
3. oficina, matriz e testemunha como fatos posteriores;
4. preparo negativo para nova oportunidade ainda projeta a missão ativa;
5. fato institucional com Luath resolve a fase via substituição permitida;
6. ambas as condições de sucesso são satisfeitas;
7. missão termina `concluida` exatamente uma vez;
8. recompensa segue Task43 sem duplicação;
9. contrato Task44 original mantém o mesmo hash;
10. reação sucessora é avaliada separadamente;
11. alternativa sem conhecimento/capacidade é bloqueada;
12. operação elegível pode entrar no Mundo Vivo sem criar nova quest;
13. eventual grupo simultâneo reserva recursos distintos;
14. retry e recovery preservam exatamente-once.

### Não poluição da suíte

Antes do merge:

- nenhum teste altera arquivos do repositório real;
- integração contra `ROOT` limita-se a invariantes estruturais/read-only;
- valores absolutos pertencem somente a fixtures ou snapshot justificado;
- nenhum estado vivo é congelado como fotografia permanente;
- nenhum corpo de teste é duplicado;
- nenhuma cobertura existente é removida sem propriedade e destino documentados;
- arquivos temporários usam `TemporaryDirectory`;
- auditoria heurística é revisada semanticamente, não silenciada;
- novos suspeitos entram em `tests/live-state-freeze-review.yaml` apenas quando realmente necessários;
- consolidações de testes atualizam `tests/historical-test-review.yaml`;
- perfis `sidequests`, `mundo` e `cronica` incluem os novos arquivos sem removê-los de `test-full`.

### Gates finais

Executar, nesta ordem:

```text
poetry run test-fast
poetry run test-domain sidequests cronica mundo sessoes
poetry run test-full
poetry run preflight
```

Também executar as auditorias read-only de testes e comparar o rollout com o baseline somente após a implementação, nunca durante sessão ao vivo.

## Definition of done

- dry-run e aplicação da migração são idempotentes;
- estado vivo não é editado para satisfazer teste;
- missão atual é projetada e progride por fatos, sem terminal inventado;
- reação sucessora não altera contratos históricos;
- regressão end-to-end cobre o desvio pela calaria e Luath;
- nenhuma nova dívida de nomes Task, freeze vivo ou fixture global compartilhada;
- documentação e `AGENTS.md` refletem somente comportamento implementado;
- `test-full`, `preflight` e workflows obrigatórios verdes.

## Entrega realizada

- `ferramentas/migracao_sete_nomes.py` fornece `dry-run`, aplicação com journal,
  recovery, retry idempotente e `check` de preflight;
- a campanha viva recebeu três fatos literais e o receipt
  `historico/migracoes/sidequests/sete-nomes-session-017-v1.yaml`;
- a missão permanece `aceita`, com `verificar_autoridade: possivel`, uma condição
  de sucesso ainda pendente e `terminal: null`;
- `necessita_reavaliacao_reacao` foi marcado sem criar reação, ataque ou encontro;
- o SHA-256 do arquivo Task44 permaneceu
  `2718784f2910baa9f97df28782741eefe350aff37e690d10a1bb13a593111218`;
- o snapshot controlado e a regressão permanente estão em
  `tests/fixtures/historical/seven-names-session-017-end.yaml` e
  `tests/test_seven_names_sidequest_regression.py`;
- tamanhos observados e tetos ficam em
  `baseline/seven-names-migration-integration-orcamento.yaml`;
- o analisador de rollout reconhece `seven_names_migration_regression`, e o
  preflight executa o check real da migração.

Validação final: `test-fast` 198 testes; perfis combinados 963 testes;
`test-full` 1.416 testes; `preflight` 28 checks, todos verdes. As auditorias de
congelamento vivo e histórico ficaram limpas, e o rollout de engenharia passou
todas as sete metas comparáveis sem atribuir economia estimada à campanha real.
