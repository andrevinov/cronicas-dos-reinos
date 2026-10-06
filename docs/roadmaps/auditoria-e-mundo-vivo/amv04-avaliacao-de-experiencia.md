# AMV-04 — Avaliar resultados e oportunidades perdidas

**Data:** 2026-10-04. **Status:** concluída. **Dependências:** AMV-01–03.

## Implementação entregue

O analisador agora monta um recorte por interação com entrada literal, resposta
final visível, respostas anteriores disponíveis e operações correlacionadas.
Os textos são usados durante a revisão; o ledger exporta hashes, localizadores
e os trechos públicos necessários. Nunca consulta o estado atual para preencher
o passado. Uma observação sem identificador canônico recebe `OBS-<hash>`;
esse identificador não cria uma interação ou sessão na campanha.

[`experiencia_avaliacao.py`](../../../ferramentas/experiencia_avaliacao.py)
consome os **34 contratos de objetivo**. A matriz distingue critérios ainda sem
parecer de critérios revisados e mantém oportunidades atendidas, omitidas,
negativas válidas, sobreativações e casos indeterminados. Fonte insuficiente
continua fora do denominador; a matriz não inventa avaliações favoráveis para
preencher lacunas.

O adaptador determinístico reconhece um compromisso de aviso vencido em consulta
de cena, sem depender de chamada ou recibo do módulo de NPC. Exige ator
inequívoco, objetivo, conhecimento confirmado, presença, canal e impedimentos.
Entrega ou ausência precisam estar explícitas na resposta. Rumor, fonte ausente,
ambiguidade entre atores ou linguagem não reconhecida exigem revisão semântica.
Esse adaptador tem escopo limitado; não é um leitor semântico universal. Outros
objetivos entram pelo mesmo contrato de parecer, inclusive consequências sem
invocação do módulo correspondente.

A revisão semântica usa as adjudicações existentes. Cada parecer novo registra
revisor e papel, rubrica `objetivos-jogo/1.0.0`, configuração, hash do recorte,
citações literais com offsets e hashes, dependências operacionais, incertezas,
conflitos e guardrails. Importação sem vínculo verificado, autoavaliação do
produtor, dependência inconclusiva, corte incompleto e conflito não confirmam
qualidade. Evidência reservada permanece verificável por hash e offsets sem
publicar seu conteúdo. Pareceres antigos continuam legíveis como proveniência
legada, sem serem apresentados como revisão nova verificada.

O gerador publica a matriz em `avaliacoes-qualidade.json`, métricas por critério
e experiência separada dos indicadores operacionais. Violação de guardrail
confirmada não é compensada por uma média. Reclamação, mesmo parcialmente
adjudicada, não cria sozinha um falso positivo, omissão ou efeito inadequado;
essa decisão pertence ao parecer factual correspondente. O texto original do
jogador é preservado.

O catálogo passou a `5.1.0`, com avaliação `4.1.0` e releases anexadas ao histórico.
As versões de implementação e os registros antigos não foram modificados. Os
testes de arquitetura continuam protegendo módulos, aliases e contratos; deixaram
de exigir o número exato de uma versão minor mutável.

## Evidência e diagnóstico da 024

- [Relatório legível](../../../evaluation/aceite-avaliacao-v1/relatorio-s024-amv04.md):
  conclusões por interação, limitações e correções testáveis.
- [Reanálise verificada](../../../evaluation/aceite-avaliacao-v1/experiencia-s024-amv04.json):
  **13 pareceres, oito confirmados e cinco indeterminados**. Corte original e
  sete âncoras conferidos; referências de desenvolvimento e reservadas revisadas.
- [Pareceres de entrada](../../../evaluation/aceite-avaliacao-v1/pareceres-s024-amv04.json):
  fontes, escopos e manifestação original do jogador. Revisão pós-hoc realizada
  por Codex; não se declara validação cega por terceiro.
- [Referências congeladas](../../../evaluation/aceite-avaliacao-v1/resultado-amv04.json):
  **17 de 19 checks** passam, incluindo a omissão sem recibo e o conjunto reservado.
  As duas divergências restantes são de apresentação no dashboard, escopo AMV-05.
- [Verificação](../../../evaluation/aceite-avaliacao-v1/verificacao-amv04.json):
  testes focados, corpus anterior, schemas e preservação de fontes/save.

S024-I0005 distingue integridade do resultado do dado, necessidade do teste e
percepção de Mori. S024-I0011 identifica uma espera voluntária não autorizada,
sem reprovar a frustração que o próprio jogador declarou. Progresso de aventura,
consequências persistentes, adaptação canônica e planos adversários permanecem
indeterminados onde as fontes antigas não permitem confirmar o resultado.

O diagnóstico é local e rastreável. Ele não afirma que treze pareceres comprovam
a qualidade integral dos doze módulos ou seu desempenho longitudinal.

## Repetição e próximo gate

Para conferir novamente a fonte local identificada pelo UUID no gabarito, sem
copiar o bruto para o repositório:

```sh
poetry run python ferramentas/verificar_aceite_avaliacao.py \
  --reavaliar-experiencia --fonte /caminho/do/rollout.jsonl \
  --adjudicacoes evaluation/aceite-avaliacao-v1/pareceres-s024-amv04.json \
  --saida /tmp/nova-revisao-amv04.json
```

