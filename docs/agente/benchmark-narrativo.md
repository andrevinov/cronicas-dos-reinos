# Benchmark de memória, autonomia e consumo — NV-02

## Escopo

Ferramenta de engenharia pós-hoc. Nada foi acrescentado a `cronica preparar` / `cronica concluir`, ao contexto do narrador, ao scheduler ou ao protocolo da campanha. Não há chamada nova de IA nem dependência externa. Integridade descobre os testes automaticamente; gates e tetos anteriores continuam obrigatórios.

Três níveis não podem ser confundidos:

1. **Sonda de componente:** executa funções reais em `TemporaryDirectory` e mede argumentos/saídas em bytes. Detecta, por exemplo, perda de memória na projeção.
2. **Ensaio narrado:** segue roteiro controlado e registra o episódio inteiro em rollouts nativos, incluindo leitura, narração, checkpoint, fronteira, recuperação e retomada. A qualidade recebe revisão identificada com evidência.
3. **Comparação:** somente episódios narrados, completos e pareados permitem veredito sobre qualidade e tráfego nativo. Sondas ou dados sintéticos nunca são aprovados como prova de economia real.

A NV-02 constrói o instrumento; não antecipa a correção de compactação da NV-03 nem a execução autônoma posterior. Um diagnóstico pode continuar mostrando uma falha atual sem tornar a infraestrutura de medição incorreta.

## Roteiros isolados

`tests/fixtures/narrative-benchmark-v1.json` contém estado inicial, cinco entradas ordenadas e três critérios de revisão por cenário:

| Cenário | Propriedade no ensaio narrado |
| --- | --- |
| Reencontro com aliado | Vínculo, personalidade e limite do conhecimento |
| Promessa pendente | Recuperação do acordo; ausência de cumprimento inventado |
| Mudança de confiança | Delta antes do checkpoint; causa preservada |
| Iniciativa fora de cena | Contato não solicitado, logística e agência |
| Duas frentes adversárias | Independência, tentativa versus sucesso e recursos |
| Retomada fria | Cena, promessa e relação sem histórico do chat |

Personagens e situações foram inventados para teste, não são adições ao cânone. Não copiar os cenários para a campanha real. Executar em ambiente descartável. O benchmark não conduz a partida nem cria outro motor: o executor do ensaio usa o motor em teste. Uma variante precisa de nova versão, não de edição silenciosa após observar resultados.

As sondas são recortes dos contratos, **não episódios completos**. Iniciativa observa cadência/adiamento; frentes observa roteamento. Nenhuma dessas sondas prova que um NPC agiu ou que a prosa ficou boa. A retomada reconstrói uma projeção sem passar a saída anterior; não simula uma inferência.

## Comandos

```bash
poetry run python ferramentas/benchmark_narrativo.py cenarios
poetry run python ferramentas/benchmark_narrativo.py sondar > /tmp/sondas.json
mkdir -p /tmp/ensaio
poetry run python ferramentas/benchmark_narrativo.py manifesto \
  --codigo-ref "$(git rev-parse HEAD)" --modelo '<modelo observado>' \
  --ruleset '<ruleset do ensaio>' > /tmp/ensaio/manifesto.json
poetry run python ferramentas/benchmark_narrativo.py coletar \
  /tmp/ensaio/manifesto.json > /tmp/antes.json
poetry run python ferramentas/benchmark_narrativo.py comparar \
  /tmp/antes.json /tmp/depois.json
```

Relatórios vão somente para stdout; gravação exige redireção explícita. As sondas criam e removem apenas arquivos temporários. Não executar por rotina durante o jogo.

O modelo de manifesto nasce com `integral: false`, seed a preencher e critérios `nao_avaliado`: não é baseline aprovada. Preencher parâmetros, seed e caminhos; executar todos os roteiros e declarar `integral: true` somente após conferir arquivos integrais.

Caminhos são relativos ao manifesto, podendo apontar para fora do repo. Cada segmento deve ser sessão nativa inteira com ID único. A retomada fria exige nova sessão no ponto marcado, sem copiar a conversa. Não fracionar uma sessão: isso poderia duplicar o prefixo ou ocultar custos iniciais.

Baseline e candidata precisam do mesmo catálogo, modelo, parâmetros, ruleset, seed e condições de contexto. Conservar tentativas falhas e reparos; não excluir resultados caros. Repetições adicionais usam IDs estáveis e devem ser pareadas integralmente, sem reutilizar rollouts.

