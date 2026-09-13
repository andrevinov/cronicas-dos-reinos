# Sessão 001: preparação do narrador

Arquivo reservado ao narrador.

Não revelar este conteúdo ao jogador salvo descoberta legítima em jogo.

---

## Objetivo da sessão

Estabelecer Ravens Bluff como lugar concreto, apresentar o porto como primeira área jogável e dar a Ren uma entrada plausível na cidade sem tirar sua liberdade.

Objetivos práticos:

* mostrar que Ravens Bluff é movimentada, legalista e cheia de sombras;
* permitir que Ren investigue Masao pelo porto;
* apresentar a Night Watch como cobertura possível, não obrigatória;
* criar pelo menos um contato local recorrente;
* oferecer uma pista inicial ligada à missão pessoal de Ren;
* deixar a cidade aberta para investigação, recusa, infiltração ou trabalho formal.

---

## Abertura planejada

Ren está no Cais de Chegada de Ravens Bluff no fim da tarde.

Condições:

* névoa baixa vinda do Dragon Reach;
* madeira molhada e cheiro de peixe;
* fiscais fechando registros do dia;
* carregadores ainda movendo caixas;
* tavernas começando a encher;
* patrulheiros recolhendo relatos antes da noite.

Situação imediata:

* Ren acabou de se orientar o suficiente para saber onde ficam os registros portuários e as tavernas próximas;
* ele ouviu que a Night Watch aceita auxiliares para patrulha noturna;
* uma discussão discreta ocorre perto do pátio de carga;
* um carregador menciona que uma carga sumiu antes de chegar à alfândega.

Fechar a abertura com uma deixa aberta, sem menu rígido.

---

## Primeiros caminhos possíveis

### Aproximação da Night Watch

Se Ren procurar a guarda, Luath pode avaliá-lo com cautela.

Luath não deve oferecer confiança imediata. Ele pode permitir que Ren acompanhe uma ronda curta se Ren parecer capaz, discreto e útil.

Possível consequência:

* Ren ganha cobertura temporária;
* a guarda passa a saber seu nome;
* criminosos locais podem notá-lo mais cedo.

### Investigação direta no porto

Se Ren ignorar a Night Watch e investigar Masao por conta própria, dar pistas pequenas e ambíguas.

Fontes possíveis:

* carregadores;
* registros incompletos;
* taverna portuária;
* mercado de peixe;
* fiscal nervoso;
* informante oportunista.

### Infiltração ou vigilância

Se Ren seguir alguém, esconder-se ou observar antes de falar, usar o porto como ambiente favorável.

Elementos úteis:

* pilhas de carga;
* névoa;
* ruído de cordas e sinos;
* passarelas de serviço;
* becos entre depósitos;
* trabalhadores que olham para outro lado por hábito.

### Recusa completa dos ganchos

Se Ren sair do porto, permitir.

Rotas imediatas:

* taverna;
* Fishtown;
* posto da guarda;
* hospedagem barata;
* mercado;
* templo ou praça mais segura.

O desaparecimento da carga continua avançando fora de cena.

---

## Testes prováveis

Usar o rolador local quando houver rolagem.

```bash
python3 ferramentas/rolar-dados.py ren pericia percepcao --cd 12
python3 ferramentas/rolar-dados.py ren pericia investigacao --cd 13
python3 ferramentas/rolar-dados.py ren pericia intuicao --cd 14
python3 ferramentas/rolar-dados.py ren pericia furtividade --cd 13
```

Referências:

* Percepção CD 12: notar discussão no pátio de carga, alguém observando Ren ou uma marca fora do lugar.
* Investigação CD 13: associar registro incompleto, lacre violado ou rota de carga inconsistente.
* Intuição CD 14: perceber que uma testemunha omite algo por medo, não necessariamente por culpa.
* Furtividade CD 13: seguir alguém em meio ao movimento do porto.
* Persuasão CD 12 a 15: obter ajuda sem pagamento, dependendo da abordagem.
* Intimidação CD 13: pressionar trabalhador comum; pode gerar medo e rumor negativo.

Não pedir teste se Ren descrever uma abordagem claramente suficiente ou impossível.

---

## Combate provável, se houver

Evitar combate gratuito na abertura.

Combate pode ocorrer se:

* Ren intervier em extorsão;
* seguir alguém até beco isolado;
* tentar tomar objeto protegido;
* for emboscado depois de chamar atenção.

Escala recomendada:

* 1 valentão de cais e 1 a 2 cúmplices;
* ou 2 criminosos comuns tentando fugir, não morrer;
* ou uma perseguição sem combate fechado.

Ren está sozinho. Priorizar inimigos que queiram escapar, assustar ou recuperar algo, não lutar até a morte.

---

## Recompensas iniciais possíveis

Recompensas devem depender do caminho escolhido.

Possíveis ganhos:

* nome de uma testemunha;
* acesso a uma ronda da Night Watch;
* pequena carta provisória de apresentação;
* 5 a 15 po por serviço concreto;
* favor de um carregador, pescador ou fiscal;
* pista parcial sobre passageiro estrangeiro;
* informação sobre taverna ou armazém específico.

Evitar entregar confirmação direta sobre Masao na primeira troca.

---

## Encerramento provável da primeira sessão curta

Bom ponto de pausa:

* Ren aceita ou recusa entrada na Night Watch;
* Ren identifica o primeiro local suspeito;
* Ren segue uma testemunha;
* Ren entra em armazém ou taverna com risco;
* Ren obtém uma pista que exige decidir entre cautela e ação imediata.

Ao encerrar, atualizar:

* `sessoes/001/resumo.md`;
* `sessoes/001/alteracoes-de-estado.yaml`;
* `estado/estado-atual.yaml`;
* `personagens/jogador/conhecimento.md`, se Ren aprender algo;
* relações, se um NPC recorrente for estabelecido.

