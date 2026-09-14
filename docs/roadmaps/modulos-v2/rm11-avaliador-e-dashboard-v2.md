# RM-11 — Avaliador e dashboard v2

## Status e dependências

**Implementada em 2026-09-14.** Depende da emissão v2 completa das RM-03–RM-10.

Artefatos principais: `ferramentas/interacoes_narrativas.py`, gerador e detector
v2, `evaluation/metas-avaliacao-v2.json`, `evaluation/module-releases.json`,
schemas publicados e dashboard bifurcado entre legado e produção.

## Objetivo

Migrar gerador, scorecard, feedback e painel para os doze módulos hierárquicos,
preservando pacotes v1 como história não comparável. A avaliação v2 deve:

- identificar a versão de implementação e a versão de avaliação de cada módulo;
- tornar comparável o desempenho de implementações medidas pela mesma régua;
- identificar de forma estável cada par entre entrada do jogador e resposta final
  visível do narrador/Codex;
- receber observações concretas do jogador por interação, prioritariamente no
  próprio Codex;
- usar o dashboard para revisão, adjudicação, exploração e consolidação, sem
  exigir que o jogador atribua notas numéricas a módulos.

## Unidade de interação narrativa

### Definição

Uma **unidade de interação narrativa** é o par formado por:

1. uma entrada lógica do jogador, que pode consolidar mensagens consecutivas
   recebidas antes da resposta final; e
2. uma resposta final visível do narrador/Codex.

Raciocínio interno, chamadas e saídas de ferramentas, atualizações intermediárias
e retries técnicos não criam novas unidades. Uma entrada que não alcance resposta
final continua registrada com estado incompleto, sem reutilização posterior de sua
identidade.

Cada unidade recebe:

- `interaction_id`, identidade técnica imutável;
- `interaction_ref`, referência humana no formato `S<sessao>-I<ordinal>`, com
  preenchimento à esquerda, por exemplo `S022-I0049`;
- sessão, ordinal, classe `ON`/`OFF`/`RECALL`/operacional e `turn_id` nativo;
- hashes da entrada consolidada e da resposta final, sem substituir os textos
  preservados por suas fontes autorizadas;
- estado `reservada`, `completa` ou `incompleta` e vínculo com eventos modulares.

O ordinal é monotônico e único dentro da sessão. A chave humana completa é única
no conjunto das sessões. Retry da mesma entrega reutiliza a reserva; nova entrada
lógica cria outra unidade. A numeração é metadado de avaliação append-only e não
é cânone do mundo.

### Visibilidade obrigatória

Durante uma sessão iniciada, toda resposta final visível deve mostrar exatamente
uma `interaction_ref`:

- em resposta ON, como campo gerado dentro do `RODAPE_CANONICO`, que continua
  verbatim e como última linha visível;
- em resposta OFF, RECALL ou operacional sem rodapé canônico, em marcador visual
  compacto e padronizado no fim da resposta;
- nunca como texto improvisado pelo narrador nem deduzido retrospectivamente pelo
  dashboard.

A identidade deve ser reservada antes da emissão da resposta. `cronica preparar`
deve devolvê-la para respostas ON, e o fluxo sem `preparar` deve usar a mesma fonte
durável de numeração sem avançar tempo, mundo ou personagem. O concluir e a
telemetria devem propagar a referência, não criar outra.

## Versionamento dos módulos

### Dois eixos independentes

Todo módulo pai possui duas versões SemVer obrigatórias, preservadas no catálogo e
copiadas para cada evento no momento em que ele acontece:

- `versao_implementacao`: versão do comportamento executado pelo módulo;
- `versao_avaliacao`: versão do contrato usado para detectar, classificar e medir
  esse comportamento.

O pacote também conserva versões de catálogo, detector, gerador, metas e pesos,
mas nenhuma delas substitui as versões por módulo.

### Política de incremento

Para `versao_implementacao`:

- **patch** (`2.0.0` → `2.0.1`): correção ou ajuste interno que não altera
  responsabilidades, interface observável nem contrato de avaliação;
- **minor** (`2.0.1` → `2.1.0`): mudança comportamental substancial e compatível,
  mantendo identidade, responsabilidades e régua de avaliação;
- **major** (`2.1.0` → `3.0.0`): mudança incompatível de responsabilidade,
  elegibilidade, ativação, efeito ou interface observável. Se a identidade
  conceitual não sobreviver, deve nascer outro `module_id`, em vez de apenas uma
  versão major.

