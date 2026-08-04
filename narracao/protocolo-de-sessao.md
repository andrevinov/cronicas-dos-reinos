# Protocolo de sessão

Este protocolo define como iniciar, escrever, alternar, encerrar e consolidar sessões de **Crônicas dos Reinos**.

O guia de estilo e condução fica em `narracao/guia-de-narrativa.md`.

Os limites de conteúdo ficam em `narracao/limites.md` e devem ser consultados sempre que a sessão envolver romance, intimidade, violência intensa, crueldade, horror ou temas adultos.

---

## Estrutura de diretórios

Cada sessão deve ter uma pasta própria:

```text
sessoes/001/
```

Arquivos recomendados:

```text
sessoes/001/
├── transcricao.md
├── resumo.md
├── alteracoes-de-estado.yaml
├── experiencia.md
├── consequencias.md
└── imagens/
```

O arquivo `transcricao.md` é o arquivo vivo da sessão, escrito em alternância entre narrador e jogador.

---

## Cabeçalho da transcrição

Modelo:

```markdown
# Sessão 001

Data real: AAAA-MM-DD
Data no mundo: pendente
Personagem: Ren Kagehira
Local inicial: Ravens Bluff
Modo inicial de cena: interação

Estado inicial:

* PV: 24/24
* Ki: 3/3
* condições: nenhuma
* localização: a definir

---
```

Atualizar o cabeçalho se uma informação pendente for definida durante a preparação.

---

## Abertura

A primeira entrada da sessão é sempre do narrador.

Ela deve conter:

* recap curto, se houver sessão anterior;
* localização atual;
* situação imediata;
* elementos importantes no ambiente;
* NPCs ou ameaças perceptíveis;
* estado crítico de Ren, se relevante;
* modo inicial de cena;
* uma deixa clara para o jogador agir.

Exemplo de fechamento da abertura:

```markdown
**Narrador**

...

O que Ren faz?
```

---

## Alternância

A sessão deve alternar entre:

```markdown
**Narrador**

...

**Jogador**

...
```

O jogador escreve o que Ren faz, diz, tenta, pensa ou sente.

O narrador resolve o mundo, rolagens, NPCs, consequências e nova situação.

---

## Tamanho das entradas

Entrada típica do jogador:

* uma frase a um parágrafo.

Entrada típica do narrador:

* duas frases a três parágrafos.

Entradas maiores são aceitáveis em:

* abertura de sessão;
* descoberta importante;
* encerramento de cena;
* resolução de combate;
* transição de viagem;
* consolidação de consequências.

---

## Modos de cena

Registrar o modo quando ele mudar de forma relevante.

Formato:

```markdown
> Modo de cena: exploração
```

Modos:

* interação;
* exploração;
* combate.

---

## Cena de interação

Usar para conversa, cidade relativamente segura, investigação social e desenvolvimento de personagem.

Granularidade:

* uma troca pode representar segundos, minutos ou uma pequena cena;
* poucas rolagens;
* foco em diálogo, postura, descoberta e relações.

O narrador deve acompanhar:

* atitude dos NPCs;
* informações reveladas;
* mentiras ou omissões;
* mudanças de reputação;
* favores, dívidas e promessas.

---

## Cena de exploração

Usar para locais perigosos sem iniciativa ativa.

Granularidade:

* uma troca representa uma ação ou sequência curta;
* posição, luz, ruído, ferramentas e rotas importam;
* rolagens são mais comuns.

O narrador deve acompanhar:

* sala ou área atual;
* saídas;
* ruído;
* luz;
* distância aproximada;
* armadilhas;
* criaturas escondidas;
* tempo gasto;
* rota de volta.

---

## Cena de combate

Usar quando houver iniciativa, ataque, perseguição tática ou risco imediato equivalente.

Fluxo:

1. estabelecer surpresa, se houver;
2. rolar iniciativa;
3. descrever posição inicial;
4. jogador declara ação de Ren;
5. narrador resolve rolagens e consequências;
6. repetir até encerrar o combate.

Cada rodada deve deixar claro:

* rodada atual;
* turno atual;
* PV de Ren;
* ki restante;
* inimigos visíveis;
* estado aparente dos inimigos;
* distâncias relevantes;
* cobertura e rotas de fuga.

Formato recomendado:

```markdown
> Combate, rodada 2. Ren: PV 18/24, Ki 2/3.
```

---

## Rolagens visíveis

Quando a rolagem puder ser conhecida pelo jogador, registrar no texto.

Formato:

```text
Teste de Furtividade: d20 12 + 5 = 17 contra CD 15. Sucesso.
```

Formato para ataques:

```text
Ataque com wakizashi: d20 14 + 5 = 19. Acerto. Dano: 1d6 4 + 3 = 7.
```

O narrador deve rolar para Ren quando a ação declarada exigir rolagem.

---

## Rolagens ocultas

Usar rolagens ocultas quando revelar a rolagem já entregaria informação indevida.

Exemplos:

