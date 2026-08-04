# Crônicas dos Reinos

Campanha privada de **Dungeons & Dragons**, ambientada em **Forgotten Realms**, na qual o Codex atua como narrador, árbitro de regras e guardião da continuidade.

Este repositório mantém o estado do mundo, a ficha e a progressão do personagem, as consequências persistentes de suas decisões, os acontecimentos das sessões, os segredos da campanha e o material de referência necessário para conduzir a aventura.

> Todo o conteúdo deste repositório deve ser escrito em **português** e salvo com codificação **UTF-8**.

---

## Visão geral

O projeto **Crônicas dos Reinos** busca criar uma campanha duradoura de RPG de mesa conduzida pelo Codex.

O objetivo não é apenas conversar com uma inteligência artificial que improvisa histórias. O repositório funcionará como a memória permanente da campanha e como a principal fonte de verdade para o narrador.

Personagens, lugares, regras, facções, acontecimentos, promessas, alianças, conflitos e consequências serão registrados em arquivos versionados. Dessa forma, a campanha poderá continuar por muitas sessões sem depender exclusivamente da memória temporária de uma conversa.

O Codex deverá atuar simultaneamente como:

* narrador;
* intérprete dos personagens do mundo;
* árbitro das regras;
* administrador da ficha;
* guardião dos segredos;
* mantenedor do estado da campanha;
* cronista das sessões;
* responsável pela preparação do material necessário para novas aventuras.

O jogador continuará sendo o responsável por decidir livremente o que seu personagem pensa, diz e tenta fazer.

O narrador apresentará o mundo, interpretará seus habitantes, aplicará as regras quando necessário e determinará as consequências das ações do personagem.

---

## Objetivo do repositório

Este repositório existe para oferecer à campanha:

* continuidade entre sessões;
* coerência interna;
* memória de longo prazo;
* regras de referência rápida;
* registro das decisões do jogador;
* acompanhamento da progressão do personagem;
* manutenção dos segredos da campanha;
* simulação de um mundo que continua existindo fora da presença do protagonista;
* preparação gradual de novas regiões e aventuras;
* possibilidade de revisar a história completa da campanha.

A campanha será conduzida principalmente por meio do Codex, mas o estado oficial do jogo deverá permanecer registrado nos arquivos do repositório.

Conversas isoladas, lembranças vagas ou improvisações não registradas não deverão substituir o material canônico da campanha.

---

## Sistema e edição

Este repositório será dedicado exclusivamente a uma combinação específica de:

* sistema;
* edição;
* cenário;
* período histórico;
* conjunto de livros autorizados.

A campanha usará **Dungeons & Dragons 5ª edição** como base mecânica.

A edição está registrada em `campanha.yaml` e deverá ser tratada como parte fundamental do contrato da campanha.

O projeto não pretende ser um motor agnóstico capaz de executar simultaneamente diferentes sistemas de RPG.

Embora algumas estruturas possam ser reutilizáveis, este repositório será construído especificamente para a campanha de Dungeons & Dragons em Forgotten Realms.

Materiais de outras edições poderão ser usados como fontes de cenário, aventura, personagens, lugares e conflitos, mas suas mecânicas deverão ser adaptadas para 5e.

---

## Cenário

A campanha será ambientada em **Forgotten Realms**.

Forgotten Realms será tratado como um mundo histórico e vivo, não apenas como uma coleção de nomes famosos e lugares conhecidos.

A campanha deverá considerar, conforme forem relevantes:

* geografia;
* história;
* religião;
* povos;
* organizações;
* cidades;
* reinos;
* conflitos políticos;
* tradições mágicas;
* ameaças sobrenaturais;
* relações entre facções;
* acontecimentos recentes do período escolhido.

Entretanto, não será necessário documentar todo o cenário antes do início do jogo.

A preparação deverá começar pela região inicial da campanha, **Ravens Bluff**, e se expandir gradualmente, acompanhando os movimentos do personagem.

Ravens Bluff será tratada como a base inicial da campanha. A intenção é permanecer por várias sessões nessa região antes de ampliar o escopo para outras partes de Forgotten Realms.

O material inicial de Ravens Bluff poderá incluir:

* visão geral de Ravens Bluff e da região ao redor;
* vilas e lugares importantes;
* personagens influentes;
* facções presentes;
* criaturas comuns;
* ameaças locais;
* acontecimentos em andamento;
* rumores;
* relações com regiões próximas;
* informações conhecidas pelo personagem;
* segredos reservados ao narrador.

Novas regiões serão preparadas quando a campanha se aproximar delas.

