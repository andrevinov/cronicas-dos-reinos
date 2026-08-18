# Correções de continuidade da Sessão 007

## COR-007-001 — Reparação do checkpoint final

- Data da correção: 2026-08-17
- Motivo: o checkpoint final aplicou localização e hora corretas, mas conservou campos operacionais do início da sessão, anteriores às interações com Halessa, Silva e Nera.
- Informação anterior: o modo e a descrição operacional ainda indicavam que Ren aguardava o relato a Luath; o documento falsificado ainda aparecia sob posse de Ren; a data estruturada permanecia em 9 Eleasis; campos narrativos antigos ainda apontavam para o confronto na casa de Iria.
- Informação corrigida: Ren entregou formalmente o documento à Casa de Tyr, voltou ao circo, conversou com Silva, compartilhou um momento íntimo e romântico com Nera, dormiu poucas horas sem completar descanso longo, assumiu a persona de Shinta e chegou à Casa do Salgueiro Seco ao primeiro clarear de 10 Eleasis.
- Natureza: correção de projeção e checkpoint; nenhum acontecimento da transcrição ou do resumo consolidado foi alterado.
- Arquivos atualizados: `estado/estado-atual.yaml`, `estado/tempo.yaml`, `sessoes/007/alteracoes-de-estado.yaml`, `sessoes/007/handoff.yaml`, runtime e memória compacta da sessão corrente.
- Consequências: o documento falsificado deixa o inventário de Ren; a retomada passa a abrir diante do portão lateral da Casa do Salgueiro Seco, aguardando o jardineiro, e não na conversa com Luath.

## COR-007-002 — Operação da Ponte Baixa removida dos prazos futuros

- Data da correção: 2026-08-17
- Motivo: o prazo de vigilância da Ponte Baixa foi carregado para 10 Eleasis como se ainda fosse futuro, embora a operação, o encontro de Brass e Rook, a perseguição de Kurobane e a recuperação do documento tenham ocorrido na noite de 9 Eleasis.
- Informação anterior: Luath ainda colocaria observadores antes do poente de 10 Eleasis e Brass ainda cruzaria a ponte depois do segundo sino.
- Informação corrigida: esses acontecimentos pertencem ao histórico concluído da sessão 7 e não figuram mais entre os prazos operacionais da sessão 8.
- Natureza: correção de projeção temporal; nenhum acontecimento da sessão concluída foi alterado.
- Arquivos atualizados: `estado/tempo.yaml`, `sessoes/007/handoff.yaml`, runtime e memória compacta da sessão corrente.
- Consequências: permanecem como prazos futuros apenas a segunda manhã de Shinta, a visita prevista de Tomas Rell e a apresentação de Kage em 17 Eleasis.