Para outros recortes, a porta continua sendo o gerador existente com
`--adjudicacoes-modulares`. Pareceres devem ser elaborados a partir das fontes
daquele recorte; não se reutilizam hashes ou decisões de outro episódio.
A geração revalida fontes e evita duplicar avaliações na regeneração.

**G0 continua pendente da AMV-05.** Os novos pareceres já estão disponíveis,
sem exigir nova sessão. O pacote histórico e sua visualização original foram
preservados; o painel ainda precisa apresentar a revisão derivada e corrigir as
duas falhas de conclusão visual. Runtime AMV-06–13 não foi iniciado.

Nenhum gate de preflight foi desabilitado. Saiu do cálculo a inferência de que
uma manifestação percebida é, por si, falha factual de módulo. Checks de execução,
recibos, rodapé e mecânica continuam protegendo suas propriedades próprias.
Suite completa/preflight antes de merge seguem como gate; esta entrega foi
verificada com testes direcionados, sem repetir as falhas preexistentes já
documentadas na AMV-01.

---

## Especificação original preservada

## O que implementar

Acoplar ao fluxo pós-hoc existente uma avaliação efetiva de qualidade por
interação, módulo e critério. Usar entrada do jogador, estado efetivo anterior,
operações e resposta final realmente visível, com hashes e fontes congeladas.
O texto enviado ao writer não substitui a resposta final se houver divergência.

Produzir julgamentos explicados sobre continuidade, convicções e objetivos,
iniciativa, consequências, progresso de aventuras, adaptação dramática,
percepção legítima e dificuldade justa. Combinar verificações determinísticas
com revisão semântica; registrar revisor, versão de rubrica, configuração,
evidência literal, justificativa, incerteza e eventuais conflitos. O julgamento
do próprio produtor não serve de confirmação independente de sua qualidade.

Construir denominadores de oportunidades a partir dos fatos e obrigações
alcançáveis no recorte, inclusive quando nenhum módulo foi invocado. Distinguir
oportunidade atendida, omitida, negativa válida e indeterminada. Conhecimento
do narrador não cria oportunidade social para quem desconhece o fato; zero
missões ativas não exige inventar uma oferta. Sem fontes suficientes, abster-se.

Integrar manifestações já registradas ao processo de adjudicação, mantendo o
texto do jogador e a decisão técnica em camadas separadas. O jogador não precisa
dar nota nem preencher uma ficha técnica. Reclamação relevante entra como caso
a verificar e só muda métrica factual com evidência e decisão rastreável.

Entregar essa cadeia já na reavaliação da sessão 024, antes de AMV-06–13.
Reconstruir o contexto histórico somente pelas fontes disponíveis no instante
avaliado ou por histórico autorizado verificável. Não aplicar retrospectivamente
um plano criado agora. Critério novo pode revisar texto antigo com proveniência
explícita, sem inventar que o módulo antigo tinha a instrumentação nova.

O relatório deve distinguir defeito de extração/avaliação, comportamento inadequado
de módulo, problema de instrução/dado e limitação de fonte. Para achado confirmado,
entregar evidência por interação, objetivo afetado, diagnóstico e proposta de
correção que possa ser testada. Avaliação vazia, aprovação só por rodapé ou uma
lista genérica de sugestões não satisfazem essa entrega.

## Por que corrige a causa

Hoje a qualidade pode permanecer vazia, e a ausência de invocação pode esconder
a omissão do módulo. A avaliação passa a olhar a finalidade e a oportunidade
independentemente de um recibo positivo. Isso torna possível reprovar uma cena
passiva com ferramentas bem executadas e reconhecer silêncio justificado.

## Prova de correção e aceite

- Pares de episódios com operações iguais e resultados narrativos diferentes
  recebem julgamentos diferentes nos critérios afetados.
- Remover uma iniciativa elegível ou consequência esperada aumenta omissões,
  mesmo que o módulo não tenha emitido qualquer recibo.
- Ausência legítima de causa, falta de percepção ou silêncio estratégico não
  geram obrigação artificial de fala, quest ou ataque.
- Revisão pendente, conflito e corte incompleto não entram como qualidade positiva.
- Calibrar a revisão com casos de referência independentes, incluindo erros
  deliberados e negativos legítimos; documentar divergências por critério.
- Reavaliar recortes das reclamações existentes sem mudar os pacotes históricos
  originais nem criar versões executadas que não constam das fontes.
- Na 024, revisar S024-I0005 com intenção, ficção disponível, compromisso mecânico,
  rolagem e resposta final. Confirmar, rejeitar ou limitar cada alegação com fonte;
  a reclamação sozinha não serve como gabarito confirmado.
- Demonstrar os julgamentos do G0 sobre o recorte original e os casos reservados,
  incluindo falha conhecida, caso legítimo e fonte realmente insuficiente.
- Fontes reservadas são examinadas em contexto autorizado; exportação para o
  jogador não revela plano secreto ou informação que Ren ainda não descobriu.

## Onde mudar e o que poderá sair

Analisador, adjudicações, critérios do catálogo e gerador de avaliação. Remover
a equivalência entre marcador estrutural e qualidade depois de preservar os
checks de entrega estrutural em sua dimensão correta. Não eliminar rodapé ou
contrato mecânico: eles protegem outras propriedades.
