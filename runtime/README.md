# Runtime — estado quente da campanha

`runtime/` contém apenas o contexto operacional mais provável de ser necessário na próxima interação narrativa.

Ele **não é fonte de verdade**. Os arquivos canônicos continuam em `estado/`, `personagens/`, `sessoes/`, `narrador/` e demais áreas do repositório. Se houver divergência, o runtime deve ser regenerado ou corrigido a partir das fontes canônicas; nunca o contrário apenas por conveniência.

## Arquivos

- `contexto.yaml`: sessão, personagem, recursos, tempo, localização e ponteiros de consulta.
- `cena.yaml`: recorte imediato da cena atual, deliberadamente pequeno.
- `eventos-pendentes.jsonl`: reservado para deltas transacionais durante a narração. Nesta etapa ele existe, mas ainda não substitui a consolidação canônica atual.
- `consultas-contexto.jsonl`: telemetria local opcional criada por `ferramentas/contexto.py`; é ignorada pelo Git e não contém o conteúdo consultado.

## Regeneração

```bash
python3 ferramentas/gerar-runtime.py
```

Para somente verificar se o runtime corresponde ao estado canônico:

```bash
python3 ferramentas/gerar-runtime.py --check
```

A geração é determinística e não altera arquivos canônicos.

## Regras de tamanho

A camada é intencionalmente pequena. `contexto.yaml` e `cena.yaml` não devem virar novos depósitos históricos. Se um fato não for necessário para a próxima decisão provável, ele deve permanecer atrás de um ponteiro e ser consultado somente quando necessário.

## Uso pelo agente

O acesso normal deve passar por `ferramentas/contexto.py`, que lê essas projeções e só escala para fontes maiores quando a consulta exige:

```bash
python3 ferramentas/contexto.py status
python3 ferramentas/contexto.py cena
```

Durante narração:

1. tente resolver em L0 com o contexto já carregado;
2. se faltar estado operacional, use `contexto.py status`;
3. se a decisão depender da situação imediata, use `contexto.py cena`;
4. para NPC, relação, conhecimento ou regra, use a consulta dirigida correspondente;
5. só depois use `contexto.py buscar` ou siga uma fonte específica apontada pela consulta.

Não leia automaticamente `estado/estado-atual.yaml`, `estado/tempo.yaml`, `estado/relacoes.yaml`, `personagens/jogador/conhecimento.md` ou transcrições apenas para se situar.
