# Direções canônicas como restrições de destino

Direção canônica não é agente, operação, método, ação nem scheduler. Ela define
**o que precisa acabar sendo verdade na campanha**, sem prescrever quem fará isso,
como, quando ou em qual cena.

Separação operacional:

```text
Contrato de Arco   → espaço estratégico permitido
Direção canônica   → destino/marco obrigatório
Plano mestre       → intenção estratégica
Linha operacional  → problema ativo
Agente             → repertório de meios
Mundo Vivo         → quando reavaliar
Contexto da cena   → oportunidade concreta
```

## Consulta

Descoberta contextual abre **zero fragmentos** e pode apenas apontar uma direção
ativa. Se ela merece avaliação dirigida:

```bash
python3 ferramentas/direcoes.py avaliar-destino ponte_de_kozakura
```

A saída contém somente o marco atual, `criterio_para_avancar` e `guardrails`, com
`papel: restricao_destino` e `executavel: false`.

## Avanço

Avanço nunca acontece por cadência nem por conveniência narrativa. Além da nota
interpretativa, exige uma fonte canônica existente e um trecho literal do fato-base:

```bash
python3 ferramentas/direcoes.py avancar ponte_de_kozakura \
  --origem sessoes/010/consequencias.md \
  --evidencia "trecho literal já canonizado" \
  --nota "por que esse fato satisfaz o critério do marco"
```

A evidência literal prova o fato-base; o narrador continua responsável pelo juízo
semântico de que o fato realmente satisfaz o critério. A direção não pode conter
campos `executor`, `acao`, `metodo`, `alvo`, `operacao` ou equivalentes, nem pode
usar o mesmo ID de uma linha operacional do arco.
