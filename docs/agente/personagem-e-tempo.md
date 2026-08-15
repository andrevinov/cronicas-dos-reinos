# Personagem, progressão, recursos e tempo

Este documento é referência para criação e progressão do personagem, inventário, recursos e cronologia. Não deve ser carregado em cenas sem relação com esses assuntos.

## Ficha canônica

A ficha deve permanecer em formato estruturado, preferencialmente YAML. Conforme a edição, deve representar identidade, ancestralidade ou espécie, classe e nível, antecedentes, atributos, perícias, proficiências, defesas, pontos de vida, condições, recursos, magias, equipamentos, experiência, idiomas, características e escolhas de progressão.

Não alterar a ficha silenciosamente. Toda mudança deve ter origem rastreável: criação, subida de nível, item recebido ou perdido, dano, cura, efeito temporário, decisão de regra ou correção documentada.

Durante narração ao vivo, origem rastreável **não significa reescrever a ficha a cada ação**. A mudança entra primeiro em `runtime/eventos-pendentes.jsonl`; a ficha é sincronizada na consolidação.

## Criação de personagem

Ao orientar criação:

1. consultar edição e fontes autorizadas;
2. apresentar apenas opções permitidas;
3. explicar pré-requisitos;
4. conferir cálculos;
5. distinguir eficiência mecânica de coerência narrativa;
6. não escolher pelo jogador;
7. registrar decisões finais;
8. produzir histórico inicial compatível com cenário e período.

Sugestões podem ser qualificadas como mecanicamente fortes, narrativamente adequadas, versáteis, especializadas ou arriscadas, sem substituir a escolha do jogador.

## Experiência e progressão

Toda experiência recebida ou marco alcançado deve ser rastreável. Durante sessão ativa, o ganho pode ser registrado como delta/evento transacional; a atualização da ficha, arquivo de experiência e nível ocorre em consolidação ou quando a decisão de progressão exigir checkpoint canônico.

Ao conferir progressão, considerar total anterior, ganho ou marco pendente, estado atualizado, nível correspondente, opções disponíveis, recursos adquiridos e escolhas pendentes.

Ao orientar evolução, listar opções válidas, indicar pré-requisitos, explicar impactos mecânicos, relacionar opções ao histórico quando útil, identificar necessidade de treinamento, mentor ou acesso quando a campanha exigir e atualizar a ficha somente depois da decisão do jogador.

Caminhos possíveis de crescimento podem ser documentados, mas não obrigam Ren a segui-los.

## Inventário e recursos

Registrar itens, quantidades, peso quando relevante, localização, cargas, munição, moedas, consumíveis, empréstimos, propriedade contestada e identificação quando esses aspectos importarem. Evitar microgerenciamento de objetos triviais salvo quando o tom ou a situação tornarem isso relevante.

Durante narração, mudanças imediatas devem ser deltas mínimos. Exemplos:

```json
{"alvo":"estado","op":"inc","caminho":"recursos.pontos_de_vida.atuais","valor":-7}
{"alvo":"estado","op":"inc","caminho":"recursos.ki.atuais","valor":-1}
{"alvo":"estado","op":"inc","caminho":"recursos.dinheiro.po","valor":-2}
```

Para item adquirido/perdido, usar `append`/`remove` no caminho pertinente quando isso for suficiente para a futura consolidação. Não editar simultaneamente ficha, estado, inventário e transcrição para registrar o mesmo fato.

`contexto.py status` e `contexto.py cena` projetam deltas de PV, Ki, dinheiro, CA, deslocamento e outros campos suportados sobre o snapshot-base. Assim, o valor operacional permanece correto antes da consolidação.

## Descansos

Descanso curto ou longo pode produzir vários efeitos previsíveis. Registrar os efeitos em **uma única transação** do turno: recursos recuperados, tempo transcorrido, duração/expiração de efeitos e mudança de cena relevante. Não fazer uma chamada/patch separado para cada recurso.

A consolidação posterior sincroniza os destinos canônicos necessários.

## Tempo, viagem e calendário

Manter cronologia consistente. Registrar quando relevante data do mundo, hora aproximada, duração de viagens, descansos, prazos, eventos marcados, estações, duração de efeitos e avanço de planos externos.

Durante uma sessão ativa, tempo novo deve entrar primeiro como delta de `tempo` ou de `estado.tempo`, por exemplo:

```json
{"alvo":"tempo","op":"set","caminho":"hora_aproximada","valor":"08:17 de 7 Eleasis"}
```

`contexto.py` aplica esse delta imediatamente ao estado efetivo. `estado/tempo.yaml` continua representando o último checkpoint consolidado até a consolidação em lote.

Para viagens considerar distância, terreno, transporte, ritmo, clima, interrupções e regras da edição. Não deslocar o personagem instantaneamente na narrativa sem considerar tempo e consequências, salvo magia ou elipse explicitamente adotada.
