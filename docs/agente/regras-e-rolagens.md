# Regras, decisões e rolagens

Este documento reúne obrigações antes presentes no `AGENTS.md` sobre manuais de regras, fidelidade, decisões e dados. Consultá-lo quando a tarefa for mecânica; não carregá-lo preventivamente para cenas sem dúvida de regra.

## Manuais de regras

Os arquivos em `regras/` devem funcionar como referência rápida durante o jogo, não como reprodução de livros inteiros. Cada resumo deve, quando aplicável:

- indicar edição e fontes;
- explicar a regra em português claro;
- incluir fórmulas ou passos necessários;
- registrar exceções relevantes;
- separar regra oficial de regra da casa/adaptação;
- trazer exemplos curtos quando úteis;
- registrar dúvidas ainda abertas.

Manuais historicamente prioritários incluem `regras/fontes.md`, `regras/resolucao-de-acoes.md`, `regras/combate.md`, `regras/surpresa.md`, `regras/magia.md`, `regras/descanso-e-cura.md`, `regras/condicoes.md`, `regras/criacao-de-personagem.md`, `regras/progressao.md`, `regras/regras-da-casa.md` e `regras/decisoes.md`. Criar ou completar somente quando a campanha realmente exigir.

Durante a sessão, consultar primeiro o resumo interno pertinente. Livro oficial é nível de escalada, não rotina.

## Contrato de ruleset e migração

A autoridade sobre **qual versão de D&D está ativa** fica em `campanha.yaml`, em `sistema.ruleset`.

Após a ativação concluída pela Task 8:

- `ruleset.atual = dnd_5_5e`;
- `ruleset.alvo = dnd_5_5e`;
- D&D 5.5e é a autoridade mecânica corrente;
- material 2014 só entra por compatibilidade explicitamente aprovada;
- `migracao.status = concluida` e `migracao.ativacao.permitida = true`;
- o gate concluído foi `task_8_auditoria_final`.

A hierarquia mecânica declarada em `campanha.yaml` é:

1. decisões registradas da campanha;
2. regras da casa;
3. ruleset atual;
4. compatibilidade aprovada explicitamente;
5. fontes antigas/adaptadas.

Depois da ativação, uma opção mecânica 5e 2014 só pode permanecer como fallback quando não houver equivalente 5.5e aplicável e houver aprovação explícita. Não misturar rulesets implicitamente.

A migração é prospectiva: preservar decisões antigas até substituição explícita futura e **não reescrever sessões concluídas**, rolagens, recursos, descobertas ou consequências para simular aplicação retroativa de 5.5e.

Materiais de AD&D continuam seguindo a mesma regra conceitual: cenário e aventura podem ser preservados, mas qualquer mecânica que **entre em jogo** é adaptada para o `ruleset.atual`. Durante a migração, novas adaptações persistentes podem ser preparadas diretamente para 5.5e; elas só se tornam elegíveis ao runtime quando `adaptado_para` coincidir com o ruleset ativo.

### Gate formal de material AD&D

A Task 7 torna essa disciplina executável. Prosa narrativa de AD&D não paga gate nem precisa de versão mecânica. Qualquer material AD&D marcado como mecânico ativo/preparado deve declarar `proveniencia_mecanica.edicao_origem`, `adaptado_para` e `fonte_mecanica`; adaptações persistentes são registradas em `regras/adaptacoes-mecanicas.yaml`.

O validador recusa transporte literal de THAC0, CA descendente, salvamentos antigos e campos equivalentes. Para material preparado, AD&D→5.5e é válido como alvo de migração. Para entrar no runtime, porém, `adaptado_para` precisa ser igual ao `ruleset.atual`. Enquanto 2014 estiver ativo, uso AD&D→2014 só passa com `fallback_2014` explicitamente declarado, com motivo e decisão; depois da Task 8 esse mesmo ticket/material deixa de ser elegível se o ruleset mudar.

`cronica preparar --mecanica-json` aceita `proveniencia` somente quando houver esse vínculo com fonte antiga; o gate roda antes de o contrato ser anexado ao ticket. A ausência de `--mecanica-json` continua não abrindo nenhum material mecânico.