---

## Fontes oficiais

O conteúdo utilizado deverá vir prioritariamente dos livros oficiais definidos para a campanha.

Antes do início do jogo, será criado um documento listando:

* livros autorizados;
* suplementos permitidos;
* livros de cenário consultados;
* fontes opcionais;
* materiais proibidos;
* adaptações adotadas;
* regras da casa.

Os livros em PDF ou outros formatos poderão ser utilizados durante a preparação, mas não deverão ser a principal referência durante as sessões.

Sempre que possível, o material relevante será transformado em resumos próprios em Markdown.

Esses resumos deverão registrar suas fontes para facilitar futuras conferências.

Exemplo:

```markdown
## Ataque surpresa

Resumo baseado em:

- Livro do Jogador, capítulo X;
- Livro do Mestre, página Y;
- decisão registrada em `regras/decisoes.md`.
```

Os resumos não deverão reproduzir livros inteiros. Eles deverão conter apenas as informações necessárias para a campanha.

---

## Filosofia de regras

A campanha buscará aproximadamente **70% de fidelidade às regras canônicas**.

Essa porcentagem não será calculada matematicamente. Ela representa um equilíbrio desejado entre:

* respeitar o sistema;
* preservar o risco;
* permitir escolhas estratégicas;
* manter as diferenças entre personagens;
* evitar burocracia desnecessária;
* proteger o ritmo da narrativa.

As regras deverão ser aplicadas principalmente quando houver:

* risco real;
* oposição;
* incerteza;
* custo;
* disputa;
* possibilidade de fracasso;
* consequências interessantes;
* necessidade de preservar a imparcialidade.

Nem toda ação precisará de uma rolagem.

Um personagem não deverá rolar dados para realizar algo simples, seguro e compatível com suas capacidades.

Uma rolagem será apropriada quando o resultado não for evidente e tanto o sucesso quanto o fracasso puderem alterar a situação.

---

## Ordem de resolução das regras

Quando surgir uma dúvida, o narrador deverá seguir preferencialmente esta ordem:

1. consultar o resumo existente no repositório;
2. aplicar uma decisão já utilizada anteriormente;
3. consultar a regra oficial;
4. interpretar a regra de forma coerente com o sistema;
5. simplificar o procedimento quando sua aplicação literal for excessivamente burocrática;
6. usar a regra de ouro;
7. registrar a decisão tomada.

O objetivo é evitar que a mesma dúvida seja resolvida de maneiras incompatíveis em sessões diferentes.

Decisões recorrentes deverão ser registradas em:

```text
regras/decisoes.md
```

Uma decisão poderá conter:

* contexto;
* regra oficial;
* interpretação adotada;
* motivo;
* exemplo;
* data ou sessão de origem.

---

## Regra de ouro

A regra de ouro poderá ser usada quando:

* a regra oficial não for clara;
* existirem interpretações conflitantes;
* a consulta interromper excessivamente o ritmo;
* a aplicação literal produzir um resultado absurdo;
* a situação não estiver prevista;
* uma simplificação for necessária para preservar a diversão.

A regra de ouro não deverá ser usada para favorecer arbitrariamente o jogador ou o narrador.

Ela deverá buscar:

* coerência;
* justiça;
* previsibilidade;
* respeito às capacidades dos personagens;
* preservação das consequências;
* continuidade da campanha.

Quando uma decisão improvisada puder voltar a ser relevante, ela deverá ser registrada.

---

## Rolagens de dados

As rolagens deverão ser apresentadas de forma clara.

Quando uma rolagem ocorrer, o narrador deverá informar, sempre que isso não revelar um segredo indevido:

* o que está sendo testado;
* qual habilidade ou atributo está envolvido;
* a dificuldade;
* vantagens ou desvantagens;
* modificadores;
* resultado do dado;
* resultado final;
* consequência.

Exemplo:

```text
Teste de Furtividade: 1d20 + 5
Dificuldade: 14
Resultado do dado: 11
Total: 16
Resultado: sucesso
```

Algumas rolagens poderão ser ocultas quando o conhecimento do resultado prejudicar o mistério.

Exemplos:

* percepção passiva de inimigos;
* detecção de mentiras;
* encontros aleatórios;
* reações secretas;
* testes ligados a armadilhas desconhecidas;
* acontecimentos fora da presença do personagem.

O repositório poderá futuramente possuir ferramentas simples para automatizar rolagens e registrar seus resultados.

---

## Mundo aberto

A campanha buscará simular um mundo relativamente aberto.

Isso significa que o jogador poderá:

