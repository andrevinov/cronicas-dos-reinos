# NV-07 — reconciliação do PR #120 com o #119

## Uma única implementação operacional

Os PRs #119 e #120 foram implementações concorrentes da mesma etapa, não duas
etapas complementares. Após o merge do #119, a autoridade operacional é
`ferramentas/acionamentos_leves.py`, com o controle `acionamentos_leves` e a causa
`acionamento_causal`. O manual vigente é `docs/agente/acionamentos-causais.md`.

A resolução textual dos conflitos do #120 deixou código de ambos os mecanismos.
Em especial, `turno.py` ainda chamava `acionamento_npcs.deadline_reached` após o
import correspondente ter sido substituído. Isso causava `NameError` em avanços
curtos e longos. `checkpoint.py`, `fronteira_mundo.py` e trechos sem marcadores
continuavam usando a segunda fila, produzindo duas representações do mesmo prazo.

A reconciliação restaurou os arquivos operacionais à versão integrada do #119,
sem sobrepor outro scheduler. O módulo alternativo `acionamento_npcs.py` foi
retirado: não fica código morto testando a si mesmo nem uma segunda fonte de
verdade escondida. A cobertura foi portada para o motor adotado. Depois disso,
o teste de cancelamento revelou uma falha real no staging repetido, corrigida
pontualmente em `acionamentos_leves.stage` e descrita abaixo. Portanto, o diff
final inclui essa correção de produção, além dos testes e da documentação.
A branch e o histórico do #120 são preservados por commits normais, sem
force-push ou alteração da main.

## Compatibilidade sem mascarar falhas

Os 36 cenários de domínio e os 21 cenários de integração do segundo PR foram
portados para o motor realmente instalado. Isso não significa preservar os nomes
de campos ou as escolhas internas de uma API alternativa que nunca foi adotada.
As divergências semânticas foram tratadas explicitamente:

- Motivos públicos: `acontecimento_relevante` e `prazo_relevante`.
- Projeção do lote: `contexto.acionamento_causal` e classificação
  `avaliar_condicao_causal`, não `acionamento_npc`/`avaliar_condicao_concreta`.
- A fronteira identifica `compromisso:<id>:<fase>`, uma vez. O destinatário continua
  verificado na fila. Não são aceitos dois candidatos para o mesmo prazo.
- A barreira conta os itens ativos. Causas aguardando são verificadas separadamente;
  a conclusão repõe a próxima vaga antes de instalar o estado e só libera o turno
  depois de escoar o trabalho. O teste exige dois ativos, um aguardando e todas as
  três avaliações concluídas; não apenas um número menor na saída.
- Cancelamento revoga o gatilho antigo com `gatilho_revogado`. Não inventa
  cumprimento/falha nem gera uma nova autoavaliação para o mesmo NPC. A remoção do
  compromisso, o recibo, o histórico da revogação e a recuperação são verificados.
- Resolver uma causa não cria loop por causa da própria alteração. O teste exige
  persistência da mudança, preservação do ID durante a resolução, retry sem
  escrita e notificação de outro dependente explícito.
- Um no-op exige motivo concreto no contrato da main. Ausência, texto curto e
  ausência de ação de Ren continuam rejeitados, antes de gravar cache ou estado.
  O antigo teste supunha que qualquer nota sem a flag da API alternativa seria
  inválida, o que não faz parte da porta instalada.
- Informação no teste integrado usa `informacoes_recebidas`, domínio reconhecido
  pela seleção NV-03. Não se supõe que qualquer nome arbitrário de campo seja
  automaticamente classificado como conhecimento. O valor inteiro e seu estatuto
  `rumor` precisam aparecer; as relações dos demais NPCs permanecem byte-idênticas.

## Rastreabilidade da cobertura de domínio

Arquivo preservado: `tests/test_acionamento_npcs.py` (36 cenários). Os helpers de
teste apenas compõem o índice, a entrada e a cópia staged; não implementam fila,
relógio, roteamento ou projeção paralelos.

