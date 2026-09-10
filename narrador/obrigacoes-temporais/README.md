# Estado reservado — obrigações temporais NV-18

Este diretório guarda apenas infraestrutura técnica da NV-18. O fato ficcional continua em `estado/estado-atual.yaml -> compromissos`; os arquivos daqui não criam acontecimentos, presença, conhecimento ou decisões de NPC por si sós.

- `evidencias.yaml`: lista pequena e explícita usada somente pela migração one-shot. Cada candidato precisa de evidência histórica literal e de uma fonte canônica atual. Não existe busca ampla de transcrições.
- `estado.yaml`: recibo da migração, adiamentos explícitos de no-op e rastros técnicos de despacho. `adiamentos` nunca encerram a obrigação; apenas registram quando/por qual condição ela deve voltar à fronteira.
- `indice.yaml`: projeção derivada por data, condição e responsável. Pode ser reconstruída a partir dos compromissos canônicos e não é um scheduler independente.

O hot path não lê histórico. No checkpoint, `obrigacoes_temporais.py` consulta somente compromissos temporais ativos, o tempo atual e fontes dirigidas necessárias a adiamentos por condição. Pressão vencida é entregue ao acionamento causal já existente dos agentes leves; compromissos com janela exata continuam usando o mecanismo de `prazo` de `acionamentos_leves.py`.

Um `concluir-noop` comum continua compatível. Se a pendência envolve obrigação temporal vencida, porém, o no-op só pode prosseguir depois de registrar `--retomar-data ... --retomar-hora ...` ou `--retomar-condicao ...`. O recibo é escrito antes de a pendência ser removida, de modo que queda/retry não apague o futuro causal.
