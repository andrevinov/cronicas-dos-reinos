# Baseline de aceitação — Etapa 12

Data de implantação: 2026-08-15/16

## Papel

Este arquivo registra **o contrato da auditoria final**, não um novo estado canônico da campanha.

A referência histórica de integridade continua sendo `baseline/estado-logico-2026-08-15.yaml`. A referência de custo pré-refatoração continua sendo `baseline/rollout-2026-08-15.json`.

## Critérios obrigatórios

A Etapa 12 só pode ser declarada concluída quando `python3 ferramentas/auditoria-final.py --json` retornar:

```json
{
  "veredito": "PRONTO PARA RETOMAR",
  "pronto_para_retomar": true
}
```

Todos os gates abaixo precisam estar verdes:

1. `estrutura_acumulada`;
2. `regressoes_e_baseline`;
3. `retomada_somente_camada_quente`;
4. `retomada_com_delta_pendente`;
5. `telemetria_pos_hoc`;
6. `privacidade_rollouts`;
7. `auditoria_sem_mutacao`.

## Estado que deve sobreviver à migração

No instante da auditoria final, o runtime/handoff ainda representa o ponto em que o jogo foi suspenso para a refatoração:

- sessão 3;
- campanha `em_sessao`;
- modo `resgate_rural`;
- Ren Kagehira, Monge 6, Caminho da Sombra;
- PV 45/45;
- Ki 5/6;
- CA 17;
- 7 Eleasis, 1372 DR;
- aproximadamente 08:03 de 7 Eleasis;
- estrada do Fire River;
- Ren adjacente ao homem de mãos limpas junto à cerca de salgueiros;
- é o turno de Ren no confronto atual.

Esses valores não são uma nova fonte independente. Eles são consequência das fontes canônicas e da baseline lógica capturada antes da reforma.

## Prova de retomada fria/quente

O teste de aceitação remove do sandbox:

- transcrição da sessão;
- `estado/estado-atual.yaml`;
- ficha;
- `historico/`.

Mesmo assim `contexto.py retomada` deve reconstruir a cena a partir de runtime + handoff + pendências.

Isso é o critério operacional que separa “arquivos frios documentados como frios” de “arquivos realmente dispensáveis na retomada normal”.

## Prova de interrupção entre checkpoints

Um segundo sandbox recebe um delta sintético de Ki no buffer pendente. A retomada precisa projetar esse delta sem consolidá-lo e sem tocar o repositório real.

## Imutabilidade

A auditoria calcula digest das áreas protegidas antes e depois. O digest deve permanecer idêntico.

Nenhuma execução de aceitação pode avançar a história, alterar PV/Ki/dinheiro, modificar relações, criar conhecimento, reescrever transcrições ou consolidar deltas reais.

## Telemetria

A Etapa 11 está testada funcionalmente, mas não há ainda rollout **real de jogo pós-refatoração**, porque a campanha permaneceu suspensa durante a migração.

Portanto:

- metas pós-refatoração estão definidas;
- analyzer/comparador estão verdes;
- a economia real será medida depois que a campanha voltar e produzir novos avanços;
- nenhum número sintético deve ser apresentado como economia observada da campanha.

## Saída da migração

Depois deste gate final verde, a próxima operação narrativa normal deve começar pela informação já disponível e, se necessário, por:

```bash
python3 ferramentas/contexto.py retomada
```

Não há necessidade de reler transcrições ou reexecutar a auditoria a cada sessão/turno.
