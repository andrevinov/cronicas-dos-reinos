# Saneamento de congelamentos de estado vivo — Task 2

## Objetivo

A Task 2 elimina testes que tratavam valores mutáveis da campanha como
invariantes permanentes. Nenhum cânone, estado corrente ou sessão histórica é
alterado para satisfazer a suíte.

A regra é simples:

- **estado vivo** é validado por relações, faixas, consistência entre fontes e
  propriedades estruturais;
- **valor absoluto histórico** pertence a fixture isolada;
- **propriedade permanente** pode continuar literal quando há justificativa
  semântica explícita.

## Origem da revisão

A Task 1 marcou nove arquivos como `congelamento_suspeito` por combinarem
leitura direta de estado vivo com assertions literais. A heurística era
intencionalmente conservadora: ela apontava candidatos, não erros confirmados.

A decisão humana de cada candidato está em:

```text
tests/live-state-freeze-review.yaml
```

O gate:

```bash
python ferramentas/verificar-congelamentos-estado-vivo.py
```

reexecuta o inventário da Task 1 e falha se surgir um novo suspeito sem decisão
registrada. O manifesto aceita apenas:

- `corrigido`: o valor mutável foi substituído por invariantes/relacionamentos
  ou por fixture isolada;
- `justificado`: o literal protege uma propriedade permanente, não o valor
  corrente da campanha.

## Correções realizadas

### Identidade

A ausência inicial de suspeita de Kethra não é mais consultada no estado vivo.
O comportamento de bootstrap é exercitado com `identidades.empty_state()`.
Assim, uma suspeita legítima adquirida durante jogo não quebra a suíte.

### Migração e ativação 5.5e

Os números do instante da ativação — HP, Focus, CA, ataques, passivos e o efeito
legado de Passos sem Pegadas — foram movidos para:

```text
tests/fixtures/ren-5-5e-activation-snapshot.yaml
```

Essa fixture é explicitamente histórica. A ficha viva pode avançar depois da
ativação sem precisar continuar em Focus 1, HP 45 ou nível 7.

No estado corrente, os testes protegem:

- Focus existe e Ki estrutural não volta;
- Focus da ficha e do estado coincidem;
- recursos atuais ficam dentro de suas faixas;
- efeito legado, **se ainda existir**, permanece 2014, preservado e não
  recastável;
- o gate anti-híbrido continua verde.

### Actor e Observant

Atributos, perícias, passivos, CA e CD de Focus não são mais comparados com os
números que Ren tinha no dia em que os testes nasceram. As assertions agora
usam a ficha canônica corrente e relações mecânicas:

- modificador deriva do atributo;
- perícias derivam de modificador + proficiência quando aplicável;
- passivos de Observant derivam das perícias;
- CA e CD derivam dos modificadores e proficiência correntes;
- adaptador, runtime quente, L1 e retomada precisam concordar entre si.

As escolhas históricas — Móvel, Actor, Observant, escolha Inteligência e
DEC-0007 — continuam protegidas.

### População e papéis conversacionais

Contadores de população agora são derivados das próprias classificações em vez
de congelar `1`, `8` e `6`. Promoções já canonizadas são subconjuntos
obrigatórios, permitindo novas promoções futuras.

A garantia de que promoção estratégica não cria scheduler deixou de exigir que
Corven permaneça para sempre sem agenda: o teste agora prova que a validação
populacional não modifica o arquivo de agenda.

Os oito papéis conversacionais inaugurais também são subconjunto obrigatório,
não o conjunto máximo possível para sempre.

### Reputação pública

O bootstrap vazio é cenário isolado. O repo real é aceito com qualquer estado
de reputação válido que a campanha venha a adquirir.

Testes de repetição de marco, acúmulo antes de checkpoint, esclarecimento e
separação Kage/Ren constroem explicitamente o estado necessário. Eles não
partem mais da suposição de que a campanha viva ainda está em reputação zero.

A sessão 014 continua preservada como histórico e continua proibido criar
reputação retroativa apenas por varrer seu resumo.

### Rodapé

O runtime real não precisa possuir exatamente um item mágico para sempre. O
Broche do Semblante Humilde continua protegido, mas itens adicionais podem ser
adicionados sem quebrar o teste.

## O que permanece literal de propósito

Fixtures sintéticas, contratos de orçamento, decisões históricas, IDs de regras
e o snapshot da ativação 5.5e continuam usando valores absolutos. Nesses casos
o valor é a própria propriedade sob teste e não uma fotografia acidental do
estado corrente.

`test_auditoria_final.py` também permanece justificado: sua leitura direta do
buffer pendente é usada somente para provar igualdade byte a byte antes/depois
de uma operação read-only.

## Critério de regressão

Uma mudança futura não deve fazer teste falhar simplesmente porque:

- Ren perdeu/recuperou HP ou Focus;
- a sessão atual mudou;
- tempo ou cena avançaram;
- uma suspeita legítima surgiu;
- reputação pública mudou;
- novas relações, papéis, agentes ou itens foram acrescentados.

Se um novo teste precisar congelar um valor histórico, o cenário deve ser
isolado em fixture. Se precisar ler o estado vivo, deve comparar propriedades
que continuem verdadeiras após avanço legítimo da campanha.