* ignorar missões;
* abandonar regiões;
* mudar de objetivo;
* criar alianças inesperadas;
* negociar com inimigos;
* investigar rumores;
* seguir interesses pessoais;
* rejeitar direções sugeridas;
* provocar consequências não previstas.

O mundo não será organizado principalmente como uma árvore rígida de missões.

Em vez disso, cada região deverá possuir elementos ativos, como:

* personagens com objetivos próprios;
* facções com interesses;
* conflitos em andamento;
* ameaças;
* oportunidades;
* segredos;
* recursos disputados;
* acontecimentos que avançam com o tempo.

O jogador poderá interferir nesses elementos, ignorá-los ou nem sequer descobri-los.

---

## Direções narrativas e mão do destino

Embora o mundo seja aberto, a campanha não será completamente aleatória.

O narrador poderá manter algumas direções narrativas possíveis, responsáveis por dar forma, ritmo e significado à história.

Essas direções não deverão obrigar o personagem a seguir um roteiro específico.

Elas poderão aparecer como:

* coincidências plausíveis;
* reencontros;
* consequências antigas;
* convites;
* rumores;
* ameaças crescentes;
* mudanças no cenário;
* interesses de personagens poderosos;
* acontecimentos ligados ao passado do protagonista.

A chamada “mão do destino” deverá conduzir oportunidades e confrontos, mas não controlar as decisões do personagem.

O personagem poderá resistir, fugir, fracassar ou alterar completamente a direção esperada.

---

## Forças em movimento

Conflitos importantes poderão ser acompanhados por relógios narrativos ou estados de progresso.

Exemplo:

```yaml
infiltracao_zhentarim:
  progresso: 3
  limite: 6
  descricao: >
    Agentes dos Zhentarim estão infiltrando comerciantes,
    guardas e lideranças locais.
  avanca_quando:
    - o personagem ignora indícios relevantes
    - um aliado local é removido
    - os agentes obtêm um recurso importante
  consequencia_no_limite:
    - controle parcial da administração local
```

Esses relógios poderão avançar quando:

* o personagem falhar;
* o personagem demorar;
* um inimigo obtiver sucesso;
* uma oportunidade for ignorada;
* o tempo passar;
* alguma condição específica for cumprida.

Nem todo relógio precisará ser conhecido pelo jogador.

---

## Preparação do cenário

Antes da campanha começar, será criado um conjunto inicial de resumos.

O material poderá incluir:

* visão geral do período histórico;
* região inicial;
* cidades e vilas próximas;
* personagens importantes;
* facções;
* conflitos;
* religiões;
* criaturas comuns;
* ameaças;
* rumores;
* rotas;
* pequenos mapas;
* cronologia;
* eventos recentes.

Os arquivos deverão ser objetivos o suficiente para serem consultados rapidamente, mas detalhados o suficiente para sustentar improvisação coerente.

O narrador não deverá precisar consultar continuamente os livros oficiais durante uma sessão comum.

---

## Expansão regional

A documentação do mundo será produzida gradualmente.

Quando o personagem demonstrar intenção de viajar para uma nova região, o narrador poderá solicitar uma etapa de preparação.

Exemplo:

> A campanha está se aproximando do Vale da Adaga. Antes da próxima aventura, é recomendável revisar o material oficial dessa região e preparar seus arquivos de referência.

Essa preparação poderá ocorrer:

* entre sessões;
* ao fim de uma aventura;
* antes do início de um novo arco;
* quando o jogador anunciar uma viagem;
* quando uma trama passar a envolver uma região ainda não documentada.

A preparação de uma região poderá gerar:

```text
cenario/regioes/vale-da-adaga/
├── visao-geral.md
├── lugares.md
├── personagens.md
├── faccoes.md
├── conflitos.md
├── criaturas.md
├── rumores.md
├── cronologia.md
└── segredos.md
```

O material deverá refletir o estado atual da campanha, e não apenas a situação original descrita nos livros.

---

## Estado do mundo

O estado atual da campanha deverá ser mantido separadamente dos registros históricos.

Os registros históricos explicam o que aconteceu.

Os arquivos de estado mostram como o mundo está agora.

Exemplos de informações mantidas no estado atual:

* localização do personagem;
* data e horário no mundo;
* clima relevante;
* pontos de vida;
* condições;
* magias preparadas;
* recursos;
* inventário;
* relações;
* reputação;
* personagens presentes;
* ameaças ativas;
* missões conhecidas;
* acontecimentos em andamento;
* relógios narrativos;
* consequências persistentes.

O estado atual deverá ser atualizado ao fim de cada sessão.

