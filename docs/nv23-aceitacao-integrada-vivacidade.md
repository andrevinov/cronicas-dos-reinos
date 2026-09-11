# NV-23 — Aceitação integrada de vivacidade

A NV-23 não acrescenta um motor novo. Ela fecha a sequência NV-13 → NV-22
provando, em episódios completos, que as causas já modeladas continuam
alcançando Ren pela arquitetura existente e que a ausência de acontecimentos
também pode ser demonstrada.

## Propriedade global

> O mundo permanece causalmente alcançável por Ren sem precisar escanear ou
> improvisar o mundo inteiro; quando nada acontece, o sistema prova que a calma
> foi um resultado válido, e não uma falha em consultar os produtores.

O checker `ferramentas/aceitacao_vivacidade.py` é **read-only**. Ele reutiliza
`fronteira_vivacidade.project_span`; não cria scheduler, fila, writer, hot path,
RNG ou chamada de IA. O orçamento fica em
`baseline/aceitacao-vivacidade-orcamento.yaml`.

## Episódio A — dia carregado no circo

A fixture `tests/fixtures/aceitacao-vivacidade-episodios.yaml` parte de causas
já existentes: mensagem comunicável vencida, compromisso temporal vencido,
causa NV-11 vencida, iniciativa plausível de elenco presente, slot espacial
canônico e um conteúdo reservado bloqueado. A fronteira possui um único slot
primário por janela: o que não cabe é adiado, o que não pode ser revelado é
bloqueado com motivo, e nenhuma candidata pode desaparecer sem destino.

Além da fila causal, o episódio registra uma cadeia semântica explícita para as
composições que não devem virar outra fila: clima → trânsito; política cívica →
entrega pública; presença incidental → cena; causa de side quest → oportunidade;
gate mecânico → resultado; consequências relacional, reputacional e espacial →
estado futuro. As arestas são verificadas, não apenas a presença de flags.

## Episódio B — dia legitimamente calmo

O segundo episódio consulta os mesmos sete domínios da fronteira, mas não contém
mensagens, compromissos, causas, iniciativas ou incidentes elegíveis. Cada
janela deve emitir `calma_justificada`, nenhuma pressão pode ser criada e a
permanência continua ancorada a um local válido. Calma não significa ausência de
mundo; significa ausência comprovada de causa elegível.

## Regressões e rollout

As regressões obrigatórias são ancoradas por nome em testes permanentes dos
domínios produtores. O checker usa AST para confirmar que as âncoras ainda
existem; a suíte integral continua responsável por executá-las. Isso cobre, entre
outros pontos, entrega causal, permanência com local não nulo, causa NV-11,
decisão de iniciativa, ausência de scan/IA por NPC, caminho econômico de turno
curto, reutilização da fronteira em turno longo, limites de projeção,
clima→trânsito, política cívica, presença incidental, gate mecânico e reputação.

A amostra operacional `tests/fixtures/rollout-step11-mini.jsonl` também é lida
semanticamente: uma intenção narrativa do usuário precisa formar a sequência
**contexto → mecânica → writer**, nesta ordem, e o sucesso do writer precisa
aparecer depois da decisão mecânica. A aceitação não considera suficiente apenas
contar chamadas ou conferir cobertura de flags.

## Gate

`preflight` inclui o gate **aceitação integrada de vivacidade**, executando:

```bash
python ferramentas/aceitacao_vivacidade.py check
```

O teste permanente novo é `tests/test_aceitacao_vivacidade.py`: nome de domínio,
não nome de task/NV.
