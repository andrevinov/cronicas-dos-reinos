# RM-11 — Avaliador e dashboard v2

## Status e dependências

**Proposta.** Depende da emissão v2 completa das RM-03–RM-10.

## Objetivo

Migrar gerador, scorecard, feedback e painel para os doze módulos hierárquicos,
preservando pacotes v1 como história não comparável.

## Implementação

1. Evoluir o pacote de avaliação com:
   - `serie_avaliacao` e versões de catálogo, detector e pesos;
   - nota por módulo pai;
   - diagnóstico por subcapacidade;
   - guardrails fora da média;
   - custo aditivo pai e custo exposto interno;
   - confiança por unidade de análise.
2. Recalibrar metas somente com justificativa e fixtures, nunca para melhorar
   artificialmente a nota.
3. Atualizar formulário do jogador para nomes e comportamentos perceptíveis v2.
4. Exibir no painel:
   - ranking apenas de módulos pais;
   - drilldown das subcapacidades;
   - violações críticas em bloco próprio;
   - série e versão claramente visíveis;
   - linha de tendência sem atravessar mudança incompatível de série.
5. Marcar sessão 021 e demais pacotes v1 como `legacy-v1`.
6. Permitir agregação retroativa apenas como referência legada, nunca como ponto
   comparável da curva v2.

## Política de notas

- N/D continua excluído e pesos restantes são renormalizados;
- percepção do jogador conserva peso explícito e menor que a evidência agregada;
- subcapacidade explica a nota, mas não cria segunda prioridade concorrente;
- guardrail crítico violado marca sessão comprometida;
- uma sessão v2 é provisória; estabilidade exige três sessões comparáveis e a
  amostra mínima definida no catálogo.

## Testes

- soma dos custos pai fecha no total da sessão;
- ranking contém somente doze módulos v2;
- subcapacidades aparecem apenas no drilldown;
- feedback v1 não é encaixado silenciosamente em rótulo incompatível;
- tendência separa `legacy-v1` e `modules-v2`;
- importação/exportação CSV preserva campos desconhecidos ou falha claramente;
- painel continua estático e executável por `http.server`.

## Definition of done

- gerador e dashboard consomem schema v2;
- pacote 021 permanece legível e identificado como legado;
- nenhuma nota histórica é reescrita;
- receita de avaliação documenta o novo corte;
- testes de avaliação, telemetria e dashboard ficam verdes.
