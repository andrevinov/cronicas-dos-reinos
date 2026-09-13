# Correção canônica explícita

Esta rota existe para **retificar uma cena já registrada que se provou incorreta**. Ela é manutenção causal rara, não parte do hot path e não deve ser usada para mudar uma decisão legítima do jogador, um resultado de dado válido ou uma consequência que apenas se tornou inconveniente.

## Princípio

Correção não é acontecimento novo. O texto original continua na transcrição para auditoria; uma entrada `CORREÇÃO CANÔNICA` registra que aquele trecho foi retificado. O estado corrente recebe apenas os valores corretivos necessários e o checkpoint regenera runtime pelos mecanismos normais.

A operação automática só atua na **última transação normal da sessão**. Se já existe turno posterior, parar: fatos posteriores podem depender da versão errada e precisam de replay/auditoria específica. Não se reescreve causalidade antiga por aproximação.

## Fluxo

Preparar sem escrever:

```bash
python3 ferramentas/correcao.py preparar <transacao-id> <<'JSON'
{
  "motivo": "A cena foi associada ao local errado.",
  "retificacao": "O local correto era o Lavadouro dos Três Tanques.",
  "resumo": "Substitui o local incorreto e corrige os derivados diretamente afetados.",
  "deltas": [
    {
      "alvo": "estado",
      "op": "set",
      "caminho": "localizacao.area",
      "valor": "Lavadouro dos Três Tanques"
    }
  ],
  "invalidar_mapas": ["local_errado"]
}
JSON
```

A saída fornece `preparacao_id`. Se a proposta estiver correta, repetir o mesmo payload:

```bash
python3 ferramentas/correcao.py aplicar <transacao-id> \
  --preparacao-id corr-prep-... <<'JSON'
{ ...mesmo payload... }
JSON
```

`preparar` é read-only. `aplicar` revalida a preparação, registra uma transação sem `jogador`, força checkpoint e grava auditoria em `sessoes/NNN/correcoes.jsonl`.

## Deltas permitidos

A correção automática aceita apenas `set` e `remove`. Eles precisam expressar **o estado final correto**.

Não usar `inc`, `append` ou `registrar`: o ledger não guarda inversas suficientes para provar que uma compensação numérica ou remoção cronológica é equivalente a apagar a versão errada. Quando o fato exige reconstrução mais complexa, fazer auditoria/replay em vez de fabricar uma inversa.

Correção automática também não altera deltas com `visibilidade: narrador`; estado reservado pode possuir dependências invisíveis que exigem análise específica.

## Mapas de recompensa derivados

`invalidar_mapas` é deliberadamente restrito. Um mapa pode ser removido automaticamente somente se:

- todas as recompensas continuam `oculto`;
- todas têm origem `procedural`;
- o mapa possui zero recompensa planejada/autoral;
- índices e fragmentos ainda correspondem à mesma geração preparada.

Se algum item foi descoberto, obtido ou possui origem planejada/autoral, a correção falha fechada. Nesse caso existe história dependente e o artefato não é lixo procedural descartável.

## Barreira do Mundo Vivo

Uma cena errada pode ter deixado a barreira bloqueada. A operação de correção possui uma autorização local e estreita para registrar **somente a transação corretiva**, sem ação do jogador. Em seguida ela força checkpoint antes de liberar o fluxo. A regra normal da barreira não é enfraquecida para outros turnos.

## Journal e retry

Durante a aplicação existe:

```text
runtime/correcao-em-andamento.json
```

Se o processo cair, não narrar novo turno. Repetir exatamente `correcao.py aplicar` com o mesmo alvo, `preparacao_id` e payload. O ID da correção é determinístico e `turno.py`/ledger impedem duplicação.

Depois de sucesso, `sessoes/NNN/correcoes.jsonl` preserva alvo, motivo, retificação, quantidade de deltas, mapas invalidados e o marcador `nao_e_evento_novo: true`.

## O que a correção não faz

- não apaga a transcrição original;
- não transforma um erro antigo em um novo evento diegético;
- não corrige automaticamente uma transação que já possui turnos posteriores;
- não revoga rolagem válida ou escolha legítima do jogador;
- não apaga item já descoberto/autoral;
- não roda a cada turno, checkpoint ou abertura de cena.

## Verificação

```bash
python3 ferramentas/correcao.py check
```

O check detecta journal interrompido, auditoria duplicada, correção sem transação consolidada e marcador de transcrição ausente/duplicado.
