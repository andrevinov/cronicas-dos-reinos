# Fontes da campanha

Este arquivo define as fontes autorizadas para a campanha **Crônicas dos Reinos**.

A campanha está em migração controlada de **D&D 5e 2014** para **D&D 5.5e**. Enquanto o gate final não for satisfeito, D&D 5e 2014 continua sendo o ruleset mecânico ativo; 5.5e é fonte de comparação, preparação e conversão, mas ainda não substitui a mecânica usada em sessão.

Materiais de AD&D, D&D 3e, D&D 4e e suplementos compatíveis continuam sendo usados principalmente como fontes de cenário, aventuras, personagens, lugares, facções, rumores e inspiração. Quando uma mecânica antiga precisar entrar em jogo, ela deve ser adaptada para o **ruleset atual** declarado em `campanha.yaml`.

Os PDFs locais em `books/` são material privado de consulta e não fazem parte do repositório versionado.

---

## Contrato de ruleset

A fonte de verdade executável para versão e migração é `campanha.yaml`, em `sistema.ruleset`.

Estado inicial da migração:

- ruleset atual: `dnd_5e_2014`;
- ruleset alvo: `dnd_5_5e`;
- status: `em_andamento`;
- ativação 5.5e: proibida até `task_8_auditoria_final` concluir todos os requisitos e o preflight completo.

A migração é prospectiva. Ela **não reescreve sessões concluídas**, não recalcula resultados canonizados e não altera decisões antigas apenas para fazê-las parecer originadas em 5.5e. Uma decisão antiga pode ser substituída futuramente apenas por decisão explícita, com aplicação prospectiva.

Compatibilidade também é explícita:

- antes da ativação, material 5.5e serve somente à migração;
- depois da ativação, material 5e 2014 só pode permanecer como fallback quando não houver equivalente 5.5e aplicável e houver aprovação explícita;
- material de AD&D é sempre adaptado para o ruleset atual, nunca aplicado mecanicamente de forma literal.

---

## Regra geral

Quando houver conflito **mecânico** entre fontes:

1. decisões registradas da campanha prevalecem;
2. regras da casa prevalecem;
3. regras oficiais do `ruleset_atual` prevalecem;
4. compatibilidade só entra quando estiver aprovada explicitamente;
5. fontes de outras edições devem ser adaptadas, não aplicadas literalmente;
6. conteúdo opcional ou de terceiros só entra quando for aprovado ou preparado explicitamente.

Para cenário, Forgotten Realms continua sendo a base ampla e material regional de Ravens Bluff prevalece para detalhes locais, sujeito ao período adotado de 1372 DR.

O agente deve registrar qualquer adaptação relevante em `regras/decisoes.md` ou no arquivo de preparação correspondente.

---

## Regras-base ativas — D&D 5e 2014

Estas fontes continuam sustentando a resolução mecânica **até a ativação final de 5.5e**.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Alta | Livro do Jogador, D&D 5e 2014 | criação de personagem, testes, combate, magia, equipamentos e regras centrais | `books/high_rules_dnd5e_players-handbook_pt-br.pdf` |
| Alta | Manual dos Monstros, D&D 5e 2014 | estatísticas de criaturas, ameaças e referência para substituições de monstros antigos | `books/high_rules_dnd5e_monster-manual_pt-br.pdf` |
| Baixa | Regras Básicas de D&D 5e 2014 | consulta rápida quando conveniente; não substitui os livros-base | `books/low_rules_dnd5e_basic-rules-player_v0-2_printer-friendly.pdf`, `books/low_rules_dnd5e_basic-rules-dm_v0-3_printer-friendly.pdf` |

Enquanto `sistema.ruleset.atual` for `dnd_5e_2014`, nenhuma regra 5.5e entra automaticamente em uma sessão só por ser mais recente.

---

## Regras-base alvo — D&D 5.5e

