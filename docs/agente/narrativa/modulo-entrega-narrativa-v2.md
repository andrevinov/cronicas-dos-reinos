# Módulo de entrega narrativa v2

`narrative_delivery` é o dono da resposta visível ao jogador. Ele reúne
densidade narrativa, mecânica diegética e fechamento visível, mas não recebe
autoridade para decidir a ficção, escolher por Ren ou alterar uma resolução.

## Porta operacional

O módulo não acrescenta uma terceira chamada ao turno. Depois de o writer do
`cronica concluir` aceitar a transação, a fachada
`ferramentas/narrative_delivery.py` observa `narracao`, o recibo transacional e
o rodapé já produzido. O mesmo output recebe `entrega_narrativa`, com:

- `entrega_id` determinístico para a prosa registrada;
- correlação com ticket, transação e sessão;
- classe e medidas estruturais da resposta;
- presença do rodapé esperado;
- auditoria semântica e nota do jogador explicitamente N/D;
- guardrails críticos separados e não compensáveis.

Retry do mesmo concluir preserva o identificador e publica
`replay_sem_nova_persistencia`. A fachada faz cópia do resultado, não escreve
estado canônico, não reescreve prosa e não executa telemetria no hot path.

## Três camadas de evidência

### Estrutural automática

O analisador pós-hoc correlaciona o recibo com a última mensagem `final`, mede
tamanho, parágrafos, linhas `MECÂNICA —`, posição do `RODAPE_CANONICO`, latência
quando o rollout fornece timestamps e sinais explícitos de retrabalho no turno
seguinte. Essas medidas descrevem a entrega; resposta curta ou longa não recebe
nota automática.

### Auditoria semântica

Um auditor avalia, com evidência, `progressao_jogavel`,
`densidade_proporcional`, `voz_e_dialogo`, `camadas_de_conhecimento` e
`conclusao_aberta`. Os estados são `adequado`, `inadequado`, `indeterminado` ou
`nao_aplicavel`. Nenhuma busca por palavras-chave substitui essa leitura.

Agência do jogador, sigilo das camadas de conhecimento e integridade da rolagem
são registrados à parte como `ok`, `violado`, `indeterminado` ou
`nao_aplicavel`. Uma boa nota perceptiva não compensa uma violação.

### Percepção do jogador

O jogador pode atribuir notas de 1 a 5 para `ritmo`, `naturalidade`,
`profundidade` e `agencia_percebida`, deixando dimensões sem opinião como
`null`. Se não houver nenhuma nota, o bloco deve ser omitido e permanece N/D.
Essa percepção tem papel limitado na agregação posterior e não muda guardrails.

## Adjudicação pós-hoc

`ferramentas/analisar-rollout.py --adjudicacoes-modulares <arquivo.json>` aceita
os blocos opcionais `semantic_audits` e `player_feedback` no mesmo contrato das
correções manuais. Cada item aponta para o `event_id` de uma entrega narrativa.
O formato autoritativo está em
`evaluation/schemas/adjudicacoes-ledger-v2.schema.json`; o ledger resultante
preserva essas camadas em listas separadas.

Até a RM-11, isso produz evidência comparável, não um score de produção. A série
`legacy-v1` continua vigente e a sessão 021 permanece histórica.

## Verificação

```bash
poetry run python ferramentas/narrative_delivery.py check
poetry run test-domain narrativa
poetry run test-full
poetry run preflight
```