## Catálogo executável de regras

`regras/catalogo.yaml` é o índice mecânico dirigido introduzido pela Task 2. Ele não substitui os manuais humanos nem muda a hierarquia da Task 1: cada entrada identifica `id`, aliases, domínio, ruleset, autoridade, fonte humana, resumo interno, executor, persistência e eventual regra da casa.

Para dúvida mecânica conhecida, `contexto regra <termo>` consulta primeiro esse catálogo. Um acerto por `id` ou alias retorna em L2 a identidade da regra, o `ruleset` aplicável, sua autoridade, quem a executa e a seção humana que documenta a decisão. A fonte declarada precisa existir e a seção precisa continuar presente; divergência faz o catálogo falhar fechado.

Enquanto a cobertura do catálogo não for completa, termo não catalogado preserva o fallback textual anterior em `regras/*.md`, explicitamente marcado como `catalogada: false`. Esse fallback não ganha versão, executor ou autoridade por inferência. D&D 5.5e é a regra operacional; fallback textual não pode inventar autoridade 2014.

## Contrato mecânico do turno

`cronica preparar` aceita opcionalmente um contrato mecânico estruturado com IDs/aliases do `regras/catalogo.yaml` e obrigações do turno. Quando presente, o mesmo ticket congela ruleset, regras aplicáveis, parâmetros de teste/ataque/salvaguarda e snapshot de Focus/Focus necessário aos gastos.

A rolagem continua fora de `cronica`, pela CLI `dados`. Em `cronica concluir`, a transação fornece os dados já rolados em `mecanica.resolucoes`; `cronica` os repassa ao núcleo mecânico para reconstruir deterministicamente escolhido, total e resultado. Só depois compara a consequência com os deltas e chama o writer.

Gasto de Focus sem obrigação correspondente é recusado. Mudança do recurso desde `preparar` torna o ticket mecânico obsoleto. O caminho sem mecânica não abre catálogo nem estado adicional e continua em exatamente duas chamadas de orquestração: `preparar` e `concluir`.

### Receita operacional para gasto de Focus

Para um gasto simples, preferir o atalho, que gera uma obrigação `focus_spend` no
mesmo ticket:

```bash
poetry run cronica preparar --cena-id <id-estavel> --sem-oportunidade-sidequest --gasto-focus 1
```

`--gasto-focus` e `--mecanica-json` são mutuamente exclusivos. Quando a regra
específica também precisa ficar congelada — por exemplo, Escuridão pelas Artes
Sombrias — usar o contrato completo:

```bash
poetry run cronica preparar --cena-id <id-estavel> --sem-oportunidade-sidequest \
  --contexto-tag acao:escuridao \
  --mecanica-json '{"regras":["artes_sombrias_escuridao"],"obrigacoes":[{"id":"focus_darkness","tipo":"gasto_recurso","regra":"artes_sombrias_escuridao","recurso":"focus","custo":1}]}'
```

O `cronica concluir` deve confirmar a obrigação e enviar exatamente o delta
previsto pelo preparo:

```json
{
  "deltas": [
    {"alvo":"estado","op":"inc","caminho":"recursos.focus.atuais","valor":-1}
  ],
  "mecanica": {
    "resolucoes": [
      {"obrigacao_id":"focus_darkness","tipo":"gasto_recurso","aplicado":true}
    ]
  }
}
```

A saída de `preparar` fornece `mecanica.resolucao_modelo` e repete o mesmo
modelo em `contrato_conclusao.campos.mecanica`; copiar os IDs do ticket, sem
recriá-los por memória. O atalho usa `obrigacao_id=focus_spend`.

## Ficha mecânica única de Ren

`personagens/jogador/ficha.yaml` é a única fonte persistida dos números mecânicos de Ren. `ferramentas/ficha_ren.py` apenas valida e adapta essa ficha para os consumidores; não mantém cópia numérica própria. O rolador não deve declarar tabelas paralelas de atributos, perícias, passivos, salvaguardas, ataques, CA, iniciativa ou recursos de Ren.

