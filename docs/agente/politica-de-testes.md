# Política permanente de testes

Esta política encerra o saneamento iniciado nas Tasks 1–6 e define como a suíte deve evoluir daqui em diante.

O objetivo não é minimizar a quantidade de testes. O objetivo é fazer cada teste proteger uma propriedade que realmente não pode quebrar, sem transformar a evolução normal da campanha em falso positivo.

## Princípio central

**Estado vivo é protegido por invariantes. Valores absolutos mutáveis pertencem a cenários controlados.**

Antes de escrever uma assertion, classifique a fonte observada como uma destas três categorias:

- **estado vivo**: ficha atual, estado atual, runtime, sessão corrente, reputação, suspeitas, condições, rastros, progressão, agenda e outros dados que a campanha pode alterar legitimamente;
- **fixture/cenário temporário**: entrada construída pelo próprio teste, normalmente em `TemporaryDirectory`;
- **snapshot/histórico imutável**: fotografia deliberada de um instante passado cuja imutabilidade é a propriedade protegida.

A categoria determina o tipo de assertion permitido.

## Regra 1 — estado vivo

Testes que leem estado canônico corrente devem preferir **invariantes, relações entre fontes e propriedades estruturais**.

Evite proteger uma fotografia do dia em que o teste foi escrito.

Ruim para estado vivo:

```python
self.assertEqual(ficha["focus"]["atuais"], 1)
self.assertEqual(status["sessao"], 8)
self.assertEqual(reputacao["estado"], "estrangeiro_desconhecido")
```

Preferir relações como:

```python
self.assertEqual(estado_focus["atuais"], ficha_focus["pontos_atuais"])
self.assertGreaterEqual(estado_focus["atuais"], 0)
self.assertLessEqual(estado_focus["atuais"], estado_focus["maximos"])
self.assertEqual(status["sessao"], runtime["sessao"]["numero"])
```

Se um valor puder mudar legitimamente porque a campanha avançou, ele não deve ser tratado como constante permanente do repo.

## Regra 2 — valores absolutos mutáveis

Valores absolutos mutáveis só devem ser congelados quando fazem parte de uma entrada controlada ou de história explicitamente imutável.

Locais legítimos:

- fixtures;
- snapshots;
- cenários em diretórios temporários;
- registros históricos explicitamente imutáveis.

Exemplo legítimo:

```python
fixture = {"ki": {"atuais": 1, "maximos": 7}}
resultado = migrar(fixture)
self.assertEqual(resultado["focus"]["atuais"], 1)
```

Nesse caso, `1` pertence à entrada do experimento. Ele não exige que a ficha viva de Ren permaneça para sempre com Focus 1.

## Regra 3 — snapshots históricos

Todo snapshot que congela números ou conteúdo de campanha deve declarar claramente:

1. que sua natureza é histórica/isolada;
2. qual instante ou migração representa;
3. por que precisa permanecer congelado;
4. que não descreve obrigatoriamente o estado vivo futuro.

O padrão existente em `tests/fixtures/ren-5-5e-activation-snapshot.yaml` é a referência: os números exatos da ativação 5.5e são legítimos porque documentam aquele instante, não porque Ren deva continuar naquele estado.

Um snapshot sem justificativa histórica deve ser tratado como candidato a freeze acidental.

## Regra 4 — nomes de testes pertencem ao domínio, não à Task

Novos testes permanentes não devem ser nomeados ou estruturados em torno do número da Task quando a propriedade já representa comportamento de domínio.

Preferir:

```text
test_sidequest_router.py
test_runtime.py
test_session_lifecycle.py
```

Evitar como nome permanente:

```text
test_task53_router.py
test_task61_fix.py
```

O número da Task pode continuar aparecendo em documentação histórica, comentários de migração ou fixtures quando ele é parte real da proveniência. Ele não deve ser a identidade duradoura de um contrato de domínio.

## Regra 5 — remoção e consolidação

Nunca remover um teste apenas porque ficou inconveniente, lento ou vermelho.

Antes de remover ou consolidar, responder explicitamente:

1. Qual propriedade este teste protege?
2. Essa propriedade ainda é relevante?
3. Se sim, onde ela continuará coberta?
4. A cobertura nova exercita a mesma falha, ou apenas parece semelhante?

Se dois testes parecidos protegem modos de falha diferentes, ambos permanecem.

