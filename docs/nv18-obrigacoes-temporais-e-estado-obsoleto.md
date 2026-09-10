# NV-18 — Obrigações temporais e estado obsoleto

## Objetivo

A NV-18 impede que promessas de retorno, marcos futuros já vencidos e reavaliações sem mudança desapareçam por inércia operacional. Ela não garante que um acontecimento ocorra: garante que uma obrigação comprovada continue tendo responsável, destinatário, rota de retorno e próximo gatilho até receber destino causal explícito.

A implementação reutiliza `estado.compromissos`, o acionamento causal de agentes leves, a barreira do Mundo Vivo e o checkpoint. **Não existe scheduler temporal paralelo.**

## Contrato de uma obrigação temporal

Um compromisso comum continua aceitando o schema anterior. Quando o registro representa obrigação futura relevante, acrescenta `obrigacao_temporal` com:

```yaml
obrigacao_temporal:
  schema: 1
  estado: ativa|reconciliar
  responsavel: <npc-id>
  destinatario: <id>
  local_ou_canal: <texto causal>
  prazo_ou_condicao:
    instante: {data: <Harptos>, hora: HH:MM}
    # ou data: <Harptos>
    # ou condicao: <texto>
  resultado_esperado: <resultado que exige retorno/reconciliação>
  modo_retorno: <como a atualização pode alcançar o destinatário>
  fonte_canonica:
    arquivo: <arquivo atual dirigido>
    evidencia_literal: <trecho literal>
```

`prazo_ou_condicao` aceita exatamente uma forma. Fonte absoluta ou com `..` falha fechada. Evidência é referência causal; não autoriza inventar resultado, presença, conhecimento ou ação de Ren.

## Estado obsoleto

`estado: reconciliar` marca um fio cuja data/condição relevante já foi alcançada, mas cujo próximo passo não foi registrado. A reconciliação não afirma que o evento esperado aconteceu. O caso de Kage é a regressão de referência: a apresentação marcada para 17 Eleasis não pode continuar descrita como "próxima" em 21 Eleasis. A correção canônica apenas registra que a data ficou para trás e que Jack precisa produzir novo prazo, retorno ou encerramento; ela **não inventa** se a apresentação ocorreu.

Datas sem hora vencem somente depois do término do dia canônico. Instantes usam o calendário/relógio já implementados em `mundo.py`.

## Checkpoint e prioridade

`checkpoint.py` executa a reconciliação NV-18 antes da sincronização normal do Mundo Vivo. O índice reservado é derivado somente das obrigações ativas e contém chaves por data, condição e responsável.

- compromisso com `janela.inicio`/`fim` exata continua entrando por `acionamentos_leves.deadline_events`; esse mecanismo já classifica `prazo` acima de mudança causal ordinária;
- obrigação vencida sem prazo exato, como condição de acompanhamento, é injetada na fila causal **existente** de `acionamentos_leves`, que suspende uma rotina genérica quando necessário;
- se o responsável não é agente leve ativo, a obrigação continua devida, mas o runtime não fabrica um agente ou canal para entregá-la.

A mesma causa não é duplicada enquanto estiver aguardando ou numa pendência aberta. Depois que a pendência recebe destino, a obrigação canônica deve ser removida/atualizada ou explicitamente adiada; do contrário ela volta a ser devida.

## No-op com próxima avaliação obrigatória

`agentes_leves.py concluir-noop <id>` mantém o comportamento anterior para pendências sem obrigação temporal vencida. Quando a pendência pertence a um responsável com obrigação vencida, o no-op exige uma destas formas:

```text
--retomar-data '<data>' --retomar-hora HH:MM
```

ou

```text
--retomar-condicao '<condição concreta>'
```

Uma nova data precisa estar no futuro. Um adiamento por condição guarda a assinatura da fonte canônica atual; quando essa fonte muda, a condição volta à fronteira para nova avaliação. O recibo é gravado antes de a pendência ser removida. Se houver queda entre as etapas, o retry completa a operação sem perder o próximo gatilho nem duplicar o turno.

O no-op não encerra o compromisso canônico. Ele somente torna explícita a próxima condição/data de avaliação.

## Migração histórica one-shot

`obrigacoes_temporais.py migrar` usa exclusivamente `narrador/obrigacoes-temporais/evidencias.yaml`. Não busca palavras-chave, não abre transcrições em massa e não transforma plausibilidade em promessa.

Cada candidato precisa:

1. possuir trecho histórico literal declarado;
2. produzir um registro temporal válido;
3. apontar para uma fonte canônica atual que também contenha a evidência literal declarada.

Depois de gravado `migracao.executada: true`, repetir a migração retorna antes de abrir o catálogo de evidências ou qualquer histórico.

Na migração atual há duas obrigações comprovadas:

- **Jack/Kage:** o histórico preserva literalmente a apresentação pública marcada para 17 Eleasis; o estado atual foi corrigido para não chamá-la mais de futura e exige reconciliação do próximo passo;
- **Silva/Colm:** o histórico prova a rota compartimentada e que a segunda mão/cama final permanecem ocultas; o estado atual prova Colm em trânsito para a segunda transferência. A obrigação exige retorno genérico sobre segurança quando a transferência mudar, preservando deliberadamente o segredo da rota.

## Economia e idempotência

- máximo de 32 obrigações temporais estruturadas;
- no máximo 8 obrigações devidas projetadas por checkpoint;
- nenhum scan global de NPCs;
- nenhum scan de transcrições no hot path;
- nenhum RNG ou chamada de IA;
- índice derivado somente dos compromissos ativos;
- condição adiada lê apenas sua fonte canônica dirigida;
- compromisso com prazo exato usa o mecanismo de prazo já existente;
- fila causal e barreira existentes continuam autoritativas;
- writes reservados são atômicos via `mundo._atomic_write_yaml`;
- retries não substituem silenciosamente o follow-up já preparado.

## Compatibilidade

Compromissos legados sem `obrigacao_temporal` continuam válidos e com o mesmo comportamento. Os wrappers de `compromissos.py`, `agentes_leves.py` e `checkpoint.py` executam a implementação anterior no mesmo namespace antes de acrescentar a NV-18, preservando a identidade pública dos módulos e o comportamento de fixtures antigas sem instalação NV-18.

O `checkpoint.py check`, já pertencente ao preflight, passa a agregar o check NV-18; não é necessário criar um segundo gate de preflight.

## Fora de escopo

A NV-18 não cria novas promessas, não decide que um evento passado realmente ocorreu, não revela a rota final de Colm, não cria contato onde não existe, não transforma no-op em resultado ficcional e não substitui planos NV-08/NV-09 ou entrega causal NV-13. Seu papel é manter **obrigações já comprovadas temporalmente alcançáveis e auditáveis** até que o próprio cânone lhes dê destino.
