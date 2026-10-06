# AMV-14 — Aceite por episódios realmente executados

**Data:** 2026-10-04. **Status:** avaliador antecipado em 2026-10-06; integração de jogo pendente.
**Dependências:** AMV-04–05 e AMV-07–13.

## Parte antecipada entregue

[Entrega de 2026-10-06](entrega-avaliador-2026-10-06.md): revisão pelo agente,
24 episódios com 168 verificações, diagnóstico por estágio, publicação protegida
e prioridades corrigidas. Essa parte depende de AMV-04–05. AMV-07–13 seguem
necessárias para executar os módulos alterados pelas portas públicas. Replay
de pareceres não conclui a integração nem inaugura aceite longitudinal.

Este é o aceite integrado das mudanças de jogo. O aceite inicial do avaliador
ocorre antes, no G0 da etapa A; não pode ser adiado até esta tarefa.

## O que implementar

Evoluir o benchmark narrativo e o aceite modular existentes para executar
episódios por portas públicas em campanha isolada, com o narrador efetivamente
configurado, contexto realmente entregue e ações de jogador controladas.
Registrar operações, respostas visíveis, alterações de estado, decisões de
fronteira e retomada. Não fornecer ao teste, como resultado esperado, a lista
de iniciativas ou consequências que ele deveria descobrir sozinho.

Manter duas camadas: regressões determinísticas de contratos na suíte e episódios
narrados com avaliação semântica independente. Replays congelados servem para
regredir o avaliador; não demonstram que uma mudança no narrador produz a mesma
qualidade. Alteração comportamental precisa de nova execução dos episódios
afetados, com versões e configuração registradas.

Ampliar a amostra externa com recortes históricos e episódios novos sobre os
objetivos de experiência, sem transformar a pequena amostra operacional em
gabarito literário. Congelar referências depois de revisão e reservar casos
independentes para detectar critérios ajustados aos exemplos conhecidos.

## Episódios mínimos

| Episódio | Prova esperada | Falha que a avaliação deve detectar |
| --- | --- | --- |
| Reencontro e promessa | Lembrança muda decisão depois de retomada | Promessa ignorada ou lembrança inventada |
| NPC fora do piloto | Iniciativa coerente sem seleção manual artificial | Causa legítima ignorada |
| Silêncio e calma | Negativa adequada sem evento obrigatório | Iniciativa fabricada para atingir quota |
| Plano fora de cena | Ação afeta cena futura por canal legítimo | Mundo congelado ou percepção onisciente |
| Quebra de acordo | Reação plausível e persistente | Retaliação sem conhecimento ou consequência esquecida |
| Sidequest multietapa | Oferta opcional, progresso e terminal | Missão esquecida, fase vazia ou prêmio duplicado |
| Desvio canônico | Forma muda e função dramática permanece | Roteiro literal incompatível ou núcleo apagado |
| Chuva e instituição | Condição/medida altera atividade posterior | Descrição decorativa ou penalidade sem causa |
| Perigo solo | Oposição capaz e alternativa viável | Vitória garantida ou obstáculo arbitrário |
| Retry e interrupção | Um único efeito após recuperação | Duplicação, reroll ou avanço indevido |

## Por que corrige a causa

Um cenário com candidatas previamente preenchidas prova o roteador sob aquela
entrada, mas não a descoberta e a narração da oportunidade. Executar a cadeia
completa e julgá-la por fontes externas à decisão do módulo fecha essa lacuna.

## Prova de correção e aceite

- Episódios demonstram causa → decisão → texto visível → efeito → lembrança,
  preservando contexto, versões e limites de conhecimento.
- Para cada propriedade crítica, injetar uma falha isolada no cenário ou na saída
  e comprovar que o gate correspondente reprova; caso legítimo continua passando.
- Vínculo de prosa e estado é verificável; trecho literal sozinho não vale como
  demonstração semântica da adequação da ação.
- Rodar tudo em `TemporaryDirectory`; hashes das fontes canônicas não mudam.
- Separar sucesso técnico, resultado da revisão e aceite real; fixture não
  inaugura a série nem confirma satisfação do jogador.
- Episódios custosos ficam na manutenção/aceitação de mudanças pertinentes,
  com replay determinístico na CI e proveniência de quando foram executados.

## Onde mudar e o que poderá sair

Benchmark narrativo, aceites integrados, corpus, amostra externa e testes de
domínio. Após equivalência demonstrada, o gate de piloto, o aceite de vivacidade
baseado em candidatas preenchidas e o smoke antigo podem sair do preflight.
Preservar os casos úteis como regressões com dono explícito.
