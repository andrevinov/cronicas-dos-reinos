# Personalidade para decidir — NV-06

## Escopo

O piloto reúne **Silva Elkwood, Nera Vell e Luath**. A projeção
`personalidade_decisoria` aparece na seleção da consulta `contexto.py npc` e em
`memoria_cena` no preparar e na retomada. Não há novo comando obrigatório, leitor
por NPC, banco de memórias, scheduler ou chamada de IA. Não implementa ainda a
execução de planos, contatos ou prazos das NV-07 a NV-11.

O adaptador puro `ferramentas/personalidade_decisoria.py` seleciona trechos dos
papéis conversacionais **já existentes** em `cenario/texturas/index.yaml`.
Esses papéis são orientação interpretativa, não fatos novos ou conhecimento do
personagem. A projeção conserva essa natureza: não promove sugestão a cânone,
não altera os perfis originais, não importa segredos e não cria acontecimentos.

## Contrato e proveniência

`estavel` contém seis eixos: valores, desejos, receios, métodos preferidos, limites
e maneira de se relacionar (`relacionamento`). Cada critério possui ID, recorte
literal e `origem` relativa ao papel indicado na raiz da projeção. Um limite com
`sentido: evitar` descreve conduta a evitar, não um desejo de realizá-la.

A seleção curada identifica o **ID canônico**, o papel e a frase integral de
origem. O recorte só vale enquanto a frase completa coincidir, normalizando
somente whitespace de YAML. Uma edição que preserve palavras mas negue seu
sentido invalida a seleção. O resultado passa a declarar a lacuna e pede
recuração; nunca reutiliza um traço obsoleto nem adivinha a intenção da edição.
A tabela de seleção no código é um adaptador, não uma fonte concorrente: sem o
conteúdo vigente correspondente, não há traço projetado.

`null` significa não estabelecido nas fontes selecionadas, não ausência do traço.
O piloto não inventa receios estáveis para nenhum dos três, nem um desejo pessoal
para Luath. Pode haver material adicional em outras fontes; esta tarefa não o
varre por precaução. NPCs fora do piloto preservam a saída anterior.

`situacao_em` aponta para `/medidores/dados` no mesmo resultado efetivo. Ali ficam
tom, leitura recente, humor **quando registrado**, vínculo, confiança e risco.
Esses campos não são copiados para o perfil estável. `tom_atual` não vira um humor
inventado e risco alto não prova medo permanente. As alterações transacionais
chegam ao estado antes da seleção. Na memória de cena, os ponteiros são relativos
ao item daquele participante. A ausência de um campo exige consulta dirigida,
não permissão para preencher o que falta.

## Usar na narração

Antes de escolher a conduta de um participante, ponderar alternativas **viáveis**
à luz dos valores, desejos, métodos e limites conhecidos. A justificativa deve
conectar a conduta a um critério e reconhecer seu custo ou renúncia quando houver
conflito. Não é necessário recitar o perfil na prosa nem registrar uma ficha de
deliberação a cada turno. O estado resultante continua entrando pelo concluir
normal; acontecimentos marcantes continuam usando o contrato da NV-04.

Diante de uma pessoa conhecida que chega abalada, por exemplo, a seleção permite
que Silva priorize cuidado concreto, Nera uma troca pessoal recíproca e Luath a
preservação da prova pertinente a um assunto da Guarda. Essas são alternativas
de teste, **não novos episódios da campanha** nem respostas obrigatórias. Silva
preocupada não precisa repetir censura já compreendida. Crueldade pode orientar
um método, mas não fornece conhecimento, meios ou garantia de sucesso.

`evaluate_options(perfil, alternativas)` é uma função pura opcional para análise
e testes: recebe até seis condutas, ligações `favorece`/`contraria` entre IDs de
critérios e justificativas, e gates declarados de conhecimento, capacidade,
recursos, presença/canal e autoridade. Não interpreta prosa para descobrir essas
ligações. Gate desconhecido aguarda base; falso indica inviabilidade declarada;
contrariar um limite conhecido exclui a alternativa da preferência do perfil.

Entre as demais, mantém as alternativas não dominadas: uma domina outra somente
se favorece todos os critérios dela, contraria no máximo os mesmos critérios e
melhora pelo menos um desses conjuntos. Não há pesos psicológicos inventados,
escore universal, escolha automática em empate ou decisão por Ren. Critérios que
não aparecem no perfil são listados e não contam como fundamento.

**Afinidades e viabilidade são declarações do chamador, não validação do mundo.**
A função não substitui os gates canônicos, não autoriza operações, não executa
uma ação e não garante sucesso. Não é uma terceira chamada ritual; o narrador
pode deliberar diretamente usando o pacote já entregue.

## Orçamento, retomada e aprofundamento

A integração ocorre em `memoria_relevante._fields`, após o estado efetivo, ponto
compartilhado pela seleção NV-03 e pela memória NV-05. Nenhuma leitura adicional
é necessária. O perfil é um campo prioritário indivisível: valores, limites e
lacunas entram juntos; se não couberem, o mecanismo existente declara necessidade
de aprofundamento. Não aumenta o teto conjunto de 4 KiB nem o envelope comum de
8 KiB. Não multiplica orçamento por participante.

Consulta excepcional, somente quando a lacuna importa:

```sh
poetry run python ferramentas/contexto.py npc silva_elkwood \
  --campo /personalidade_decisoria
```

Também se pode consultar um eixo ou a frase original em
`/textura_narrativa/papel_conversacional`. O catálogo `--campos` inclui a projeção.
Recibos da NV-05 abrangem o perfil selecionado; fonte alterada invalida seu item,
a base disponível no contexto evita retransmissão e retomada fria envia base
completa dentro do orçamento, com lacunas explícitas quando necessário.

## Evidência e limites da entrega

Os testes usam um snapshot histórico dos papéis e cenários temporários. Cobrem
proveniência literal, alteração/negação da fonte, lacunas, diferenças de escolha,
limites, viabilidade desconhecida, crueldade sem meios, empates, não mutação,
orçamento, consulta dirigida, captura NV-04 e retomada em subprocesso YAML/JSON.

A medição antes/depois desliga somente o adaptador na fixture para isolar o custo
em bytes. Confere que o ticket não muda e que recibos não reenviam itens iguais.
Essa medição **não mede tokens nativos nem prova qualidade da narração de uma IA**.
A ampliação para outros perfis exige curação ancorada, não inferência retrospectiva.
