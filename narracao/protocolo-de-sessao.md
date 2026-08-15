# Protocolo de sessão

Este protocolo define como iniciar, narrar, registrar, consolidar, pausar e encerrar sessões de **Crônicas dos Reinos**.

Estilo: `narracao/guia-de-narrativa.md`. Limites: `narracao/limites.md`. Acesso: `docs/agente/acesso-e-operacoes.md`. Consolidação: `docs/agente/consolidacao-transacional.md`.

---

## Estrutura de diretórios

Cada sessão possui pasta própria:

```text
sessoes/001/
├── transcricao.md
├── resumo.md
├── alteracoes-de-estado.yaml
├── experiencia.md
├── consequencias.md
└── imagens/
```

`transcricao.md` é o registro completo da alternância entre jogador e narrador. Durante a sessão ativa, mudanças posteriores ao último checkpoint ficam em:

```text
runtime/eventos-pendentes.jsonl
```

Depois de consolidadas, as transações passam também pelo ledger:

```text
sessoes/NNN/consolidacoes.jsonl
```

---

## Cabeçalho e abertura

O cabeçalho da transcrição é snapshot inicial; não deve ser reescrito a cada mudança. A abertura deve conter recap curto, localização, situação imediata, elementos perceptíveis relevantes, NPCs/ameaças, estado crítico quando necessário e uma deixa clara para Ren agir.

Não copiar a sessão anterior nem carregar material reservado preventivamente.

---

## Alternância

Formato:

```markdown
**Narrador**

...

**Jogador**

...
```

O jogador controla o que Ren faz, diz, tenta, pensa ou sente. O narrador resolve mundo, NPCs, regras, rolagens e consequências.

Antes de publicar: NPCs devem soar como pessoas do mundo; mecânica fica fora da voz do NPC; segredos não aparecem como certeza pública; a resposta devolve uma situação jogável.

---

## Loop transacional de narração

Uma interação comum segue:

```text
ação do jogador
→ usar contexto já presente
→ consultar somente a lacuna necessária
→ resolver rolagens
→ produzir narração
→ registrar transação
→ devolver controle ao jogador
```

Persistir com uma única chamada:

```bash
python3 ferramentas/turno.py registrar <<'JSON'
{
  "jogador": "Ren ...",
  "narracao": "...",
  "resumo": "Resumo curto do que mudou.",
  "modo": "combate",
  "deltas": []
}
JSON
```

O registrador escreve somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

A prosa completa fica só na transcrição. O JSONL guarda ID, sessão, resumo, deltas e eventualmente rolagens ocultas.

### Proibição de write amplification

Durante cada troca normal não atualizar também estado, tempo, ficha, relações, NPCs, conhecimento, consequências, relógios, resumos ou logs reservados. Esses destinos são consolidados em lote.

Também não rodar por rotina, a cada ação, `git status`, `git diff`, testes globais, regeneração de runtime ou commit.

---

## Deltas mínimos

Um delta registra somente o que mudou e precisa sobreviver à próxima interação.

```json
{"alvo":"estado","op":"inc","caminho":"recursos.pontos_de_vida.atuais","valor":-6}
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"estado","op":"set","caminho":"localizacao.ponto_exato","valor":"junto à cerca"}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04"}
{"alvo":"relacao:kethra_dunn","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
{"alvo":"consequencia","op":"registrar","valor":{"titulo":"Dívida aberta","descricao":"Pode voltar a importar."}}
```

Operações: `set`, `inc`, `append`, `remove`, `registrar`.

Se nada persistente mudou, `deltas` pode ser vazio. Descrição sensorial ou fala trivial não precisa virar estado estruturado.

`contexto.py` aplica os deltas sobre o snapshot-base até a consolidação.

---

## Idempotência do turno

Cada transação recebe ID estável e marcador interno na transcrição. Repetir a mesma entrada não duplica registros. Se houver queda entre as duas escritas, repetir a chamada repara somente o lado ausente.

```bash
python3 ferramentas/turno.py check
```

Enquanto não houver consolidação em andamento, transcrição + buffer + snapshot-base bastam para uma retomada segura.

---

## Tamanho, modos e ritmo

Entrada típica do jogador: uma frase a um parágrafo. Entrada típica do narrador: duas frases a três parágrafos. Usar entradas maiores em abertura, descoberta importante, resolução de combate, transição ou consequência substancial.

Não repetir PV, CA, Ki, dinheiro, hora e localização em toda resposta se nada relevante mudou.

Modos principais: interação, exploração e combate. Registrar mudança de modo apenas quando ela ocorrer de verdade.

### Interação

Foco em diálogo, postura, descoberta e relações. Acompanhar informação revelada, mentira/omissão, promessas, dívidas e mudanças significativas.

### Exploração

Foco em posição, luz, ruído, ferramentas, saídas, tempo gasto, riscos e rota de volta.

### Combate

Surpresa se houver → iniciativa → posição → ação de Ren → rolagens/consequências → próximo turno. Manter claros os elementos táticos relevantes sem repetir blocos inalterados.

---

