# Dificuldade

A campanha usa dificuldade **solo cautelosa, com risco real**.

Isso significa que Ren não recebe proteção automática, mas os encontros iniciais devem respeitar o fato de que ele está sozinho.

---

## Princípios

O narrador deve:

* preservar consequência real;
* sinalizar perigo letal quando Ren puder percebê-lo;
* permitir fuga, recuo, negociação, disfarce e infiltração;
* evitar encontros feitos para um grupo completo sem alternativa jogável;
* deixar inimigos agirem por objetivos próprios, não sempre até a morte;
* não reduzir secretamente a dificuldade apenas porque Ren está em risco.

---

## Escala inicial

No primeiro arco de Ravens Bluff, priorizar:

* risco baixo a moderado em cenas sociais e urbanas;
* perigo alto quando Ren entrar deliberadamente em local perigoso, isolado ou desconhecido;
* combates pequenos, perseguições, pressão social e consequências;
* inimigos que possam fugir, pedir reforço, negociar, intimidar ou tentar recuperar algo.

Combates letais podem existir, mas devem surgir de sinais, escolhas, escalada ou erro sério, não de surpresa arbitrária.

---

## Solo não significa fácil

Como Ren é furtivo e móvel, muitas soluções fortes passam por:

* observar antes de agir;
* escolher terreno;
* atacar e reposicionar;
* evitar luta desnecessária;
* usar cobertura legal quando útil;
* gastar focus em momentos decisivos.

Se Ren escolher confronto direto contra muitos inimigos ou uma autoridade poderosa, o mundo responderá de modo coerente.

---

## Ajuste de encontros

Ao adaptar encontros publicados:

* reduzir número de inimigos quando a cena pressupõe grupo completo;
* trocar morte imediata por captura, perseguição, alarme ou perda quando fizer sentido;
* manter perigos óbvios perigosos;
* não transformar todo inimigo em estatística equilibrada para o nível de Ren;
* registrar decisões recorrentes se virarem regra da campanha.

## Avaliação dirigida de ameaça

Quando uma ficha competente já estiver escolhida e a escala não for óbvia, usar
`python3 ferramentas/ameacas.py avaliar <id> --ren --vetor combate` antes da
rolagem. A avaliação pode incluir inimigos adicionais, aliados já causais,
recursos, terreno e iniciativa. Ela não escolhe encontro, não reduz ficha e não
convoca Joen, Luath ou qualquer outro aliado para corrigir dificuldade.

As classificações são preparação: `baixa`, `moderada`, `alta`, `letal` e
`esmagadora`. As duas últimas exigem perigo sinalizado e ao menos uma saída
observável ou investigável. Saída possível não significa saída automática.
