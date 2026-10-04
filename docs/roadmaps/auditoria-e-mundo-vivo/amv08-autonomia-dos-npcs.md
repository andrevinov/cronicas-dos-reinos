# AMV-08 — NPCs com convicções, objetivos e iniciativa própria

**Data:** 2026-10-04. **Status:** proposta. **Dependências:** AMV-06–07.

## O que implementar

Generalizar os perfis decisórios além dos três pilotos, usando campos de domínio
com fonte: valores, desejos, receios, método, limites, capacidade e objetivos
atuais. Prosa de papel conversacional pode alimentar a curadoria, mas não servir
como chave literal que determina se um NPC possui personalidade. Lacuna de dado
deve ser explícita; não inventar convicção histórica para satisfazer schema.

No preparar, avaliar elenco relevante já presente ou legitimamente contactável,
memória de cena e causas alcançáveis, sem exigir seleção manual de interlocutor
para descobrir que alguém tinha motivo para agir. `--participante` continua
seleção prospectiva: não cria presença. `--interlocutor` continua exigindo presença
ou canal válido. A avaliação fica limitada ao recorte, sem scan de todos os NPCs.

Ampliar motivos legítimos além de compromissos: objetivo próprio, preocupação,
conflito de valores, informação percebida, oportunidade, ressentimento ou
mudança relacional. Produzir uma decisão social fundamentada, que pode ser
abertura, recusa, contraproposta, adiamento ou silêncio. Preservar no máximo uma
abertura por janela, evitando que todo personagem fale em todo turno.

Ligar decisões fora de cena à cadeia da AMV-07. Personalidade influencia método,
prioridades e limites; não obriga comportamento teatral idêntico em qualquer
situação. Identidades, reputações e conhecimentos não se fundem por conveniência.

## Por que corrige a causa

Uma personalidade restrita a pilotos e uma iniciativa dependente de argumento
manual não sustentam o elenco inteiro. Avaliar causas reais do recorte torna a
iniciativa alcançável; objetivos e limites tornam a ação coerente. Negativas
fundamentadas preservam naturalidade e evitam trocar passividade por fala compulsiva.

## Prova de correção e aceite

- NPC fora do piloto, com perfil e causa válidos, inicia ou tenta algo coerente
  pela porta pública, sem flag manual criada apenas para o teste passar.
- Reencontro lembra promessa ou mudança relacional e afeta uma decisão concreta.
- NPC pode discordar, negar ajuda ou propor condições sem decidir a resposta de Ren.
- Candidato ausente, sem canal ou sem conhecimento não recebe iniciativa falsa.
- Mesmo perfil com objetivos conflitantes ou risco diferente pode escolher outra
  ação, com justificativa ancorada; não depende de uma fala decorada.
- Sem causa, silêncio válido é registrado; retry e mesma janela não repetem abertura.
- Caso com causa elegível e ausência deliberada de avaliação é detectado como omissão.

## Onde mudar e o que poderá sair

Perfil decisório, memória de cena, iniciativa e fachada de continuidade social.
O gate de adoção restrita ao piloto e a correspondência literal de papel podem
ser aposentados após cobertura generalizada. Permanecem sigilo, presença,
continuidade, geração reservada de nomes e separação de personas.
