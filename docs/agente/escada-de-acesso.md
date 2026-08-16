# Escada formal de acesso e limites de leitura

Este documento define a política executável de leitura da campanha. O objetivo não é fazer o agente percorrer mais etapas: é **evitar leituras sem lacuna concreta e evitar ciclos modelo → ferramenta → modelo que não acrescentam informação útil**.

A implementação mecânica vive em `ferramentas/politica_acesso.py` e é aplicada pela porta pública `ferramentas/contexto.py`.

## Princípio zero

**L0 sempre vem primeiro.** Antes de qualquer ferramenta, usar o que já está no contexto da conversa. Se isso basta para narrar ou responder com segurança, não chamar ferramenta alguma.

A escada não é uma checklist obrigatória. Quando o alvo já é conhecido, uma consulta dirigida pode saltar um nível intermediário para economizar round-trips. O que é proibido é escalar para material amplo/frio “só para conferir”.

Exemplo correto: a pergunta cita explicitamente Kethra. Pode ir direto a `contexto.py relacao kethra` em L2 sem antes chamar `status`.

Exemplo correto: a pergunta pede algo especificamente da sessão 002. `contexto.py sessao 2` pode saltar a busca ampla L3, mas deve declarar que L2 foi insuficiente e dizer qual lacuna histórica precisa responder.

Exemplo incorreto: abrir `buscar --historico` depois de uma resposta L2 suficiente apenas para confirmar que nada foi esquecido.

## Níveis

### L0 — contexto já presente

Nenhuma leitura e nenhum tool call. É o nível preferido para continuação imediata de uma cena quando o contexto atual já contém tudo que a decisão exige.

### L1 — estado quente mínimo

Comando normal:

```bash
python3 ferramentas/contexto.py status
```

Teto mecânico de saída: **4 KiB**.

Use quando falta estado corrente essencial: recursos, hora, localização ou sessão. Pare se isso resolver a lacuna.

### L2 — consulta dirigida

Comandos:

```bash
python3 ferramentas/contexto.py cena
python3 ferramentas/contexto.py retomada
python3 ferramentas/contexto.py npc kethra
python3 ferramentas/contexto.py relacao jack
python3 ferramentas/contexto.py conhecimento masao
python3 ferramentas/contexto.py regra furtividade
python3 ferramentas/contexto.py sessao atual
```

Teto mecânico: **8 KiB**.

L2 é o nível normal da narração quando L0 não basta. Índice + fragmento específico é preferível a busca ampla.

### L3 — descoberta limitada

Comando:

```bash
python3 ferramentas/contexto.py buscar "ponte baixa" \
  --apos L2 \
  --motivo "As consultas dirigidas não localizaram em qual domínio a pista está registrada."
```

Teto mecânico: **8 KiB**.

L3 exige `--apos L2` e `--motivo`. O motivo descreve a informação concreta que faltou. Frases como “só conferir” ou “por precaução” são recusadas.

Busca reservada usa a mesma disciplina e também exige motivo:

```bash
python3 ferramentas/contexto.py buscar "pressão de Masao" \
  --reservado --apos L2 \
  --motivo "A decisão do antagonista depende de agenda reservada não presente na cena atual."
```

### L4 — histórico estruturado

Busca histórica ampla:

```bash
python3 ferramentas/contexto.py buscar "homem de mãos limpas" \
  --historico --apos L3 \
  --motivo "A busca corrente encontrou o nome, mas não a origem histórica necessária para continuidade."
```

Teto mecânico: **12 KiB**.

L4 consulta handoffs, resumos, alterações, consequências e históricos específicos. Ainda não abre transcrições.

#### Salto dirigido para alvo histórico conhecido

Se a pergunta já identifica uma sessão histórica, não faz sentido pagar uma busca L3 apenas para chegar a ela:

```bash
python3 ferramentas/contexto.py sessao 2 \
  --apos L2 \
  --motivo "A pergunta aponta diretamente para a sessão 002 e exige seu resumo consolidado."
```