Para `versao_avaliacao`:

- **patch**: correção de implementação da medição sem mudança do resultado
  semântico esperado;
- **minor**: extensão compatível de evidência ou diagnóstico que preserva o
  significado das métricas existentes;
- **major**: mudança de indicador, denominador, elegibilidade, adjudicação, peso ou
  significado de nota que rompe comparação direta.

Uma alteração pode avançar um ou ambos os eixos. Mudar a implementação não deve
avançar automaticamente a avaliação, nem o inverso.

### Registro e comparação

Cada release de módulo deve registrar em histórico imutável:

- `module_id`, versões nova e predecessora;
- data de vigência e commit/revisão de origem;
- natureza `patch`/`minor`/`major`, justificativa e resumo da mudança;
- compatibilidade declarada e fixtures que a demonstram.

Eventos preservam as versões vigentes na interação; nunca as inferem do catálogo
atual durante regeneração. Comparações de implementação exigem o mesmo módulo e
uma régua de avaliação compatível. Mudança incompatível da avaliação inicia novo
segmento da série daquele módulo.

Uma alteração de módulo não fragmenta automaticamente a série de todos os outros.
O painel pode mostrar a evolução global com marcadores de release, mas médias e
declarações de “melhor versão” devem ser estratificadas por oportunidades
comparáveis, respeitar amostra mínima e exibir incerteza. Resultado abaixo da
amostra mínima é provisório.

## Avaliação do jogador por interação

### Canal primário: Codex

O canal primário é o próprio Codex, pois a observação pode ser registrada enquanto
o contexto ainda está fresco. O jogador pode enviar, em OFF, texto como:

```text
[AVALIAÇÃO S022-I0049 — havia uma boa oportunidade para um NPC interagir com Ren,
mas ele não tomou iniciativa.]
```

Registrar essa avaliação não avança a ficção. O sistema deve preservar o texto
original, confirmar a referência resolvida e estruturar a observação. Se o módulo
não for informado, o jogador não é obrigado a classificá-lo: detector ou auditor
sugerem módulo e subcapacidade separadamente, sem reescrever a manifestação
original.

O dashboard é canal secundário para cadastrar observação retroativa, corrigir
referência, revisar classificação sugerida, acompanhar adjudicação e filtrar
recorrências. Codex e dashboard escrevem no mesmo contrato append-only; não podem
produzir duas avaliações independentes para a mesma manifestação.

### Contrato da manifestação

Cada manifestação do jogador registra:

- `feedback_id`, `interaction_ref` e instante de registro;
- texto original obrigatório;
- tipo percebido: `boa_ativacao`, `oportunidade_percebida`,
  `sobreativacao_percebida`, `ativacao_inadequada`, `efeito_incorreto`,
  `timing`, `continuidade` ou `possivel_guardrail`;
- expectativa e observação, quando separáveis;
- impacto percebido opcional: `baixo`, `moderado`, `alto` ou `critico`;
- módulo e subcapacidade informados pelo jogador, se houver;
- classificação sugerida pelo sistema, com confiança e evidência;
- adjudicação `pendente`, `confirmada`, `parcial`, `nao_confirmada` ou
  `indeterminada`, com justificativa preservada em camada apropriada.

O relato começa como percepção, não como falha confirmada. A adjudicação pode
consultar elegibilidade canônica e informação reservada sem revelar segredo ao
jogador. Manifestação confirmada pode alimentar oportunidades elegíveis,
oportunidades perdidas, falsos negativos, sobreativação, adequação e guardrails;
manifestação pendente ou indeterminada permanece visível, mas não altera
silenciosamente a verdade medida.

Não há nota numérica de 1 a 5 atribuída pelo jogador a um módulo. As notas
automáticas dos módulos continuam sendo derivadas de telemetria, auditoria
semântica e manifestações adjudicadas. A contribuição humana tem proveniência,
confiança e estado próprios, em vez de um peso subjetivo agregado diretamente.

## Implementação

1. Evoluir o pacote de avaliação com:
   - `serie_avaliacao` e versões de catálogo, detector, gerador, metas e pesos;
   - versões de implementação e avaliação por módulo em catálogo, evento,
     agregação e release manifest;
   - nota por módulo pai;
   - diagnóstico por subcapacidade;
   - guardrails fora da média;
   - custo aditivo pai e custo exposto interno;
   - confiança por unidade de análise.
