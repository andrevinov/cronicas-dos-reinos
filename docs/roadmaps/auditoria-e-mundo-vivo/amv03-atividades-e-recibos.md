# AMV-03 — Atividades e recibos com o mesmo contrato

**Data:** 2026-10-04. **Status:** concluída em 2026-10-04; G0 pendente.
**Dependências:** AMV-01–02.

## Entrega executada

`ferramentas/atividades_modulares.py` centraliza o contrato 1.0.0 de fases,
unidades, alvos, rotas e gatilhos condicionais. Emissor e detector o consomem.
As tabelas de fases primárias e o vínculo livre de fachadas do detector foram
substituídos por esse contrato. Fases desconhecidas continuam rejeitadas.
Detector atualizado para 4.8.0 e gerador para 4.6.0.

A expectativa vem da invocação, do ticket capturado ou do hook observado,
independentemente do recibo específico. `concluir_iniciativa`, permanência,
autoria e instalação/progresso de sidequests têm identidades próprias. Remover
o recibo de iniciativa, ou todo seu envelope, mantém a obrigação conhecida pelo
ticket. O recibo genérico de conclusão não a satisfaz.

Os envelopes conservam o formato compacto anterior e acrescentam versão do
contrato, fingerprint do pacote de emissão e vínculo com cena/ticket/interação
quando disponíveis. A versão do produtor identifica as fachadas e seu contrato
de emissão; os hashes individuais pertencem à proveniência. O binding final
usa o ticket externo, depois da composição de wrappers. A permanência passa
pela fachada existente e expõe seu recibo, preservando o mesmo motor e reserva.

Ausência, incompletude, duplicação, contradição e orfandade são diagnósticos
distintos. Ticket, objeto ou interação divergentes não cobrem uma atividade.
Um órfão com zero atividades gera falha de instrumentação e fila de reparo,
sem invalidar arbitrariamente uma linha independente de outro módulo.
Negativas operacionais têm causa e escopo no contrato versionado, com override
explícito quando necessário. Elas descrevem o hook examinado; não provam que
não havia oportunidade narrativa no mundo.

O ledger diferencia a ocorrência na operação da identidade lógica vinculada ao
ticket. Retry/recovery preservam esta última, indicam reutilização e não passam
a representar dois efeitos. Passagens e fases continuam unidades de cobertura,
nunca unidades de qualidade ou de efeito persistente.

Metadados foram compactados para preservar o teto de saída ON e os fatos de
memória. A seleção contabiliza os metadados novos; a compensação histórica da
cobertura considera somente os recibos compactos anteriores. Os testes de
promessas, rumores, diálogo e retomada continuam passando.

## Evidência obtida

- [Observação do gabarito congelado](../../../evaluation/aceite-avaliacao-v1/resultado-amv03.json):
  as três verificações da AMV-03 passaram. São **14 de 17 checks** aprovados;
  as divergências caíram de seis para três, previstas para AMV-04–05.
  O controle de fase inventada continua reprovando a cobertura indevida.
- [Reanálise de atividades da 024](../../../evaluation/aceite-avaliacao-v1/atividades-s024-amv03.json):
  **131 passagens associadas, zero órfãos**, incluindo duas conclusões de
  iniciativa. O corte histórico e suas sete âncoras foram conferidos. As
  contagens operacionais da AMV-02, chamadas e tokens nativos foram preservados.
- [Verificação da entrega](../../../evaluation/aceite-avaliacao-v1/verificacao-amv03.json):
  **321 testes focados passaram**, em 7,665 segundos; as **226 comparações** do
  corpus anterior passaram. Save, manifesto e expectativas permanecem intactos.

Para repetir a reanálise sem publicar o bruto, usando a fonte local identificada
no gabarito e um arquivo de resultado novo:

```sh
poetry run python ferramentas/verificar_aceite_avaliacao.py \
  --reavaliar-atividades --fonte /caminho/para/rollout.jsonl \
  --saida /tmp/atividades-024-nova-observacao.json
```

## Limites e próxima etapa

Associação completa **não aprova a experiência nem o resultado terminal**.
Na 024, oito passagens pertencem a operações com evidência terminal insuficiente;
esse estado foi preservado. Uma invocação sem retorno ou confirmação de chegada
à fachada permanece no ledger operacional, sem fabricar uma passagem realizada.

Recibos históricos sem metadados novos continuam legíveis. Subfase publicada
na operação correta pode ser associada por compatibilidade, com origem explícita;
sem ticket/gatilho independente, não é possível provar retroativamente sua
omissão. Versões, causas e vínculos ausentes no histórico não são preenchidos
com o estado atual. As duas iniciativas da 024 têm gatilho independente no ticket.

Restam no gabarito a oportunidade narrativa omitida (AMV-04) e duas verificações
da apresentação de medição bloqueada (AMV-05). A sessão 024 não precisa ser
jogada novamente; a apresentação completa será regenerada na AMV-05.
Esta tarefa não reescreveu seu pacote histórico, aposentou gates nem executou
a suíte integral/preflight de merge. A última suíte integral registrada na
AMV-01 tem cinco casos preexistentes em falha. G0 continua pendente.

## O que implementar

Definir, nas fachadas existentes, contratos versionados de atividade e fases:
preparação, conclusão, permanência, fronteira, lifecycle e subfases legítimas,
incluindo `concluir_iniciativa`. Registrar qual operação produz cada atividade,
sua unidade, alvo quando houver e as condições de aplicabilidade.

Fazer produtor e detector usarem esse contrato. Associar recibos por operação,
atividade, fase e objeto, admitindo subatividades realmente produzidas pela mesma
operação. Um recibo genérico não comprova automaticamente todos os efeitos de
uma subfase. A atividade esperada não pode depender apenas da existência do
próprio recibo: invocação e gatilhos observados continuam fontes independentes.

Representar separadamente recibo ausente, incompleto, duplicado, contraditório e
órfão. Recibo órfão com zero atividades reconhecidas é falha de associação, não
ausência tranquila de atividade. Negativa válida registra causa e escopo examinado.

Preservar vínculo com ticket, interação e versão efetivamente executada. Recibos
duplicados por retry idempotente não devem ser confundidos com dois efeitos.

## Por que corrige a causa

O detector atual não conhece uma fase que seu próprio produtor emite. Um contrato
compartilhado elimina a divergência de sintaxe e unidade. A confirmação continua
dependendo do que realmente aconteceu; aceitar toda fase ou desligar a detecção
de órfãos esconderia integrações quebradas.

## Prova de correção e aceite

- Conclusão com os recibos genéricos e uma iniciativa legítima fica completamente
  associada, sem órfão falso nem dupla contagem.
- Remover o recibo da subatividade realmente executada gera falta detectável.
- Adicionar fase inventada, objeto errado ou recibo de outro ticket reprova.
- Módulo com recibo órfão e nenhuma atividade reconhecida aparece com erro de
  instrumentação, incluindo diagnóstico de associação.
- Retry, resultado fragmentado e recovery preservam a mesma identidade lógica.
- Cobertura parcial ou ausente bloqueia apenas as conclusões que exigem aquela
  prova, sem produzir uma nota saudável por exclusão silenciosa.

## Onde mudar e o que poderá sair

Contratos e emissão nas fachadas, ledger de atividade e geração de avaliação.
A tabela paralela de expectativas de fase do detector foi substituída pelo
contrato compartilhado nesta entrega. Adaptadores de leitura histórica continuam
necessários. Regressões de ausência, duplicação e órfãos continuam ativas,
incluindo os casos que antes tinham falso positivo. Nenhum check do preflight
foi removido ou desabilitado.