---

## Memória da campanha

A memória da campanha será dividida em diferentes tipos.

### Memória narrativa

Registra os acontecimentos das sessões em forma legível.

### Memória estrutural

Registra dados objetivos, como experiência, inventário, relações, ferimentos e estado do mundo.

### Memória crônica

Registra decisões e consequências que poderão reaparecer muito tempo depois.

### Memória secreta

Registra informações conhecidas apenas pelo narrador.

Essa separação ajudará o Codex a consultar apenas o material necessário para cada tarefa.

---

## Consequências persistentes

Decisões importantes deverão produzir consequências registradas.

Uma consequência persistente poderá surgir de:

* desobedecer uma figura poderosa;
* quebrar uma promessa;
* salvar alguém;
* humilhar um inimigo;
* destruir um recurso;
* favorecer uma facção;
* revelar um segredo;
* abandonar uma comunidade;
* cometer um crime;
* adquirir uma dívida;
* deixar uma ameaça escapar.

Essas consequências poderão reaparecer em lugares ou momentos diferentes de sua origem.

Exemplo:

```yaml
- id: consequencia-014
  sessao_origem: 7
  acao: "O personagem desobedeceu Elminster publicamente."
  alcance: amplo
  conhecimento_do_personagem: conhecido
  estado: ativa
  efeitos_possiveis:
    - membros dos Harpistas poderão agir com cautela
    - inimigos de Elminster poderão tentar aproximação
    - Elminster poderá negar auxílio no futuro
```

A lista de efeitos possíveis não deverá funcionar como um roteiro obrigatório.

Ela servirá para lembrar ao narrador que aquela decisão continua existindo no mundo.

---

## Relações

As relações entre o personagem, os NPCs e as facções deverão ser registradas.

Uma relação poderá incluir:

* confiança;
* respeito;
* medo;
* lealdade;
* gratidão;
* rivalidade;
* dívida;
* ressentimento;
* interesse;
* suspeita;
* conhecimento compartilhado.

As relações não deverão ser reduzidas necessariamente a um único número.

Quando valores forem utilizados, eles deverão ser acompanhados por uma descrição narrativa.

Exemplo:

```yaml
elminster:
  atitude: cautelosa
  confianca: baixa
  respeito: moderado
  motivo: >
    Reconhece a capacidade do personagem, mas considera
    suas decisões impulsivas e potencialmente perigosas.
```

---

## Conhecimento do personagem

O repositório deverá distinguir claramente:

1. o que é verdade no mundo;
2. o que os personagens acreditam;
3. o que o protagonista sabe;
4. o que o jogador sabe;
5. o que permanece secreto.

Essa distinção é essencial para evitar que personagens ajam com informações que não possuem.

O simples fato de uma informação estar registrada no repositório não significa que ela possa ser utilizada pelo protagonista.

Quando necessário, haverá arquivos específicos para o conhecimento do personagem.

Exemplo:

```text
estado/conhecimento-do-personagem.md
```

---

## Personagens não jogadores

Personagens importantes deverão possuir arquivos próprios.

Um NPC poderá ter:

* identidade;
* aparência;
* personalidade;
* objetivos;
* medos;
* relações;
* recursos;
* capacidades;
* segredos;
* conhecimento;
* planos;
* estado atual;
* histórico de encontros com o protagonista.

O narrador deverá interpretar cada personagem com base nesses elementos.

NPCs não deverão existir apenas para entregar missões ou informações.

Eles poderão:

* mentir;
* errar;
* esquecer;
* mudar de opinião;
* agir por interesse próprio;
* recusar ajuda;
* manter segredos;
* interpretar incorretamente acontecimentos.

---

## Personagem do jogador

O personagem principal deverá possuir uma ficha canônica mantida no repositório.

Ela deverá conter:

* atributos;
* classe;
* nível;
* raça ou espécie;
* antecedente;
* perícias;
* proficiências;
* talentos;
* magias;
* equipamentos;
* pontos de vida;
* condições;
* recursos;
* experiência;
* idiomas;
* características;
* histórico;
* objetivos;
* relações;
* progressão.

A ficha poderá utilizar YAML, Markdown ou uma combinação dos dois.

Informações estruturadas deverão preferencialmente ficar em YAML.

Explicações, histórico e interpretação poderão ficar em Markdown.

---

## Criação do personagem

Antes do início da campanha, será criado um manual resumido de construção de personagem.

Esse material deverá explicar:

