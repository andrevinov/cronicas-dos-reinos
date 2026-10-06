# Ecologia local

A ecologia local é uma **restrição de plausibilidade** para cenas incidentais. Ela descreve o tipo cotidiano de um lugar sem afirmar que qualquer pessoa, evento ou atividade está acontecendo agora.

O índice fica em `cenario/locais/ecologia.yaml` e cobre exatamente os IDs do registro canônico `cenario/locais/index.yaml`.

## Local efetivo e retry espacial

Permanência consulta `estado/estado-atual.yaml` com os deltas pendentes da sessão.
`localizacao.local_id` é vínculo explícito ao registro; descrição livre não é
resolvida por proximidade. ID e área cadastrada divergentes exigem correção pela
fonte. Na porta pública, entrada com mudança narrada de área compila o vínculo no
mesmo writer; saída sem entrada correspondente remove o ID antigo. Preparar não
move Ren. Buffer legado que muda área sem vínculo não transporta o ID anterior.

Falha espacial conserva cena e tipo em `runtime/preparo-espacial-pendente.json`.
Corrigir a causa e repetir o gatilho com o mesmo `--cena-id`; depois concluir o
ticket espacial. Neutralizar ou trocar o ID não satisfaz a operação. A reserva
de permanência continua no produtor e não é sorteada novamente.

Se **o jogador desistiu da operação**, a próxima chamada pode declarar
`--abandonar-preparo-espacial '<motivo factual da desistência>'`. O abandono fica
em `runtime/preparos-espaciais-abandonados.jsonl`; não remove reservas, planos,
pendências ou pressões causais. Nunca usar abandono para contornar falha técnica.

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

A ecologia local **não sorteia microeventos**. Ela só entrega o espaço de
plausibilidade que o baralho local pode usar. Em particular:

- `canais_microevento` não são cartas;
- ritmo não é probabilidade de evento;
- `atores_comuns` não estabelecem indivíduos;
- nenhuma entrada do perfil vira fato sem resolução posterior legítima.

Contrato de custo: `baseline/local-ecology-orcamento.yaml`.
