# AMV-05 — Um dashboard que mostre o que é possível concluir

**Data:** 2026-10-04. **Status:** concluída; G0 aprovado para o recorte demonstrado. **Dependências:** AMV-02–04.

**Correção posterior em 2026-10-06:** o aceite não detectou que a fila excluía a
violação crítica com nota nula e ranqueava amostras com nota 100. A
[entrega antecipada](entrega-avaliador-2026-10-06.md) corrige isso e restringe o
alcance da aprovação. AMV-05 permanece como fotografia histórica.

## O que implementar

Separar, no pacote e no painel, execução operacional, cobertura de oportunidades,
qualidade da experiência e guardrails. A visão inicial deve mostrar validade da
medição e cobertura antes de qualquer número. Com instrumentação bloqueada ou
qualidade não avaliada, exibir a limitação correspondente; não pintar uma nota
parcial como experiência saudável. Métricas operacionais parciais continuam
consultáveis, identificadas com seu escopo.

Por módulo, mostrar objetivo, oportunidades elegíveis/atendidas/omitidas, amostra,
qualidade revisada, pendências e provas por interação. Guardrail violado permanece
destacado fora das médias. A conclusão geral não pode melhorar simplesmente
porque módulos difíceis ficaram sem evidência e saíram do denominador.

Congelar versões de implementação executada, detector, rubrica e gerador, além
das entradas do pacote. Comparar apenas pontos compatíveis por módulo. Reanálise
de uma sessão produz um artefato derivado vinculado ao original; não atualiza
silenciosamente suas versões para as do catálogo corrente.

Mostrar custo observado com unidade e atribuição claras. Separar custo exclusivo,
custo compartilhado alocado e custo marginal desconhecido. Não atribuir o mesmo
contexto nativo inteiro a todos os módulos nem inferir benefício narrativo pela
redução de tokens. Comparações de eficiência precisam de recortes equivalentes.

## Por que corrige a causa

O problema visual não é resolvido apenas acrescentando um aviso ao lado de 85,1
verde. A hierarquia e a classificação passam a corresponder ao alcance real da
medição. Séries versionadas evitam interpretar mudança de régua como evolução
da campanha ou dos módulos.

## Prova de correção e aceite

- O pacote 024 original abre como medição incompleta, sem selo global saudável
  e sem tendência calculada a partir de sua nota bloqueada.
- Operação 100 com qualidade confirmada 0 aparece como execução correta e
  experiência inadequada no critério; não recebe aprovação narrativa.
- Falta de qualidade, falta de amostra e negativa válida têm estados diferentes.
- Violação crítica nunca é compensada por economia, fluidez ou outra nota alta.
- Testar o comportamento renderizado e os dados consumidos pelo painel, incluindo
  acesso à evidência e proteção de conteúdos reservados.
- Regeneração preserva proveniência, manifestações e decisões; versões
  incompatíveis não entram em deltas ou médias móveis comuns.
- A soma de custos atribuídos fecha uma vez; estimativas são identificadas.

## Onde mudar e o que poderá sair

Gerador, schemas de avaliação e `evaluation/dashboard/`. Retirar a classificação
global atual quando ela sugere experiência saudável com medição bloqueada.
Campos históricos continuam legíveis como referência; testes que congelam a
apresentação enganosa devem ser substituídos por testes desses estados de validade.

## Entrega obrigatória para G0

Exibir a sessão 024 com uma opção de reavaliação derivada, acessível na seleção
daquela sessão. Preservar o pacote original e identificar fonte, revisão do
avaliador e versões dos módulos que realmente foram jogados. Escolher a revisão
não deve fazer a 024 se passar por uma sessão posterior às mudanças de runtime.

Conferir na interface os contadores corrigidos, a cobertura real, os julgamentos
de experiência e os diagnósticos por interação. Exibir fontes insuficientes quando
existirem; não reduzir a entrega a trocar a cor da nota ou rotular tudo como N/D.
Esta demonstração usa a sessão existente e encerra a etapa A, sem exigir novo jogo.

## Implementação e aceite — 2026-10-04

O gerador **4.8.0** publica o contrato de apresentação **1.0.0**, detector
**4.9.0** e rubrica **objetivos-jogo/1.0.0**. Novos scorecards não publicam uma
nota global: o número operacional fica em `nota_operacional_parcial_0a100`.
O dashboard também impede que o **85,1** do original apareça como aprovação ou
ponto de tendência. Arquivos históricos continuam intactos.

A [revisão derivada da 024](../../../evaluation/sessions/024/revisoes/amv05/manifest.json)
está dentro da mesma sessão, com vínculo por hash ao original e ao mesmo recorte
de **2.098.214 bytes**. Implementações e avaliação **4.0.0** registradas durante
o jogo permanecem preservadas; a avaliação **4.1.0** do catálogo é a régua desta
revisão, separada da execução histórica. Não se afirma execução do runtime novo.

