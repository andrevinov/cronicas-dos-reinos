# Pesquisa, manutenção, consistência e estrutura

Este documento reúne regras especializadas para preparação de regiões, pesquisa de fontes, correções, edição do repositório, automação, consistência e Git.

## Preparação de novas regiões

Quando o personagem se aproximar de região ainda não preparada, avaliar se o material existente sustenta decisões abertas. Se não sustentar, reavaliar o material-base.

Uma região pode conter, conforme necessidade real, visão geral, lugares, personagens, facções, conflitos, criaturas, rumores, cronologia e fontes. Considerar material oficial, período histórico, mudanças causadas pelo personagem, consequências globais, facções de alcance regional, tramas capazes de chegar ao local e conhecimento prévio de Ren.

Não copiar a situação original dos livros ignorando o estado atual da campanha. Não criar todos os arquivos possíveis se ainda não houver conteúdo útil.

## Quando reavaliar material-base

Reavaliar quando nova região se tornar relevante, a campanha mudar de escala, classe/magia/subsistema não resumido passar a importar, regra recorrente continuar gerando dúvida, arco terminar, houver inconsistência entre resumos/fontes ou a preparação existente não sustentar decisões abertas.

A reavaliação deve identificar lacunas, consultar fontes autorizadas, atualizar resumos, registrar divergências e ambiguidades, pedir decisão do jogador somente quando houver escolha real de campanha e evitar preparação sem utilidade previsível.

## Pesquisa e fontes

Memória geral do modelo não é fonte definitiva. Resumo baseado em material oficial deve registrar, quando disponível e relevante, livro, edição, capítulo/seção, página, natureza da informação e adaptações aplicadas.

Distinguir categorias como regra oficial, cenário oficial, interpretação, regra da casa, adaptação e conteúdo original da campanha.

Fontes secundárias podem ajudar a localizar informação, mas não prevalecem sobre fontes oficiais autorizadas. Se fontes oficiais divergirem, registrar divergência e definir qual prevalece. Não reproduzir longos trechos dos livros; produzir resumo funcional.

## Ambiguidades e erros

Diante de regra ambígua, contradição entre fontes, erro aparente, cronologia incompatível, tradução duvidosa, interpretações plausíveis concorrentes ou estatística incoerente:

1. descrever o problema;
2. apresentar interpretações relevantes;
3. indicar impactos práticos;
4. propor decisão provisória ou definitiva;
5. registrar a decisão aprovada.

Durante sessão, favorecer decisão provisória rápida quando pesquisa longa quebraria o ritmo. Fora da sessão, fazer análise completa.

## Retcons e correções

Sessões concluídas são histórico. Não reescrever silenciosamente acontecimentos para acomodar ideia posterior.

Retcon relevante deve registrar identificador, sessão afetada, informação anterior, informação corrigida, motivo, arquivos atualizados e consequências alteradas. Retcons devem ser raros e proporcionais ao problema.

## Edição de arquivos

Ao editar o repositório:

- preservar formato existente quando não houver motivo para migração explícita;
- manter UTF-8;
- evitar duplicação desnecessária;
- usar nomes consistentes;
- atualizar referências quebradas;
- validar YAML;
- não apagar histórico sem justificativa;
- preferir mudanças mínimas e coerentes com a tarefa.

Quando uma alteração realmente exigir múltiplos arquivos dependentes, mantê-los coerentes no mesmo trabalho. Durante a refatoração de economia de contexto, evitar confundir essa regra com obrigação de reescrever várias cópias do mesmo fato a cada turno; a etapa transacional substituirá essa amplificação.

## Markdown e YAML

Usar Markdown para narrativa, guias, resumos, descrições, decisões, histórico e fontes comentadas. Usar YAML para ficha, estado, relações, relógios, consequências, configurações e dados que precisem de conferência/automação.

YAML deve usar indentação consistente, evitar chaves duplicadas, preferir identificadores estáveis e datas inequívocas, incluir unidades quando necessário e distinguir valores permanentes de temporários.

## Identificadores estáveis

Elementos persistentes devem ter identificadores quando isso facilitar referência e automação, por exemplo `npc-0012`, `faccao-0004`, `consequencia-0014`, `relogio-0007`, `retcon-0003`, `decisao-regra-0009`. Não reutilizar identificadores removidos. Nomes podem mudar; IDs não.

