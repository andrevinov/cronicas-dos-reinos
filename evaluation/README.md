# Contratos e pacotes de avaliação

Este diretório contém somente artefatos pós-hoc de engenharia. Nada aqui é
memória canônica da campanha ou participa do hot path da narração.

## Catálogos

- `catalogo-modulos.json`: catálogo v1, ainda usado pelo gerador de produção;
- `catalogo-modulos-v2.json`: contrato hierárquico dos doze módulos, preparado
  pela RM-01 e ainda não habilitado para produção;
- `catalogo-guardrails-v2.json`: propriedades críticas não compensáveis;
- `series-avaliacao.json`: corte entre `legacy-v1` e `modules-v2` e regra de
  comparabilidade;
- `schemas/`: schemas JSON dos três contratos novos.

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
