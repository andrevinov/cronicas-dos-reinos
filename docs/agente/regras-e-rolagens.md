# Regras, decisões e rolagens

Este documento reúne obrigações antes presentes no `AGENTS.md` sobre manuais de regras, fidelidade, decisões e dados. Consultá-lo quando a tarefa for mecânica; não carregá-lo preventivamente para cenas sem dúvida de regra.

## Manuais de regras

Os arquivos em `regras/` devem funcionar como referência rápida durante o jogo, não como reprodução de livros inteiros. Cada resumo deve, quando aplicável:

- indicar edição e fontes;
- explicar a regra em português claro;
- incluir fórmulas ou passos necessários;
- registrar exceções relevantes;
- separar regra oficial de regra da casa/adaptação;
- trazer exemplos curtos quando úteis;
- registrar dúvidas ainda abertas.

Manuais historicamente prioritários incluem `regras/fontes.md`, `regras/resolucao-de-acoes.md`, `regras/combate.md`, `regras/surpresa.md`, `regras/magia.md`, `regras/descanso-e-cura.md`, `regras/condicoes.md`, `regras/criacao-de-personagem.md`, `regras/progressao.md`, `regras/regras-da-casa.md` e `regras/decisoes.md`. Criar ou completar somente quando a campanha realmente exigir.

Durante a sessão, consultar primeiro o resumo interno pertinente. Livro oficial é nível de escalada, não rotina.

## Filosofia de fidelidade: aproximadamente 70%

A meta de 70% representa filosofia, não métrica matemática. Aplicar regras quando elas sustentarem risco, tensão, estratégia, diferenciação de personagens, uso significativo de recursos, imparcialidade, consequência ou surpresa legítima.

Pode simplificar quando a aplicação literal causar repetição sem valor, microgerenciamento excessivo, interrupção longa, cálculo irrelevante, rolagem sem consequência ou perda de ritmo sem ganho estratégico.

A simplificação não pode apagar custos, limitações, perigos, chances de fracasso, diferenças entre habilidades, efeitos duradouros ou escolhas táticas importantes.

## Ordem para resolver dúvidas

Parar assim que a dúvida estiver resolvida com segurança:

1. aplicar o resumo canônico interno;
2. verificar decisão anterior equivalente;
3. verificar regras da casa;
4. consultar fonte oficial autorizada;
5. interpretar de modo coerente com a edição;
6. simplificar pela regra de ouro;
7. registrar a decisão se puder se repetir.

Durante sessão, não paralisar o jogo por dúvida pequena. Se a pesquisa completa for longa, tomar decisão provisória claramente identificada, registrar a pendência, revisar depois, atualizar `regras/decisoes.md` e corrigir consequências somente quando necessário.

## Regra de ouro

Deve preservar coerência, justiça, ritmo, risco, identidade do sistema e consequências.

Nunca usar para garantir vitória, salvar NPC favorito, invalidar estratégia legítima, forçar trama, esconder erro de preparação, alterar capacidades depois de conhecer a rolagem ou mudar dificuldade retroativamente.

Decisão improvisada com chance de recorrência deve ser registrada em `regras/decisoes.md`, preferencialmente com identificador, sessão de origem, contexto, regra oficial, decisão, justificativa, aplicação futura e estado (permanente, provisória ou aguardando revisão).

## Quando pedir rolagem

Pedir rolagem somente quando coexistirem:

- incerteza real;
- consequência relevante;
- possibilidade plausível de sucesso e fracasso;
- regra, atributo, perícia ou recurso capaz de influenciar o resultado.

Não pedir para ação trivial, conhecimento automático do personagem, tarefa sem pressão repetível até funcionar, ação impossível, ação inevitável ou decisão puramente interpretativa. Quando algo for impossível, explicar pela ficção/regra em vez de oferecer rolagem sem chance real.

## Rolagens abertas

Quando a informação puder ser conhecida, mostrar quando possível:

- o que está sendo testado;
- atributo/perícia/jogada;
- modificadores;
- vantagem/desvantagem;
- dificuldade ou defesa, se conhecível;
- dado;
- total;
- consequência.

Definir modificadores e dificuldade antes do dado, salvo efeitos legitimamente desencadeados depois. Nunca alterar resultado depois de conhecer o valor.

Quando aplicável usar `python3 ferramentas/rolar-dados.py`; exemplos ficam em `ferramentas/README.md`. Rolagens abertas relevantes podem ir para a transcrição.

## Rolagens ocultas

Podem ser usadas quando conhecer a existência ou o resultado prejudicaria mistério ou produziria metajogo, por exemplo: armadilha desconhecida, reação secreta de NPC, encontro aleatório, ação de facção fora de cena, detecção de mentira quando a edição justificar, duração desconhecida e acontecimentos não presenciados.

Rolagens ocultas importantes devem permanecer na área do narrador e registrar contexto, fórmula, resultado, consequência e sessão/data do mundo. Nunca usar rolagem oculta para corrigir a história depois do fato.
