# Integração reativa: locais, encontros, side quests e recompensas

Esta camada fecha o Mundo Vivo sem criar um novo scheduler. Ela só acorda quando
há um **gatilho real da cena**. Turnos comuns não consultam seus índices.

## 1. Entrada/exploração de local

Quando Ren efetivamente entra ou começa a explorar uma área/setor com identidade
operacional estável:

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

## 2. Encontro com NPC

No início de um encontro social elegível:

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

## 3. Efeitos de side quest

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

## 4. Pós-canônico

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

## 5. Lifecycle

No checkpoint, após o cânone estar instalado, quest giver morto é propagado para a
camada de oportunidades:

- perfil → `inativo`;
- potencial → descartado/inviável;
- `oferecida` ou `adiada` → `expirada`;
- `aceita` → `falhada`;
- estados terminais permanecem históricos.

Isso não sorteia oportunidade, não cria consequência e não abre side quest nova.

## 6. Orçamento

Contrato: `baseline/mundo-vivo-integracao-orcamento.yaml`.

Invariantes:

- zero scan de recompensas/NPCs por turno comum;
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

Regressão específica:
`tests/fixtures/mundo-vivo/integracao-v1.yaml`.
