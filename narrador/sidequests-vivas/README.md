# Side quests vivas — NV-17

Este diretório contém somente **controle reservado** da NV-17. Não é uma fonte narrativa paralela e não autoriza inventar uma side quest.

`estado.yaml` reserva no máximo uma nova oportunidade por janela operacional (`data + período`) para impedir que novos `preparar`, retries ou mudanças de `scene_id` troquem a causa escolhida. A reserva guarda apenas o sinal que será entregue ao pipeline Task40/46; ela não cria fato, missão, oferta, recompensa ou consequência.

`migracao-legado.yaml` é o recibo one-shot da migração do catálogo Task32/33. O catálogo frio continua fisicamente no repositório para compatibilidade histórica e auditoria, mas não participa do runtime NV-17. Uma entrada somente poderia ter sido convertida quando `evidencias-migracao.yaml` apontasse explicitamente um plano NV-11 do mesmo NPC cuja causa canônica fosse validável. Sem isso, a entrada é arquivada com razão explícita. Texto da antiga quest, afinidade, presença e ausência de missões nunca contam como evidência.

## Fonte viva

A fonte operacional é `oportunidade_sidequest` dentro de um passo de plano NV-11. A causa deve apontar para uma necessidade, conflito ou impedimento já existente no estado canônico do próprio NPC. A projeção compacta preserva dono, bloqueio, conhecimento, alcance, reavaliação, stakes e proteções. O runtime consulta a agenda NV-08 e, opcionalmente, uma referência de plano; não percorre perfis de NPC ou o catálogo legado.

Uma causa vencida só pode ocupar o slot se houver rota até Ren: presença já estabelecida do dono ou um canal de contato validado pelo motor existente. Coincidência de local serve para indexar a consulta, mas sozinha não inventa presença. Zero side quests ativas pode elevar a precedência de uma causa válida, jamais criar uma.

A Task46 permanece a autoridade de materialização. Mesmo quando a NV-17 projeta automaticamente uma causa, nenhuma quest nasce se a oferta correspondente não aparecer literalmente na narração e no bloco transacional da conclusão.
