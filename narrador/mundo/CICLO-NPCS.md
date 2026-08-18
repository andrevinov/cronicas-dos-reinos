# Lifecycle terminal de NPCs

Esta camada garante que morte canônica interrompa atividade futura sem depender de releitura narrativa.

## Registro da morte

Quando um NPC realmente morre em jogo, o mesmo payload transacional do turno deve registrar o fato objetivo:

```json
{"alvo":"npc:<id>","op":"set","caminho":"vida.estado","valor":"morto"}
```

Isso não cria conhecimento para Ren. Se Ren presenciou ou descobriu a morte, registrar conhecimento/relação separadamente quando necessário.

A consolidação normal instala `vida.estado: morto` no fragmento canônico de `estado/npcs/`. No checkpoint seguinte, `ferramentas/ciclo_npcs.py` sincroniza esse fato antes das demais camadas do Mundo Vivo.

## Efeito determinístico

Para um NPC morto, a sincronização:

- registra `morto` em `narrador/mundo/ciclo-npcs.yaml`;
- muda agente estratégico correspondente para `inativo` e remove sua recorrência/agendamentos como ator;
- muda agente recorrente leve correspondente para `inativo`;
- cancela pendências abertas em que ele é o ator;
- remove o morto de listas passivas de `agentes_afetados`;
- se ele ainda era aliado futuro não apresentado, marca sua entrada como `inviavel` e libera o próximo candidato normal.

`morto` é terminal. Apagar ou omitir depois `vida.estado` não reativa o NPC. Uma ressurreição canônica exige uma futura operação explícita de reativação; não é inferida automaticamente.

## Custo

A detecção é feita em Python durante checkpoint. Fragmentos canônicos usados para conferir `vida.estado` não são devolvidos ao contexto do modelo. Sem morte nova, não existe decisão narrativa adicional nem nova pendência.

## Comandos de manutenção

```bash
python3 ferramentas/ciclo_npcs.py status
python3 ferramentas/ciclo_npcs.py sincronizar
python3 ferramentas/ciclo_npcs.py validar
```

No fluxo normal, `sincronizar` é chamado automaticamente pelo orquestrador de baixa frequência antes de direções, entradas, agentes leves e do avanço do cursor do mundo.
