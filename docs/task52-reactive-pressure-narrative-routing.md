# Task 52 — Reactive Pressure & Narrative Routing

## Status e dependências

**Planejada.** Este documento não altera sozinho o estilo ou o hot path.

Depende das projeções das Tasks 48–51 e integra os contratos existentes de iniciativa social, densidade narrativa, encontros, ameaça e mecânica diegética.

## Problema

Mesmo quando o mundo possui uma pressão material plausível, o narrador pode privilegiar conversa procedimental, explicação, nova oferta ou censura social. Isso não é apenas questão de prosa: se uma operação adversarial já foi comprometida e não aparece no preparo como prioridade, ela pode ser esquecida ou suavizada.

O manual já proíbe sermões sem gatilho e repetição de bronca. Falta fazer o hot path apresentar pressões comprometidas de forma impossível de confundir com sugestões opcionais.

## Objetivo

Criar um roteador compacto que ordene matérias já autorizadas para a cena e faça ações adversariais comprometidas prevalecerem sobre iniciativas incidentais, sem quotas artificiais de combate e sem fabricar ameaça.

## Implementação

### Projeção de pressão

`cronica preparar` anexará `pressao_narrativa` quando existir matéria causal ativa. Cada item terá:

- tipo: `operacao_comprometida`, `combate_ativo`, `fronteira_temporal`, `evidencia_em_risco`, `prazo_sidequest`, `iniciativa_social`, `nova_oportunidade` ou equivalente versionado;
- origem canônica e ID;
- urgência e janela;
- presença/percepção disponível a Ren;
- resolução exigida ou caráter opcional;
- bloqueios ainda aplicáveis;
- digest do contrato que autoriza a pressão.

Ordem padrão:

1. pendência/fronteira bloqueante e operação adversarial comprometida;
2. combate, perseguição ou perigo imediato já iniciado;
3. tempo comprimido interrompido e evidência/pessoa em risco;
4. prazo de missão ativa ou reação elegível ainda não comprometida;
5. ação social solicitada pelo jogador;
6. nova oportunidade causal;
7. iniciativa social ou rotina incidental.

A ordem organiza atenção; não decide a ação de Ren nem obriga todo risco a virar combate.

### Contrato de resolução

Quando houver pressão comprometida, o ticket carregará `contrato_pressao` e `cronica concluir` exigirá um dos resultados:

- `apresentada`: a ameaça entrou na situação jogável;
- `resolvida`: a cena produziu resultado factual;
- `adiada_por_bloqueio`: existe bloqueio causal explícito e validado;
- `continua`: a pressão permanece ativa depois da ação de Ren.

Não será permitido concluir o turno como conversa neutra enquanto uma emboscada já comprometida deveria começar. Isso não exige procurar combate: exige respeitar a ação do mundo já decidida.

### Iniciativa social e censura

Iniciativa social não cria presença, conhecimento, sidequest ou interrupção de uma pressão superior. Conselho/censura continua exigindo gatilho existente. Quando um NPC já expressou a mesma objeção e nada material mudou, a projeção relacional deve preferir silêncio, ação prática ou resposta ao assunto atual.

Não haverá parser de “tom moral” nem teste de palavras proibidas. A proteção será estrutural:

- iniciativa social perde prioridade para pressão comprometida;
- conselho exige causa identificada;
- o mesmo `topico_censura` não pode ser emitido repetidamente sem fato novo;
- resposta prática pode coexistir com uma observação curta do NPC.

### Combate e ação

Quando o item prioritário for ataque comprometido:

1. preparar encontro e ameaça antes da primeira rolagem;
2. narrar sinais perceptíveis, surpresa e iniciativa conforme regras;
3. permitir evasão, negociação, fuga, ocultação ou outra reação coerente;
4. não substituir o ataque por ameaça verbal apenas para reduzir risco;
5. não aumentar forças depois de observar sucesso de Ren.

O sistema favorece consequência concreta, não combate de preenchimento.

## O que esta Task resolve

- Pressões reais deixam de ser soterradas por burocracia ou conversa incidental.
- Ações adversariais comprometidas entram efetivamente em cena.
- Combates causais recebem preparação mecânica adequada.
- Sermões repetidos deixam de ocupar o lugar de ação prática.
- O narrador continua livre para cenas sociais relevantes quando não há pressão superior.

## Testes

Criar `tests/test_reactive_pressure_routing.py` e ampliar testes de iniciativa social/cronica.

Cobertura obrigatória:

1. operação comprometida aparece antes de iniciativa social e nova oportunidade;
2. pressão bloqueante exige decisão de conclusão;
3. conversa neutra não pode encerrar silenciosamente uma pressão comprometida;
4. bloqueio causal válido permite adiamento sem apagar a reação;
5. pressão `continua` reaparece no preparo seguinte;
6. iniciativa social não cria presença, segredo, ação física ou sidequest;
7. `topico_censura` repetido sem fato novo é suprimido estruturalmente;
8. fato novo reautoriza resposta social coerente;
9. ataque comprometido exige encontro/mecânica preparados antes da rolagem;
10. turno sem pressão preserva o comportamento neutro e não ganha leitura adversarial;
11. nenhum teste tenta julgar qualidade literária por substring frágil;
12. nenhuma quota de combate, RNG ou scheduler novo é introduzida.

Regressões a preservar:

- iniciativa social relacional;
- pending gate do Mundo Vivo;
- cena mecânica e ameaça;
- turnos neutros da Task47;
- densidade e controle de Ren.

## Definition of done

- pressão comprometida possui contrato de resolução no ticket;
- prioridade é estrutural e determinística;
- conselho repetido exige fato novo;
- turno neutro permanece barato;
- testes usam fixtures controladas e nomes de domínio;
- `test-domain cronica mundo sidequests`, `test-full` e `preflight` verdes.