## Rolagens

Para rolagens visíveis, usar `ferramentas/rolar-dados.py`. Quando duas ou mais rolagens independentes já forem necessárias, usar uma chamada a `ferramentas/rolar-lote.py`. Não antecipar rolagens condicionais.

Rolagens ocultas relevantes ficam no campo `rolagens_ocultas` da transação. Isso evita uma terceira escrita durante o turno. Na consolidação elas são transferidas em lote para:

```text
narrador/sessoes/NNN/rolagens-ocultas.md
```

---

## Material reservado, dungeons, cidades e imagens

Material reservado necessário fica em `narrador/sessoes/NNN/`; não carregar a pasta inteira sem lacuna concreta.

Em dungeon, preservar topologia e segredos, revelando apenas o percebido. Em cidade, abstrair deslocamento salvo perseguição, cauda, tempo crítico, perigo ou rota com consequência.

Imagens pedidas durante sessão ficam em `sessoes/NNN/imagens/` e são referenciadas na transcrição sem revelar elementos ainda não percebidos.

---

## Checkpoint de cena

Não consolidar por cronômetro nem depois de cada ação. Consolidar quando houver **fronteira de cena importante** e um checkpoint canônico for útil: fim de combate relevante, saída de local perigoso, descanso/transição forte, mudança clara de objetivo ou antes de uma pausa operacional longa.

```bash
python3 ferramentas/consolidar.py cena
```

O comando:

- valida o buffer;
- calcula todas as alterações em memória;
- prepara staging + journal;
- instala estado/ficha/tempo/entidades/conhecimento/artefatos afetados;
- instala o novo runtime;
- remove as transações aplicadas do buffer por último.

Depois de sucesso, a narração pode continuar normalmente. Não executar `gerar-runtime.py` novamente por rotina: o novo runtime já faz parte do mesmo lote.

---

## Encerramento de sessão

Antes de declarar a sessão encerrada:

```bash
python3 ferramentas/consolidar.py sessao
```

A consolidação de sessão aplica os deltas pendentes e mantém, conforme houver conteúdo real:

```text
sessoes/NNN/consolidacoes.jsonl
sessoes/NNN/resumo.md
sessoes/NNN/alteracoes-de-estado.yaml
sessoes/NNN/consequencias.md
sessoes/NNN/experiencia.md
```

Se já existir `alteracoes-de-estado.yaml` manual em formato incompatível com o gerado automaticamente, ele não é destruído; a ferramenta usa `alteracoes-transacionais.yaml`.

Texto manual em resumo, consequências e experiência fica fora dos marcadores automáticos e é preservado.

O resumo automático **não reconstrói a história por inferência**: usa os resumos curtos das transações. Informações importantes que precisam virar conhecimento, consequência, progressão ou outro estado devem existir como deltas explícitos.

`consolidar.py sessao` marca seus artefatos automáticos como encerrados, mas não incrementa automaticamente a sessão, não cria a próxima e não escolhe progressão por Ren.

---

## Conhecimento, relações e NPCs depois da consolidação

Conhecimento novo registrado é materializado em fragmentos incrementais por sessão e ligado a `conhecimento/ativo.yaml`; os fragmentos legados permanecem intocados e reconstruíveis.

Mudança de relação atualiza somente o fragmento corrente da entidade e registra a causa no histórico específico. O mesmo vale para medidores de NPC. Novas entidades podem nascer na consolidação sem exigir retorno aos antigos monólitos.

---

## Consequências, progressão e relógios

Consequências só entram no artefato automático quando houver delta explícito `consequencia`.

`progressao` pode registrar um marco/recompensa, mas isso não autoriza escolher opção de nível pelo jogador. Mudanças mecânicas efetivas precisam de delta próprio.

Relógios reservados usam `relogio:<id>` e permanecem em `narrador/relogios/`. Delta com `visibilidade: narrador` não pode ser instalado em domínio público.

---

## Queda durante consolidação

Se existir:

```text
runtime/consolidacao-em-andamento.json
```

não narrar, não usar `contexto.py` e não registrar novo turno. O estado pode estar entre dois arquivos do mesmo commit lógico.

Recuperar primeiro:

```bash
python3 ferramentas/consolidar.py recuperar
```

A recuperação usa os bytes já staged e aceita como estado de cada destino apenas o hash anterior ou o hash final. Ela não recalcula o lote e, portanto, não reaplica incrementos.

Depois de sucesso, journal/staging são removidos e a operação normal é liberada.

---

## Pausas e retomadas

Sem journal de consolidação, `turno.py check` valida uma pausa com eventos pendentes. Ao retomar, tentar L0 → `contexto.py status` → `contexto.py cena`; não reler automaticamente a transcrição inteira.

Se a pausa ocorreu durante consolidação, usar `consolidar.py recuperar` antes de qualquer leitura operacional.

---

## Correções

Erro de regra, estado ou continuidade deve ser corrigido explicitamente. Não apagar decisão do jogador. Durante sessão, correção vira nova transação/delta; nunca alteração silenciosa de evento anterior já narrado.
