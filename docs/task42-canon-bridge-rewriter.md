# Task 42 — Canon Bridge & Rewriter

## Propósito

A Task 42 permite que uma sidequest emergente aceita se torne uma **ponte causal para a espinha canônica**, sem editar o cânone-base e sem controlar Ren.

A Task 36 continua sendo a realização padrão dos eventos futuros. A Task 39 continua sendo a autoridade sobre a intenção canônica e sua elasticidade. A Task 42 acrescenta apenas um overlay reservado em `narrador/arcos/parte_1/rewrites-causais.yaml`.

O princípio é: **a forma pode mudar; a intenção não pode evaporar**.

## Relações

A Task 41 continua autorizando a autoria com cinco relações:

- `lateral`: não cria estado Task42 e não toca no cânone;
- `candidata_ponte`: ao aceite vira `ponte`; aproxima o fim da quest da janela canônica e fornece uma estrada causal, mas não altera o agendamento;
- `candidata_convergente`: ao aceite vira `convergente`; pode fazer o clímax da quest e a intenção canônica se encontrarem. A realização padrão só pode ser suprimida depois de a intenção ser provada satisfeita;
- `candidata_adiamento`: ao aceite vira `adiamento`; desloca apenas o disparo efetivo dentro de `atraso_maximo_horas` autorizado pela Task 39;
- `candidata_transformacao`: ao aceite vira `transformacao`; permite que outra causalidade satisfaça a função narrativa. Até existir prova suficiente, a realização padrão permanece fallback.

A Task 41 pode considerar até três candidatas durante autoria. A Task 42 exige **exatamente uma intenção alvo** quando uma quest não lateral é aceita, evitando reservar vários marcos por uma única aventura.

## O que uma reserva NÃO faz

Aceitar uma ponte não:

- move Ren;
- decide que Ren comparecerá ao local;
- decide como Ren resolverá a quest;
- estabelece que um NPC reservado apareceu;
- materializa a intenção canônica;
- entrega recompensa;
- altera arquivo da Task 36 ou da Task 39.

A reserva contém apenas a relação causal, o prazo da quest e os locais de sua fase final. Se Ren nunca chegar ali, o mundo responde ao que realmente ocorreu.

## Ledger de overlays

`rewrites-causais.yaml` possui duas coleções pequenas:

- `reservas`: intenções temporariamente vinculadas a uma sidequest aceita;
- `resolucoes`: intenções já satisfeitas por um caminho alternativo comprovado.

O ledger tem teto de 12 KiB e não é carregado no turno comum. Não há novo scheduler, RNG, busca global ou catálogo paralelo.

Uma intenção não pode estar simultaneamente reservada por duas quests. A segunda tentativa falha antes do aceite.

## Adiamento e fallback

O agendamento persistido da Task 36 **não é editado**. A Task 42 retém o disparo padrão somente enquanto a sidequest responsável permanece aceita e a reserva de adiamento está válida.

Se a quest falha, expira ou deixa de sustentar a reserva, o bridge libera o vínculo. Se o instante canônico original já passou, a pendência padrão é restaurada na fila existente do Mundo Vivo. A causalidade volta a procurar a realização normal/adaptada.

Se a quest permanece aceita até o instante adiado, o mesmo agendamento da agenda produz uma pendência equivalente no instante efetivo. Isso reutiliza o scheduler e a barreira já existentes; não existe relógio Task42.

## Convergência e transformação

Concluir uma quest convergente ou de transformação **não satisfaz automaticamente o cânone**. A reserva passa para `aguarda_evidencia`.

Para satisfazer a intenção, é necessário fornecer exatamente uma evidência para cada `criterio_satisfacao` da Task 39. Cada evidência declara:

- o critério exato;
- uma fonte canônica do repo;
- um trecho literal existente nessa fonte.

Arquivos reservados de planejamento — fragmentos de sidequest, intenção ou evento futuro — não podem servir como prova. Planejamento não prova a si mesmo.

Somente depois de todos os critérios serem comprovados a resolução recebe `estado: satisfeita`. Nesse momento a realização padrão pode ser suprimida. O evento e a intenção originais continuam byte-preservados como fonte autoral.

Se a realização padrão já foi materializada, a Task 42 recusa a satisfação retroativa. Passado não é reescrito.

## Lifecycle

Até a integração final da Task 46, sidequests emergentes que usam relação canônica devem passar pela porta Task42:

```text
python ferramentas/canon_bridge_runtime.py responder <mission_id> aceitar|adiar|recusar
python ferramentas/canon_bridge_runtime.py finalizar <mission_id> concluida|falhada|expirada --motivo '...'
python ferramentas/canon_bridge_runtime.py reconciliar
```

Uma quest lateral também pode usar essa porta: o lifecycle é atualizado normalmente e nenhuma reserva canônica é criada.

Satisfação de convergência/transformação usa stdin para as evidências:

```text
python ferramentas/canon_bridge.py satisfazer <mission_id> --nota '...'
```

com um mapa contendo `evidencias`.

A Task 46 incorporará reconciliação e roteamento ao fluxo unificado `cronica`; a Task 42 deliberadamente não aumenta ainda o custo do turno normal.

## Checks de integridade

A Task 42 falha fechado quando:

- tenta reservar evento congelado/passado;
- a intenção não permite integração com sidequest;
- um adiamento excede a elasticidade da Task 39;
- uma segunda quest tenta reservar a mesma intenção;
- uma resolução tenta suprimir a realização padrão sem `estado: satisfeita`;
- os critérios de satisfação não estão todos comprovados;
- a evidência vem de planejamento reservado;
- a realização padrão já foi materializada.

O resultado é um reescritor de **forma e causalidade**, não um apagador de cânone.
