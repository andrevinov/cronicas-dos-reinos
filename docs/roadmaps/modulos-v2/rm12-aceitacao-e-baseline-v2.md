# RM-12 — Aceitação integrada e baseline v2

## Status e dependências

**Implementação técnica concluída; aceite operacional aguardando a primeira
sessão real v2.** Último item do roadmap, construído sobre os contratos da RM-11
e de todos os módulos v2. O gate reproduzível está verde sem escrever no save
canônico nem fabricar uma sessão de jogo.

## Objetivo

Provar que a nova arquitetura preserva os contratos do jogo, não encarece o
turno neutro e consegue produzir o primeiro pacote real da série `modules-v2`,
com interações e versões históricas rastreáveis por módulo.

## Etapas de aceite

### 1. Regressão estrutural

- executar testes por domínio e rastrear cada teste consolidado ao seu novo dono;
- executar auditorias de estado vivo e histórico;
- validar catálogo, aliases, guardrails, histórico de releases e soma de custos;
- validar coerência entre `module-releases.json`, versões correntes do catálogo e
  snapshots de versão preservados nas interações;
- confirmar que Sete Nomes continua regressão e Torneio continua extensão;
- provar que nenhuma fachada v2 criou writer, scheduler, RNG ou scan paralelo.

### 2. Episódios controlados

Em `TemporaryDirectory`, cobrir ao menos:

- turno curto neutro, com exatamente uma `interaction_ref` no rodapé canônico;
- cena social com memória e relação;
- regra e rolagem com recurso persistente;
- oportunidade negativa e autoria positiva de sidequest;
- progresso e terminal exactly-once;
- permanência e compressão temporal;
- evento canônico devido;
- duas operações adversariais simultâneas;
- retry e recovery em pontos de commit;
- respostas OFF, RECALL e operacionais com marcador de interação, sem avanço de
  mundo, tempo ou personagem;
- retry idêntico reutilizando a reserva e nova entrada lógica avançando o ordinal;
- reserva incompleta preservada sem ser confundida com interação completa;
- detecção de divergência pelos hashes de entrada e resposta;
- manifestação do jogador registrada no Codex e importada pelo dashboard sem
  duplicar o mesmo `feedback_id` nem reescrever seu texto original.

Os episódios precisam verificar que toda resposta final possui exatamente uma
referência visível. ON usa o `RODAPE_CANONICO`; OFF, RECALL e operacional usam o
marcador compacto devolvido por `interacao`.

### 3. Rollout técnico pós-hoc

Executar um rollout controlado em uma **sessão ativa isolada**, inteiramente em
`TemporaryDirectory`, para verificar correlação, numeração, compatibilidade,
snapshot de releases e orçamento. Ele fica fora do save canônico e não inaugura
a série de experiência do jogador.

O teste deve produzir ON e OFF/RECALL pelo mesmo ledger, comprovar que
`cronica preparar` e `cronica concluir` propagam a mesma referência e confirmar
que o custo da identidade não elimina memória ou iniciativa elegível do preparo.

### 4. Primeira sessão real v2

Somente depois dos gates verdes, jogar uma sessão normal no sistema refatorado,
encerrá-la pelo lifecycle e gerar seu pacote pós-hoc. Esse pacote recebe:

- `serie_avaliacao: modules-v2`;
- status provisório;
- `interacoes.json`, cobrindo todas as respostas finais da sessão;
- `manifestacoes-jogador.json`, possivelmente vazio e sem nota numérica;
- `adjudicacoes-modulares.json`, preservando percepção e decisão em camadas
  distintas;
- adjudicação da validade da medição;
- snapshot do release set e versões de implementação e avaliação por módulo;
- doze linhas de módulos pais, com nota N/D quando não houver amostra elegível,
  além de diagnósticos por subcapacidade;
- custos aditivos dos módulos pais e custos internos somente expositivos;
- baseline operacional observada v2, vinculada às versões efetivamente executadas.

Manifestação do jogador é opcional e sempre referencia uma interação concreta.
Ela começa como percepção pendente, não compõe uma média subjetiva e só altera
métrica factual depois de adjudicada.

## Comparabilidade

O primeiro rollout real v2 é o ponto inicial da nova curva. Sua baseline não é
um número monolítico: cada observação fica vinculada a `module_id`,
`versao_implementacao` e `versao_avaliacao`, além das versões de catálogo,
detector, gerador, metas e pesos do pacote.

Sessão 021 não entra no cálculo de delta, média móvel ou tendência v2. Pode
aparecer ao lado como referência legada, com aviso explícito de incompatibilidade,
mas não recebe `interaction_ref` inventada nem versões correntes retroativas.

Uma sessão permite avaliação provisória. A leitura longitudinal começa no
segundo ponto e só recebe status estável após pelo menos três sessões comparáveis
e amostra mínima por módulo.

Implementações diferentes podem disputar desempenho apenas sob régua de
avaliação compatível. Mudança incompatível da avaliação abre novo segmento
somente para o módulo afetado; módulos inalterados preservam sua própria série.
Regenerar um pacote nunca substitui versões históricas pelo catálogo corrente.

## Gates finais

Executar, nesta ordem:

```text
poetry run test-fast
poetry run test-domain mecanica cronica sessoes sidequests mundo runtime
poetry run test-full
poetry run preflight
poetry run python ferramentas/catalogo_avaliacao.py --json
poetry run python ferramentas/aceitacao_modular_v2.py check
poetry run python ferramentas/gerar-avaliacao-sessao.py <rollout> --sessao-id <id>
```

A medição continua pós-hoc e nunca roda durante o jogo. Depois da geração, o
aceite confere cobertura e unicidade das interações, versões congeladas, soma dos
custos pais, campos N/D e preservação de manifestações/adjudicações em uma
regeneração idempotente.

O penúltimo comando executa os nove episódios ancorados em
`tests/fixtures/aceitacao-modular-v2.yaml`, valida o rollout técnico determinista
e compara suas medidas observadas com
`baseline/modules-v2-technical-acceptance.json`. Seu estado esperado antes da
primeira sessão é `pronta_para_primeira_sessao_real`; isso é sucesso técnico,
mas ainda não satisfaz os itens operacionais abaixo.

## Definition of done

- todos os gates técnicos ficam verdes;
- turno neutro preserva duas chamadas de orquestração;
- nenhum guardrail crítico é violado;
- primeiro pacote `modules-v2` é produzido e revisado;
- toda resposta final da sessão real possui exatamente uma `interaction_ref`;
- ledger, pacote e eventos modulares apontam para as mesmas interações;
- versões históricas por módulo sobrevivem à regeneração do pacote;
- manifestações do jogador permanecem textuais, opcionais e fora da nota direta;
- os doze módulos pais estão presentes, admitindo N/D sem fabricar ativação;
- dashboard inicia uma nova série sem comparar notas incompatíveis;
- baseline versionada registra valores observados, não economia estimada;
- limitações da primeira sessão permanecem explícitas.

Os três itens que dependem de uma sessão jogada — primeiro pacote real,
cobertura de todas as respostas finais reais e inauguração da curva no
dashboard — ficam deliberadamente pendentes até essa sessão existir. A fixture
técnica `900` nunca pode satisfazê-los.
