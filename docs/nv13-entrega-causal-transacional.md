# NV-13 — Entrega causal transacional ao jogador

## Objetivo

Toda resolução genérica do Mundo Vivo precisa encerrar explicitamente a pergunta: **a resolução produziu informação destinada a Ren?**

A resposta faz parte do mesmo lote transacional da causa. Não existe fila paralela de mensagens e não existe entrega presumida.

## Contrato

Uma transação `modo: mundo` que resolve uma pendência por `resolver-pendencia-mundo:<id>` deve seguir exatamente um dos caminhos:

1. nenhuma informação foi produzida para Ren: incluir a tag `entrega-causal:nao-comunicavel`;
2. informação foi produzida: registrar exatamente um recibo reservado em `relogio:entrega_<hash-da-pendencia>` com `op: registrar` e `visibilidade: narrador`.

O recibo usa `versao: 1`, `tipo: entrega_causal`, aponta a pendência, marca `comunicavel: true`, usa `destinatario: ren` e contém `causa`, `conteudo` e um `destino` explícito.

## Destinos permitidos

- `entregue`: exige `canal` real já consumado;
- `plano`: exige `plano_id`, `responsavel`, `canal` e `prazo`; o `plano:<id>` correspondente precisa existir no mesmo lote;
- `bloqueada`: somente `motivo: sem_canal`, com detalhe concreto; a informação permanece pendente no Mundo Vivo;
- `falhou`: exige o canal tentado e a consequência da falha;
- `abandonada`: exige a consequência factual de abandonar a entrega.

`bloqueada`, `falhou` e `abandonada` não podem ser usados como sinônimo de “o narrador esqueceu de entregar”. São resultados causais do mundo.

## Exemplo mínimo — entregue

```json
{
  "modo": "mundo",
  "tags": ["resolver-pendencia-mundo:mundo-1111111111111111"],
  "deltas": [
    {
      "alvo": "relogio:entrega_1111111111111111",
      "op": "registrar",
      "visibilidade": "narrador",
      "valor": {
        "versao": 1,
        "tipo": "entrega_causal",
        "pendencia": "mundo-1111111111111111",
        "comunicavel": true,
        "destinatario": "ren",
        "causa": "A resolução do mundo produziu notícia para Ren.",
        "conteudo": "O cais sul foi fechado pela guarda.",
        "destino": {
          "estado": "entregue",
          "canal": "mensageiro da guarda"
        }
      }
    }
  ]
}
```

## Entrega bloqueada

Se não existe canal causal válido, o recibo é consolidado primeiro. Ao concluir a pendência, a causa resolvida é substituída deterministicamente por uma nova pendência `tipo: entrega_causal`, preservando o conteúdo e a transação de origem. Repetir a operação não duplica a pendência.

Quando surgir canal válido, uma nova resolução da pendência de entrega registra seu novo destino no mesmo contrato. Só então ela pode desaparecer da barreira.

## Idempotência

O writer revalida a forma NV-13 também em retries. O fingerprint transacional continua sendo a trava de conteúdo: repetir exatamente a mesma transação é reparo; trocar silenciosamente o destino causal exige outra transação e outra resolução.

## Escopo

Pendências que já possuem writer de domínio próprio — reavaliações de agentes leves, reações de side quest, grupos/operações adversariais, planos de personagem e resolução de side quest — não passam pelo gate genérico da NV-13. Esses fluxos continuam responsáveis pelos seus próprios efeitos e compromissos.
