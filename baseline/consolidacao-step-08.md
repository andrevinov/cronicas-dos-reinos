# Etapa 8 — baseline estrutural da consolidação transacional

A Etapa 8 fecha o circuito iniciado na Etapa 7: eventos baratos acumulados durante a narração agora podem virar cânone em lote sem reaplicação e sem exigir atualização de todos os destinos a cada turno.

## Contrato operacional

Durante um avanço narrativo comum continuam existindo somente dois destinos de escrita:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

A consolidação ocorre apenas em checkpoint de cena importante ou encerramento de sessão.

## Propriedades exigidas

- cada ID de transação é incorporado ao cânone no máximo uma vez;
- `sessoes/NNN/consolidacoes.jsonl` é o ledger de IDs já aplicados;
- PV, Ki, CA, dinheiro, nível e tempo permanecem coerentes entre suas representações espelhadas;
- relação/NPC atual é separado de seu histórico pós-migração;
- conhecimento novo entra em fragmentos incrementais sem alterar a reconstrução byte a byte do conhecimento legado;
- consequências e progressão só são materializadas quando houver delta explícito correspondente;
- rolagens ocultas e relógios reservados não vazam para artefatos públicos;
- texto humano já existente em resumo/consequências/experiência é preservado fora das seções automáticas;
- runtime novo é preparado no mesmo lote e não exige regeneração posterior;
- o buffer pendente é instalado por último.

## Segurança contra queda

Antes da primeira escrita canônica, todos os bytes finais são preparados em `runtime/.consolidacao-stage/` e seus hashes entram em `runtime/consolidacao-em-andamento.json`.

Enquanto o journal existe, leituras operacionais e novos turnos são bloqueados.

`consolidar.py recuperar` aceita para cada destino apenas o hash anterior ou o hash final staged. Assim, uma queda após N arquivos não transforma um `inc` em incremento duplicado quando o processo volta.

## Testes de referência

`tests/test_consolidacao.py` cobre:

- aplicação de recursos, tempo e localização com espelhamento em ficha/estado;
- esvaziamento do buffer somente no final;
- segunda consolidação sem reaplicação;
- criação de relação e NPC novos;
- conhecimento incremental e consequência;
- queda no meio da instalação e recuperação sem duplicar Ki/dinheiro;
- rejeição de segredo direcionado a arquivo público;
- relógio e rolagem oculta mantidos na área reservada;
- fechamento de sessão preservando texto manual e registrando progressão explícita.

## Métrica para o próximo rollout real

A consolidação será medida separadamente do loop narrativo. O objetivo não é que consolidar custe zero, e sim **amortizar muitas alterações em poucas execuções**.

Indicadores desejados:

- avanços narrativos continuam próximos de 2 arquivos escritos;
- arquivos canônicos alterados por turno comum permanecem em 0;
- número de consolidações é muito menor que número de avanços narrativos;
- nenhum evento é reaplicado;
- nenhuma retomada exige reconstrução manual do estado;
- o custo de uma consolidação é distribuído pelo número de turnos que ela incorpora.

Esta baseline não altera fatos da campanha. O buffer real permanece vazio durante a refatoração.