## Ferramentas e automação

Criar scripts somente quando houver benefício prático claro, como rolagem, validação de YAML, cálculo de XP, conferência de ficha, geração/fechamento de pacote de sessão, busca de inconsistências e atualização de índices.

Toda ferramenta deve, salvo decisão explícita em contrário, funcionar offline, usar mensagens em português, tratar erros básicos, deixar claro quando altera dados, preservar conteúdo existente, ser testável e evitar dependências desnecessárias. Não automatizar julgamento narrativo.

O rolador padrão é `ferramentas/rolar-dados.py`. Se a ficha mudar de modo que invalide atalhos, atualizar a ferramenta ou registrar pendência antes de usar os atalhos afetados.

## Validação de consistência

Quando apropriado verificar YAML, referências/IDs, XP e nível, PV, recursos inválidos, datas incompatíveis, localização impossível, itens duplicados, condições expiradas, relações sem causa, relógios além do limite, conhecimento sem origem, NPC morto agindo sem explicação e vazamento indevido de segredo.

Inconsistência encontrada deve ser corrigida ou registrada como pendência; não ignorá-la silenciosamente só porque não bloqueia a tarefa imediata.

### Continuidade autoral preventiva

Personagem nomeado, identidade operacional, grupo individualizável, local com
desfecho próprio ou fio capaz de atravessar cenas não pode permanecer apenas na
memória do narrador. Ao identificá-lo em manutenção, adotar exatamente um destino:

- camada operacional própria, quando já existe e é necessária;
- representação explícita por agente, instituição, grupo ou registro reservado;
- estado dormente com gatilho causal de retomada;
- encerramento explícito com motivo;
- reserva não materializada, quando a existência é canônica mas a presença ainda não é.

`narrador/populacao-canonica.yaml` cobre **todo** `estado/npcs/index.yaml`, inclusive
NPCs sem relação com Ren. `narrador/continuidade-autoral.yaml` cobre compromissos
que não cabem nesse inventário e aponta para a verdade canônica sem duplicá-la.
Validar com `python3 ferramentas/populacao.py validar` e
`python3 ferramentas/continuidade_autoral.py check`; ambos também integram o gate
de integridade existente.

Esses registros são frios: não entram em turno, checkpoint, lifecycle, runtime ou
contexto do modelo; não criam agenda, reaparição, consequência nem conhecimento de
Ren. A validação não tenta extrair semântica de transcrições. Quando uma revisão
humana encontra novo compromisso, a ausência de classificação passa a ser erro
estrutural verificável, sem transformar heurística em verdade narrativa.

Cada compromisso também declara chaves exatas de consulta. Quando L0 e uma
consulta comum de NPC não bastarem para uma questão objetiva de continuidade, usar
`contexto.py continuidade <chave> --motivo "<lacuna concreta>"`. O roteador pode
sugerir aproximações, mas nunca escolhe verdade por fuzzy matching. A saída abre
somente a âncora selecionada, é reservada e não deve ser reproduzida ao jogador.

Durante esta refatoração, executar também `python3 ferramentas/verificar-integridade.py` e, quando aplicável, comparar com a baseline lógica criada na Etapa 1.

## Git e histórico

Commits devem refletir mudanças coerentes. É apropriado separar preparação regional, criação/progressão de personagem, encerramento de sessão, atualização de regras, correção de continuidade e ferramentas quando não forem a mesma unidade de trabalho.

Evitar misturar alterações não relacionadas. Mensagens de commit devem ser claras e preferencialmente em português. Nunca publicar o repositório ou mudar sua visibilidade sem pedido explícito.

## Estrutura do repositório

A antiga árvore completa do `AGENTS.md` era **ilustrativa**, não obrigação de criar diretórios vazios. Preservar a separação conceitual entre:

- configuração raiz (`campanha.yaml`);
- regras (`regras/`);
- condução (`narracao/`);
- cenário (`cenario/`);
- personagens (`personagens/`);
- estado atual (`estado/`);
- registros históricos (`sessoes/` e registros persistentes quando existirem);
- material secreto (`narrador/`);
- automação (`ferramentas/`).

A estrutura pode evoluir por migração explícita, desde que autoridade, referências e integridade sejam atualizadas e testadas.
