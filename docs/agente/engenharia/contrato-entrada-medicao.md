# Contrato de entrada e unidades de medição

Atividade 1 do reparo do instrumento de avaliação, integrada ao gerador pela
atividade 9: contrato `1.0.0`, schema de entrada `1`. A porta executável prepara
e valida a entrada da medição pós-hoc. Ela não executa operações do rollout nem
altera campanha, ledger ou pacotes anteriores.

`status: valida` certifica o envelope, a integridade das fontes e as unidades
declaradas; não certifica o desempenho da sessão. O gerador 4.4.0 usa esse
documento como autoridade única, volta a validar todos os hashes e o ambiente
antes da análise e publica a decisão separada em `conclusao_medicao`.

## Preparar e verificar

```bash
poetry run python ferramentas/entrada_medicao.py preparar \
  /caminho/rollout.jsonl --sessao-id 023 \
  --saida /tmp/entrada-s023.json

poetry run python ferramentas/entrada_medicao.py validar \
  /tmp/entrada-s023.json --rollout /caminho/rollout.jsonl

poetry run python ferramentas/gerar-avaliacao-sessao.py \
  /caminho/rollout.jsonl --sessao-id 023 \
  --entrada-medicao /tmp/entrada-s023.json
```

Sem corte explícito, o preparo captura o tamanho disponível ao abrir o arquivo.
O corte deve terminar em registros JSON completos. Para selecionar o mesmo
prefixo de um rollout que continuou crescendo, fornecer `--corte-bytes N` e,
quando conhecido, `--sha256-esperado HASH`. A verificação lê exatamente esse
prefixo; acréscimos posteriores não mudam a entrada e alterações dentro dele
falham. O arquivo bruto deve continuar disponível: seu conteúdo não é copiado
para a entrada.

O identificador `entrada_id` é SHA-256 do documento completo, exceto o próprio
identificador, em JSON canônico UTF-8 com chaves ordenadas. O hash do rollout é
calculado sobre os bytes originais do prefixo; hashes de snapshots são calculados
sobre seu conteúdo JSON canônico. Não se incluem relógio do preparo ou caminhos
absolutos no identificador. Mesmas fontes, corte, contratos, código e ambiente
produzem os mesmos bytes de entrada. Uma saída existente com conteúdo diferente
não é sobrescrita: selecionar outro arquivo preserva a entrada anterior.

## Fontes e versões

São congelados os nove componentes:

| Componente | Seleção padrão | Ausência |
| --- | --- | --- |
| `catalogo` | `evaluation/catalogo-modulos-v2.json` | Bloqueia |
| `metas` | `evaluation/metas-avaliacao-v2.json` | Bloqueia |
| `baseline` | `baseline/rollout-2026-08-15.json` | Bloqueia |
| `guardrails` | `evaluation/catalogo-guardrails-v2.json` | Limitação |
| `series` | `evaluation/series-avaliacao.json` | Limitação |
| `releases` | `evaluation/module-releases.json` | Limitação |
| `interacoes` | Somente `--interacoes` | Limitação |
| `adjudicacoes` | Somente `--adjudicacoes` | Limitação |
| `validade` | Somente `--validade` | Limitação |

Cada componente aceita a opção de mesmo nome para selecionar uma fonte JSON ou
JSONL. Por exemplo, `--interacoes sessoes/023/interacoes.jsonl` seleciona o ledger
explicitamente. Não há busca implícita pelo ledger, estado vivo ou adjudicações
de um pacote anterior. Ausência permanece `estado: ausente`, com conteúdo e hash
nulos e diagnóstico. Fonte selecionada ilegível ou malformada bloqueia; não é
tratada como ausência opcional.

O contrato comum e os contratos locais também são embutidos. O catálogo congela
as versões de implementação e avaliação **selecionadas para a medição**; isso
não comprova qual implementação rodou historicamente. São registrados hashes
dos arquivos Python de `ferramentas/`, `pyproject.toml` e `poetry.lock`, além das
versões de Python e PyYAML. Hashes identificam o código, mas não o arquivam.
Na geração, cada caminho de código precisa continuar dentro do repositório e
seu conteúdo deve corresponder ao hash. Os cinco componentes críticos do
avaliador precisam estar declarados. Python e PyYAML também precisam conservar
as versões congeladas. Divergência falha antes de criar o diretório do pacote.