Esse é um **salto dirigido L2 → L4** permitido pela política. Ele reduz round-trips em vez de enfraquecer a escada.

### L4T — transcrição fria

Última escalada local:

```bash
python3 ferramentas/contexto.py buscar "carroça-escritório cheira" \
  --historico --transcricoes --apos L4 \
  --motivo "O histórico estruturado não contém a formulação exata necessária para resolver a continuidade."
```

Teto mecânico: **16 KiB**.

`--transcricoes` exige `--historico`, `--apos L4` e motivo. Mesmo nesse nível, a ferramenta devolve somente ocorrências limitadas; não despeja a transcrição inteira no prompt.

### L5 — fonte externa/autorizada

Não é comando de `contexto.py`. Significa consultar livro oficial, fonte externa autorizada ou pesquisa material-base. Só usar quando a lacuna for de regra/lore que o repositório não resolve.

A fonte externa também não deve ser aberta “para garantir”. Defina primeiro a pergunta concreta.

## Orçamentos são tetos, não metas

`--max-bytes` pode pedir menos que o teto do nível, nunca mais. Exemplos:

```bash
python3 ferramentas/contexto.py --max-bytes 2048 status
python3 ferramentas/contexto.py --max-bytes 4096 npc nera
```

Pedir `--max-bytes 16000 status` continua limitado a 4 KiB. Isso impede que uma chamada simples vire acidentalmente uma resposta enorme.

Tetos:

- L1: 4 KiB;
- L2: 8 KiB;
- L3: 8 KiB;
- L4: 12 KiB;
- L4T: 16 KiB.

## Declaração de escalada não cria tool call

`--apos` não prova que uma chamada anterior ocorreu e **não exige que ela ocorra**. Ele registra a decisão do agente: “o nível declarado não respondeu esta lacuna”. Isso é deliberado.

Obrigar fisicamente L1 → L2 → L3 → L4 em todas as perguntas recriaria o problema observado no rollout: muitos round-trips carregando novamente um contexto grande. A política combina duas metas:

1. impedir escalada especulativa;
2. não criar degraus artificiais quando o alvo já é conhecido.

## Metadados de parada

Toda saída de `contexto.py` recebe `controle_acesso` com:

- nível efetivo;
- teto de bytes aplicado;
- `pare_se_suficiente: true`;
- condição de parada daquele nível;
- próximo nível possível;
- declaração `--apos`, quando houver;
- motivo de escalada, quando houver.

A finalidade é fazer a própria resposta da ferramenta lembrar ao agente que uma consulta bem-sucedida deve encerrar a busca.

## Critérios práticos para escalar

Escalar somente quando for possível completar a frase:

> “Ainda preciso saber ______ para executar esta resposta corretamente, e o nível atual não contém isso.”

Boas lacunas: identidade de um NPC citado, valor atual de recurso, origem histórica de uma pista, texto exato de uma promessa, regra que decide uma rolagem.

Más justificativas: “para ter certeza”, “pode ser útil”, “só conferir”, “ler o contexto”, “ver se existe mais alguma coisa”.

## Relação com material reservado

`--reservado` é uma dimensão de visibilidade, não um nível próprio. Uma busca reservada continua obedecendo L3/L4/L4T e sempre exige motivo concreto. Conteúdo reservado não deve aparecer como conhecimento de Ren sem descoberta legítima.

## Testes permanentes

`tests/test_politica_acesso.py` e o CI verificam:

- classificação dos comandos;
- escalada L3, L4 e L4T;
- salto dirigido para sessão histórica conhecida;
- rejeição de motivo genérico;
- exigência de motivo para reservado;
- tetos de bytes por nível;
- presença da condição de parada nas respostas;
- rejeição CLI de buscas caras sem `--apos`/`--motivo`.

A meta de produção continua simples: **a maioria das interações deve morrer em L0–L2**. L3+ deve ser exceção explicável e mensurável.
