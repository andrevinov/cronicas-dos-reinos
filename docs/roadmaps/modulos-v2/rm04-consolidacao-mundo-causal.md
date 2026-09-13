# RM-04 — Consolidação do mundo causal

## Status e dependências

**Proposta.** Depende das RM-01–RM-02.

## Objetivo

Organizar seis capacidades atuais em três módulos:

- `scene_world_projection`;
- `world_boundary_resolution`;
- `causal_narrative_routing`.

## Implementação

### Scene world projection

Compor incidentes, microeventos e condições persistentes em uma projeção espacial
única por gatilho real. Preservar reserva determinística, ausência de reroll e
distinção entre contexto ambiental e efeito mecânico.

### World boundary resolution

Compor vivacidade durante compressão temporal e resolução em lote de pendências.
A fronteira decide interrupção ou calma justificada; a barreira materializa apenas
itens que requerem resolução. Retry não sorteia novamente nem duplica evento.

### Causal narrative routing

Receber somente matérias já autorizadas, incluindo eventos canônicos datados, e
ordená-las por urgência. O roteador não vira produtor universal, scheduler ou
licença para abrir fontes reservadas.

## Invariantes

- turno curto não consulta fronteira temporal;
- permanência reutiliza identidade espacial da janela;
- condição persistente não vira teste ou penalidade automaticamente;
- evento canônico devido nunca é no-op;
- pressão comprometida não é soterrada por matéria incidental;
- ausência de causa produz calma comprovada, não ameaça inventada;
- nenhuma nova chamada de orquestração entra no turno neutro.

## Testes

- uma projeção espacial pode conter várias subcapacidades, mas conta um módulo;
- fronteira e lote preservam exatamente-once em retry/recovery;
- roteamento não abre produtor reservado inelegível;
- cenários de permanência, trânsito, sono e dia calmo permanecem cobertos;
- orçamentos existentes não são afrouxados sem medição explícita.

## Definition of done

- seis aliases v1 têm destino e fachada v2;
- produtores, fronteira e roteador continuam causalmente separados internamente;
- ledger distingue gate neutro de evento material;
- nenhum estado paralelo ou scheduler é criado;
- perfis `mundo`, `cronica` e `sessoes` ficam verdes.