2. Criar o registro durável de unidades de interação, sua reserva exactly-once,
   propagação por preparar/concluir e marcador visível em toda resposta final.
3. Evoluir ledger, adjudicações, CSVs e manifestos para usar `interaction_id` e
   `interaction_ref`, preservando `turn_id` como vínculo técnico.
4. Substituir `player_feedback` numérico pelo contrato de manifestações por
   interação e criar o fluxo OFF de registro pelo Codex.
5. Recalibrar metas somente com justificativa e fixtures, nunca para melhorar
   artificialmente a nota.
6. Exibir no painel:
   - ranking apenas de módulos pais;
   - drilldown das subcapacidades;
   - versões de implementação e avaliação e seus marcos de release;
   - manifestações por interação, classificação sugerida e adjudicação;
   - violações críticas em bloco próprio;
   - série e versões claramente visíveis;
   - linha de tendência sem atravessar mudança incompatível da régua relevante.
7. Marcar sessão 021 e demais pacotes v1 como `legacy-v1`.
8. Permitir agregação retroativa apenas como referência legada, nunca como ponto
   comparável da curva v2.

## Política de notas

- N/D continua excluído e pesos restantes são renormalizados;
- não há nota direta do jogador por módulo;
- manifestação humana só altera métrica factual depois de adjudicada e conserva
  sua proveniência;
- subcapacidade explica a nota, mas não cria segunda prioridade concorrente;
- guardrail crítico violado marca sessão comprometida;
- uma sessão v2 é provisória; estabilidade exige três sessões comparáveis e a
  amostra mínima definida no catálogo;
- versões de implementação só disputam desempenho sob avaliação compatível e
  mistura de oportunidades explicitamente controlada.

## Migração

- `turn_id` legado permanece válido como vínculo técnico, mas não é promovido
  retroativamente a `interaction_ref` sem reconstrução determinística e marcada;
- feedback v1 de 1 a 5 permanece legível como legado e não é convertido em
  manifestação factual;
- sessão 021 e demais pacotes v1 permanecem `legacy-v1` e não recebem numeração
  inventada para aparentar comparabilidade;
- nenhuma versão histórica é substituída pela versão corrente do catálogo.

## Testes

- soma dos custos pai fecha no total da sessão;
- ranking contém somente doze módulos v2;
- subcapacidades aparecem apenas no drilldown;
- toda resposta final de sessão possui exatamente uma referência visível;
- ON recebe a referência dentro do rodapé canônico e ele continua sendo a última
  linha verbatim;
- OFF/RECALL registra referência sem avançar mundo, tempo ou personagem;
- retry reutiliza a reserva e nova entrada lógica avança o ordinal;
- interação incompleta não tem identidade reutilizada;
- hashes detectam desalinhamento entre referência, entrada e resposta;
- evento modular conserva versões vigentes na interação mesmo após novo release;
- patch, minor e major seguem as regras de compatibilidade declaradas;
- comparação não atravessa avaliação incompatível nem fragmenta módulos que não
  mudaram;
- manifestação via Codex e dashboard converge para o mesmo registro append-only;
- relato do jogador não classificado pode ser mapeado sem alterar seu texto;
- percepção pendente não vira falha confirmada nem revela informação reservada;
- feedback v1 não é encaixado silenciosamente em rótulo incompatível;
- tendência separa `legacy-v1` e `modules-v2`;
- importação/exportação CSV preserva campos desconhecidos ou falha claramente;
- painel continua estático e executável por `http.server`.

## Definition of done

- gerador e dashboard consomem schema v2;
- toda resposta de sessão expõe uma referência estável e os eventos do pacote
  apontam para ela;
- cada módulo tem releases rastreáveis nos dois eixos de versão;
- avaliações podem ser registradas no Codex por referência, revisadas no dashboard
  e adjudicadas sem perder o texto original;
- formulário numérico do jogador deixa de compor a avaliação v2;
- pacote 021 permanece legível e identificado como legado;
- nenhuma nota, manifestação ou versão histórica é reescrita;
- receita de avaliação documenta o novo corte, o registro por interação e a
  comparação entre versões;
- testes de avaliação, telemetria, interação, narração e dashboard ficam verdes.
