# Reprodutibilidade e conclusão do pacote de avaliação

A atividade 9 liga a entrada congelada ao gerador 4.4.0. Uma execução apta a
sustentar conclusão depende de uma identidade única: rollout até o corte,
fontes, contratos, código e ambiente. O mesmo `entrada_id` precisa produzir o
mesmo conjunto de arquivos e os mesmos bytes em diretórios vazios distintos.

## Ordem fail-closed

Antes de executar o analisador, o gerador:

1. valida o schema, a identidade e todos os hashes internos da entrada;
2. exige que a sessão solicitada seja a sessão congelada;
3. compara cada hash de código declarado com o arquivo corrente e exige os
   cinco componentes críticos do avaliador;
4. compara as versões de Python e PyYAML;
5. lê exatamente o prefixo do rollout e confirma seu SHA-256;
6. valida a forma semântica das interações, adjudicações e validade congeladas.

Qualquer divergência termina sem criar o diretório de saída. Formato nativo
desconhecido, JSON inválido e snapshot alterado seguem a mesma regra.

Após essa barreira, o gerador materializa o prefixo em arquivo temporário de
nome fixo e fornece ao analisador o catálogo embutido. Interações em JSONL são
materializadas a partir dos registros congelados. Ausências opcionais produzem
defaults vazios e continuam registradas como limitações; não autorizam uma
leitura implícita do estado vivo ou de um pacote já existente.

## Proveniência publicada

`proveniencia-medicao.json`, schema 1, registra `entrada_id`, corte e hash da
fonte, hashes dos snapshots, contratos locais, código e ambiente. O manifesto
aponta esse artefato e resume se a conclusão reproduzível é permitida. O
conteúdo dos snapshots não é duplicado no pacote.

O modo direto permanece disponível para compatibilidade. Ele publica
`modo: direto_nao_congelado`, `conclusao_reprodutivel_permitida: false` e o
bloqueio `entrada_nao_congelada`. Assim, uma execução antiga pode ser
inspecionada sem ser apresentada como reprodução certificada.

## Gate de conclusão

`scorecard.conclusao_medicao` separa fatos observados da autorização para tirar
uma conclusão. A conclusão fica bloqueada quando houver:

- correlação ambígua entre operação e resultado;
- resultado de operação ausente;
- evidência terminal insuficiente;
- erro de invariante do detector;
- falha de instrumentação modular;
- execução sem entrada congelada.

Falha operacional observada continua sendo um resultado do domínio e não vira
automaticamente falha do medidor. Uma nota parcial pode permanecer no pacote
para diagnóstico, mas o gate declara que ela não sustenta conclusão dependente.

Os schemas publicados são `proveniencia-medicao-v1.schema.json` e
`conclusao-medicao-v1.schema.json`. A aceitação técnica gera duas vezes a mesma
entrada em diretórios novos, altera as fontes externas depois do congelamento e
compara byte a byte todos os artefatos. A validação externa em rollout real
permanece na atividade 10.