| Prova | Resultado demonstrado |
| --- | --- |
| Operações do recorte completo | 62 chamadas; 15 escritas tentadas = 11 sucessos + 2 falhas + 2 desconhecidas; 20 alvos escritos |
| Cobertura semântica | 408 unidades interação × critério; 13 com parecer; 8 conclusões verificadas; 5 indeterminadas revisadas; 395 sem parecer |
| Diagnóstico acionável | `S024-I0011`: espera voluntária acrescentada sem autorização; guardrail de agência destacado, correção e teste acessíveis |
| Manifestação do jogador | Texto original preservado; decisão parcial posterior preservada, sem virar nota automática |
| Custo dos turnos narrativos | 5.406.799 tokens rateados uma vez entre os pais; diferença de fechamento zero; exclusivo e marginal desconhecidos |
| Regeneração | Duas saídas idênticas, inclusive proveniência, pareceres e manifestação; pacote original inalterado |
| Aceite congelado AMV-01 | 19 verificações em 12 casos, todas aprovadas; referências e expectativas originais preservadas |
| Navegador real | Original → revisão → original; evidência acessível; reserva protegida; qualidade zero separada de operação 100; versões incompatíveis excluídas da série |
| Testes finais | 366 testes de domínio e 2 testes de navegador aprovados; corpus anterior com 226/226 checks |
| Contratos exportados | 21 schemas válidos; 17 artefatos/leituras do pacote validados, incluindo os 12 módulos |

O [schema de apresentação](../../../evaluation/schemas/apresentacao-avaliacao-v1.schema.json)
valida scorecard e leitura por módulo. Testes de domínio protegem cobertura,
qualidade ausente, fontes insuficientes, negativa válida, amostra insuficiente,
violação crítica, comparação por módulo, recortes de custo e regeneração. Testes
em Chrome exercitam a interface e os dados que ela realmente consome.

Uma referência consta do registro histórico, mas não tem resposta observada no
recorte; ela permanece identificada como `apenas_registro_historico`, com flags
desconhecidas e sem entrar na amostra de respostas. O contrato de exportação
passou a representar esse estado, a cobertura operacional, chamadas observadas
e a vinculação das alegações da manifestação aos pareceres, sem relaxar a
validação das interações efetivamente observadas.

### Como apreciar e reproduzir

Com `poetry run servidor`, abrir
`http://127.0.0.1:18765/evaluation/dashboard/?sessao=024&revisao=amv05`.
No seletor **Pacote desta sessão**, comparar com **Original preservado**.
Abrir **Pareceres por interação e critério** ou o link da violação crítica.

A [entrada congelada](../../../evaluation/aceite-avaliacao-v1/entrada-s024-amv05.json)
contém configurações, contratos, hashes de código/interface, versões e decisões,
sem copiar o rollout privado. Reproduzir com a fonte privada indicada por UUID no
manifesto, enquanto código e ambiente coincidirem com a entrada:

```bash
poetry run python ferramentas/reavaliar-sessao.py \
  --rollout /caminho/privado/rollout-2026-09-16T12-14-28-01a0aac8-9b23-7c12-9520-be10b50ed451.jsonl \
  --original evaluation/sessions/024 \
  --entrada-medicao evaluation/aceite-avaliacao-v1/entrada-s024-amv05.json \
  --revisao amv05 --data-revisao 2026-10-04
```

Evidências da entrega: [aceite medido final](../../../evaluation/aceite-avaliacao-v1/resultado-amv05-final.json),
[integridade e reprodução](../../../evaluation/aceite-avaliacao-v1/integridade-s024-amv05.json)
e [verificações finais](../../../evaluation/aceite-avaliacao-v1/verificacao-amv05.json).

### Alcance do G0 e remoções

**G0 foi demonstrado na sessão existente.** A ferramenta já encontra um defeito
concreto de experiência, distingue julgamentos sustentados de indeterminados,
corrige os contadores e mostra suas provas. Isso permite iniciar a etapa B.
Não aprova os doze módulos: faltam fontes para vários objetivos, a revisão é
local e não houve validação cega por terceiro. Estabilidade longitudinal e
episódios controlados permanecem nas AMV-14/16.

Saiu a apresentação de nota parcial como saúde global e sua utilização em séries
incompatíveis. As expectativas antigas que transformavam manifestação isolada
em efeito ou guardrail confirmado foram substituídas por proteção de vinculação
ao parecer; testes de versão consultam o catálogo do cenário, e a preservação da
versão histórica é comprovada na revisão. A evidência protegida permanece testada.

**Nenhum gate do preflight foi removido.** AMV-06/15 ainda precisam demonstrar
substituições equivalentes para sua composição e verificações redundantes. A
matriz de remoção continua condicional; o avanço do G0 não autoriza apagar gates.
