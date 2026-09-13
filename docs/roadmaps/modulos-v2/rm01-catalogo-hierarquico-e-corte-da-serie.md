# RM-01 — Catálogo hierárquico e corte da série

## Status e dependências

**Proposta.** Primeira task do roadmap; não depende de implementação anterior.

## Problema

O catálogo v1 trata etapas internas, capacidades permanentes, guardrails e
regressões como vinte módulos equivalentes. Isso duplica atribuição conceitual,
faz um único domínio dominar o ranking e permite que itens específicos da
campanha pareçam componentes centrais do sistema.

## Objetivo

Definir o contrato versionado dos doze módulos v2, suas subcapacidades,
guardrails, visibilidade e unidades de análise antes de alterar runtime,
telemetria ou dashboard.

## Implementação

1. Criar o schema 2 do catálogo com, no mínimo:
   - `id`, responsabilidade e escopo estáveis;
   - `unidade_analise`: turno, cena, fronteira, sessão ou evento;
   - contrato de elegibilidade e resultados possíveis;
   - subcapacidades e aliases v1;
   - visibilidade para jogador;
   - indicadores especializados;
   - guardrails aplicáveis;
   - versão de implementação e de avaliação.
2. Registrar o mapa completo v1 → v2 apresentado no roadmap.
3. Criar catálogo separado de guardrails críticos.
4. Reclassificar Sete Nomes como regressão histórica e Torneio Clandestino como
   extensão da campanha, sem apagar seus testes ou estado.
5. Definir `serie_avaliacao`: `legacy-v1` para pacotes anteriores ao corte e
   `modules-v2` para pacotes posteriores.
6. Proibir agregação silenciosa entre séries ou versões incompatíveis.

Durante a implementação, o catálogo v1 continua sendo o padrão de produção. O
v2 só se torna padrão na RM-11.

## Testes

- schema aceita exatamente os doze IDs de primeira classe;
- aliases v1 são únicos e todos possuem destino;
- cenário/regressão não pode aparecer como módulo de primeira classe;
- guardrail não recebe peso de média modular;
- unidade de análise e contrato de elegibilidade são obrigatórios;
- pacotes sem `serie_avaliacao` são reconhecidos como `legacy-v1`.

## Definition of done

- catálogo v2 e schema documentados;
- mapa dos vinte itens v1 completo e sem órfãos;
- série histórica possui regra explícita de corte;
- nenhuma mudança no hot path ou no cânone;
- testes estruturais usam fixtures controladas e nomes de domínio.
