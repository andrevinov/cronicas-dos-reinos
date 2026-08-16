# Protocolo de sessão

Este protocolo define como iniciar, narrar, registrar, consolidar, pausar e encerrar sessões de **Crônicas dos Reinos**.

Estilo: `narracao/guia-de-narrativa.md`. Limites: `narracao/limites.md`. Entrada: `docs/agente/protocolo-de-entrada.md`. Acesso: `docs/agente/acesso-e-operacoes.md`. Consolidação: `docs/agente/consolidacao-transacional.md`. Memória: `docs/agente/memoria-de-sessoes.md`.

---

## Estrutura de diretórios

Cada sessão possui pasta própria. Os artefatos aparecem conforme houver conteúdo:

```text
sessoes/001/
├── transcricao.md
├── handoff.yaml
├── consolidacoes.jsonl
├── resumo.md
├── alteracoes-de-estado.yaml
├── experiencia.md
├── consequencias.md
└── imagens/
```

`transcricao.md` é o registro integral e append-only dos **avanços ON** entre jogador e narrador. OFF nunca é copiado para ela. **A transcrição é fria para leitura.** O arquivo normal de retomada é `handoff.yaml`, indexado por `sessoes/index.yaml`.

Durante a sessão ativa, mudanças posteriores ao último checkpoint ficam em:

```text
runtime/eventos-pendentes.jsonl
```

---

## Abertura de sessão

A abertura deve conter recap curto, localização, situação imediata, elementos perceptíveis relevantes, NPCs/ameaças, estado crítico quando necessário e uma deixa clara para Ren agir.

Para reconstruir continuidade, usar primeiro:

```bash
python3 ferramentas/contexto.py retomada
```

Se precisar de uma sessão específica:

```bash
python3 ferramentas/contexto.py sessao 2
```

**Nunca copiar o último trecho da sessão anterior para a nova transcrição.** Também não abrir a transcrição anterior por rotina. Handoff, runtime, deltas e artefatos compactos existem justamente para impedir essa duplicação.

O cabeçalho da nova transcrição é snapshot inicial curto; não deve ser reescrito a cada mudança.

---

## Linguagem da janela — ON, OFF e RECALL

A janela do Codex usa três canais explícitos:

```text
texto normal = ON
[texto]      = OFF
{texto}      = RECALL dentro de ON
```

- **ON** é ficção ativa e pode gerar avanço/transação.
- **OFF** é André falando com o narrador. Um bloco OFF inteiro começa com `[` e termina com `]`; ele não avança tempo, não consome recurso, não cria delta e não entra na transcrição. Respostas OFF do narrador também ficam entre colchetes.
- **RECALL** pede para completar uma lembrança factual que Ren legitimamente possui. Deve ser resolvido e substituído antes do avanço. Não pode escolher estratégia, emoção, vontade ou fala criativa por Ren, nem revelar segredo que ele não conhece.

ON, OFF e RECALL podem coexistir na mesma mensagem. Separar os canais antes de resolver a ficção. Se qualquer RECALL não puder ser resolvido de forma legítima e não ambígua, parar sem rolar, avançar ou registrar e explicar a lacuna em OFF.

Somente **ON já resolvido** pode ser enviado como campo `jogador` para `turno.py registrar`. `ferramentas/entrada.py` é o parser/validador determinístico; texto ON comum não precisa pagar um tool call só para classificação.

Contrato completo: `docs/agente/protocolo-de-entrada.md`.

---

## Alternância

Formato persistido para avanços ON:

```markdown
**Narrador**

...

**Jogador**

...
```

O jogador controla o que Ren faz, diz, tenta, pensa ou sente. O narrador resolve mundo, NPCs, regras, rolagens e consequências.

Antes de publicar: NPCs soam como pessoas do mundo; mecânica fica fora da voz do NPC; segredos não aparecem como certeza pública; a resposta devolve uma situação jogável.

---

## Loop transacional de narração

Uma interação com ON segue:

