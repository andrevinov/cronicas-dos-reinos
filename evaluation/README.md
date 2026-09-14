# Contratos e pacotes de avaliação

Este diretório contém somente artefatos pós-hoc de engenharia. Nada aqui é
memória canônica da campanha ou participa do hot path da narração.

## Catálogos

- `catalogo-modulos.json`: catálogo v1, ainda usado pelo gerador de produção;
- `catalogo-modulos-v2.json`: contrato hierárquico dos doze módulos, preparado
  pela RM-01 e ainda não habilitado para produção; a versão 2.6.0 registra as
  fachadas das RM-03–RM-08, incluindo o control plane de turno e sessão;
- `catalogo-guardrails-v2.json`: propriedades críticas não compensáveis;
- `series-avaliacao.json`: corte entre `legacy-v1` e `modules-v2` e regra de
  comparabilidade;
- `schemas/`: schemas JSON dos três contratos novos.

O schema do ledger hierárquico e o de suas adjudicações também ficam em
`schemas/ledger-modular-v2.schema.json` e
`schemas/adjudicacoes-ledger-v2.schema.json`. O ledger é emitido dentro de
`modular_ledger_v2` por `ferramentas/analisar-rollout.py`; o gerador de pacotes
continua pedindo explicitamente a visão v1 até a RM-11.

O validador estrutural é executado com:

```bash
poetry run python ferramentas/catalogo_avaliacao.py --json
```

Ele exige doze módulos exatos, mapa completo e único dos vinte itens v1,
guardrails sem peso e política de série compatível. Também oferece
`evaluation_series`, `comparability_key` e `require_comparable` para consumidores
pós-hoc falharem antes de misturar séries ou versões incompatíveis.

## Corte da série

O padrão de produção continua sendo `legacy-v1`. Um pacote sem
`serie_avaliacao` é classificado como legado sem ser reescrito. Isso mantém
`sessions/021` como snapshot histórico imutável. `modules-v2` só poderá ser
emitida como série de produção quando a RM-11 habilitar o avaliador hierárquico.

Pacotes de séries distintas podem aparecer lado a lado como referência, mas não
entram na mesma média, tendência ou baseline. Dentro de uma série, catálogo,
metas e gerador precisam ter versões iguais para agregação automática.

## Dados derivados

- `sessions/`: pacote autocontido por sessão e índice longitudinal derivado;
- `auditorias/`: adjudicações reutilizáveis;
- `dashboard/`: visualização estática dos pacotes publicados;
- `metas-avaliacao.json`: pesos e faixas da avaliação v1.

A receita operacional completa está em
`docs/agente/engenharia/avaliacao-desempenho-sessoes.md`.

Na RM-05, consultas dirigidas de NPC passam a sinalizar continuidade sem serem
promovidas automaticamente a iniciativa. `--interlocutor` e recibos de
`iniciativa_elenco` observam `social_initiative`; memória/relação/reputação e
presença/identidade ficam em suas subcapacidades próprias. Qualidade de voz e
contradições sem marcador estrutural continuam para adjudicação humana, sem
inferência por substring da prosa.

Na RM-06, contrato adversarial e operações simultâneas passam a compartilhar o
pai `adversarial_operations`. A fachada emite consulta, compromisso e efeito
material separadamente; a subcapacidade concorrente só é afirmada pelo recibo
novo quando há mais de uma frente. Integridade continua verificável como
guardrail não compensável e o custo aditivo pertence uma única vez ao pai.

Na RM-07, a política L0–L5, a memória de cena, a retomada fria e a persistência
durável passam a compartilhar o pai `context_and_memory`. A telemetria distingue
L0 econômico, consulta dirigida, aprofundamento justificado, leitura RAW,
redundância, consulta de memória e efeito persistido. O custo de leitura e o
recibo de memória permanecem separáveis sem cobrar novamente as subcapacidades.

Na RM-08, `turn_and_session_orchestration` correlaciona preparo, conclusão,
retry e lifecycle por recibos versionados emitidos nas chamadas existentes. O
ledger separa custo de `controle` e `dominio`; tickets obsoletos, commits
incompletos e recovery deixam de ser atribuídos por aproximação a módulos
narrativos.
