# Task 41 — Emergent Sidequest Authoring & Registry v2

## Propósito

A Task 40 responde apenas se uma cena produziu matéria causal suficiente para **pensar** uma aventura. A Task 41 transforma esse pacote numa sidequest completa e persistente, mas somente depois que a oferta realmente entrou na ficção.

A unidade criada aqui é um mini-arco: possui origem, oferta, prazo, fases, lugares, elenco, oposição, condições objetivas de sucesso/falha, stakes, recompensas declaradas, segredos, bifurcações e uma relação explícita — ainda não executiva — com a espinha canônica.

## Fluxo transacional

1. `oportunidade_sidequest.py planejar` devolve o pacote Task40.
2. O narrador autoria uma especificação Task41 a partir **somente** das possibilidades legitimadas por esse pacote.
3. `sidequests_emergentes.py preparar` valida tudo e devolve `preparacao_id`; zero writes.
4. O NPC/mensagem/instituição oferece a quest diegeticamente. Ren continua livre para responder.
5. Se a oferta realmente ocorreu, `sidequests_emergentes.py materializar --oferta-narrada ...` revalida a mesma preparação e registra a quest como `oferecida`.
6. Se a oferta não ocorreu, não se chama materializar — ou materializar sem `--oferta-narrada` retorna sem qualquer leitura/escrita. Nenhuma quest fantasma nasce.

`preparar` e `materializar` recebem via stdin um YAML/JSON com `pacote_task40` e `quest`; não é necessário criar arquivo temporário.

## Registry sem segundo lifecycle

A Task 41 não cria outro estado concorrente. `narrador/oportunidades/estado.yaml` continua sendo autoridade para `oferecida`, `aceita`, `adiada`, `recusada`, `expirada`, `concluida` e `falhada`.

Cada quest emergente ganha:

- `mission_id` `sqe-...` no lifecycle existente;
- `quest_id` `qse-...` determinístico;
- fragmento completo em `narrador/sidequests-emergentes/quests/<qse-id>.yaml`.

`listar` consulta somente índice+estado de oportunidades. `mostrar` abre apenas o fragmento solicitado.

## Schema de autoria

A especificação exige:

- `titulo` e `tipo` compatível com o lifecycle existente;
- `origem_causal`, que deve espelhar exatamente a âncora Task40;
- `quest_giver` com legitimidade explícita para fazer o pedido;
- `oferta` com premissa/pedido e recusa obrigatoriamente permitida;
- `premissa`, `prazo` e `objetivo`;
- `fases`, cada uma descrevendo uma situação do mundo e condição observável de avanço;
- `locais` canônicos ou propostos;
- `npcs_existentes` e `npcs_novos`;
- `antagonistas` com função e objetivo próprios;
- `juppongatana`, quando houver, escolhidos somente dentre os candidatos do pacote Task40;
- `condicoes_sucesso` e `condicoes_falha` objetivas;
- `stakes`: o que está em risco, consequência de expiração e perdas possíveis;
- `recompensas` declaradas;
- `relacao_canone`;
- `segredos` e `bifurcacoes`.

## Agência de Ren

O plano descreve o problema e o mundo, nunca a solução escolhida pelo jogador.

Inválido:

> Ren vai investigar o armazém e depois seguirá o mensageiro.

Válido:

> A pista está no armazém; se ninguém a recuperar antes do amanhecer, a oposição a destruirá.

O validator recusa chaves de agência (`acao_ren`, `decisao_ren`, `fala_ren`, `emocao_ren`, etc.) e formulações que prescrevem ações/escolhas futuras de Ren.

## Elenco novo não é presença

`npcs_novos` são elenco reservado do mini-arco. Na Task 41 eles devem ter `estatuto: reservado_nao_presente`.

Materializar a quest **não cria automaticamente esses NPCs no estado do mundo, não os coloca em local algum e não os torna conhecidos por Ren**. Uma cena posterior precisa canonizar identidade/presença pelos mecanismos normais.

O mesmo vale para Juppongatana: aparecer no plano da quest é permissão autoral condicionada, nunca teleport, presença ou revelação automática.

## Antagonistas e stakes obrigatórios

Toda quest precisa declarar oposição suficiente para sustentar uma aventura e o objetivo próprio de cada antagonista/força. Isso pode ser um ator estratégico que já veio da Task40, um NPC existente, NPC novo, facção, instituição ou circunstância hostil.

Também precisa declarar stakes concretos e condições de falha. A Task 41 congela esses contratos; ela **não os executa**. A Task 45 será responsável por aplicar efeitos quando sucesso, falha ou prazo forem efetivamente resolvidos.

## Recompensas obrigatórias

Toda quest precisa declarar ao menos uma recompensa possível. A estrutura já distingue tipo, modo (`sucesso`, `descoberta`, `condicional`), condição, valor aproximado e autoridade concedente.

Recompensas materiais não podem exceder o teto do envelope Reward Budget recebido da Task40. Recompensas narrativas especiais — propriedade, direito de uso, favor, contato, acesso etc. — podem existir, mas precisam declarar quem possui autoridade causal para concedê-las.

A Task 41 **não entrega prêmio algum**. Ela só registra o contrato. A Task 43 aprofundará descoberta/posse/orçamento e a Task 45 executará os contratos quando a resolução da quest justificar.

## Relação com o cânone

Modos registrados:

- `lateral`;
- `candidata_ponte`;
- `candidata_convergente`;
- `candidata_adiamento`;
- `candidata_transformacao`.

Uma quest não lateral só pode citar intenções que vieram no pequeno horizonte Task40. Mesmo assim, nesta Task a relação é **candidatura**. Somente a Task 42 poderá criar rewrite, reserva, satisfação, transformação ou adiamento real de intenção canônica.

## Idempotência e interrupção

A materialização instala primeiro o fragmento determinístico e depois registra a missão no lifecycle. Se houver interrupção entre as duas escritas, um retry com exatamente o mesmo conteúdo aceita o fragmento órfão e completa o estado; um fragmento divergente falha fechado.

Retry depois da missão registrada retorna `ja_materializada` e não duplica missão, histórico ou fragmento.

## Economia

- preparação: 0 writes;
- sem oferta narrada: 0 reads / 0 writes;
- materialização: no máximo 2 writes;
- fragmento completo: <= 20 KiB;
- saída de preparação: <= 8 KiB;
- nenhum scheduler, RNG, `rglob`, `glob`, transcript ou scan global;
- não abre catálogo Task33 nem fragmentos narrativos Task36;
- consulta de lista não abre os fragmentos completos.

O custo existe somente quando uma oportunidade Task40 já foi explicitamente sinalizada e o narrador decidiu realmente autoria-la.