Estas fontes definem o ruleset para o qual a campanha está migrando. Durante as Tasks 1–7 elas podem orientar comparação e implementação; só se tornam autoridade mecânica corrente após o gate da Task 8.

| Prioridade alvo | Fonte | Uso após ativação | Arquivo local |
| --- | --- | --- | --- |
| Alta | Player's Handbook 2024 / D&D 5.5e | criação de personagem, classes, talentos, testes, combate, magia, equipamentos e regras centrais | cadastro local pendente |
| Alta | Dungeon Master's Guide 2024 / D&D 5.5e | adjudicação, tesouros, itens mágicos e estrutura de aventuras | `books/high_rules_dnd2024_dungeon-masters-guide_en.pdf` |
| Alta | Monster Manual 2025 / D&D 5.5e | estatísticas de criaturas, ameaças e referência principal para conversões de monstros antigos | cadastro local pendente |

Se uma opção de 2014 não possuir equivalente 5.5e depois da ativação, ela não é descartada nem importada automaticamente: deve passar pela política explícita de compatibilidade da campanha.

---

## Cenário-base

Estas fontes definem Forgotten Realms em escala ampla.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Alta | Forgotten Realms Campaign Setting, D&D 3e | geografia, história, povos, religiões, organizações, regiões e contexto geral | `books/high_fr_dnd3e_forgotten-realms-campaign-setting_ocr.pdf` |
| Média | Forgotten Realms Player's Guide, D&D 4e | ideias de cenário, opções e contexto posterior, com cuidado para divergências históricas e mudanças de edição | `books/medium_fr_dnd4e_forgotten-realms-players-guide.pdf` |

Quando houver diferença entre períodos históricos, a campanha deve registrar qual período foi adotado antes de transformar o detalhe em canon.

---

## Origem de Ren: Kara-Tur

Estas fontes sustentam a origem de Ren, Masao, o Clã Kagehira, a Juppongatana,
os aliados canônicos futuros de Ren, a Ponte de Kozakura, Shin-Kozakura e
possíveis conexões futuras entre Faerûn e os reinos orientais.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Alta | Kara-Tur: The Eastern Realms, Forgotten Realms Campaign #1032, AD&D | Kozakura, Shou Lung, T'u Lung, Wa, Koryo, Tabot, cultura, facções, itens, técnicas, antagonistas e rotas orientais | `books/high_fr_adnd1e_tsr-1032_kara-tur-the-eastern-realms.pdf` |
| Alta, interna | Kara-Tur e Faerûn | Documento aprovado de campanha para encaixar Ren, Masao e o Clã Kagehira no intervalo entre o material oficial de 1357 DR e a campanha em 1372 DR; define a composição canônica da Juppongatana, a imagem canônica de Masao, seu plano maior e o nível de contato entre Kara-Tur e Faerûn | `books/Kara-Tur e Faerûn.pdf` |
| Alta, interna | Aliados para Ren | Documento aprovado de campanha para definir os aliados canônicos futuros de Ren, a ordem preferencial de entrada em cena, a ponte de Tyr/Ravens Bluff, a sobrevivente Kagehira e o eixo divino de bastidor contra Masao | `books/Aliados para Ren.pdf` |
| Alta, interna | Ponte de Kozakura | Documento aprovado de campanha para definir o eixo canônico de longo prazo da passagem permanente entre Ravens Bluff e Kozakura, suas anomalias graduais, a perda do controle exclusivo por Masao e a formação futura de Shin-Kozakura | `books/Ponte de Kozakura.pdf` |

O livro deve ser usado como fonte de cenário e inspiração de campanha. Regras,
níveis, magias, itens e estatísticas de AD&D devem ser adaptados para o ruleset
atual antes de aparecerem em jogo.

