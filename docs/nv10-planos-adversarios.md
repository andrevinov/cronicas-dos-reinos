# NV-10 — Planos adversários produzem operações próprias

## Responsabilidade e autoridade

Um antagonista estratégico pode iniciar uma operação porque seu plano, objetivo e
condições chegaram à oportunidade registrada. A origem não precisa ser uma reação
a uma sidequest ou à ação mais recente de Ren. O plano NV-08 conserva intenção,
próximo passo e último resultado; a Task51 continua sendo a única autoridade de
compromisso, reservas, encontros, canais e resolução da operação.

Não existe scheduler, catálogo de estratégias ou chamada de IA por antagonista.
`planos_adversarios.py` é um adaptador entre contratos existentes. Preparar uma
operação não a executa; competência permite tentar, sem conceder sucesso.

## Origem e proposta

Primeiro, um fato narrado registra `plano:<id>` para agente `estrategico`, com
`resolucao.tipo: operacao`. O objetivo precisa ser literal no perfil do agente; o
passo fixa ação, instante, local, condições e conhecimento. Seu `operacao_id` será
o ID da operação Task51.

Ao preparar o grupo pela porta existente `operacoes_concorrentes.py preparar`, a
operação pode usar `origem_plano` no lugar de `reaction_id` e `alternative_id`:

```yaml
id: tomar_arquivo
origem_plano:
  id: tomar_arquivo
  revisao: 1
  alternativa:
    id: extrair_registro
    tipo: furtiva
    titulo: Extração do registro
    objetivo: Impedir que a rota seja reconstruída.
    resultado_possivel: A célula pode remover o registro exposto.
    capacidade_id: extrair_registro
    conhecimentos_requeridos: [arquivo_revelado]
    alvos: [{id: arquivo_publico, tipo: informacao}]
    recursos_exigidos: [equipe de extração]
    exige_presenca_fisica: true
    grupo_exclusividade: extracao
    gravidade: moderada
    reversibilidade: reversivel
    classe_impacto: juridico
    bloqueios_causais: [O arquivo deixa o local antes do compromisso.]
  implantacao:
    arquivo: narrador/agentes/rede_fixture.yaml
    caminho: implantacoes.celula_arquivo
    valor:
      local: arquivo_publico
      celula_id: celula_arquivo
      estado: disponivel
      em_deslocamento: false
      recursos: [equipe de extração]
```

O restante mantém o schema Task51: alvo, local, objetivo operacional, célula,
atores, recursos, dependências, bloqueios, sinais e mecânica. O exemplo é sintético.
Não deve ser copiado para o save da campanha.

## Gates antes do compromisso

A preparação é read-only e confere:

- plano ainda em `pretende`, revisão atual e responsável estratégico;
- ação/local/ID da operação idênticos ao próximo passo;
- janela posterior ao instante do passo;
- objetivo da alternativa idêntico ao objetivo canônico do agente;
- capacidade presente nos métodos operacionais;
- conhecimento próprio com fonte e evidência literal;
- alvo e consequência declarados antes do resultado, sob Task44/Protected Core;
- recursos existentes no agente e coincidentes entre plano, alternativa e operação;
- implantação explícita da célula no local, disponível e sem deslocamento;
- composição, ameaça e saídas congeladas pela Task51 quando houver mecânica.

Uma fonte ausente ou uma revisão obsoleta bloqueia antes da escrita. Materialização
usa o journal existente e instala contrato, índice, estado e fila atomicamente.
Retry termina a mesma instalação sem criar reação fictícia ou duplicar pendências.

## Compromisso, resolução e continuidade

O grupo entra na fronteira normal. `resolver_fronteira.py aplicar` compromete as
operações válidas antes de qualquer escolha de Ren. Cada célula e recurso recebe
reserva própria; a reserva também impede que a Task50 reutilize o mesmo recurso.
Bloquear uma frente por prova causal não apaga as demais.

Depois do compromisso, o plano registra `tentar` no lote NV-08. Enquanto a
operação está em curso, sua pendência e a do plano coexistem. O hot path trata o
plano como dependente e apresenta a pressão Task51; ele não fica preso atrás da
própria barreira nem ganha uma avaliação adicional de IA.

`operacoes_concorrentes.py resolver` exige consequência factual, `desfecho`
estruturado e, quando aplicável, uma primeira rolagem ligada ao encontro congelado.
A resolução do mundo e a retirada da pendência são atômicas para operações de
plano. A outra frente continua comprometida até o próprio resultado.

## Informação e adaptação

O resultado remoto não aparece instantaneamente no conhecimento do antagonista.
Um canal Task51 cujo destinatário seja o próprio agente declara fatos permitidos,
prova de disponibilidade e atraso positivo. O atraso começa na resolução, não no
início da operação. A entrega revalida o canal e sua prova.

Somente depois dessa entrega o evento `resolver` do plano pode escolher
`prosseguir`, `mudar_estrategia`, `bloquear`, `desistir` ou `concluir`. O recibo do
retorno acompanha o resultado do plano. Ausência de informação mantém o plano e
sua pendência intactos; não autoriza onisciência, sucesso retroativo ou adaptação.

## Persistência, orçamento e testes

Contratos de grupos e encontros continuam nos artefatos Task51; planos continuam
no estado do mundo NV-08; conhecimento e capacidade continuam no agente. Não há
arquivo paralelo de verdade. Journals interrompidos bloqueiam novo preparo até o
retry da mesma operação.

`tests/test_planos_adversarios.py` usa somente diretórios temporários e cobre duas
frentes sem sidequest, capacidade/conhecimento/implantação/recursos, revisão
obsoleta, pressão jogável, resultado remoto, atraso de informação, adaptação,
idempotência e recuperação de materialização/resolução. Os perfis `cronica` e
`mundo` incluem todos os testes permanentes `test_planos*.py`.