Qualquer comando `ren ...` carrega e valida a ficha antes de chamar o RNG. Ficha ausente ou mecanicamente inválida deve falhar fechado antes da rolagem, em vez de recorrer a valores Python antigos ou defaults silenciosos.

## Núcleo mecânico 5.5e

`ferramentas/mecanica_dnd_5_5e.py` concentra as primitivas mecânicas do ruleset alvo: dados, d20, vantagem/desvantagem, testes, salvaguardas, ataques, críticos e dano. O módulo é interno e genérico: não conhece Ren, ficha, campanha nem apresentação textual. `dados` permanece a CLI pública e adapta entradas/saídas para esse núcleo.

Toda entrada mecânica que puder ser validada sem aleatoriedade deve falhar antes do RNG. Em particular, modo de rolagem, expressão de dados, modificadores e alvos inválidos não podem consumir dado. 1 e 20 naturais têm tratamento automático em jogadas de ataque; testes e salvaguardas continuam resolvidos pelo total contra a CD, sem sucesso/falha automática apenas pelo valor natural. Crítico dobra os dados de dano, não o modificador.

## Contrato de adversários

`narrador/adversarios/contrato.yaml` é a autoridade para blocos mecânicos de NPCs
e criaturas competentes. O registro é fragmentado: ficha-base e especialidade
não combativa são consultas distintas de até 8 KiB. Todo bloco declara ruleset e
proveniência, números defensivos, recursos, traços, ações, grupos explícitos de
ação bônus/reação/ação lendária, táticas e retirada. Escala `lendario` não pode
ser apenas rótulo: exige ao menos uma ação lendária preparada.

Ação preparada possui ativação, gatilho quando aplicável, alcance, alvos,
resolução, efeitos, dano estruturado quando houver, custo, limite e contrajogo.
Testes declaram se o adversário rola com bônus próprio ou se o opositor usa a
própria ficha contra uma CD. Custos só podem referenciar recursos declarados.
Especialidade possui procedimento com resultado de sucesso e falha; prosa como
“é excelente falsificador” não constitui resolução mecânica.
O validador recusa campos extras destinados a ajuste pós-rolagem e qualquer
ruleset divergente do ativo.

`narrador/adversarios/contrato-ameacas.yaml` governa a avaliação pré-rolagem.
Ela compara um patamar autoral de combate ou especialidade ao nível informado e
aplica apenas modificadores explícitos de economia de ações, recursos, terreno e
iniciativa. É uma heurística de preparação, não CR oficial, previsão de resultado
ou licença para corrigir a ficha. `--ren` lê a ficha canônica somente nessa
consulta; o turno comum permanece com zero leitura desta camada.

Aliado só entra no cálculo se já estiver presente, for competente para a ameaça e
tiver motivo causal para ajudar. Resultado letal/esmagador exige sinalização e
saída observável, não intervenção automática. Arquétipos `arquetipo_` permanecem
não canônicos até vínculo explícito com um ator ou criatura da ficção.

`narrador/dungeons/contrato.yaml` exige que geografia, CD, dano, sinalização,
contrajogo e saídas sejam definidos antes da rolagem. Cada encontro referencia um
bloco completo e congela apenas uma avaliação de cenário controlado; na cena real,
avaliar novamente com recursos, terreno, iniciativa, quantidade e aliados atuais.
Nunca usar a classificação do manifesto para substituir a leitura pré-rolagem do
contexto real ou para mudar números depois do dado.

A presença do núcleo 5.5e não muda `sistema.ruleset.atual`: enquanto o gate de migração não for concluído, seu uso por `dados` fica restrito às primitivas cuja semântica é compatível com o ruleset operacional. Nenhuma regra exclusiva de 5.5e pode entrar silenciosamente na narração antes da ativação final.

## Perfil alvo 5.5e de Ren

A Task 8 promoveu a conversão preparada na Task 5. `personagens/jogador/ficha.yaml` e `resumo-de-poderes.md` são agora as fontes operacionais 5.5e; `personagens/jogador/migracao-5-5e.yaml` permanece somente como registro auditável da promoção. Os shims staged da Task 5 foram removidos.