No modo `--entrada-medicao`, não se pode fornecer catálogo, metas, baseline,
interações, adjudicações ou validade em paralelo. Os snapshots embutidos são a
única autoridade. O gerador não relê o ledger vivo, um pacote anterior ou os
arquivos originais desses snapshots. Somente o rollout bruto continua externo,
e apenas o prefixo de bytes cujo hash foi congelado é lido.

## Unidades independentes

| Unidade | Significado |
| --- | --- |
| Inferência | Inferência com uso de tokens observado |
| Chamada de ferramenta | Chamada nativa identificada por `call_id` |
| Operação executada | Invocação e resultado próprios dentro da chamada |
| Turno de conversa | Turno do host/LLM identificado por `turn_id` |
| Interação | Par jogador–resposta com identidade no ledger |
| Atividade modular | Passagem de domínio por operação, módulo, fase e objeto |
| Evento modular | Sinal agregado para diagnóstico |
| Recibo modular | Declaração estruturada vinculada à atividade |
| Oportunidade | Caso com evidência de elegibilidade independente da ativação |
| Efeito modular | Resultado material confirmado com identidade causal |

As outras unidades são fato de memória, cena, janela, fronteira, sessão, módulo
e manifestação. Suas definições e campos de identidade constam de
`evaluation/contrato-medicao.json`. Identidade ausente fica indeterminada; ordinal
do host não substitui identidade canônica. Um envelope concluído não prova que
todas as operações internas tiveram sucesso. Evento detectado não prova
oportunidade, recibo estrutural não comprova qualidade semântica e manifestação
pendente não comprova falha.

Cada indicador declara unidade avaliativa, medida, origem da evidência,
denominador e tratamento da ausência. Razões, proporções e notas exigem
denominador explícito. Ausência não vira zero, sucesso ou inaplicabilidade.
N/A exige evidência própria. Custos atribuídos são identificados como rateio;
latência exposta não é custo causal.

## Contratos locais e validação

O contrato comum contém 20 indicadores globais e 32 compartilhados. Os 61
indicadores especializados atuais ficam em
`evaluation/contratos-modulos/<module_id>.json`. O núcleo consulta o catálogo
selecionado, sem impor uma quantidade fixa de módulos, e exige correspondência
exata dos IDs e medidas dos indicadores de cada módulo.

Uma mudança de versão ou critério local altera o `entrada_id` completo. A API
`module_contract_id(entrada, module_id)` identifica apenas contrato comum,
entrada do próprio módulo no catálogo e contrato local. Os testes verificam
que uma alteração em `alpha` preserva essa assinatura em `beta`. Essa assinatura
é de contrato; não promete invariância de resultados ou custos agregados.

Schemas publicados em `evaluation/schemas/`: `contrato-medicao.schema.json`,
`contrato-modulo-medicao.schema.json` e `entrada-medicao.schema.json`. O validador
Python faz também as verificações semânticas de hashes, unidades, catálogo e
status, sem adicionar dependências.

O perfil inicial é `codex_jsonl_v1`, com os tipos de registros declarados no
contrato e saídas em texto ou lista de blocos. Tipo desconhecido ou JSON inválido
gera diagnóstico com linha e bloqueia a entrada. Conteúdo de comandos e recibos
não é interpretado nesta etapa. O comando retorna `0` para entrada válida ou
limitada e `1` para bloqueada; limitações ficam sempre na saída. Os testes estão
em `tests/test_entrada_medicao.py` e
`tests/test_integracao_entrada_medicao.py`, com cenários temporários isolados.

O contrato de reprodução do pacote, a proveniência publicada e os bloqueios de
conclusão estão em
[reprodutibilidade do pacote](reprodutibilidade-pacote-avaliacao.md).