| Propriedade da versão anterior | Cobertura no motor único |
| --- | --- |
| Causa antes de rotina, dois slots, IDs restaurados | `CausalQueueTest.test_causa_precede_rotinas_sem_aumentar_dois_slots` e `test_reposicao_nao_duplica_id_entre_rotina_ativa_e_suspensa` |
| Coalescência, repetição, ordem determinística | testes `test_mesmo_agente_coalesce_sem_trocar_id_rotineiro` e `test_replay_mesma_causa_e_deterministico_e_idempotente` |
| Backlog e liberação no mesmo minuto | `test_conclusao_reabastece_adiadas_sem_amanhecer` e integração de três dependentes |
| Somente assinantes/ativos, isolamento de agentes estratégicos | testes de dependências compartilhadas, inativo e domínio estratégico |
| Overflow e controle malformado | `test_fila_cheia_falha_sem_descartar_a_entrada_staged`, `test_controle_e_causas_malformados_falham_fechado`, mais teste integrado de stage sem escrita |
| Sinal não executa ação; resolução não se perde | teste `test_notificar_nao_executa_acao_nem_atribui_conhecimento` e integração de resolução com outro dependente |
| Início/fim, recibos além do histórico, janela descritiva | dez testes de `CausalDeadlineTest` |
| Cancelamento/substituição/troca de envolvidos | testes de revogação e nova entrega; assertivas do schema retirado não permanecem como exigência artificial |
| Fonte dirigida, rumor inteiro, lacuna de orçamento | oito testes de `CausalProjectionTest`, exercitando `pending_context` real |
| Fonte alterada, inclusive fora do recorte; remoção | `base_fonte` muda, conteúdo antigo não reaparece; token obsoleto rejeitado na integração |
| Symlink e fontes não assinadas | teste de fuga por symlink e testes de dependência explícita |
| Listas/alterações pendentes e não mutação do original | `CausalDependencyTest` usa `_changed_source` com o overlay real |
| Negativa barata e ausência de nova fila | testes de gate neutro, lote vazio e legado sem camada |

O controle antigo de ponteiros por campo não é mantido como segundo índice.
A implementação adotada usa a fonte integral e seu digest para invalidar o lote,
com memória relevante e consulta dirigida. O teste exige fato indivisível ou lacuna
explícita, não corte de strings. Duplicidade entre rotinas ativas/suspensas é testada
na preempção e reposição reais, não por construção de um schema abandonado.

## Integração e regressões adicionais

`tests/test_acionamento_npcs_integracao.py` mantém as 21 jornadas com fixtures,
writer, calendário Harptos, checkpoint, journal interrompido, lote e CLI em
processo novo. Preserva as asserções da promessa NV-04: ID compilado, persistência,
NPC correto, checkpoint público e duas causas (relação e compromisso).

Três regressões adicionais cobrem especificamente a reconciliação:

1. Overflow do lote falha antes de instalar fato, notificações ou barreira.
2. Um prazo seguido de checkpoints/recovery não cria dois controles ou duas entregas.
3. As sete portas operacionais não importam nem referenciam o módulo retirado.

Todos os testes anteriores da main, incluindo guardas de journal antes da primeira
leitura e recuperação de conclusão interrompida, permanecem sem modificações.
Nenhum teste usa `skip`, nenhum validador foi afrouxado e nenhum estado da campanha
foi alterado para satisfazer uma expectativa.

## Cancelamento e identidade da resolução durante o staging

`test_cancelamento_em_resolucao_nao_deixa_prazo_falso` revelou que repetir
`stage` sobre o mesmo plano podia recriar uma causa `compromisso:mapa` para o
próprio agente cuja resolução havia cancelado o compromisso. Na primeira passagem,
o prazo era corretamente revogado. Na segunda, o vínculo `id da pendência → agente`
era reconstruído dos `outputs` já modificados; como a pendência já não existia,
a tag de resolução perdia seu destinatário e a mudança parecia independente.

O vínculo agora é obtido do mundo canônico persistido, que é a base ainda não
instalada do lote. O mundo staged continua sendo usado para as alterações e
preserva saídas de outros produtores; não é substituído pela base antiga.
Sem saída de mundo prévia, a mesma leitura da base é reutilizada. Nada muda nos
schemas, tetos, chamadas de IA, protocolo do writer ou dados da campanha.

O teste de integração que revelou o problema permanece intacto. As sete regressões
em `tests/test_acionamentos_staging.py` exercitam explicitamente a repetição do
staging, sem depender da ordem de imports: cancelamento sem autoavaliação, outro
envolvido ainda notificado, fonte alterada junto do cancelamento, fato independente
não suprimido, saída de outro produtor preservada, rotina promovida mantendo ID e
uma única leitura do mundo quando não há saída prévia. Também verificam igualdade
dos bytes staged, imutabilidade das transações e ausência de escritas na fixture.

## Orçamento e validação

O contrato acompanha a implementação adotada: duas avaliações leves ativas, uma
nova rotina por checkpoint elegível, oito causas por agente, 32 sinais, 16 KiB de
controle e 2.560 bytes por contexto causal. A regressão existente da main cobre
as duas avaliações no envelope conjunto de 8 KiB. Não se preservam os limites
maiores da implementação descartada.

Os registros `NV07_BYTES` medem bytes YAML, não tokens nativos. Não há alegação de
economia de episódios narrados ou melhora literária a partir de testes estruturais.
A confirmação dos checks deve corresponder ao head final, não ao antigo
`c3c45e8`, que era verde antes da junção das duas implementações.
