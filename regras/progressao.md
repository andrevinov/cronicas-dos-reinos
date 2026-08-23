# Progressão

A campanha usará **avanço por marcos narrativos**.

XP numérico pode ser usado como referência ocasional para calibrar recompensas, mas não será a moeda principal de evolução de Ren.

---

## Método adotado

Ren sobe de nível quando alcançar marcos relevantes de campanha.

Um marco pode ser:

* conclusão de um arco local;
* descoberta importante ligada a Masao, ao Selo da Lua Velada ou a Ravens Bluff;
* resolução de ameaça significativa;
* conquista de aliado, patrono, reputação ou base operacional;
* sobrevivência a uma sequência de riscos reais;
* decisão com consequência persistente que mude sua posição no mundo.

Combates isolados, cenas sociais simples e rolagens bem-sucedidas não concedem progressão automática.

---

## Ritmo esperado

Como a campanha é solo, o avanço deve considerar risco e densidade narrativa, não número de inimigos derrotados.

Ritmo inicial recomendado:

* nível 3 deve durar o primeiro arco de Ravens Bluff;
* nível 4 pode vir após Ren estabelecer uma posição real na cidade e resolver uma ameaça inicial importante;
* níveis seguintes devem exigir arcos mais amplos, consequências maiores ou expansão regional.

O avanço não precisa ocorrer em intervalos iguais.

---

## Faixa 8–17 — espinha da Juppongatana

A partir do nível 7 atual, os níveis **8 a 17** usam uma espinha especial de dez marcos: cada membro **único** da Juppongatana neutralizado de forma **canônica e durável** desbloqueia exatamente o próximo nível.

A ordem dos membros é livre. O primeiro neutralizado desbloqueia o nível 8; o segundo, o 9; e assim sucessivamente até o décimo desbloquear o 17. Marcos de aparição não impõem ordem de neutralização.

Neutralização não exige morte. Podem contar morte confirmada, prisão ou confinamento estável, incapacitação durável, ruptura definitiva com Masao ou expulsão/exílio operacional. Não contam derrota temporária, fuga, objetivo frustrado, ferimento recuperável, exposição, primeiro contato ou simples sobrevivência ao duelo.

Nenhum crédito retroativo é concedido na instalação desta regra: a frustração anterior de Kurobane não foi neutralização durável e o ledger começa em 0/10.

Outros grandes marcos continuam relevantes para história, aliados, reputação, recursos e estrutura de arco, mas **não substituem** uma neutralização da Juppongatana para consumir um dos níveis 8–17. Depois do nível 17, a progressão geral por marcos narrativos reassume.

O milestone é registrado por `ferramentas/progressao_juppongatana.py`, mas o nível mecânico não é aplicado automaticamente. Depois do desbloqueio, seguir a seção **Progressão mecânica** abaixo.

---

## Quando subir de nível

Subir de nível preferencialmente:

* entre sessões;
* após descanso seguro;
* depois de registrar consequências e estado;
* quando houver tempo narrativo para treino, reflexão, adaptação ou consolidação.

Evitar subir de nível no meio de uma cena perigosa, salvo decisão excepcional registrada.

---

## Registro

Quando um marco for alcançado, registrar em:

```text
sessoes/NNN/experiencia.md
```

ou, se o arquivo ainda não existir:

```text
registros/experiencia.md
```

O registro deve conter:

* sessão;
* nível anterior;
* novo nível, se houver;
* marco alcançado;
* motivo da progressão;
* escolhas pendentes;
* arquivos atualizados.

Para níveis 8–17, o registro de experiência deve apontar também para o milestone correspondente em `narrador/juppongatana/estado-progressao.yaml`.

---

## XP como apoio

XP pode ser anotado apenas quando for útil para comparação com D&D 5e.

Ele não precisa ser somado após cada cena.

Se um encontro for muito arriscado ou se uma recompensa oficial depender de XP, registrar como referência, mas a decisão final de nível continua sendo por marco narrativo.

---

## Progressão mecânica

Ao subir de nível:

1. consultar a ficha atual;
2. consultar regras de classe relevantes;
3. aplicar PV, recursos, proficiência e habilidades novas;
4. registrar escolhas abertas;
5. atualizar `personagens/jogador/ficha.yaml`;
6. atualizar `personagens/jogador/resumo-de-poderes.md`;
7. registrar o marco.

Habilidades novas devem ser interpretadas de forma coerente com a história de Ren, especialmente treinamento monástico, técnicas de sombra, contatos locais e experiência real adquirida em Ravens Bluff.
