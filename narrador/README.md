# Área do narrador

Esta pasta é a área reservada ao narrador/GM.

Quando o jogador mencionar "gm/", tratar como referência a esta pasta `narrador/`.

O jogador não deve ler os arquivos daqui durante a campanha. Eles podem conter:

* segredos;
* motivações reais de NPCs;
* planos de facções;
* mapas completos;
* armadilhas;
* estatísticas ocultas;
* rolagens ocultas;
* relógios;
* consequências ainda não percebidas por Ren.

Informações desta pasta só devem migrar para arquivos públicos quando Ren descobrir, deduzir ou testemunhar algo em jogo.

---

## Estrutura sugerida

```text
narrador/
├── verdade-da-campanha.md
├── agentes/
│   ├── README.md
│   ├── index.yaml
│   └── <agente>.yaml
├── mundo/
│   ├── README.md
│   ├── agenda.yaml
│   └── estado.yaml
├── aliados/
│   ├── README.md
│   ├── personagens.md
│   ├── tadasu-no-kami.md
│   ├── marcos-de-aparicao.md
│   └── imagens/
├── juppongatana/
│   ├── README.md
│   ├── membros.md
│   ├── marcos-de-aparicao.md
│   └── imagens/
├── masao/
│   ├── README.md
│   ├── plano.md
│   └── imagens/
├── ponte-de-kozakura/
│   ├── README.md
│   ├── anomalias-e-revelacao.md
│   └── shin-kozakura.md
├── segredos/
│   └── canone.md
├── sessoes/
│   └── 001/
│       ├── preparacao.md
│       ├── segredos.md
│       ├── mapa-e-salas.md
│       ├── relogios.md
│       ├── rolagens-ocultas.md
│       └── npcs.md
├── planos-dos-npcs/
├── acontecimentos-ocultos/
└── possibilidades-futuras/
```

Criar arquivos apenas quando houver conteúdo real para registrar.

## Cânone de pressão

O arquivo reservado `segredos/canone.md` registra acontecimentos externos e
reações de mundo que podem avançar independentemente das ações imediatas de Ren.
Ele deve ser consultado ao abrir um novo dia no mundo ou quando uma sessão
atravessar várias horas relevantes.

## Agentes autônomos

`agentes/` é a camada operacional fragmentada para NPCs, facções e instituições
capazes de agir fora da presença de Ren. Ela não substitui as fontes canônicas:
cada fragmento aponta para elas e registra objetivo atual, recursos, restrições,
conhecimento sustentado, presença, mobilidade e plano corrente.

Durante narração, consultar um agente de forma dirigida com
`python3 ferramentas/agentes.py mostrar <id-ou-nome>`. A validação ampla
`python3 ferramentas/agentes.py validar` pertence a manutenção/CI e não ao loop
normal de cada turno.

## Mundo Vivo

`mundo/` guarda a agenda determinística, o cursor de processamento e as decisões
pendentes. `checkpoint.py cena` e `checkpoint.py sessao` sincronizam o motor
depois que o tempo já foi consolidado. Além disso, `turno.py registrar` promove
checkpoint de cena automaticamente quando o tempo efetivo acumula pelo menos duas
horas desde o último cursor ou atravessa o amanhecer configurado. Passagens
pequenas continuam no fluxo transacional comum.

## Antagonistas maiores

Os arquivos reservados `juppongatana/` e `masao/` registram a estrutura canônica
dos antagonistas orientais ligados à história de Ren. Eles devem ser consultados
antes de usar Masao, um membro das Dez Espadas, artefatos do plano de deicídio ou
pressões de escala regional/continental em Faerûn.

## Aliados maiores

Os arquivos reservados `aliados/` registram Shen Meihua, Tsukishiro Jōen, Dame
Jenilynn Leyland, Kagehira Hotaru e Tadasu no Kami como pilares futuros da
campanha de Ren. Eles devem ser consultados antes de introduzir aliados
orientais, treinamento avançado do Getsuei-ryū, a ponte com Tyr/Right Hand of
Tyr, sobreviventes Kagehira ou revelações sobre a divindade que condenou Masao.

## Ponte de Kozakura

Os arquivos reservados `ponte-de-kozakura/` registram a direção canônica de longo
prazo em que anomalias de Kara-Tur em Ravens Bluff levam à revelação de uma
passagem permanente para Kozakura. Eles devem ser consultados antes de explicar
mercadorias orientais sem manifesto, pessoas de Kozakura sem porto, chegadas da
Juppongatana por rota não marítima, perda do controle exclusivo de Masao sobre a
passagem ou o surgimento futuro de Shin-Kozakura.