`Kara-Tur e Faerûn` não é suplemento oficial. Ele é fonte interna autorizada
para decisões desta campanha: a lacuna de quinze anos de Kozakura, a função dos
Kagehira em Gifu, a ascensão de Masao no submundo kozakurano e o conhecimento
parcial entre Kara-Tur e Faerûn. Também fixa os dez membros da Juppongatana e a
direção maior do plano de Masao. Se uma preparação antiga do repo contradisser
esse encaixe, atualizar a preparação antiga em vez de ignorar o documento.

`Aliados para Ren` também não é suplemento oficial. Ele é fonte interna
autorizada para Shen Meihua, Tsukishiro Jōen, Dame Jenilynn Leyland, Kagehira
Hotaru e Tadasu no Kami como pilares futuros da campanha de Ren. Suas revelações
de bastidor ficam em `narrador/aliados/`.

`Ponte de Kozakura` também não é suplemento oficial. Ele é fonte interna
autorizada para a existência futura de um portal estável entre Ravens Bluff e
Kozakura, para a evolução de sinais materiais antes da revelação e para
Shin-Kozakura como consequência histórica posterior. Seus detalhes de bastidor
ficam em `narrador/ponte-de-kozakura/`.

Resumos derivados ficam em `cenario/regioes/kara-tur/`.

---

## Região inicial: Ravens Bluff

Ravens Bluff é a região inicial da campanha e deve receber prioridade de preparação.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Alta | LC1 - Gateway to Ravens Bluff, The Living City | entrada regional, visão geral e base para campanha urbana | `books/high_fr_adnd2e_tsr-8908_lc1_gateway-to-ravens-bluff-the-living-city.pdf` |
| Alta | LC2 - Inside Ravens Bluff | vida urbana, locais internos, instituições e detalhes de cidade | `books/high_fr_adnd2e_tsr-9282_lc2_inside-ravens-bluff.pdf` |
| Alta | LC3 - Nightwatch in the Living City | patrulha, crime, conflitos noturnos e ganchos urbanos | `books/high_fr_adnd2e_tsr-9316_lc3_nightwatch-in-the-living-city.pdf` |
| Alta | LC4 - Port of Ravens Bluff | porto, comércio, viagens, contrabando e conexões externas | `books/high_fr_adnd2e_tsr-9315_lc4_port-of-ravens-bluff.pdf` |
| Alta | The City of Ravens Bluff | expansão local, facções, personagens e estrutura de campanha prolongada | `books/high_fr_adnd2e_tsr-9575_city-of-ravens-bluff.pdf` |

Essas fontes são de AD&D 2e. Para a campanha, devem ser usadas como material de cenário e aventura, não como autoridade mecânica literal.

---

## Aventuras e regiões próximas

Estas fontes são úteis para arcos iniciais, viagens futuras ou expansão gradual.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Alta | FRQ1 - Haunted Halls of Eveningstar | aventura localizada em Cormyr, boa para arco de baixo nível ou viagem regional | `books/high_fr_adnd2e_tsr-9354_frq1_haunted-halls-of-eveningstar.pdf` |
| Alta | FRQ3 - Doom of Daggerdale | aventura e ameaça regional nas Dalelands | `books/high_fr_adnd2e_tsr-9391_frq3_doom-of-daggerdale.pdf` |
| Média | FRQ2 - Hordes of Dragonspear | ameaça regional maior e possível arco de viagem | `books/medium_fr_adnd2e_tsr-9369_frq2_hordes-of-dragonspear.pdf` |
| Média | Hellgate Keep | dungeon, ameaça extraplanar e arco posterior | `books/medium_fr_adnd2e_tsr-9562_hellgate-keep.pdf` |

Esses materiais não precisam ser preparados antes da primeira sessão, salvo se forem conectados diretamente ao histórico do personagem.

---

## Waterdeep e Undermountain

Estas fontes formam um segundo bloco regional coerente, indicado para fase posterior.