## Revisão de qualidade

Cada critério recebe `aprovado`, `reprovado` ou `nao_avaliado`. Os dois primeiros exigem avaliador, justificativa semântica e trecho literal de resposta final do assistente. Exemplo com endereço ilustrativo:

```json
{
  "resultado": "aprovado",
  "avaliador": "humano:revisor-do-ensaio",
  "justificativa": "O vínculo aparece coerentemente sem atribuir decisão ao jogador.",
  "evidencias": [
    {"segmento": 0, "linha": 12, "trecho": "Trecho literal da resposta final observada."}
  ]
}
```

Segmento começa em zero; linha física do JSONL começa em um. Prompt, instrução, raciocínio interno e saída de ferramenta não provam qualidade da **narração**. O código verifica endereço, papel e literalidade; **não certifica a interpretação semântica do avaliador**. Revisar o episódio inteiro, incluindo contradições e omissões. Uma ação ausente pode ser julgada a partir da resposta em que deveria ter sido considerada, explicando a omissão.

O relatório derivado conserva resultados, avaliador, endereços e hashes das citações, não a prosa do rollout. Brutos e manifesto completo devem permanecer fora do repo. Anotação não transforma o ensaio em revisão independente.

## Medição e comparação

`analisar-rollout.py` continua fornecendo **schema 3** e classificações operacionais inferidas. A extensão usa `all_turns`, nunca apenas `narration_turns`. Uma leitura complementar verifica cobertura e preserva ausência de contadores sem reinterpretar o schema público anterior.

Entrada, cache, saída e raciocínio são apresentados separadamente. `input_plus_output_tokens = input_tokens + output_tokens`; cache é parte da entrada, raciocínio é parte da saída. Não somar novamente. `uncached_input_tokens` é diferença observacional, não fórmula de quota/faturamento. Parcela ausente mantém a métrica `null`.

Snapshots cumulativos idênticos são deduplicados. Regressões, lacunas cumulativas, início parcial, turnos sem medição, chamadas sem resultado e modelo ausente/divergente impedem aprovação. Sem contador cumulativo, `last_token_usage` é contado por evento como no formato legado; não é possível deduzir duplicação de eventos idênticos sem identidade. Os validadores detectam inconsistências observáveis, não provam que o arquivo jamais foi editado ou que não existiu inferência sem registro. Integralidade declarada e retenção dos brutos são parte da auditoria.

Bytes de argumentos incluem tickets; bytes de resultados incluem retornos das ferramentas. São diagnósticos de transporte, **não o prompt inteiro nem substitutos de tokens nativos**. Volume narrativo conta mensagens finais; código e rodapés nelas podem influenciar essa aproximação e exigem revisão.

A comparação exige seis cenários e o mesmo conjunto de repetições. Nenhum critério fica sem avaliação; a candidata satisfaz todos. A soma de entrada e saída de todos os episódios não pode aumentar. Quando cache existe nos dois lados, entrada não-cache mais saída também não aumenta. Cobertura assimétrica de cache impede comparação; ausência nos dois mantém `null`, sem alegação de economia de cache.

Cada episódio deve ter entre 80% e 125% do volume de palavras da baseline: trava de comparabilidade, não meta de concisão nem prova de qualidade. P95 por episódio é diagnóstico sem esconder outliers na média. Falta de dado é `INCONCLUSIVO` (exit 2), falha avaliada é `REPROVADO` (exit 1), aprovação é exit 0. `coletar` apenas produz medição; exit 0 de coleta/sonda **não** aprova economia.

## Baseline inicial e validação

A baseline NV-02 registra sondas sobre componentes pós-NV-01, com hashes dos fontes e catálogo. É fotografia histórica do instrumento, não de valores vivos da campanha. Tokens nativos e qualidade narrada permanecem não medidos nessa fotografia. A primeira baseline narrada exige rollouts reais destes roteiros; a baseline de agosto não representa essa execução nova.

Testes cobrem contagem integral com fronteiras, contadores parciais, duplicações, evidência inválida, amostra não pareada, modelo/seed divergentes, redução artificial de prosa, falsa economia em bytes, isolamento e integração real. A suíte integral e Preflight permanecem gates de merge; qualidade narrada é critério das melhorias posteriores.