```text
entrada
→ separar ON/OFF/RECALL
→ resolver RECALL
→ usar contexto já presente
→ consultar somente a lacuna necessária
→ resolver rolagens do ON
→ produzir narração
→ registrar somente ON resolvido + narração + deltas
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

O registrador recusa `jogador` contendo OFF ou RECALL não resolvido antes de qualquer escrita. Ele escreve somente:

1. `sessoes/NNN/transcricao.md`;
2. `runtime/eventos-pendentes.jsonl`.

A prosa completa fica só na transcrição. O JSONL guarda ID, sessão, resumo, deltas e eventualmente rolagens ocultas.

### Proibição de write amplification

Durante cada troca normal não atualizar também estado, tempo, ficha, relações, NPCs, conhecimento, consequências, relógios, resumos, handoff, índice de sessões ou logs reservados. Esses destinos pertencem ao checkpoint.

Também não rodar por rotina, a cada ação, `git status`, `git diff`, testes globais, regeneração de runtime ou commit.

### Proibição de repetição mecânica

Não repetir em toda resposta um painel com PV, CA, Ki, dinheiro, munição, hora e localização quando esses valores não mudaram e não alteram a decisão imediata.

Mostrar mecânica quando ela mudou, é taticamente relevante, evita ambiguidade ou resolve a ação. O runtime/delta já guarda o estado completo; a transcrição não precisa duplicá-lo em cada bloco.

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

Se nada persistente mudou, `deltas` pode ser vazio. Descrição sensorial ou fala trivial não precisa virar estado estruturado. `contexto.py` aplica os deltas sobre o snapshot-base até o checkpoint.

---

## Idempotência do turno

Cada transação recebe ID estável e marcador interno na transcrição. Repetir a mesma entrada não duplica registros. Se houver queda entre as duas escritas, repetir a chamada repara somente o lado ausente.

```bash
python3 ferramentas/turno.py check
```

Sem journal de consolidação, runtime + handoff + buffer + transcrição append-only preservam a sessão. Para **ler** o que é necessário à retomada, usar `contexto.py retomada`.

---

## Tamanho, modos e ritmo

A ação do jogador pode ser curta ou extensa conforme a intenção. A resposta do narrador usa **densidade adaptativa**: ações simples podem ser breves; diálogo, lugar novo, revelação, transição e cenas importantes recebem o espaço necessário para serem vividos, sem enchimento. Não existe teto normal de duas frases/três parágrafos.

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

Rolagens ocultas relevantes ficam no campo `rolagens_ocultas` da transação. Isso evita uma terceira escrita durante o turno. No checkpoint canônico elas são transferidas em lote para:

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

Não consolidar por cronômetro nem depois de cada ação. Fazer checkpoint quando houver **fronteira de cena importante** e um estado canônico for útil: fim de combate relevante, saída de local perigoso, descanso/transição forte, mudança clara de objetivo ou antes de pausa operacional longa.

```bash
python3 ferramentas/checkpoint.py cena
```

O fluxo possui duas fases:

1. `consolidar.py` instala atomicamente o novo cânone/runtime e limpa os eventos por último;
2. `checkpoint.py` deriva do resultado instalado `sessoes/NNN/handoff.yaml` e `sessoes/index.yaml`.

Handoff e índice são cache reconstruível. Se houver queda depois da primeira fase, nenhum delta precisa ser reaplicado; a memória compacta pode ser regenerada.

---

## Encerramento de sessão

Antes de declarar a sessão encerrada:

```bash
python3 ferramentas/checkpoint.py sessao
```

O motor canônico mantém, conforme houver conteúdo real:

```text
sessoes/NNN/consolidacoes.jsonl
sessoes/NNN/resumo.md
sessoes/NNN/alteracoes-de-estado.yaml
sessoes/NNN/consequencias.md
sessoes/NNN/experiencia.md
```

A camada de memória atualiza:

```text
sessoes/NNN/handoff.yaml
sessoes/index.yaml
```

Se já existir `alteracoes-de-estado.yaml` manual em formato incompatível com o gerado automaticamente, ele não é destruído; a ferramenta usa `alteracoes-transacionais.yaml`. Texto manual fora dos marcadores automáticos é preservado.

O resumo automático não reconstrói história por inferência: usa os resumos curtos das transações. Informações que precisam virar conhecimento, consequência, progressão ou outro estado devem existir como deltas explícitos.

O encerramento não incrementa automaticamente a sessão, não cria a próxima e não escolhe progressão por Ren.

---

## Histórico e transcrições frias

Para investigar passado, primeiro usar memória estruturada:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico
```

Isso ainda **não** abre transcrições. Se handoff, resumo, alterações, consequências e histórico específico não responderem à lacuna, escalar deliberadamente:

```bash
python3 ferramentas/contexto.py buscar "termo" --historico --transcricoes
```

A transcrição é evidência bruta de último recurso para leitura. Ela continua completa e preservada; apenas saiu do caminho quente.

---

## Conhecimento, relações e NPCs depois do checkpoint

Conhecimento novo registrado é materializado em fragmentos incrementais por sessão e ligado a `conhecimento/ativo.yaml`; os fragmentos legados permanecem intocados e reconstruíveis.

Mudança de relação atualiza somente o fragmento corrente da entidade e registra a causa no histórico específico. O mesmo vale para medidores de NPC. Novas entidades podem nascer sem exigir retorno aos antigos monólitos.

---

## Consequências, progressão e relógios

Consequências só entram no artefato automático quando houver delta explícito `consequencia`.

`progressao` pode registrar marco/recompensa, mas isso não autoriza escolher opção de nível pelo jogador. Mudanças mecânicas efetivas precisam de delta próprio.

Relógios reservados usam `relogio:<id>` e permanecem em `narrador/relogios/`. Delta com `visibilidade: narrador` não pode ser instalado em domínio público.

---

## Queda durante consolidação ou memória

Se existir:

```text
runtime/consolidacao-em-andamento.json
```

não narrar, não usar `contexto.py` e não registrar novo turno. Recuperar primeiro:

```bash
python3 ferramentas/checkpoint.py recuperar
```

A recuperação canônica usa os bytes já staged e não reaplica incrementos. Depois reconstrói handoff/índice.

Se **não** houver journal canônico, mas handoff/índice estiverem ausentes ou desatualizados, o mesmo comando pode reconstruir apenas a memória derivada sem alterar fatos da campanha.

---

## Pausas e retomadas

Sem journal, `turno.py check` valida a persistência dos eventos pendentes. Para retomar:

```text
L0
→ contexto.py retomada
→ contexto.py cena/entidade se houver lacuna específica
→ histórico estruturado se necessário
→ transcrição somente como última escalada
```

Nunca reler automaticamente a transcrição inteira. Um pedido OFF como `[Continue a sessão 3.]` apenas solicita retomada; ele não deve ser gravado como ação de Ren.

---

## Correções

Erro de regra, estado ou continuidade deve ser corrigido explicitamente. Não apagar decisão do jogador. Durante sessão, correção vira nova transação/delta; nunca alteração silenciosa de evento anterior já narrado.
