# Runtime — estado quente e sobreposição transacional

`runtime/` contém o contexto operacional mais provável de ser necessário na próxima interação narrativa.

Ele **não é fonte de verdade canônica**. `contexto.yaml` e `cena.yaml` são projeções-base derivadas do último estado consolidado. Durante uma sessão ativa, `eventos-pendentes.jsonl` pode conter deltas ainda não consolidados; `ferramentas/contexto.py` projeta esses deltas sobre a base ao consultar o estado efetivo.

Assim, durante jogo ao vivo, não é necessário reescrever estado, ficha, relações e conhecimento a cada fala.

## Arquivos

- `contexto.yaml`: snapshot-base pequeno de sessão, personagem, recursos, tempo, localização e ponteiros.
- `cena.yaml`: snapshot-base da situação imediata.
- `eventos-pendentes.jsonl`: **buffer transacional ativo**, uma linha JSON por avanço narrativo ainda não consolidado.
- `consultas-contexto.jsonl`: telemetria local opcional criada por `ferramentas/contexto.py`; é ignorada pelo Git e não contém o conteúdo consultado.

## Regra de escrita durante narração

Um turno narrativo comum escreve somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

Use `ferramentas/turno.py` para fazer as duas escritas em uma única chamada lógica e de forma idempotente.

```bash
python3 ferramentas/turno.py registrar <<'JSON'
{
  "jogador": "Ren tenta alcançar o alvo.",
  "narracao": "...",
  "resumo": "Ren alcança o alvo e gasta 1 Ki.",
  "modo": "combate",
  "deltas": [
    {
      "alvo": "estado",
      "op": "inc",
      "caminho": "recursos.ki.atuais",
      "valor": -1
    }
  ]
}
JSON
```

A prosa completa não é copiada para o JSONL. O buffer guarda apenas ID, sessão, resumo curto, deltas e, quando necessário, rolagens ocultas até a consolidação.

## Deltas

Operações suportadas:

- `set`: substitui valor corrente;
- `inc`: soma delta numérico;
- `append`: acrescenta item a lista;
- `remove`: remove chave ou item;
- `registrar`: registra fato que não precisa alterar imediatamente um valor estruturado, como descoberta ou consequência.

Alvos típicos:

- `estado`;
- `tempo`;
- `relacao:<id>`;
- `npc:<id>`;
- `conhecimento`;
- `consequencia`;
- `relogio:<id>`.

Deltas com `visibilidade: narrador` permanecem fora das consultas públicas normais. Rolagens ocultas podem ficar em `rolagens_ocultas` até a consolidação da sessão.

## Estado efetivo

Durante uma sessão com eventos pendentes:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py relacao kethra
python3 ferramentas/contexto.py npc nera
python3 ferramentas/contexto.py conhecimento "ponte baixa"
```

Essas consultas combinam o snapshot-base com os deltas pendentes relevantes **em memória**. Os YAMLs de runtime não precisam ser regravados por turno.

Isso permite interromper o processo no meio de uma cena: snapshot-base + `eventos-pendentes.jsonl` + transcrição bastam para reconstruir o estado operacional corrente.

## Idempotência e recuperação

Cada bloco gravado na transcrição recebe um comentário HTML interno com o ID da transação. A mesma entrada executada novamente gera o mesmo ID automaticamente.

Se o processo cair depois de escrever o evento, mas antes da transcrição — ou o inverso — repetir a mesma operação repara apenas o lado ausente. Não duplica o que já foi persistido.

Validação:

```bash
python3 ferramentas/turno.py check
python3 ferramentas/turno.py status
```

## Regeneração do snapshot-base

```bash
python3 ferramentas/gerar-runtime.py
python3 ferramentas/gerar-runtime.py --check
```

Esses comandos continuam tratando `contexto.yaml` e `cena.yaml` como projeções do **estado canônico consolidado**. Eventos pendentes são uma sobreposição separada e não tornam o snapshot-base inválido.

Após a futura consolidação dos eventos nos arquivos canônicos, o buffer será esvaziado/marcado e o runtime-base será regenerado.

## Regras de tamanho

`contexto.yaml` e `cena.yaml` continuam abaixo de 8 KiB. `eventos-pendentes.jsonl` tem limite operacional de 512 KiB; atingir esse limite indica que a sessão precisa ser consolidada antes de continuar.

Não transforme nenhum desses arquivos em diário histórico. A transcrição é o registro completo; o JSONL contém apenas deltas de trabalho.
