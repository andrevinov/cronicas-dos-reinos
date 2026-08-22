# Ecologia local

A ecologia local é uma **restrição de plausibilidade** para cenas incidentais. Ela descreve o tipo cotidiano de um lugar sem afirmar que qualquer pessoa, evento ou atividade está acontecendo agora.

O índice fica em `cenario/locais/ecologia.yaml` e cobre exatamente os IDs do registro canônico `cenario/locais/index.yaml`.

## Consulta dirigida

```bash
python3 ferramentas/ecologia_local.py mostrar galeria_dos_escribas
python3 ferramentas/ecologia_local.py mostrar "mansão Narwhal" --periodo anoitecer
python3 ferramentas/ecologia_local.py check
```

O lookup público resolve alias pelo registro canônico e depois abre somente o índice ecológico. Quando o chamador já possui `local_id` canônico, `lookup_canonical` abre apenas o índice ecológico.

## Perfil

Cada local possui:

- `familia`: categoria operacional do lugar;
- `acesso`: `publico`, `semipublico`, `controlado` ou `privado`;
- `ritmo_baseline`: atividade relativa 0–3 em `amanhecer`, `dia`, `anoitecer`, `noite`;
- `tags`: características úteis para filtragem;
- `atores_comuns`: **papéis anônimos**, nunca NPCs estabelecidos;
- `canais_microevento`: famílias de acontecimento cotidiano que podem ser plausíveis ali.

A escala de ritmo é relativa. Ela não consulta relógio e não prova que o local está aberto, cheio ou vazio em um instante concreto.

## Ordem de autoridade

Ecologia não é cânone independente. A ordem é:

```text
estado canônico / cena atual / evento pendente / arco
→ ecologia local
→ possibilidade incidental
```

Se o estado diz que uma loja está fechada por incêndio, o perfil `comercio_varejista` não a reabre. Se um NPC está fora da área, `atores_comuns` não o traz de volta. Se há uma pendência estratégica, a ecologia não a silencia.

## Integração com cena transacional

Quando `cena_mundo.py preparar` recebe gatilho local:

1. resolve o alias para `local_id` canônico;
2. abre exatamente um índice ecológico;
3. anexa `local.ecologia` à preparação;
4. só depois executa a simulação de recompensa/gates já existente.

O perfil e o arquivo ecológico entram no fingerprint da preparação. Alterar a ecologia depois de `preparar` torna o `preparacao_id` antigo obsoleto, como qualquer outra fonte relevante.

Cena sem gatilho local não consulta ecologia. Ecologia também não exige leitura de tempo.

## Limite desta task

A Task 11 **não sorteia microeventos**. Ela só entrega o espaço de plausibilidade que a Task 12 poderá usar. Em particular:

- `canais_microevento` não são cartas;
- ritmo não é probabilidade de evento;
- `atores_comuns` não estabelecem indivíduos;
- nenhuma entrada do perfil vira fato sem resolução posterior legítima.

Contrato de custo: `baseline/local-ecology-orcamento.yaml`.
