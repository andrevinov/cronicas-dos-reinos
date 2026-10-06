# Revisão efetiva após a sessão

Porta: `poetry run avaliar-sessao`. Implementação: `revisao_sessao.py`.
O responsável por interpretar a ficção é o agente que recebe o pedido de avaliar
a sessão. O usuário não precisa escrever pareceres, rodar a CLI ou preencher
formulário. A avaliação permanece fora do jogo e não altera cânone.

## Fluxo obrigatório do agente

1. Congelar a entrada pelo [contrato existente](contrato-entrada-medicao.md),
   com o corte correto até o encerramento, sem incluir manutenção posterior.
   Usar fontes do instante; o save atual não completa silenciosamente o passado.
   Para sessões com [captura causal](evidencias-sessao.md), selecionar o arquivo
   encerrado com `entrada_medicao.py --evidencias-sessao`. Consultar
   `causal_coverage` e arquivos congelados pelo índice privado; fonte de revisão
   não comprova que foi entregue ao narrador. Lacuna exige abstenção delimitada.
2. Preparar a revisão integral. O diretório de trabalho contém fontes reservadas:
   precisa ficar fora do repositório servido, com permissão 0700. Arquivos são
   0600; o bruto não é copiado para o projeto.
3. Ler o índice e as fontes necessárias, por interação e localizador. Textos
   históricos repetidos ficam deduplicados. Examinar todos os critérios escolhidos,
   inclusive causas sem recibo, e comparar ficção, efeitos e memória posterior.
4. Escrever decisões no diretório reservado. Cada unidade recebe `avaliada`,
   `nao_aplicavel` ou `fontes_insuficientes`, com razão e citação literal. Negativa
   exige ausência ou impedimento legítimo; desconhecimento da fonte não é negativa.
   Toda falha inclui estágio provável, limite da hipótese, correção e teste.
5. Concluir e publicar o pacote. A tarefa só termina com a revisão publicada e
   um relatório legível, ou com um bloqueio técnico concreto explicado ao usuário.
   `aguarda_revisao_do_agente` é estado intermediário, nunca entrega final.

```bash
poetry run avaliar-sessao preparar \
  --rollout /caminho/rollout.jsonl --entrada-medicao /tmp/entrada-s025.json \
  --trabalho /tmp/revisao-s025
poetry run avaliar-sessao casos --trabalho /tmp/revisao-s025 --indice
poetry run avaliar-sessao casos --trabalho /tmp/revisao-s025 \
  --interacao S025-I0001 --fonte S025-I0001/response
# O agente produz /tmp/revisao-s025/pareceres.json pela leitura semântica.
poetry run avaliar-sessao concluir --trabalho /tmp/revisao-s025 \
  --pareceres /tmp/revisao-s025/pareceres.json --saida evaluation/sessions/025
```

Se já existe pacote histórico, publicar em `revisoes/<id>` e acrescentar
`--original evaluation/sessions/025 --revisao <id> --data-revisao AAAA-MM-DD`.
Nada sobrescreve o original. Retry exige mesmos dados e verifica os bytes do
pacote; alteração de fonte, código ou decisão exige versão nova. Um destino
parcial não é divulgado: a geração acontece em staging antes da publicação.

## Formato de decisões

```json
{
  "request_id": "campo devolvido por preparar",
  "reviewer": {
    "identity": "identidade do agente e data",
    "role": "revisor_poshoc",
    "configuration": {"executor": "agente_ativo", "mode": "leitura_semantica_das_fontes"}
  },
  "decisions": [{
    "interaction_ref": "S025-I0001",
    "criterion_id": "npc_continuity_and_social_behavior.social_initiative",
    "state": "avaliada",
    "eligibility": "sim", "activation": "ausente", "quality": "nao_aplicavel",
    "reason": "Explicação da obrigação alcançável e da omissão observada.",
    "evidence": [{"locator": "localizador do índice", "quote": "trecho literal"}],
    "guardrails": {},
    "diagnosis": {
      "category": "comportamento_modulo", "stage": "indeterminada",
      "cause_status": "hipotese",
      "finding": "Achado vinculado às fontes.",
      "correction": "Correção concreta a tentar.",
      "test": "Comparação que poderia refutar ou confirmar a correção."
    }
  }]
}
```

O exemplo ilustra uma unidade; revisão integral exige todas as unidades do pedido.
Confirmadas exigem citações da entrada e resposta. Citar a matéria causal também
quando a conclusão depende dela. Offsets e hashes são calculados e verificados
pela ferramenta. Dependências de operação entram em `dependency_operation_ids`;
resultado ausente impede a conclusão que depende dele.

Estágios: causa, elegibilidade, selecao, contexto, narracao, persistencia,
recuperacao, medicao ou indeterminada. Causa reproduzida usa
`confirmada_por_reproducao` com `reproduction_ref`; hipótese não fecha o bug.
Guardrails aceitos: player_agency, knowledge_secrecy, roll_integrity e
canonical_consistency. Fontes reservadas são expurgadas na publicação; uma
descrição genérica verificável continua explicando o estágio e a correção.

## Escopo, custo e limites

Padrão: matriz integral de interações × critérios. `--criterio`, `--interacao`
ou `--unidade interação:critério` declaram revisão parcial. O painel e o relatório
mostram esse alcance. Decisões faltantes não viram abstenções automáticas.
Fontes efetivamente insuficientes continuam inconclusivas mesmo após leitura.

A porta não chama API externa nem implementa um juiz literário por regex. O
agente executa a revisão na avaliação pós-sessão; seu trabalho consome contexto
e tokens. Deduplicação e seleção por fonte evitam reler todo o rollout. Pareceres
inalterados podem ser revalidados, com isso explicitamente registrado como
revalidação; essa operação não conta como novo julgamento.

O aceite de episódios verifica diferenças narrativas com operações iguais,
negativas legítimas, abstenções e apresentação. Replay de pareceres testa o
pipeline; não prova uma nova execução semântica ou generalização. A entrega
integrada dos módulos e o acompanhamento longitudinal continuam separados.