| Prioridade | Fonte | Uso na campanha | Arquivo local |
| --- | --- | --- | --- |
| Média | Undermountain: The Lost Level | dungeon e exploração em Waterdeep/Undermountain | `books/medium_fr_adnd2e_tsr-9519_undermountain-the-lost-level.pdf` |
| Média | Undermountain: Maddgoth's Castle | dungeon, ameaça arcana e exploração posterior | `books/medium_fr_adnd2e_tsr-9528_undermountain-maddgoths-castle.pdf` |
| Média | Undermountain: Stardock | dungeon e expansão exótica de Undermountain | `books/medium_fr_adnd2e_tsr-9538_undermountain-stardock.pdf` |

Undermountain não deve deslocar Ravens Bluff como foco inicial, mas pode servir como destino futuro quando a campanha ampliar escala.

---

## Suplementos opcionais e adaptáveis

Estas fontes podem enriquecer a campanha, mas não entram automaticamente como regra autorizada.

| Prioridade | Fonte | Uso possível | Arquivo local |
| --- | --- | --- | --- |
| Média | Strixhaven: Curriculum of Chaos | escola arcana, facções acadêmicas, NPCs, rivalidades e estrutura de aventura adaptável para Faerûn | `books/medium_dnd5e_setting-adventure_strixhaven-curriculum-of-chaos.pdf` |
| Média | Valda's Spire of Secrets | opções extras, ideias de personagens, classes, arquétipos e magia, mediante aprovação específica | `books/medium_dnd5e_third-party_valdas-spire-of-secrets.pdf` |
| Média | Raças e Talentos | opções adicionais de personagem, mediante conferência e aprovação | `books/medium_rules_dnd5e_races-and-feats_pt-br.pdf` |
| Média | Tesouros e Itens Mágicos | inspiração para recompensas, com ajuste de raridade e impacto pela lógica do ruleset atual | `books/medium_rules_dnd5e_magic-items-and-treasure_pt-br.pdf` |
| Baixa | Resumo das Classes | consulta rápida, sem autoridade contra os livros-base do ruleset atual | `books/low_rules_dnd5e_class-summary_biblioteca-elfica_pt-br.pdf` |

Conteúdo de terceiros ou compilado não deve ser oferecido ao jogador como opção padrão sem aprovação.

---

## Adaptação leve de AD&D para o ruleset atual

Ao usar material de AD&D:

* preservar lugares, NPCs, facções, tramas, mapas, rumores, tesouros narrativos e consequências;
* substituir estatísticas por criaturas equivalentes do bestiário principal do ruleset atual sempre que possível;
* recriar NPCs importantes com blocos simples do ruleset atual, focando no papel deles em cena;
* converter testes antigos para CDs do ruleset atual usando dificuldade aproximada;
* ajustar encontros pela ameaça real ao personagem ou grupo, não pela matemática antiga;
* converter tesouros para raridade, economia e progressão do ruleset atual;
* evitar importar restrições, classes, tabelas, THAC0, salvamentos antigos ou XP antigo de forma literal;
* registrar apenas adaptações que possam voltar a ser relevantes.

Enquanto o ruleset atual for 5e 2014, continua válida a escala prática já usada pela campanha:

| Dificuldade | CD |
| --- | --- |
| Fácil | 10 |
| Média | 15 |
| Difícil | 20 |
| Muito difícil | 25 |
| Quase impossível | 30 |

A Task 7 tornará essa fronteira de adaptação verificável. Até lá, a regra operacional é simples: o material antigo aponta para `sistema.ruleset.atual`, portanto a mudança para 5.5e não exige reescrever aventuras ou cenário de AD&D; muda apenas o alvo mecânico das conversões futuras.

Essa adaptação deve ser prática. O objetivo é fazer o material antigo funcionar em mesa, não criar uma conversão perfeita entre edições.

---

## Pendências

A migração mecânica para 5.5e é uma pendência controlada pelas Tasks 1–8. Novas fontes regionais devem ser registradas aqui quando passarem a sustentar preparação ou jogo; fontes 5.5e só passam a ser autoridade corrente no gate final de ativação.
