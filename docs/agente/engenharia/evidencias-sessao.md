# Evidências causais preservadas por sessão

Captura `evidencias_sessao` 1.0.0, schema 1. Configuração:
`configuracoes/evidencias-sessao.yaml`. A captura acontece na abertura, antes da
consolidação, depois do checkpoint e no encerramento; recuperação de journal
completa a captura correspondente. Não é executada no preparar/concluir comum.

## Arquivo reservado e recuperação

Destino padrão: `~/.local/state/cronicas-evidencias/<id-do-repositorio>/NNN.json`.
`CRONICAS_EVIDENCIAS_DIR` permite escolher outro diretório **fora** do repositório.
O processo precisa ter permissão de escrita; a abertura verifica isso antes de
alterar a campanha. Diretório 0700, arquivo 0600, substituição atômica. O recibo
público contém apenas estado e identificador. O conteúdo encerrado não muda com
retry ou manutenção posterior. Conservar esse arquivo para avaliações futuras;
backup deve manter seu caráter reservado.

O pacote guarda conteúdos UTF-8 endereçados por hash, instantes e versões,
catálogo/contratos e registros transacionais completos. O ledger de consolidação
contém IDs: por isso o buffer é preservado **antes** de ser limpo. Hashes validam
conteúdo realmente armazenado, não substituem esse conteúdo. Domínios capturados
são declarados em `DOMAINS`/`FILES`; livros, histórico geral, transcrições e
runtime derivado não são copiados. Saídas do preparo vêm do rollout nativo.

Na avaliação, selecionar explicitamente o pacote:

```bash
poetry run python ferramentas/entrada_medicao.py preparar \
  /caminho/rollout.jsonl --sessao-id 025 \
  --evidencias-sessao /caminho-reservado/025.json \
  --saida /tmp/revisao-privada/entrada-s025.json
```

Esse modo exige captura encerrada e válida. Sem `--corte-bytes`, procura recibo
estrutural bem sucedido de `cronica sessao encerrar` e inclui a resposta final
subsequente, excluindo a manutenção. Recibo ausente/ambíguo não é resolvido pela
frase “sessão encerrada”: exige corte explícito verificável. Seleção explícita do
corte continua sendo responsabilidade do revisor. Pacotes antigos sem essa
extensão continuam funcionando com as limitações históricas declaradas.

## Instante reconstruído e fonte entregue

Vínculo: `transacao.id` presente em saída anterior à resposta → posição no buffer
arquivado → último snapshot anterior → deltas anteriores. Estado, tempo, ficha,
NPC e relação são reconstruídos com deltas atômicos e espelhos de consolidação.
Registro ausente, alvo não suportado ou mudança sem ordem intermediária são
lacunas. Não supor que um arquivo no fim da sessão existia em todos os turnos.
A captura tardia é identificada por `inicio_preservado: false`.

`causal_coverage` informa vínculo, raízes ausentes e lacunas. `frozen_state`
contém caminho e conteúdo recuperado; o índice privado de `avaliar-sessao casos
--indice` informa `arquivo`, permitindo selecionar seu localizador. Essas fontes
são **reservadas e disponíveis ao revisor**, não prova de entrega ao narrador.
Para provar entrega, consultar saída nativa de preparar/consulta e seu instante.
Nenhuma dessas fontes aparece em texto nos descritores ou na publicação pública.

## Cobertura por família

Todas usam entrada/resposta/saídas nativas e contratos congelados em
`evaluation/contratos-modulos`. A tabela especifica o complemento necessário.
`causal_coverage.families` verifica raízes; existência da raiz não certifica todos
os perfis, subcontratos ou evidências referenciados. O revisor deve abrir a fonte
concreta necessária ao critério e se abster especificamente quando faltar.

| Família de critérios | Fonte congelada e recuperação | Limite de cobertura |
| --- | --- | --- |
| context_and_memory | estado, índices/perfis de NPC/relação, conhecimento de Ren; `frozen_state` + memória entregue | Fragmento histórico referenciado fora dos domínios não está embutido; arquivo no disco não prova leitura. |
| turn_and_session_orchestration | estado/tempo antes da transação, saídas e recibos nativos, corte final | Sem vínculo unívoco não reconstruir interação por proximidade. |
| narrative_delivery | AGENTS, guia/densidade e ficção atual/anterior | Fonte causal não julga sozinha a qualidade da prosa; exige leitura semântica. |
| rules_and_character_state | ficha, tempo, regras/decisões e compromissos mecânicos entregues | Livro externo não é copiado; rolagem e CD devem estar nas saídas anteriores ao resultado. |
| sidequest_authoring | tramas/sidequests, gates, contratos/stakes/recompensas e envelope | Ausência de oferta não prova ausência de causa; buscar âncora alcançável e impedimento. |
| sidequest_lifecycle | estado vivo de quests e contratos/progresso referenciados | Evento sem delta reproduzível exige evidência nativa; não atribuir estado terminal retrospectivo. |
| canonical_quest_integration | campanha, direções, quests/gates/segredos canônicos | Possibilidade futura não vira fato; precisa fonte canônica legítima no instante. |
| npc_continuity_and_social_behavior | NPC/relação, elenco e medidores, presença/canal e decisão entregue | Índice sem perfil ou capacidade não autoriza iniciativa; não inventar presença. |
| scene_world_projection | local em estado, cenário, condições persistentes e decisões entregues | Clima/incidente precisa instante/alcance; captura da condição não prova percepção de Ren. |
| world_boundary_resolution | tempo, agenda, estado do mundo, condições e elenco | Causa não selecionada é recuperável; elegibilidade depende de alcance/capacidade e janela concreta. |
| causal_narrative_routing | agenda, direção e causas/âncoras locais, saídas do preparo | Fonte não entregue permite investigar omissão, mas não comprova seleção/contexto. |
| adversarial_operations | estado do mundo/planos, elenco, sidequest-reacoes e operações concorrentes | Intenção não prova capacidade/execução; compromisso prévio e resultados precisam registro no instante. |

Mudanças fora da transação não têm ordem presumida: fonte reconstruída recebe
`reconstrucao: parcial` e a lacuna nomeia o arquivo/alvo. Revisão deve citar a
lacuna, delimitar quais conclusões dependem dela e usar `fontes_insuficientes`
nessas unidades. Não transformar isso em negativa legítima ou aprovação.

A captura preserva material para investigar omissões; não executa julgamentos
literários, não remedeia automaticamente sessões antigas e não substitui o
aceite integrado RCV-08 ou a próxima sessão real RCV-09.
