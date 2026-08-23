# Adventure Drought Pressure

A Task 13 adiciona uma pressão operacional contra sequências longas de cenas locais sem sequer um candidato de microevento. Ela **não mede tempo sem aventura**, não lê transcrição e não decide se uma sessão foi “chata”.

A métrica é deliberadamente observável e determinística:

```text
quantas cenas locais confirmadas consecutivas terminaram com resultado `rotina`
no histórico do Local Microevent Deck?
```

Esse número é uma heurística operacional, não um fato canônico.

## Níveis

A pressão é global entre locais e deriva apenas do histórico recente já persistido pelo deck:

- 0–3 cenas secas → nível 0 `normal`;
- 4–5 → nível 1 `leve`;
- 6–7 → nível 2 `alta`;
- 8+ → nível 3 `critica`.

O baralho-base da Task 12 continua exatamente `3 rotina : 1 microevento` e continua sem reposição. A pressão não reseta nem reordena esse deck.

Ela age **depois** que uma ficha de ocorrência já foi sorteada:

- nível 0: nenhuma ficha de rotina é promovida;
- nível 1: `rotina_03` pode virar `microevento`;
- nível 2: `rotina_02` e `rotina_03` podem virar `microevento`;
- nível 3: qualquer `rotina_*` vira `microevento`.

Uma ficha que já era `microevento` permanece microevento. Portanto nível crítico garante somente que a próxima **cena local já acionada** produzirá um candidato de microevento; não cria cena por conta própria.

## O que “seca” significa

A pressão mede ausência de **candidatos determinísticos de incidente local**, não ausência de acontecimentos canônicos.

Quando um candidato é produzido, a sequência seca operacional é encerrada porque o histórico grava `resultado: microevento`. Isso continua verdadeiro mesmo se o narrador posteriormente descartar a manifestação por conflito com cânone forte. Esse compromisso é intencional: a Task 13 regula a oferta do motor, não julga semanticamente se a prosa final foi aventureira o suficiente.

Task 14 pode consultar essa pressão para seu próprio gate sem transformar esta métrica em verdade narrativa.

## Guardrails

Pressão nunca pode, por si só:

- criar NPC nomeado;
- criar combate, dano ou crime grave;
- criar side quest;
- criar recompensa;
- criar pista/segredo;
- sobrepor estado canônico, arco, cena aceita ou pendência;
- rerrolar uma carta vetada.

O resultado promovido continua passando pelo mesmo pool ecológico, pelos mesmos guardrails e pelo mesmo `preparar → narrar → confirmar` da Task 12.

## Custo

Não existe arquivo de estado novo. A pressão é derivada em memória de `historico_recente`, que já foi lido por `microeventos_locais.plan`.

Portanto a Task 13 adiciona ao hot path:

- 0 fontes;
- 0 leituras de tempo;
- 0 escritas;
- 0 scheduler;
- 0 scan semântico;
- 0 tool calls.

O registro da pressão (`resultado_base`, nível, seca anterior e promoção) é persistido dentro da mesma entrada de histórico e na mesma escrita de estado já necessária para confirmar o deck local.

## Structured Endpoint

`endpoints.py cena` expõe a pressão dentro de `disponibilidade.microevento_local.pressao_aventura`.

Quando nível > 0, também adiciona a `modificadores`:

```yaml
- tipo: pressao_seca_aventura
  nivel: 2
  nome: alta
  cenas_secas_antes: 6
  promovido: true|false
```

Isso reutiliza o contrato da Task 10 sem criar novo formato ou nova consulta.

## Manutenção

Consulta read-only:

```bash
python3 ferramentas/pressao_aventura.py status
```

A consulta valida o catálogo e o estado do Local Microevent Deck e lê somente esses dois arquivos reservados. Isso é uma porta de manutenção/inspeção; não é chamada adicional do hot path.

Contrato de regressão: `baseline/adventure-drought-pressure-orcamento.yaml`.
