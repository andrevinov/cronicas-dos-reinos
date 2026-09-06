# NV-01 — Base confiável de testes e estado

## Escopo e origem

Base examinada: `aa29fb104237a79c72ad3ca203205726561c11e6`, checkpoint de 1º de setembro de 2026. A execução original de Integridade da campanha registrou 1.427 testes e cinco falhas, correspondentes a quatro causas: reserva ligada a missão terminal (dois testes), prazo temporal duplicado, expectativa de recurso temporário histórico e números mutáveis congelados na ficha.

A tarefa não altera regras de jogo, personalidades, compromissos narrados ou decisões do jogador. Não implementa NV-02 nem as melhorias de memória posteriores.

## Correções

### Autoridade temporal

Foi removida somente a cópia de `tempo.prazo_relevante` em `estado/estado-atual.yaml`. O mesmo texto permanece em `estado/tempo.yaml`, sua autoridade única. Data, hora, recursos, localização e efeitos correntes não foram modificados.

### Reserva canônica terminal

O lifecycle já havia registrado a missão como terminal; o bridge ainda mantinha sua reserva ativa. A reconciliação já existia em `canon_bridge.reconcile_lifecycle`, mas faltava na sequência do checkpoint depois de `interacoes_mundo.sync_lifecycle`.

O checkpoint passa a chamar essa autoridade após o lifecycle e antes de processar o mundo. Também a chama quando o lifecycle não sofreu uma nova alteração, cobrindo recuperação após interrupção entre as duas escritas. Sem reservas, não abre oportunidades, tempo ou fragmentos de intenção.

A reserva obsoleta instalada foi liberada com registro no histórico do próprio bridge, no instante canônico corrente. O estado terminal da missão, sua causa e seu instante de encerramento permanecem intactos. A ativação canônica de referência ainda é futura: nenhum evento foi materializado, antecipado ou declarado satisfeito, e nenhuma nova consequência foi inventada.

### Testes que confundiam estado vivo com fotografia histórica

`tests/test_ficha_ren.py` passa a comparar ataques, PV, Focus e proficiência com os respectivos campos da ficha atual. Não restaura valores antigos. A mutação controlada da ficha continua coberta em diretório temporário.

`tests/test_contexto.py` usa o snapshot histórico já existente da ativação 5.5e para testar o efeito legado em cenário isolado. Exercita tanto sua presença quanto sua remoção, sem exigir que o efeito continue ativo no estado vivo. A ficha sintética mantém o registro de habilidade removida: isso não pode fazê-la reaparecer como recurso executável.

Nenhum teste foi desativado, nenhum validador foi afrouxado e nenhum snapshot histórico foi reescrito.

## Regressões adicionais

`tests/test_checkpoint_canon_bridge.py` verifica expiração e liberação no mesmo checkpoint, recuperação de reserva terminal sem repetir o encerramento, restauração idempotente de fallback já devido e ausência de leituras adicionais de oportunidades/tempo quando não há reserva. Catálogo, evento e intenção permanecem byte-preservados nas fixtures.

## Preservação e orçamento

As únicas alterações de dados da campanha são a remoção da duplicata temporal e a liberação auditada da reserva terminal. Ficha, transcrições, relações, conhecimento, fila do mundo, buffer pendente, runtime, handoffs e estado da missão não são reescritos por esta tarefa.

Não há nova chamada de IA, scheduler, endpoint, varredura global ou instrução no AGENTS.md. A dupla comum `cronica preparar` / `cronica concluir` permanece inalterada. A leitura adicional do ledger ocorre somente no checkpoint; não representa um benchmark empírico de tokens. A medição comparativa pertence à NV-02.

## Validação

A reprodução e a validação integral usam os workflows existentes do GitHub Actions. O PR registra as execuções e seus resultados antes do merge. Integridade da campanha continua responsável pela suíte completa; Preflight continua executando os demais gates. Não se altera a configuração do CI para obter aprovação.