Na ativação, Focus foi mapeado 1:1 para Focus a partir do estado efetivo, sem restaurar nem gastar recurso. Daqui em diante a ficha e o estado usam somente Focus. Os benefícios de criação preservados pela DEC-0008 são decisões de campanha canonizadas, não fallback silencioso de regras 2014.

## Filosofia de fidelidade: aproximadamente 70%

A meta de 70% representa filosofia, não métrica matemática. Aplicar regras quando elas sustentarem risco, tensão, estratégia, diferenciação de personagens, uso significativo de recursos, imparcialidade, consequência ou surpresa legítima.

Pode simplificar quando a aplicação literal causar repetição sem valor, microgerenciamento excessivo, interrupção longa, cálculo irrelevante, rolagem sem consequência ou perda de ritmo sem ganho estratégico.

A simplificação não pode apagar custos, limitações, perigos, chances de fracasso, diferenças entre habilidades, efeitos duradouros ou escolhas táticas importantes.

## Ordem para resolver dúvidas

Parar assim que a dúvida estiver resolvida com segurança:

1. aplicar o resumo canônico interno;
2. verificar decisão anterior equivalente;
3. verificar regras da casa;
4. consultar a fonte oficial do **ruleset atual**;
5. usar compatibilidade previamente aprovada, quando existir;
6. interpretar de modo coerente com o ruleset atual;
7. simplificar pela regra de ouro;
8. registrar a decisão se puder se repetir.

Fonte 5.5e ocupa o passo 4 como ruleset atual; fonte 2014 só entra no passo seguinte quando houver compatibilidade explicitamente aprovada. Durante sessão, não paralisar o jogo por dúvida pequena. Se a pesquisa completa for longa, tomar decisão provisória claramente identificada, registrar a pendência, revisar depois, atualizar `regras/decisoes.md` e corrigir consequências somente quando necessário.

## Regra de ouro

Deve preservar coerência, justiça, ritmo, risco, identidade do sistema e consequências.

Nunca usar para garantir vitória, salvar NPC favorito, invalidar estratégia legítima, forçar trama, esconder erro de preparação, alterar capacidades depois de conhecer a rolagem ou mudar dificuldade retroativamente.

Decisão improvisada com chance de recorrência deve ser registrada em `regras/decisoes.md`, preferencialmente com identificador, sessão de origem, contexto, regra oficial, decisão, justificativa, aplicação futura e estado (permanente, provisória ou aguardando revisão).

## Quando pedir rolagem

Pedir rolagem somente quando coexistirem:

- incerteza real;
- consequência relevante;
- possibilidade plausível de sucesso e fracasso;
- regra, atributo, perícia ou recurso capaz de influenciar o resultado.

Não pedir para ação trivial, conhecimento automático do personagem, tarefa sem pressão repetível até funcionar, ação impossível, ação inevitável ou decisão puramente interpretativa. Quando algo for impossível, explicar pela ficção/regra em vez de oferecer rolagem sem chance real.

## Rolagens abertas

Quando a informação puder ser conhecida, mostrar quando possível:

- o que está sendo testado;
- atributo/perícia/jogada;
- modificadores;
- vantagem/desvantagem;
- dificuldade ou defesa, se conhecível;
- dado;
- total;
- consequência.

Definir modificadores e dificuldade antes do dado, salvo efeitos legitimamente desencadeados depois. Nunca alterar resultado depois de conhecer o valor.

Quando aplicável usar `poetry run dados`; exemplos detalhados ficam em `ferramentas/README.md`. Rolagens abertas relevantes podem ir para a transcrição. Não redescobrir a assinatura por `--help` quando o roteador já a forneceu.

## Rolagens ocultas

Podem ser usadas quando conhecer a existência ou o resultado prejudicaria mistério ou produziria metajogo, por exemplo: armadilha desconhecida, reação secreta de NPC, encontro aleatório, ação de facção fora de cena, detecção de mentira quando a edição justificar, duração desconhecida e acontecimentos não presenciados.

Rolagens ocultas importantes devem permanecer na área do narrador e registrar contexto, fórmula, resultado, consequência e sessão/data do mundo. Nunca usar rolagem oculta para corrigir a história depois do fato.
