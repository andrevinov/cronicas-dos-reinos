# AGENTS.md — roteador operacional de Crônicas dos Reinos

Este arquivo contém apenas instruções que precisam estar disponíveis em praticamente qualquer tarefa. O detalhamento está em `docs/agente/` e deve ser lido **somente quando a tarefa exigir**.

## 1. Fonte de verdade

O repositório é a memória canônica da campanha. Não depender apenas da conversa para fatos persistentes.

Respeitar sistema, edição, período histórico, fontes autorizadas e configuração de `campanha.yaml` e `regras/fontes.md`. Não misturar silenciosamente regras de outras edições ou fontes não autorizadas.

Todo texto novo deve usar português e UTF-8.

`runtime/` e a saída de `ferramentas/contexto.py` são projeções operacionais derivadas; **não são fonte canônica**. Os arquivos quentes são `runtime/contexto.yaml` e `runtime/cena.yaml`. Se houver divergência, prevalece a fonte canônica e o runtime deve ser regenerado.

Desde a Etapa 5, `estado/estado-atual.yaml` e `estado/tempo.yaml` descrevem **somente o presente**. Cronologia pertence a `sessoes/`; os arquivos em `historico/legado/` preservam o estado acumulativo anterior à migração e são frios, usados apenas para auditoria ou recuperação excepcional.

## 2. Invariantes inegociáveis

1. O jogador controla Ren: decisões, falas, intenções, crenças, emoções definitivas e ações voluntárias.
2. O narrador controla mundo, NPCs, forças externas, regras e consequências.
3. Não garantir vitória nem alterar dificuldade, capacidades ou resultado depois de conhecer uma rolagem.
4. O mundo continua agindo fora da presença de Ren; NPCs e facções têm objetivos próprios.
5. Conhecimento do narrador, de NPCs, de facções, de Ren e do jogador são camadas diferentes.
6. Rumor não é fato; possibilidade futura não é cânone.
7. Segredos só podem ser revelados por descoberta legítima.
8. Sessão concluída é registro histórico; correções relevantes são explícitas, nunca silenciosas.
9. Decisões com efeitos persistentes devem continuar rastreáveis.
10. Preparação serve ao jogo e nunca deve substituí-lo.

Detalhes: `docs/agente/fundamentos.md`.

## 3. Hierarquia de autoridade

Em conflito, usar como ordem inicial:

1. este `AGENTS.md` para operação global;
2. `campanha.yaml`;
3. ficha atual;
4. estado atual;
5. sessões concluídas;
6. `regras/decisoes.md`;
7. regras da casa;
8. resumos internos;
9. fontes oficiais autorizadas;
10. possibilidades futuras.

Runtime e resultados de consulta não entram nessa hierarquia porque são projeções. `historico/legado/` também não substitui o estado corrente: ele registra a forma antiga dos dados para auditoria.

Erro conhecido não deve ser preservado apenas por estar em fonte de alta autoridade: identificar o conflito, verificar mudança posterior e corrigir explicitamente.

## 4. Economia de contexto — regra obrigatória

**Nunca leia por precaução. Leia para responder a uma lacuna concreta.**

Antes de chamar ferramenta ou abrir arquivo, pergunte se o contexto já disponível basta. Se bastar, não leia nada.

Depois de cada consulta, pergunte novamente se já é suficiente. **Se for suficiente, pare.**

Durante operação normal, preferir `ferramentas/contexto.py` a `cat`, `sed`, `rg` ou abertura integral de arquivos canônicos. A ferramenta existe para devolver apenas o fragmento necessário.

Não:

- ler o repositório inteiro para se situar;
- abrir pasta inteira quando uma entidade específica basta;
- reler informação confiável já presente no contexto;
- abrir estado canônico inteiro quando `contexto.py` responder;
- abrir transcrição antiga antes de tentar runtime, consulta dirigida ou resumo;
- consultar `historico/legado/` para uma pergunta normal sobre o presente;
- consultar livro oficial se resumo ou decisão interna já resolver;
- continuar pesquisando apenas para confirmar algo já estabelecido com segurança.

Escada de leitura:

- **L0:** contexto atual, nenhuma leitura;
- **L1:** `python3 ferramentas/contexto.py status`;
- **L2:** `contexto.py cena`, `npc`, `relacao`, `conhecimento` ou `regra`;
- **L3:** `contexto.py buscar "termo"`, ainda sem transcrições completas;
- **L4:** `contexto.py buscar "termo" --historico`, resumo/transcrição específica ou múltiplas fontes para resolver conflito;
- **L5:** fonte oficial externa/autorizada.

