# Protocolo de sessão

Este protocolo define como iniciar, narrar, registrar, pausar e encerrar sessões de **Crônicas dos Reinos**.

Estilo: `narracao/guia-de-narrativa.md`. Limites: `narracao/limites.md`. Acesso e economia de contexto: `docs/agente/acesso-e-operacoes.md`.

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

`transcricao.md` é o registro completo da alternância entre jogador e narrador.

Durante a sessão ativa, mudanças ainda não consolidadas ficam em:

```text
runtime/eventos-pendentes.jsonl
```

---

## Cabeçalho da transcrição

Modelo:

```markdown
# Sessão 001

Data real: AAAA-MM-DD
Data no mundo: pendente
Personagem: Ren Kagehira
Local inicial: Ravens Bluff
Modo inicial de cena: interação

Estado inicial:

* PV: 24/24
* Ki: 3/3
* condições: nenhuma
* localização: a definir

---
```

O cabeçalho é snapshot inicial. Não deve ser reescrito a cada mudança durante a sessão.

---

## Abertura

A primeira entrada é do narrador e deve conter recap curto, localização, situação imediata, elementos perceptíveis relevantes, NPCs/ameaças, estado crítico de Ren quando necessário e uma deixa clara para agir.

O recap não deve carregar a sessão anterior inteira nem revelar material reservado.

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

Checklist breve antes de publicar resposta:

- NPCs falam como pessoas do mundo, não como interface de sistema;
- mecânica necessária fica fora da voz do NPC;
- segredos não aparecem como certeza pública;
- a resposta devolve situação jogável, não solução pronta.

---

## Loop transacional de narração

Desde a Etapa 7, uma interação comum segue:

```text
ação do jogador
→ usar contexto já presente
→ consultar somente lacuna necessária
→ resolver rolagens
→ produzir narração
→ registrar transação
→ devolver controle ao jogador
```

A persistência deve ser feita em uma única chamada:

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

A prosa da narração fica apenas na transcrição. O JSONL guarda ID, sessão, resumo, deltas e eventualmente rolagens ocultas.

### Proibição de write amplification

Durante cada troca normal **não** atualizar também:

- `estado/estado-atual.yaml`;
- `estado/tempo.yaml`;
- ficha;
- relações;
- medidores de NPC;
- conhecimento consolidado;
- consequências;
- relógios;
- resumos de sessão;
- logs reservados separados.

Esses destinos são consolidados posteriormente em lote.

Também não rodar por rotina, a cada ação, `git status`, `git diff`, testes globais, regeneração de runtime ou commit.

---

## Deltas mínimos

