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
├── juppongatana/
│   ├── README.md
│   ├── membros.md
│   ├── marcos-de-aparicao.md
│   └── imagens/
├── masao/
│   ├── README.md
│   ├── plano.md
│   └── imagens/
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

## Antagonistas maiores

Os arquivos reservados `juppongatana/` e `masao/` registram a estrutura canônica
dos antagonistas orientais ligados à história de Ren. Eles devem ser consultados
antes de usar Masao, um membro das Dez Espadas, artefatos do plano de deicídio ou
pressões de escala regional/continental em Faerûn.
