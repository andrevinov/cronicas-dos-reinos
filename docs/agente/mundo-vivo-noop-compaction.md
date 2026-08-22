# Mundo Vivo — no-op compaction

A Task 9 reduz reavaliações narrativas repetidas de **agentes leves** quando a última avaliação explícita concluiu que a rotina continuou sem mudança extraordinária.

O cache é uma otimização operacional reservada. Ele não é fato canônico, não afirma que nada aconteceu no mundo e não substitui evidência nova. Seu significado é estrito: **as fontes canônicas que o próprio perfil leve permite usar continuam byte a byte iguais desde o último no-op explícito**.

## Fluxo

Quando o checkpoint produzir `reavaliar_agente_leve`, consultar somente o agente indicado:

```bash
python3 ferramentas/agentes_leves.py mostrar <id-ou-nome>
```

Se houver causa concreta para iniciativa extraordinária, resolver/canonizar normalmente e concluir a pendência pela porta existente do Mundo Vivo.

Se a avaliação concluir que a rotina continua e nenhuma mudança persistente deve ser criada, usar:

```bash
python3 ferramentas/agentes_leves.py concluir-noop <pendencia-id> \
  --nota "nenhuma mudança extraordinária"
```

`concluir-noop` grava primeiro o cache negativo no estado reservado dos agentes leves e depois remove a pendência do Mundo Vivo. Se houver queda entre as duas escritas, a pendência continua bloqueando o avanço; repetir o comando termina a operação sem duplicar conclusão.

## Assinatura causal

Cada agente do schema 2 declara no índice compacto:

- `fontes_causais`: no máximo duas fontes pequenas sob `estado/relacoes/`;
- `perfil_blob_git`: identidade byte a byte do fragmento operacional versionado.

A validação de CI exige que `fontes_causais` coincidam exatamente com `fontes_canonicas` do perfil. Assim o cache não pode omitir uma fonte que o próprio perfil usa para justificar objetivo ou iniciativa.

Em runtime, o hash é calculado sem abrir o fragmento narrativo: lê somente o índice já necessário e as fontes causais compactas. O hash inclui também a versão declarada do perfil.

## Cadência posterior

Quando o mesmo agente vencer novamente:

1. sem cache → comportamento anterior: cria a pendência normal e não lê fonte causal;
2. cache + assinatura diferente → limpa o cache e cria a pendência normal;
3. cache + assinatura idêntica → não cria pendência, não abre perfil e apenas avança `proxima_avaliacao`.

Hits repetidos não criam uma linha de histórico por cadência. O mesmo registro de cache mantém apenas `acertos_compactados` e `ultima_compactacao`, evitando crescimento linear do estado.

## Limites

A otimização é deliberadamente estreita:

- somente agentes leves;
- máximo 1 check de cache negativo por checkpoint;
- máximo 2 fontes causais por agente;
- máximo 32 KiB por fonte causal;
- 0 fragmentos narrativos em cache hit;
- 0 scheduler novo;
- 1 escrita no cache hit;
- no máximo 2 escritas em `concluir-noop`.

Direções, eventos mundiais, agentes estratégicos, relógios, entradas de aliados e outras pendências continuam usando seus próprios contratos. Um no-op de Silva, por exemplo, nunca silencia uma direção canônica ou uma pressão do Mundo Vivo.

## Migração

O estado real começa com `cache_negativo: null` para todos os agentes. Nenhum no-op é inferido retroativamente de sessões antigas. O cache só nasce depois de uma decisão explícita registrada por `concluir-noop`.

O schema 1 permanece aceito para fixtures/compatibilidade e simplesmente opera sem cache. O repositório vivo usa schema 2.

Contrato de regressão: `baseline/mundo-vivo-noop-orcamento.yaml`.