Um delta registra apenas o que mudou e precisa sobreviver à próxima interação.

Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.pontos_de_vida.atuais","valor":-6}
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"estado","op":"set","caminho":"localizacao.ponto_exato","valor":"junto à cerca"}
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:04 de 7 Eleasis"}
{"alvo":"relacao:kethra_dunn","op":"set","caminho":"confianca","valor":"moderada"}
{"alvo":"conhecimento","op":"registrar","valor":{"assunto":"ponte baixa","texto":"brasa protegida é sinal"}}
```

Operações: `set`, `inc`, `append`, `remove`, `registrar`.

Se nada persistente mudou, `deltas` pode ser vazio. Não transformar descrição sensorial ou fala trivial em estado estruturado.

`contexto.py` aplica deltas suportados sobre o snapshot-base ao responder consultas. Assim, o estado operacional permanece correto antes da consolidação.

---

## Idempotência e interrupção

Cada transação recebe ID estável e marcador HTML interno na transcrição. Repetir exatamente a mesma entrada não duplica registros.

Se houver queda entre as duas escritas, repetir a chamada repara somente o lado ausente.

Validação barata:

```bash
python3 ferramentas/turno.py check
```

Uma pausa no meio da sessão é segura quando esse comando passa: transcrição + buffer pendente + snapshot-base bastam para retomada.

---

## Tamanho das entradas

Entrada típica do jogador: uma frase a um parágrafo.

Entrada típica do narrador: duas frases a três parágrafos.

Entradas maiores são apropriadas em abertura, descoberta importante, encerramento de cena, resolução de combate, transição de viagem ou consequência substancial.

Não repetir PV, CA, Ki, dinheiro, hora e localização em toda resposta se nada relevante mudou.

---

## Modos de cena

Modos principais:

- interação;
- exploração;
- combate.

Registrar mudança de modo quando ela for relevante, como delta de `estado.campanha.modo_de_cena_atual`. Não repetir o rótulo em toda entrada se o modo não mudou.

### Interação

Foco em diálogo, postura, descoberta e relações. Acompanhar informação revelada, mentira/omissão, promessas, dívidas e mudanças significativas de atitude.

### Exploração

Foco em posição, luz, ruído, ferramentas, saídas, tempo gasto, riscos e rota de volta.

### Combate

Fluxo: surpresa se houver → iniciativa → posição → ação de Ren → rolagens/consequências → próximo turno.

Manter claro, quando relevante, rodada/turno, PV/Ki, inimigos visíveis, estado aparente, distâncias, cobertura e fuga. A clareza tática não exige repetir o bloco inteiro quando nada nele mudou.

---

## Rolagens visíveis

Formato recomendado:

```text
Teste de Furtividade: d20 12 + 5 = 17 contra CD 15. Sucesso.
```

Usar:

```bash
python3 ferramentas/rolar-dados.py ren pericia furtividade --cd 15
python3 ferramentas/rolar-dados.py ren ataque wakizashi --ca 14
```

Quando duas ou mais rolagens são independentes e já sabemos que todas serão necessárias, usar **uma chamada**:

```bash
python3 ferramentas/rolar-lote.py <<'JSON'
[
  ["ren", "pericia", "furtividade", "--cd", "15"],
  ["npc", "d20", "--nome", "Guarda", "--bonus", "3", "--cd", "12"]
]
JSON
```

Não antecipar uma rolagem que só deveria existir se outra tiver determinado resultado.

---

## Rolagens ocultas

Usar quando revelar o dado já entregaria informação indevida: mentira, criatura escondida, armadilha, facção fora de cena, relógio oculto etc.

Durante o loop narrativo, rolagens ocultas relevantes podem ser registradas em `rolagens_ocultas` da transação. Elas não entram em consultas públicas normais.

Na consolidação serão transferidas, quando necessário, para:

```text
narrador/sessoes/NNN/rolagens-ocultas.md
```

Isso evita uma terceira escrita por turno.

---

## Preparação do narrador

Criar material reservado somente quando necessário em `narrador/sessoes/NNN/`: preparação, segredos, mapas, relógios, rolagens ou NPCs relevantes. Não carregar a pasta inteira durante narração sem lacuna concreta.

---

## Dungeons e cidades

Em dungeon, preservar topologia, saídas, mudanças e segredos; revelar apenas o percebido por Ren.

Em cidade, abstrair deslocamento salvo perseguição, cauda, tempo crítico, perigo de bairro ou rota com consequência. Não detalhar caminho por rotina.

---

## Imagens

Imagens pedidas durante sessão ficam em `sessoes/NNN/imagens/` e são referenciadas na transcrição. Não revelar elementos ainda não percebidos.

---

## Encerramento de cena

A narração pode fazer checkpoint curto do que mudou, mas não precisa virar relatório. Não é obrigatório consolidar todos os arquivos canônicos ao fim de cada cena.

Se uma pausa longa acontecer, `turno.py check` é suficiente para verificar persistência transacional.

---

## Encerramento de sessão

Criar/atualizar, conforme aplicável:

```text
sessoes/NNN/resumo.md
sessoes/NNN/alteracoes-de-estado.yaml
sessoes/NNN/consequencias.md
sessoes/NNN/experiencia.md
```

A consolidação deve considerar ponto inicial/final, tempo, decisões, rolagens decisivas, combates, recursos, itens, relações, descobertas, mistérios, consequências e pendências.

`runtime/eventos-pendentes.jsonl` é a lista explícita das alterações ainda não consolidadas. A Etapa 8 implementará sua aplicação automática/idempotente. Até lá, não limpar o buffer por rotina.

Após consolidação canônica, regenerar `runtime/contexto.yaml` e `runtime/cena.yaml`.

---

## Pausas e retomadas

Não é necessário escrever um novo bloco de pausa se a última transação já contém resumo suficiente e `turno.py check` passa. Quando útil para legibilidade humana, um marcador de pausa pode continuar na transcrição.

Ao retomar, tentar L0 → `contexto.py status` → `contexto.py cena`. Não reler automaticamente a transcrição inteira.

---

## Correções

Corrigir explicitamente erro de regra, estado ou continuidade. Não apagar decisão do jogador. Uma correção durante sessão deve entrar como nova transação/delta, nunca como alteração silenciosa de evento anterior já narrado.
