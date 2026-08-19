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

### Data + hora são um único fato

Durante sessão ativa, uma mudança do instante corrente deve entrar como **um único delta atômico**:

```json
{
  "alvo": "tempo",
  "op": "instante",
  "valor": {
    "data": "11 Eleasis, 1372 DR",
    "hora": "05:10"
  }
}
```

Regras obrigatórias:

- `hora` contém somente `HH:MM`;
- nunca escrever `"05:10 de 11 Eleasis"` em `hora`;
- não enviar data e hora como fatos independentes;
- mudança de dia exige a nova `data` explicitamente no mesmo `instante`;
- uma transação aceita no máximo um `tempo/instante`;
- não misturar `tempo/instante` com deltas diretos para `tempo.data_atual`, `tempo.hora_aproximada`, `estado.tempo.data_exata` ou `estado.tempo.hora_aproximada`.

Um par legado completo e consistente de data+hora pode ser normalizado pela camada transacional para o formato novo, mas **o JSONL novo permanece com um único delta temporal**. Um campo isolado, uma data divergente ou hora com data/prosa embutida falha antes das duas escritas do turno.

`contexto.py` expande o instante somente em memória para projetar data+hora imediatamente. Na consolidação, o mesmo delta é expandido apenas dentro do plano de staging; `estado/tempo.yaml`, `estado/estado-atual.yaml` e runtime são derivados juntos e instalados pelo journal multiarquivo existente. Portanto não existe estado persistente válido em que apenas metade do instante novo foi instalada.

Os arquivos canônicos antigos podem ainda conter `hora_aproximada` com texto histórico do tipo `15:30 de 11 Eleasis`. Isso é tolerado para leitura/migração; **novas escritas não usam esse formato**.

### Autoridade de prazos e alertas temporais

`estado/tempo.yaml:prazo_relevante` é a **fonte autoritativa única** para texto livre de efeitos em duração, vencimentos e alertas temporais do checkpoint corrente. A cópia histórica `estado/estado-atual.yaml:tempo.prazo_relevante` é legado de uma representação anterior e não deve ser mantida como espelho obrigatório.

O runtime deriva `prazos_e_alertas` de `estado/tempo.yaml` e só aceita o campo legado do estado como fallback de migração. Essa regra evita que duas paráfrases igualmente válidas do mesmo conjunto de prazos bloqueiem um checkpoint.

Data, hora aproximada, período do dia e clima continuam com espelhamento/consistência rígidos onde a arquitetura exigir; a exceção é específica para o campo textual `prazo_relevante`.

Para viagens considerar distância, terreno, transporte, ritmo, clima, interrupções e regras da edição. Não deslocar o personagem instantaneamente na narrativa sem considerar tempo e consequências, salvo magia ou elipse explicitamente adotada.
