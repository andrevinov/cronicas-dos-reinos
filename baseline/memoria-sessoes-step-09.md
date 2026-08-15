# Etapa 9 — baseline de memória fria de sessões

A Etapa 9 transforma transcrições em **arquivo frio para leitura**, sem deixar de preservá-las como registro integral e destino append-only da narração.

## Situação herdada

Na entrada da Etapa 9, as três transcrições existentes somam aproximadamente **1,19 MB**:

- sessão 001: 503.764 bytes;
- sessão 002: 339.372 bytes;
- sessão 003: 349.892 bytes.

A sessão 003 também preserva um padrão legado explícito de continuação técnica em que um trecho da sessão 002 foi copiado para o início da nova transcrição. Esse material histórico não é reescrito pela refatoração, mas o padrão fica proibido para novas sessões.

## Novo contrato

- `sessoes/index.yaml` é o índice pequeno de memória de sessões;
- `sessoes/NNN/handoff.yaml` é o checkpoint compacto de retomada;
- `contexto.py retomada` é a porta normal de reentrada em uma cena/sessão;
- `contexto.py sessao N` consulta memória compacta sem abrir a transcrição;
- `buscar --historico` continua em material histórico estruturado;
- transcrição só entra com `buscar --historico --transcricoes`;
- runtime deixa de oferecer a transcrição como ponteiro normal de consulta;
- consolidação de cena/sessão atualiza handoff e índice no mesmo lote atômico;
- novas sessões não copiam o trecho final da anterior;
- blocos mecânicos completos não devem ser repetidos se nada relevante mudou.

## Metas operacionais

- `contexto.py retomada` <= 8 KiB;
- `contexto.py sessao N` <= 8 KiB;
- nenhuma fonte `transcricao.md` em busca histórica sem `--transcricoes`;
- zero leitura automática de transcrição para criar handoff;
- handoff <= 8 KiB;
- índice de sessões muito menor que a soma das transcrições;
- sessão 004+ falha no CI se copiar bloco da sessão anterior;
- o registro integral antigo permanece intacto.

## O que medir no próximo rollout

Além dos indicadores das Etapas 7 e 8, observar:

- quantidade de chamadas que abrem `sessoes/*/transcricao.md`;
- proporção de retomadas resolvidas por `retomada`/`sessao`;
- bytes de saída dessas consultas;
- ocorrências de busca `--transcricoes` por sessão;
- repetição de blocos de PV/CA/Ki/dinheiro/hora sem mudança correspondente;
- tamanho incremental da transcrição por avanço narrativo.

O objetivo é que transcrições continuem crescendo como arquivo histórico, mas deixem de crescer **dentro do prompt** salvo quando uma pergunta realmente exigir evidência bruta.