A rastreabilidade criada em `tests/historical-test-review.yaml` e validada por `ferramentas/verificar-testes-historicos.py` é o modelo para consolidações maiores.

## Regra 6 — estado real é exceção, não padrão

Testes contra `ROOT` são apropriados quando a propriedade depende realmente da integração com o repositório canônico atual: consistência entre fontes, existência de registros, contratos de integração, tamanho de artefatos ou invariantes do estado instalado.

Quando o comportamento puder ser provado isoladamente, prefira `TemporaryDirectory` ou fixture explícita.

Isso produz testes que:

- deixam claro quais entradas importam;
- não dependem de sessão, hora, HP, Focus ou progresso corrente;
- não quebram só porque a campanha avançou;
- são mais fáceis de reproduzir e diagnosticar.

## Auditoria heurística e revisão semântica

`ferramentas/auditar-testes.py` continua sendo a ferramenta de inventário **read-only**. Ela procura sinais como:

- leitura direta de `estado/**` ou `runtime/**`;
- leitura de `personagens/jogador/ficha.yaml` e `sessoes/index.yaml`;
- uso do repo real;
- assertions literais;
- fixtures/isolamento;
- nomes históricos de Task;
- corpos de teste exatamente duplicados.

Um resultado `congelamento_suspeito` é **sinal de revisão**, não veredito automático de erro. A heurística não conhece a semântica completa do domínio.

A camada seguinte é deliberadamente semântica:

- `tests/live-state-freeze-review.yaml` registra se um candidato foi `corrigido` ou `justificado`;
- `ferramentas/verificar-congelamentos-estado-vivo.py` exige que um novo suspeito direto receba decisão explícita;
- `tests/historical-test-review.yaml` registra propriedade e destino da cobertura histórica;
- `ferramentas/verificar-testes-historicos.py` impede remoção sem destino e novo teste permanente acoplado a Task sem revisão.

Portanto o fluxo é:

```text
heurística encontra sinal
        ↓
revisão humana da propriedade
        ↓
corrigir ou justificar
        ↓
preservar cobertura relevante
```

Não transformar a heurística em bloqueio cego baseado apenas na presença de um literal ou de `ROOT`. Um guard mais rígido só deve ser adotado quando houver dados suficientes para demonstrar poucos falsos positivos.

## Como escrever um teste novo

Use esta sequência:

1. identifique a propriedade que não pode quebrar;
2. determine se a fonte é viva, fixture ou snapshot;
3. se for viva, formule uma relação/invariante;
4. se precisar de número absoluto mutável, construa fixture ou snapshot explícito;
5. dê ao arquivo e aos métodos nomes do domínio;
6. use estado real apenas quando a integração real for a propriedade;
7. execute `test-fast`/`test-domain` durante desenvolvimento e `test-full` + `preflight` antes de merge.

Perfis e comandos: `docs/agente/perfis-de-testes.md`.

## Exemplos de propriedades adequadas ao estado vivo

- recurso atual está entre zero e o máximo;
- ficha, estado e runtime concordam sobre o mesmo recurso;
- sessão projetada coincide com a sessão corrente da fonte autoritativa;
- contador retornado é derivado do ledger atual;
- IDs conhecidos continuam presentes, permitindo novos IDs legítimos;
- operação declarada read-only não altera bytes antes/depois;
- estado corrente respeita schema, limites e relações causais.

## Exemplos que normalmente pedem fixture ou snapshot

- “na migração X, Ki 1/7 virou Focus 1/7”;
- “este histórico concluído possui exatamente este hash”;
- “com três evidências sintéticas, o grau esperado é Y”;
- “um input nível 7 produz determinada saída mecânica”;
- “este contrato de orçamento possui teto N explicitamente versionado”.

## Definition of done para mudanças em testes

Antes de merge:

- nenhum arquivo de cânone/estado é alterado apenas para satisfazer um teste;
- snapshots novos explicam por que são históricos;
- novos testes permanentes usam nomes de domínio;
- remoções possuem propriedade e cobertura de destino identificadas;
- testes isoláveis não dependem desnecessariamente de `ROOT`;
- os testes diretamente relacionados passam;
- `poetry run test-full` continua representando toda a suíte;
- `poetry run preflight` continua sendo o gate local completo;
- os workflows obrigatórios permanecem verdes.
