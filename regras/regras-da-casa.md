# Regras da casa

Regras da casa iniciais para **Crônicas dos Reinos**.

Estas regras podem ser revisadas após uso em sessão.

---

## Base

A campanha usa **D&D 5e 2014** como ruleset mecânico ativo durante a migração e tem **D&D 5.5e** como ruleset alvo.

O contrato executável fica em `campanha.yaml`, em `sistema.ruleset`. Enquanto `sistema.ruleset.migracao.status` não for `concluida` e o gate `task_8_auditoria_final` não permitir a ativação, regras 5.5e podem ser consultadas para preparar a migração, mas **não substituem silenciosamente a mecânica ativa de 2014 em sessão**.

Material de AD&D e outras edições pode ser usado como cenário, aventura, NPC, local, item ou inspiração. A mecânica que **entrar em sessão** deve estar adaptada para o ruleset atual. Durante a migração, uma adaptação persistente pode ser preparada para 5.5e antecipadamente, mas permanece inelegível ao runtime até a ativação; uso 2014 derivado de AD&D é fallback explícito.

---

## Hierarquia mecânica

Quando duas fontes mecânicas entrarem em conflito, usar nesta ordem:

1. decisões registradas da campanha;
2. regras da casa;
3. ruleset atual declarado em `campanha.yaml`;
4. compatibilidade aprovada explicitamente;
5. fontes antigas/adaptadas.

Durante a migração, D&D 5.5e é fonte de preparação, comparação e conversão, não autoridade mecânica da sessão.

Depois da ativação, conteúdo 5e 2014 só pode permanecer como fallback quando não houver equivalente 5.5e aplicável e seu uso tiver sido aprovado explicitamente. Compatibilidade nunca significa misturar versões por conveniência sem registrar a escolha.

---

## Preservação histórica

A migração é **prospectiva**.

Ela não deve:

* reescrever sessões concluídas para fingir que foram jogadas sob 5.5e;
* recalcular retroativamente rolagens, combates, recursos, descobertas ou consequências já canonizadas;
* modificar decisões antigas apenas para harmonizar sua terminologia com a nova versão.

Se uma decisão existente precisar mudar por causa da 5.5e, criar uma substituição explícita com aplicação futura. Em particular, **não reescrever sessões concluídas** para aplicar retroativamente a nova decisão.

---

## Progressão

A progressão oficial é por **marcos narrativos**, conforme `regras/progressao.md`.

XP pode ser usado como referência, mas não precisa ser somado a cada encontro.

---

## Rolagens

Rolagens abertas devem usar, sempre que possível:

```bash
python3 ferramentas/rolar-dados.py
```

Rolagens ocultas podem ser usadas quando revelar o dado prejudicar o mistério.

Até a ativação final da 5.5e, o rolador e a ficha continuam resolvendo a mecânica do ruleset 5e 2014.

---

## Campanha solo

Ren é o único personagem jogador.

Por isso:

* encontros não precisam pressupor grupo completo de quatro personagens;
* inimigos podem ter objetivos além de matar;
* fuga, infiltração, negociação e recuo são soluções legítimas;
* aliados temporários podem aparecer, mas não devem roubar agência de Ren;
* o mundo não deve ser ajustado secretamente para garantir vitória.

---

## Adaptação de material antigo

A Task 7 separa formalmente lore de mecânica. Lore e aventura de AD&D podem ser usados sem envelope especial. Uma adaptação que produza números, testes, statblock, recurso ou outra mecânica ativa precisa declarar `proveniencia_mecanica` e passar por `ferramentas/gate_adnd.py` antes de chegar ao runtime. Adaptações persistentes entram em `regras/adaptacoes-mecanicas.yaml`.

THAC0, CA descendente, categorias antigas de salvamento e outros campos mecânicos de AD&D nunca são persistidos como regra operacional; são somente insumo para construir uma equivalência moderna. Uma conversão para 2014 é fallback excepcional e exige declaração, motivo e decisão explícita.

Ao adaptar material de AD&D para o ruleset atual:

* preservar nomes, função no cenário, tom e conflito;
* converter estatísticas apenas quando entrarem em jogo;
* usar blocos simples do ruleset atual quando bastarem;
* evitar importar subsistemas antigos sem necessidade;
* registrar decisões recorrentes em `regras/decisoes.md`, quando esse arquivo existir.

A troca do alvo de adaptação para 5.5e ocorrerá automaticamente quando `sistema.ruleset.atual` for ativado como `dnd_5_5e`; não é necessário alterar o cânone de cenário para isso.

---

## Decisão provisória

Se uma regra não estiver clara durante a sessão:

1. tomar uma decisão provisória coerente com o ruleset atual;
2. seguir a cena;
3. registrar a dúvida se ela puder voltar;
4. revisar depois da sessão.

Não parar o jogo por pesquisa longa quando a decisão puder ser feita com justiça razoável.
