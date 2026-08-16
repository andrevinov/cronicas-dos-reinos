# Protocolo de entrada — ON, OFF e RECALL

Este documento define a linguagem explícita usada pelo jogador na janela do Codex. O objetivo é eliminar ambiguidade entre **agir como Ren**, **falar com o narrador** e **pedir ao sistema para completar uma lembrança que Ren possui**.

## Sintaxe

Há três canais:

```text
texto normal   = ON
[texto]        = OFF
{texto}        = RECALL, somente dentro de ON
```

### ON — ficção ativa

Texto normal é uma declaração dentro da ficção: ação, fala, intenção, postura ou pensamento de Ren fornecido pelo jogador.

Exemplo:

```text
Ren coloca três moedas sobre a mesa.

— Cuide bem dele.
```

ON pode avançar a ficção e, quando houver uma resolução narrativa, é o único texto do jogador que pode ser persistido por `turno.py registrar`.

### OFF — conversa de mesa

Um **bloco inteiro** cujo primeiro caractere não branco é `[` e o último é `]` é OFF.

Exemplo:

```text
[Quanto dinheiro eu tenho?]
```

OFF é André falando com o narrador/Codex. Pode pedir esclarecimento, contexto, regra, descrição adicional, retomada, manutenção ou confirmação.

OFF:

- não é ação de Ren;
- não avança tempo;
- não consome recurso;
- não cria delta;
- não chama `turno.py registrar` por si só;
- não entra na transcrição da sessão.

A resposta do narrador a conteúdo OFF também deve aparecer entre colchetes e deve permanecer fora da transação narrativa.

Blocos ON e OFF podem coexistir na mesma mensagem. Separá-los antes de resolver a ficção.

Exemplo:

```text
[Eu ainda tenho 45 PO?]

Ren coloca três moedas diante de Iria.

— Considere pago.
```

O primeiro bloco é respondido como OFF. Somente o texto ON e a narração causada por ele podem ir para a transação.

Não usar um tool call apenas para classificar texto normal óbvio. A separação ON/OFF é L0. `entrada.py` existe como parser/validador determinístico e deve ser chamado quando houver sintaxe explícita, ambiguidade ou necessidade de validação mecânica.

## RECALL — autocomplete da memória de Ren

`{...}` dentro de ON significa: **complete esta lacuna factual com algo que Ren legitimamente sabe, antes de executar a ação**.

Exemplo:

```text
Ren diz a Nera:

— Quando eu vivia em {cidade onde Ren passou seus anos mais pobres}, a vida era muito difícil.
```

Se a informação for determinada pelo cânone/conhecimento de Ren, o narrador substitui a chave pela resposta e executa a versão resolvida. A transcrição deve guardar apenas o ON final já expandido, nunca o placeholder bruto.

RECALL pode recuperar, por exemplo:

- nome de pessoa conhecida;
- cidade, bairro ou lugar da história de Ren;
- item conhecido ou carregado;
- título, alcunha ou organização conhecida;
- palavra/termo que Ren saberia;
- fato que já pertence ao conhecimento de Ren.

RECALL **não é autorização para inventar**. A ordem de resolução segue a política de contexto: L0 primeiro; depois consulta dirigida suficiente, normalmente `contexto.py conhecimento`, ficha, relação ou outra fonte pública apropriada. Não abrir material reservado para pôr informação secreta na boca de Ren.

### Limites de agência

RECALL completa memória/conhecimento factual; não delega a personagem ao narrador.

Permitido:

```text
— Procure {nome do guarda que nos ajudou na Ponte Baixa}.
```

Não permitido:

```text
Ren decide {qual é a melhor estratégia}.
```

Não permitido:

```text
Ren diz {algo romântico que ele sentiria}.
```

Não permitido:

```text
— O assassino foi {quem realmente matou a vítima}.
```

se Ren ainda não souber quem foi.

O narrador nunca usa RECALL para escolher vontade, estratégia, emoção, crença, fala criativa ou decisão de Ren.

### RECALL não resolvido

Se a resposta não estiver definida, estiver ambígua ou não for legitimamente conhecida por Ren:

1. não inventar;
2. não executar o ON;
3. não rolar dados;
4. não avançar tempo;
5. não registrar turno;
6. responder em OFF explicando a lacuna e pedir ao jogador que defina ou reformule.

Exemplo:

```text
[O cânone atual não define uma cidade única para esse período da vida de Ren. Quer defini-la agora ou reformular a fala?]
```

## Mensagens mistas

Uma mensagem pode conter OFF + ON + RECALL:

```text
[Quanto dinheiro tenho agora?]

Ren separa três moedas.

— Quando eu vivia em {cidade onde Ren passou seus anos mais pobres}, isso teria sido uma fortuna. Cuide dele.
```

Fluxo correto:

```text
mensagem
→ separar ON/OFF
→ responder/obter apenas o contexto necessário ao OFF
→ resolver todos os RECALL do ON
→ se algum RECALL falhar: parar sem avançar
→ resolver o ON
→ narrar
→ registrar somente ON expandido + narração + deltas
```

A resposta visível pode conter primeiro um bloco OFF entre colchetes e depois a narração normal. O bloco OFF do narrador não deve ser copiado para `narracao` na transação.

## Sintaxe e parser

Ferramenta:

```bash
python3 ferramentas/entrada.py classificar
```

ou, com Poetry:

```bash
poetry run entrada classificar
```

A mensagem é lida de stdin por padrão. O parser retorna:

- `tipo`: `somente_on`, `somente_off`, `misto`, `vazio` ou `invalido`;
- `tem_on`;
- `tem_off`;
- `tem_recall`;
- blocos em ordem;
- conteúdo ON separado;
- blocos OFF;
- placeholders RECALL encontrados;
- `pode_registrar`.

Para validar o texto que será enviado como campo `jogador` a `turno.py`:

```bash
poetry run entrada validar-registro
```

Só ON puro e já resolvido é registrável.

### Regras sintáticas

- OFF precisa ocupar um bloco/parágrafo completo: começa com `[` e termina com `]`;
- `[pergunta] ação` no mesmo bloco é inválido como OFF; separar por linha em branco;
- `{...}` só é interpretado como RECALL em bloco ON;
- RECALL vazio, aninhado ou com chave sem par é inválido;
- chaves literais podem ser escapadas como `\{` e `\}`.

## Barreira transacional

`turno.py registrar` deve validar o campo `jogador` antes de qualquer escrita. Se houver OFF ou RECALL não resolvido, a operação falha sem tocar em transcrição ou buffer.

Isso é uma barreira de segurança, não uma razão para chamar o parser em toda mensagem. Texto ON comum continua no caminho rápido sem tool call extra de classificação.