* opções permitidas;
* livros autorizados;
* método de geração de atributos;
* nível inicial;
* equipamentos iniciais;
* antecedentes;
* raças ou espécies disponíveis;
* classes e subclasses;
* regras de multiclasse;
* talentos;
* magias;
* restrições;
* adaptações de cenário.

O Codex deverá orientar a criação sem tomar decisões fundamentais pelo jogador.

Ele poderá:

* explicar opções;
* verificar pré-requisitos;
* comparar caminhos;
* apontar sinergias;
* alertar sobre limitações;
* conferir cálculos;
* registrar escolhas.

---

## Progressão

O Codex deverá acompanhar toda a progressão do personagem.

Quando solicitado, deverá:

* conferir experiência recebida;
* calcular experiência acumulada;
* identificar o nível atual;
* informar quando uma progressão estiver disponível;
* explicar opções de avanço;
* verificar pré-requisitos;
* sugerir possibilidades compatíveis com o personagem;
* registrar a escolha realizada;
* atualizar a ficha;
* manter histórico das alterações.

A progressão poderá considerar tanto eficiência mecânica quanto coerência narrativa.

Uma habilidade não deverá surgir sem explicação quando o sistema ou a campanha exigirem treinamento, estudo, contato com um mestre ou acesso a uma fonte específica.

O repositório poderá registrar caminhos de crescimento possíveis.

Exemplo:

```markdown
## Possíveis caminhos de evolução

### Especialização arcana

Requer:

- acesso a treinamento;
- estudo de determinadas magias;
- vínculo com um mentor ou instituição.

### Liderança local

Pode evoluir por meio de:

- alianças;
- reputação;
- aquisição de terras;
- proteção da comunidade.
```

---

## Experiência

Toda experiência recebida e gasta deverá ser registrada.

O registro deverá informar:

* sessão;
* origem;
* quantidade;
* total anterior;
* total atualizado;
* nível correspondente;
* observações.

Exemplo:

```markdown
## Sessão 004

- Combate principal: 300 XP
- Resolução diplomática: 150 XP
- Descoberta importante: 100 XP
- Total recebido: 550 XP
- Total acumulado: 2.350 XP
```

Caso seja utilizado avanço por marcos, os marcos também deverão ser registrados e justificados.

---

## Guia de narrativa

O repositório deverá possuir um guia específico para o estilo narrativo.

Esse documento poderá definir:

* tom;
* nível de descrição;
* ritmo;
* grau de dificuldade;
* presença de humor;
* violência;
* horror;
* política;
* romance;
* temas;
* limites;
* elementos a evitar;
* elementos a incentivar.

O narrador deverá manter consistência com esse guia.

O guia também poderá registrar preferências como:

* não controlar pensamentos ou decisões do protagonista;
* não transformar todo NPC em aliado ou inimigo;
* evitar exposição excessiva;
* evitar soluções convenientes;
* permitir fracassos;
* permitir retirada;
* evitar tornar o personagem o centro absoluto do universo;
* valorizar consequências;
* respeitar o tom de Forgotten Realms;
* não resumir decisões importantes do jogador.

---

## Agência do jogador

O narrador jamais deverá determinar unilateralmente:

* o que o personagem pensa;
* o que o personagem sente;
* o que o personagem decide;
* o que o personagem diz;
* qual objetivo pessoal ele deve seguir.

O narrador poderá descrever:

* sensações físicas;
* percepções;
* impulsos sobrenaturais;
* efeitos mágicos;
* informações que chegam ao personagem;
* consequências emocionais sugeridas pelo contexto.

Entretanto, a reação final pertencerá ao jogador, salvo quando uma regra específica retirar ou limitar temporariamente o controle do personagem.

---

## Dificuldade e imparcialidade

O mundo não deverá ser ajustado constantemente para garantir a vitória do personagem.

Algumas ameaças poderão ser fortes demais para um confronto direto.

O jogador deverá ter a possibilidade de:

* investigar;
* negociar;
* preparar-se;
* fugir;
* buscar aliados;
* desistir;
* retornar mais tarde.

A dificuldade deverá ser comunicada por meio do mundo sempre que for razoável.

O narrador não deverá esconder deliberadamente todos os sinais de perigo apenas para surpreender ou punir o jogador.

Ao mesmo tempo, o protagonista não deverá possuir proteção automática contra todas as consequências.

---

## Segredos da campanha

Os segredos ficarão em uma área reservada ao narrador.

Exemplo:

```text
narrador/
├── verdade-da-campanha.md
├── segredos/
├── planos-dos-npcs/
├── acontecimentos-ocultos/
└── possibilidades-futuras/
```

O jogador se compromete a não consultar essa área.

