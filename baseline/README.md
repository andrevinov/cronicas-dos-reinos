# Linha de base da refatoração de contexto

Esta pasta preserva o estado anterior à refatoração voltada à economia de contexto do Codex.

## Conteúdo

- `estado-logico-2026-08-15.yaml`: fatos essenciais da campanha que devem sobreviver às migrações estruturais.
- `rollout-2026-08-15.json`: métricas resumidas do rollout do Codex usado como benchmark pré-refatoração.

O rollout bruto não é versionado: ele é grande, contém histórico operacional e pode incluir conteúdo que não precisa fazer parte do repositório. Para analisá-lo localmente:

```bash
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl
python3 ferramentas/analisar-rollout.py ~/.codex/sessions/.../rollout-....jsonl --json
```

## Verificação de integridade

A verificação normal testa estrutura, UTF-8, YAML, referências e consistência entre estado e ficha:

```bash
python3 ferramentas/verificar-integridade.py
```

Durante a refatoração, a comparação contra a fotografia lógica original deve ser executada explicitamente:

```bash
python3 ferramentas/verificar-integridade.py \
  --baseline baseline/estado-logico-2026-08-15.yaml
```

A baseline não deve ser usada depois que a campanha voltar a avançar normalmente, pois PV, Ki, hora, local e outros fatos legitimamente mudarão durante o jogo. Sua função é proteger a migração enquanto a campanha está suspensa.

## Política durante a migração

1. Não apagar a baseline original.
2. Toda mudança estrutural deve passar pelo verificador normal.
3. Enquanto a campanha estiver suspensa, toda mudança que mexa em estado canônico deve também passar pela comparação com a baseline.
4. Se uma etapa exigir mudar a localização física de um fato, adaptar o extrator/verificador antes de remover a fonte antiga.
5. Divergências da baseline só podem ser aceitas quando forem consequência consciente da própria migração, nunca por perda silenciosa de informação.
