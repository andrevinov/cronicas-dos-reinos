# Integração reativa: locais, encontros, side quests e recompensas

Esta camada fecha o Mundo Vivo sem criar um novo scheduler. Ela só acorda quando
há um **gatilho real da cena**. Turnos comuns não consultam seus índices.

## 1. Porta preferencial: abertura de cena

Na narração ao vivo, a porta preferencial é uma única abertura reativa:

```bash
python3 ferramentas/cena_mundo.py abrir \
  --cena-id "sessao-009:bram-loja" \
  --local loja_bram_vask --acao entrar --tier 2 --periculosidade media \
  --npc bram_vask --npc noll
```

Ela recebe os gatilhos que realmente começaram naquela fronteira de cena e
encaminha cada um para a camada já existente:

```text
abertura de cena
├─ local entrou/explorou? → mapa de recompensas
└─ NPC(s) presentes?      → gate raro de sidequest por NPC elegível
```

A intenção é tornar difícil esquecer um dos dois mecanismos. `local` e `encontro`
continuam disponíveis em `interacoes_mundo.py` como primitivas de baixo nível,
mas o narrador ao vivo deve preferir `cena_mundo.py abrir`.

### `cena_id` e idempotência

`cena_id` é um identificador ASCII estável e único daquela cena narrativa. Não
criar um novo ID a cada fala.

A mesma abertura pode ser repetida com segurança. Para cada NPC, a porta deriva:

```text
scene:<cena_id>:npc:<npc_id_canonico>
```

Se o mesmo NPC já foi processado naquela cena, o gate não roda novamente.

Quando um NPC novo entra numa cena que já está em andamento, chamar novamente a
porta com o **mesmo `cena_id`** e o elenco atualizado é seguro: NPCs antigos viram
`encontro_ja_processado`; somente o recém-chegado pode consumir novo gate.

### Vários NPCs simultâneos

Todos os IDs são resolvidos antes de qualquer mutação. Se houver typo ou
ambiguidade, a abertura falha antes de gerar mapa ou consumir gate.

Referências duplicadas que apontam para o mesmo NPC são colapsadas. Encontros que
começam simultaneamente são ordenados pelo **ID canônico**, não pela ordem dos
argumentos do CLI. Assim a distribuição do baralho 8/2 não depende de uma ordem
acidental de escrita.

A abertura aceita no máximo 12 referências de NPC por chamada. O gate global
continua permitindo no máximo uma pendência de avaliação; portanto uma abertura
pode expor no máximo um perfil narrativo de oportunidade.

### Economia

A porta não cria scan novo:

- cena só com local → não lê oportunidades nem tempo;
- NPC canônico sem perfil → não lê tempo;
- ID exato de perfil → resolução custa só o índice de oportunidades;
- alias/typo → no máximo índice de oportunidades + índice de relações;
- nenhum fragmento é aberto para resolver identidade;
- turno comum continua sem chamar esta porta.

## 2. Primitiva local: entrada/exploração

Quando Ren efetivamente entra ou começa a explorar uma área/setor com identidade
operacional estável, a abertura de cena pode despachar o local. A primitiva
continua disponível para manutenção/teste:

```bash
python3 ferramentas/interacoes_mundo.py local sarbreen_setor_a \
  --acao entrar --tier 2 --periculosidade alta
```

Se o mapa já existe, lê somente índice + mapa e o reutiliza. Se não existe, a
geração determinística acontece uma vez. Mudanças posteriores de tier/perigo não
rerrolam a área.

O retorno oferece candidatos/condições ao narrador. **Item existir no mapa não
significa que Ren o encontrou.** Fragmento de item só deve ser aberto quando sua
condição se tornar relevante.

## 3. Primitiva de encontro com NPC

A abertura de cena despacha encontros elegíveis com IDs estáveis. A primitiva
continua disponível quando for necessário acionar somente um encontro:

```bash
python3 ferramentas/interacoes_mundo.py encontro maerra_thandrel \
  --encontro-id "sessao-009:cena-03:maerra"
```

O `encontro_id` identifica a conversa inteira. Não gerar um novo ID a cada fala.

### Resolução do NPC

Preferir sempre o **ID estável completo**. Esse é o caminho mais barato: um ID de
perfil exato é reconhecido somente com `narrador/oportunidades/index.yaml`.

A porta tolera nome/alias humano sem criar identidade paralela:

```text
nera       -> nera_vell
Nera Vell  -> nera_vell
```

Nome completo normalizado pode ser resolvido no próprio índice de oportunidades.
Alias parcial consulta no máximo o índice canônico `estado/relacoes/index.yaml`
para provar que a referência é **globalmente unívoca**, sem abrir fragmentos.