A separação será baseada principalmente em confiança.

Não será presumido que os arquivos possam ser criptografados de forma que apenas o Codex possua acesso permanente, pois o Codex não mantém uma chave secreta própria fora do repositório.

Caso uma barreira técnica seja desejada futuramente, poderá ser estudado um sistema de criptografia com chave externa. Entretanto, essa solução poderá aumentar a complexidade e dificultar o acesso do próprio narrador.

---

## Verdade da campanha

O arquivo de verdade da campanha deverá registrar os elementos que são objetivamente reais no mundo, mesmo quando ainda não forem conhecidos pelo jogador.

Ele poderá conter:

* identidade de vilões;
* causas reais de acontecimentos;
* relações secretas;
* localização de objetos;
* natureza de maldições;
* planos de facções;
* profecias;
* falsos rumores;
* informações manipuladas;
* mistérios ainda não revelados.

A verdade da campanha poderá mudar apenas quando:

* o mundo mudar organicamente;
* uma decisão anterior for explicitamente corrigida;
* um retcon for registrado;
* uma possibilidade ainda não definida for concretizada.

O narrador não deverá alterar retroativamente a verdade apenas para invalidar uma boa decisão do jogador.

---

## Possibilidades futuras

Nem todo elemento preparado precisa ser imediatamente transformado em verdade definitiva.

A área do narrador poderá distinguir:

* fatos confirmados;
* hipóteses;
* ideias;
* possibilidades;
* cenas potenciais;
* personagens ainda não utilizados;
* direções narrativas disponíveis.

Isso permitirá improvisação sem obrigar a campanha a seguir ideias preparadas anteriormente.

Uma possibilidade só se tornará canônica quando entrar efetivamente no mundo ou quando for definida como verdade pelo narrador.

---

## Sessões

Cada sessão deverá possuir seu próprio diretório.

Exemplo:

```text
sessoes/
└── 001-a-estrada-para-shadowdale/
    ├── transcricao.md
    ├── resumo.md
    ├── alteracoes-de-estado.yaml
    ├── experiencia.md
    ├── consequencias.md
    └── notas-do-narrador.md
```

Nem todos os arquivos serão obrigatórios desde a primeira sessão.

A estrutura deverá ser ajustada com base na experiência prática.

---

## Preparação de sessão

Antes de uma sessão, o narrador deverá revisar um conjunto reduzido de arquivos.

Esse conjunto poderá incluir:

* ficha atual;
* estado atual;
* localização;
* personagens presentes;
* relações relevantes;
* acontecimentos ativos;
* consequências persistentes;
* relógios narrativos;
* conhecimento do personagem;
* segredos relacionados;
* resumo da sessão anterior.

O narrador não deverá precisar reler toda a campanha antes de cada sessão.

---

## Abertura de sessão

No início de uma sessão, o narrador poderá apresentar:

* data e localização;
* situação atual;
* estado físico do personagem;
* recursos relevantes;
* acontecimentos recentes;
* resumo breve da sessão anterior;
* decisões pendentes.

O resumo não deverá retirar do jogador a oportunidade de recordar ou reinterpretar acontecimentos por conta própria.

---

## Encerramento de sessão

Ao fim de cada sessão, deverão ser registrados:

* acontecimentos principais;
* decisões do personagem;
* resultados de combates;
* experiência;
* recursos ganhos ou perdidos;
* ferimentos;
* condições;
* relações alteradas;
* promessas;
* favores;
* dívidas;
* rumores descobertos;
* missões;
* relógios avançados;
* mudanças no mundo;
* consequências persistentes;
* mistérios abertos;
* mistérios resolvidos;
* localização e data finais.

O encerramento deverá produzir um estado claro para a próxima sessão.

---

## Registro histórico

Sessões concluídas deverão ser tratadas como registros históricos.

Seu conteúdo não deverá ser silenciosamente reescrito para combinar com acontecimentos posteriores.

Correções poderão ser feitas quando houver:

* erro factual;
* erro de regra;
* inconsistência;
* informação registrada incorretamente;
* decisão explícita de retcon.

Nesse caso, a correção deverá ser documentada.

Exemplo:

```markdown
## Retcon 003

- Sessão afetada: 008
- Informação anterior: a viagem durou três dias.
- Informação corrigida: a viagem durou cinco dias.
- Motivo: distância incompatível com o mapa e o ritmo adotado.
- Consequências atualizadas: data atual e consumo de suprimentos.
```

---

## Canon

O material da campanha poderá possuir diferentes níveis de autoridade.

Uma hierarquia inicial possível é:

