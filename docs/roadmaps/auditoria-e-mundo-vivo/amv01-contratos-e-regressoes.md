# AMV-01 — Objetivos dos módulos e regressões do diagnóstico

**Data:** 2026-10-04. **Status:** concluída em 2026-10-04; G0 pendente.
**Dependências:** nenhuma.

## Entrega executada

Contratos das 34 capacidades dos 12 módulos foram adicionados ao catálogo e ao
schema, com validação compatível com catálogos históricos. O
[pacote de referência](../../../evaluation/aceite-avaliacao-v1/README.md) congela
12 casos (11 de desenvolvimento e 1 reservado), expectativas, metas, fontes da
024 e inventário de cobertura. O corte original e sete âncoras foram verificados
sem copiar o rollout bruto para o repositório.

A [medição inicial](../../../evaluation/aceite-avaliacao-v1/resultado-inicial.json)
registra **7 falhas em 17 verificações** do conjunto de desenvolvimento. Os casos
mínimos de qualidade ausente/inadequada passam como controles; a referência não
afirma que eles reproduzem toda a insuficiência de apresentação. O painel bloqueado
da 024 reproduz a aprovação indevida nas funções reais de apresentação.

O inventário registra os 31 checks diretos aprovados em 19,727 segundos, sete
comandos repetidos na auditoria final e nove testes ancorados repetidos. Nenhuma
aposentadoria foi executada. Contratos e gabaritos são a entrega desta tarefa;
consumo semântico, correções do avaliador e aceite G0 permanecem nas AMV-02–05.

**Verificação:** 23 testes focados e as 226 comparações do corpus anterior passaram.
A suíte integral executou 2.352 testes, com quatro falhas e um erro; os cinco casos
foram reproduzidos numa cópia isolada da revisão anterior. A árvore protegida
da campanha permaneceu idêntica. O
[registro da verificação](../../../evaluation/aceite-avaliacao-v1/verificacao-implementacao.json)
preserva essas limitações; a suíte integral não foi declarada aprovada.

## O que implementar

Evoluir o catálogo existente com um contrato por capacidade: objetivo de jogo,
gatilho legítimo, fontes necessárias, resultado verificável, negativa válida,
unidade de avaliação e guardrails. Separar execução operacional, oportunidade
de atuação, efeito persistente e qualidade da experiência. Cada critério recebe
um responsável e uma regra explícita para ausência de dados.

Congelar em cenários isolados os erros já observados: conclusão YAML contada como
desconhecida; recibo `concluir_iniciativa` órfão; recibo sem atividade reconhecida;
qualidade vazia com painel saudável; julgamento inadequado sem consequência
na apresentação de experiência; módulo omitido apesar de causa válida.
Registrar entrada, resultado defeituoso observado e expectativa justificada por
contrato independente do código que será corrigido.

Definir antes da correção o gabarito do G0: casos verificáveis da sessão 024,
critérios narrativos com fontes suficientes, negativos legítimos e abstenções
justificadas. Reservar um recorte independente para verificar o avaliador depois
do ajuste. Julgamento de referência e decisão do detector ficam em camadas
separadas; divergência exige explicação e impede aprovar silenciosamente o caso.

Localizar e verificar o corte original da 024 pelo hash do manifest, registrando
como ele será recuperado sem versionar o bruto. O corte foi conferido em
2026-10-04: 2.098.214 bytes, hash correspondente e linha final completa. Enumerar
quais fatos anteriores à cena podem ser reconstruídos e quais permanecem ausentes;
não substituir contexto histórico pelo estado atual da campanha.

Inventariar também o preflight efetivo, suas chamadas internas e a CI: propriedade,
comando, testes relacionados, origem histórica, frequência, custo observado e
possível duplicação. Os 31 checks diretos são o ponto inicial, não uma meta de
quantidade. Usar a auditoria de testes existente para sinais e revisar a semântica.

## Por que corrige a causa

O avaliador atual consegue reconhecer chamadas sem necessariamente conhecer a
finalidade do módulo. Contratos de resultado dão à auditoria uma pergunta que
pode reprovar uma entrega tecnicamente bem-sucedida. Regressões anteriores à
correção impedem que a nova régua seja ajustada apenas para deixar o pacote verde.
O inventário evita retirar uma proteção porque ela parece duplicada pelo nome.

## Prova de correção e aceite

- Cada uma das doze famílias possui objetivos e critérios de oportunidade e efeito,
  incluindo memória, agência, NPCs, sidequests, cânone, mundo e adversários.
- Casos de falha reproduzíveis ficam vermelhos na implementação diagnosticada;
  casos de silêncio ou inatividade legítima têm expectativas distintas.
- O gabarito do G0 e o recorte reservado são congelados antes de ajustar a régua;
  não aumentar tolerâncias depois para aprovar os resultados obtidos.
- Os cenários não exigem modificar o save, revelar segredos ou reescrever sessões.
- As entradas históricas declaram natureza, instante e motivo do congelamento;
  uma reprodução mínima nova não se apresenta como sessão realmente jogada.
- Inventário liga cada candidato à remoção a uma propriedade e à tarefa que
  demonstrará a substituição. Casos suspeitos não são removidos automaticamente.

**Limite:** esta tarefa especifica a régua e as falhas; não torna os módulos bons
nem inaugura uma baseline de jogo.

## Onde mudar e cobertura futura

Catálogo e contratos em `evaluation/`, corpus de avaliação, fixtures isoladas e
testes com nomes de domínio. Políticas vigentes de teste permanecem aplicáveis.
Esta tarefa não aposenta gates; prepara a rastreabilidade usada pela AMV-15.