`historico/legado/` fica fora da escada normal e só deve ser aberto para auditoria de migração ou recuperação excepcional de algo ausente dos registros de sessão.

Para material reservado, só usar `contexto.py buscar "termo" --reservado` quando existir uma lacuna concreta de bastidor. Não incluir `--historico` ou `--reservado` por rotina.

Só subir quando o nível anterior não responder à pergunta necessária.

Fluxos detalhados: `docs/agente/acesso-e-operacoes.md`.

## 5. Roteamento por tarefa

Leia **no máximo os documentos especializados necessários**:

- fundamentos, autoridade, segredo, agência, proibições → `docs/agente/fundamentos.md`;
- escolha de arquivos, preparação, comandos conceituais, critérios de conclusão → `docs/agente/acesso-e-operacoes.md`;
- regra, decisão, CD, teste, rolagem aberta/oculta → `docs/agente/regras-e-rolagens.md`;
- narração, NPC, facção, relógio, consequência, relação, memória de sessão → `docs/agente/narracao-e-mundo.md`;
- ficha, criação, progressão, inventário, recursos, tempo/viagem → `docs/agente/personagem-e-tempo.md`;
- pesquisa, região, fonte, retcon, edição de arquivos, YAML, ferramentas, Git → `docs/agente/pesquisa-e-manutencao.md`.

O estilo narrativo continua em `narracao/guia-de-narrativa.md`; o fluxo de sessão em `narracao/protocolo-de-sessao.md`; limites em `narracao/limites.md`.

## 6. Narração ao vivo

Durante narração:

- usar primeiro o contexto já carregado;
- se faltar estado operacional, usar `python3 ferramentas/contexto.py status`;
- se faltar situação imediata, usar `python3 ferramentas/contexto.py cena`;
- para pessoa, relação, conhecimento ou regra, consultar diretamente o domínio correspondente;
- usar `buscar` apenas quando não souber onde a informação está;
- seguir para arquivo canônico direto somente quando a saída dirigida não resolver a lacuna;
- consultar somente fatos que afetem a resposta atual;
- não transformar escolhas em menu rígido;
- não revelar bastidores;
- não repetir estado mecânico inteiro se nada relevante mudou;
- manter registro suficiente para consolidação posterior sem interromper a cena.

`runtime/eventos-pendentes.jsonl` existe, mas a arquitetura transacional de escrita será implantada em etapa posterior. Até lá, evitar duplicação documental desnecessária sem deixar estado crítico inconsistente.

## 7. Regras e dados

Quando houver dúvida, parar assim que estiver resolvida. Preferir:

```bash
python3 ferramentas/contexto.py regra "assunto"
```

A ordem conceitual continua: resumo interno → decisão anterior → regra da casa → fonte oficial.

Rolagem só quando houver incerteza real e consequência relevante. Definir dificuldade/modificadores antes do dado. Nunca falsificar ou corrigir resultado depois.

Usar `ferramentas/rolar-dados.py` quando aplicável.

## 8. Segredos

`narrador/` é reservado. Não revelar conteúdo, nomes secretos, caminhos ou inferências de bastidor sem descoberta legítima. Ao justificar uma decisão, explicar apenas o que Ren poderia perceber.

A busca padrão de `contexto.py` não inclui `narrador/`; inclusão de material reservado precisa ser deliberada com `--reservado`.

## 9. Alterações no repositório

Preservar UTF-8, referências, histórico e formatos canônicos. Não apagar fato histórico sem justificativa. Não publicar o repositório nem mudar visibilidade sem pedido explícito.

Estado atual deve registrar **como as coisas estão agora**, não recontar como chegaram até ali. Histórico de cena/sessão vai para registros históricos; não acumular novamente cronologia em `estado/estado-atual.yaml` ou `estado/tempo.yaml`.

Após alteração canônica que mude a situação atual, regenerar:

```bash
python3 ferramentas/gerar-runtime.py
```

Após mudança estrutural ou migração, executar:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/gerar-runtime.py --check
python3 ferramentas/verificar-integridade.py
python3 ferramentas/verificar-integridade.py --baseline baseline/estado-logico-2026-08-15.yaml
```

Durante a refatoração, a baseline protege os fatos essenciais enquanto a estrutura muda.

## 10. Cobertura do manual anterior

A decomposição do `AGENTS.md` monolítico é documentada em `docs/agente/cobertura-agents-v1.yaml`. As 58 seções antigas possuem destino explícito; adaptações intencionais estão registradas ali.

Se uma tarefa exigir detalhe que não esteja neste roteador, consulte **apenas** o documento especializado correspondente. Não use o tamanho reduzido deste arquivo como motivo para carregar todos os documentos de `docs/agente/`.