1. estado atual validado;
2. ficha atual;
3. registros das sessões;
4. decisões de regras;
5. verdade da campanha;
6. resumos de cenário;
7. ideias e possibilidades ainda não utilizadas.

Quando dois arquivos entrarem em conflito, o narrador deverá identificar a inconsistência e corrigi-la explicitamente.

---

## Estrutura inicial prevista

```text
.
├── AGENTS.md
├── README.md
├── campanha.yaml
│
├── regras/
│   ├── fontes.md
│   ├── resolucao-de-acoes.md
│   ├── combate.md
│   ├── surpresa.md
│   ├── magia.md
│   ├── descanso-e-cura.md
│   ├── condicoes.md
│   ├── criacao-de-personagem.md
│   ├── progressao.md
│   ├── regras-da-casa.md
│   └── decisoes.md
│
├── narracao/
│   ├── guia-de-narrativa.md
│   ├── protocolo-de-sessao.md
│   ├── ritmo.md
│   ├── dificuldade.md
│   ├── limites.md
│   └── elementos-a-evitar.md
│
├── cenario/
│   ├── visao-geral.md
│   ├── cronologia.md
│   ├── regioes/
│   ├── lugares/
│   ├── faccoes/
│   ├── religioes/
│   ├── personagens/
│   ├── criaturas/
│   └── rumores/
│
├── personagens/
│   ├── jogador/
│   │   ├── ficha.yaml
│   │   ├── historia.md
│   │   ├── progressao.md
│   │   └── conhecimento.md
│   └── npcs/
│
├── estado/
│   ├── estado-atual.yaml
│   ├── tempo.yaml
│   ├── relacoes.yaml
│   ├── reputacao.yaml
│   ├── relogios.yaml
│   ├── tramas-ativas.md
│   └── conhecimento-do-personagem.md
│
├── registros/
│   ├── experiencia.md
│   ├── inventario.md
│   ├── consequencias.yaml
│   ├── promessas.md
│   ├── favores-e-dividas.md
│   ├── misterios.md
│   ├── retcons.md
│   └── mudancas-no-mundo.md
│
├── sessoes/
│   └── 001/
│
├── narrador/
│   ├── verdade-da-campanha.md
│   ├── segredos/
│   ├── planos-dos-npcs/
│   ├── acontecimentos-ocultos/
│   └── possibilidades-futuras/
│
└── ferramentas/
    ├── rolar-dados.py
    ├── validar-estado.py
    └── encerrar-sessao.py
```

Essa estrutura é apenas uma proposta inicial.

Ela deverá evoluir com base no uso real durante a campanha.

A organização não deverá ser mais importante do que a experiência de jogo.

---

## Formatos de arquivo

Os formatos preferenciais serão:

### Markdown

Usado para:

* explicações;
* resumos;
* narrativa;
* histórico;
* guias;
* decisões;
* descrições;
* personagens;
* lugares.

### YAML

Usado para:

* ficha;
* estado atual;
* relações;
* relógios;
* consequências;
* configurações;
* dados estruturados.

### Python

Usado apenas quando uma automação trouxer benefício real.

Exemplos:

* rolagem de dados;
* validação da ficha;
* cálculo de experiência;
* geração de resumo de estado;
* verificação de inconsistências.

Não deverão ser criadas ferramentas apenas por entusiasmo técnico.

---

## Idioma e codificação

Todo o conteúdo deverá ser escrito em português.

Isso inclui:

* nomes de arquivos;
* nomes de diretórios;
* comentários;
* documentação;
* mensagens de ferramentas;
* campos estruturados;
* commits relacionados à campanha, sempre que possível.

Todos os arquivos de texto deverão utilizar UTF-8.

Acentos e caracteres próprios da língua portuguesa deverão ser preservados normalmente no conteúdo.

Nomes de arquivos poderão utilizar hífens e letras sem acentuação quando isso melhorar a compatibilidade.

Exemplo:

```text
criacao-de-personagem.md
```

Em vez de:

```text
criação de personagem.md
```

---

## Convenções de escrita

Os documentos deverão buscar:

* clareza;
* consistência;
* objetividade;
* separação entre fato e hipótese;
* identificação de fontes;
* distinção entre conhecimento público e secreto;
* facilidade de consulta durante uma sessão.

Informações importantes não deverão ficar enterradas em grandes blocos de texto quando puderem ser apresentadas de forma mais direta.

Ao mesmo tempo, os resumos não deverão ser tão curtos que percam as relações e nuances necessárias para uma boa narrativa.

---

## Controle de versão

O Git será utilizado como registro histórico do projeto.