* NPC mentindo;
* criatura escondida;
* armadilha não percebida;
* facção agindo fora de cena;
* relógio oculto;
* encontro aleatório secreto;
* consequência que ainda não é perceptível.

Rolagens ocultas importantes devem ser anotadas em:

```text
narrador/sessoes/NNN/rolagens-ocultas.md
```

Não registrar rolagens ocultas na transcrição se isso revelar o segredo.

---

## Preparação do narrador

Antes de uma sessão, criar material reservado apenas quando necessário.

Pasta recomendada:

```text
narrador/sessoes/001/
```

Arquivos possíveis:

```text
preparacao.md
segredos.md
mapa-e-salas.md
relogios.md
rolagens-ocultas.md
npcs.md
```

Esse material não deve ser lido pelo jogador durante a campanha.

---

## Dungeons

Quando uma dungeon ou local perigoso tiver mapa, o narrador deve preparar um resumo reservado.

Formato recomendado:

```markdown
# Mapa e salas

## Topologia

Entrada A -> Corredor B -> Sala C -> Escada D

## Sala C

Descrição pública:

Segredo:

Perigos:

Saídas:

Mudanças se Ren voltar:
```

A transcrição deve revelar apenas o que Ren percebe.

Manter consistência espacial. Se Ren voltar por uma rota, ela deve continuar existindo salvo mudança causada por eventos.

---

## Cidades

Em cidade, usar abstração maior.

O narrador pode resolver deslocamentos como:

* "do porto ao mercado";
* "do quartel aos cais";
* "da taverna ao templo".

Detalhar rota apenas quando:

* houver perseguição;
* alguém estiver seguindo Ren;
* tempo for relevante;
* bairro for perigoso;
* rota escolhida tiver consequência;
* Ren estiver tentando evitar ser visto.

---

## Imagens durante sessão

Quando o jogador pedir imagem, salvar em:

```text
sessoes/NNN/imagens/
```

Nome:

```text
sessao-NNN-momento-XX-slug.png
```

Registrar no ponto correspondente da transcrição:

```markdown
Imagem: [nome da imagem](imagens/sessao-NNN-momento-XX-slug.png)
```

Se a imagem representar uma sala de dungeon, ela não deve revelar saídas, armadilhas ou criaturas que Ren ainda não percebeu.

---

## Encerramento de cena

Ao encerrar uma cena importante, o narrador deve registrar na transcrição:

* o que mudou;
* informação descoberta;
* recursos gastos;
* novas ameaças;
* próximos caminhos óbvios;
* pendências imediatas.

Não precisa transformar todo encerramento em relatório.

---

## Corte de cena por conteúdo adulto

Quando uma cena romântica chegar a intimidade sexual, usar corte de cena.

Formato possível:

```markdown
> Corte de cena: os personagens passam a noite juntos. A sessão retoma depois, quando isso voltar a importar para escolhas, emoções ou consequências.
```

O narrador pode registrar consequências emocionais, sociais, materiais ou narrativas, mas não deve transformar a transcrição em descrição sexual explícita.

Quando violência ou crueldade ultrapassarem o necessário para a cena, resumir e focar no impacto percebido por Ren.

---

## Encerramento de sessão

Ao encerrar uma sessão, criar ou atualizar:

```text
sessoes/NNN/resumo.md
sessoes/NNN/alteracoes-de-estado.yaml
sessoes/NNN/consequencias.md
```

Quando houver XP, marco, recompensa ou progresso:

```text
sessoes/NNN/experiencia.md
```

O encerramento deve registrar:

* ponto inicial e final;
* tempo transcorrido;
* cenas principais;
* decisões de Ren;
* rolagens decisivas;
* combates;
* recursos gastos;
* itens ganhos ou perdidos;
* NPCs conhecidos;
* informações descobertas;
* mistérios abertos;
* consequências persistentes;
* pendências para a próxima sessão.

---

## Consolidação pós-sessão

Depois do encerramento, atualizar os arquivos canônicos necessários:

* `estado/estado-atual.yaml`;
* `estado/tempo.yaml`, quando existir;
* `estado/relacoes.yaml`, quando existir;
* `registros/consequencias.yaml`, quando existir;
* `personagens/jogador/ficha.yaml`, se recursos mudarem;
* `personagens/jogador/conhecimento.md`, se Ren aprender algo;
* arquivos de NPC ou facção, se necessário.

Não consolidar segredos em arquivos públicos.

---

## Pausas e retomadas

Se a sessão for interrompida, registrar no fim da transcrição:

```markdown
> Pausa: Ren está em X, tentando Y. Última situação imediata: Z.
```

Ao retomar, o narrador deve ler esse ponto e abrir com recap curto.

---

## Correções

Quando houver erro de regra, estado ou continuidade:

* corrigir explicitamente;
* registrar o motivo se afetar fatos relevantes;
* evitar apagar decisões do jogador;
* preferir ajuste diegético quando não distorcer o jogo.

Correções grandes devem ir também para `registros/retcons.md` quando esse arquivo existir.