Por isso:

```text
dunn  -> ERRO: colm_dunn ou kethra_dunn
nrea  -> ERRO: NPC desconhecido; sugestão nera_vell
```

Um NPC canônico realmente conhecido, mas sem perfil de oportunidade, continua
retornando `npc_sem_perfil_ativo`. Um identificador desconhecido **nunca** recebe
essa resposta. Ambiguidade ou typo falham antes de consumir o gate e pedem o ID
estável. O resultado usa sempre o ID canônico resolvido em cooldown, idempotência,
necessidades e missões.

A ordem barata é:

```text
resolver ID/nome do NPC
→ perfil existe no índice?
→ orçamento/cooldown permitem?
→ encontro já foi processado?
→ gate global 8 nada / 2 oportunidade
   → nada: fim, sem abrir perfil
   → oportunidade: abre exatamente 1 perfil dirigido
                  → escolhe 1 necessidade ainda disponível
                  → cria apenas potencial
```

`potencial` não é oferta. O narrador decide `oferecer` ou `descartar` com
`oportunidades.py`; Ren decide aceitar, adiar ou recusar.

## 4. Efeitos de side quest

Uma side quest aceita pode tocar estruturas já existentes sem bypassar seus
contratos. Antes de registrar o turno que materializa o efeito:

```bash
python3 ferramentas/interacoes_mundo.py preparar-sidequest sq-... <<'YAML'
- tipo: operacao
  operacao: red_sail_reconstruir_cadeia_colm
- tipo: pressao
  relogio: rastro_fraco_no_pomar
- tipo: consequencia
  valor:
    titulo: Um custo persistente
    descricao: O resultado da missão criou uma consequência.
YAML
```

- `agente`: referencia agente existente; agente novo é devolvido para
  **classificação NPC v2**, nunca criado silenciosamente;
- `operacao`: valida vínculo no roteador compacto;
- `pressao`: produz delta `relogio:<id>` para o mesmo `turno.py registrar`;
- `consequencia`: produz delta `consequencia/registrar`;
- `rastro` e `recompensa`: ficam em `pos_canonico`.

No máximo 6 efeitos por decisão. A preparação não abre fragmento de relógio.

## 5. Pós-canônico

Depois que o fato-base foi consolidado:

```bash
python3 ferramentas/interacoes_mundo.py pos-sidequest sq-... <<'YAML'
- tipo: rastro
  especificacao:
    ...
- tipo: recompensa
  local_id: sarbreen_setor_a
  especificacao:
    ...
YAML
```

Rastros continuam exigindo fonte canônica + evidência literal. Recompensa de quest
entra como `origem: quest`. Se o mapa ainda não existe, fica planejada para ele;
se já existe, é anexada sem rerrolar o núcleo procedural nem trocar a chave de
geração. Retry com o mesmo ID é idempotente; conteúdo divergente falha.

## 6. Lifecycle

No checkpoint, após o cânone estar instalado, quest giver morto é propagado para a
camada de oportunidades:

- perfil → `inativo`;
- potencial → descartado/inviável;
- `oferecida` ou `adiada` → `expirada`;
- `aceita` → `falhada`;
- estados terminais permanecem históricos.

Isso não sorteia oportunidade, não cria consequência e não abre side quest nova.

## 7. Orçamento

Contrato: `baseline/mundo-vivo-integracao-orcamento.yaml`.

Invariantes:

- zero scan de recompensas/NPCs por turno comum;
- abertura de cena é a porta preferencial única para gatilhos reativos ao vivo;
- no máximo 12 referências de NPC por abertura;
- identidades são resolvidas antes de qualquer mutação;
- encontros simultâneos são ordenados por ID canônico;
- cena só com local não lê oportunidades/tempo;
- NPC sem perfil não lê tempo;
- gate de side quest somente no início de encontro elegível;
- ID exato de perfil não abre o índice canônico de relações;
- alias/typo abre no máximo oportunidades + índice de relações, nunca fragmento;
- ficha `nada` abre zero perfis;
- ficha `oportunidade` abre no máximo um perfil;
- mapa existente nunca relê tabelas nem rerrola;
- mapa novo é gerado uma vez;
- no máximo um fragmento dirigido por decisão;
- lifecycle de checkpoint expõe zero fragmentos narrativos;
- turno comum continua com duas escritas.

Regressões específicas:

- `tests/fixtures/mundo-vivo/integracao-v1.yaml`;
- `tests/test_cena_mundo.py`.