Commits deverão representar mudanças coerentes, como:

* preparação de uma região;
* criação de personagem;
* encerramento de sessão;
* atualização de regras;
* correção de inconsistência;
* registro de progressão;
* preparação de aventura.

Informações secretas da campanha poderão permanecer no mesmo repositório privado.

O histórico do Git poderá ser utilizado para verificar quando uma informação foi criada ou alterada.

---

## Privacidade

Este repositório será privado.

Seu conteúdo poderá incluir:

* segredos da campanha;
* anotações do narrador;
* transcrições;
* decisões do jogador;
* material derivado de livros utilizados na preparação;
* informações que perderiam valor narrativo caso fossem publicadas.

A eventual publicação de qualquer parte do projeto deverá ocorrer apenas após revisão específica.

---

## O que este projeto não pretende ser

Este projeto não pretende:

* reproduzir integralmente os livros de Dungeons & Dragons;
* substituir a compra dos livros oficiais;
* criar um sistema universal para qualquer RPG;
* automatizar cada aspecto do jogo;
* transformar a campanha em um videogame;
* eliminar a improvisação;
* reduzir todas as relações a números;
* preparar todo Forgotten Realms antes da primeira sessão;
* garantir que o personagem sempre vença;
* seguir um roteiro imutável.

---

## Princípios do projeto

1. O jogador controla seu personagem.

2. O narrador controla o mundo e suas consequências.

3. As regras serão usadas para produzir risco, justiça e identidade mecânica.

4. A regra de ouro poderá simplificar burocracias, mas não deverá eliminar consequências.

5. O mundo continuará existindo mesmo quando o protagonista não estiver presente.

6. Personagens não jogadores terão objetivos próprios.

7. Facções poderão agir independentemente do personagem.

8. Decisões antigas poderão reaparecer muito tempo depois.

9. O conhecimento do narrador não será automaticamente conhecimento dos personagens.

10. A continuidade registrada no repositório prevalecerá sobre lembranças vagas.

11. Retcons deverão ser explícitos.

12. Segredos deverão ser protegidos da perspectiva do jogador.

13. Preparação deverá servir à próxima sessão.

14. A arquitetura do projeto deverá crescer com a campanha.

15. Diversão, coerência, agência e descoberta terão prioridade sobre perfeição técnica.

---

## Estado atual do projeto

O projeto encontra-se em fase de concepção e preparação.

Já foram definidos:

* o uso de um repositório exclusivo para esta campanha;
* Dungeons & Dragons como sistema;
* Dungeons & Dragons 5ª edição como base mecânica;
* Forgotten Realms como cenário;
* 1372 DR, Ano da Magia Selvagem, como período histórico;
* português como idioma;
* UTF-8 como codificação;
* aproximadamente 70% de fidelidade às regras;
* o Codex como narrador e mantenedor da campanha;
* a proposta de mundo aberto;
* o registro de consequências persistentes;
* a separação entre conhecimento, verdade e segredo;
* Ravens Bluff como região inicial;
* fontes iniciais registradas em `regras/fontes.md`;
* pacote mínimo de Ravens Bluff para apoiar criação de personagem;
* Ren Kagehira como personagem inicial;
* nível inicial 3;
* método de atributos por array solo melhorado;
* nenhum suplemento mecânico opcional no personagem inicial;
* a preparação gradual de novas regiões.

---

## Próximas decisões

Antes da primeira sessão, ainda será necessário definir:

* grau de dificuldade;
* regras da casa;
* protocolo de rolagens;
* método de progressão;
* estado inicial;
* estrutura mínima necessária para a primeira sessão.

---

## Próximos documentos

Os próximos arquivos recomendados são:

```text
regras/criacao-de-personagem.md
estado/estado-atual.yaml
regras/resolucao-de-acoes.md
narracao/guia-de-narrativa.md
narracao/protocolo-de-sessao.md
```

Depois dessas decisões, poderá começar a preparação da primeira sessão.

---

## Compromisso central

O projeto deverá sempre evitar dois extremos.

No primeiro extremo, a campanha se tornaria uma simulação excessivamente burocrática, interrompida constantemente por consultas, cálculos e aplicações minuciosas de regras.

No segundo extremo, ela se tornaria apenas uma narrativa improvisada, sem risco real, sem limitações mecânicas e sem consequências imparciais.

**Crônicas dos Reinos** buscará o ponto intermediário: um verdadeiro RPG de mesa, com regras suficientes para sustentar escolhas e incertezas, mas flexível o bastante para permitir uma história viva, aberta e duradoura.
