# Área reservada do narrador

Esta árvore contém verdade, planos, capacidades e consequências que o jogador ou
Ren podem ainda não conhecer. `gm/` é tratado como sinônimo conceitual de
`narrador/`.

Conhecimento só migra daqui para as camadas públicas depois de descoberta
legítima e consolidação. Possibilidade preparada, sorteio, direção ou pendência
não são cânone por si.

## Mapa atual

- [`verdade-da-campanha.md`](verdade-da-campanha.md): núcleo reservado de autoridade;
- [`indices/`](indices/README.md): roteadores e contratos estruturais pequenos;
- [`elenco/`](elenco/README.md): agentes, aliados, adversários e antagonistas;
- [`tramas/`](tramas/README.md): arcos, direções, side quests, dungeons e recompensas;
- [`mundo/`](mundo/README.md): projeção, eventos, incidentes, relógios e rastros;
- [`historico/`](historico/README.md): preparação reservada de sessões concluídas.

## Regra de acesso

Não varrer esta árvore durante o jogo. Começar pelos endpoints e índices dirigidos
e abrir apenas o fragmento apontado por uma necessidade concreta. Conhecimento do
narrador, de uma facção, de um NPC, de Ren e do jogador são camadas distintas.

## Autoridade e estado

- `indices/estrutura.yaml` declara autoridades e raízes de consulta;
- índices roteiam, mas não materializam fatos;
- arquivos `estado.yaml` e ledgers registram controle persistente do seu domínio;
- `historico/` é evidência fria e não deve ser usado como estado corrente;
- transcrições públicas e estado consolidado continuam fora desta árvore.

Alterações estruturais devem passar por
`poetry run python ferramentas/estrutura_narrador.py validar`.
