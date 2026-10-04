# AMV-15 — Preflight menor, com cobertura demonstrável

**Data:** 2026-10-04. **Status:** proposta. **Dependências:** AMV-06, AMV-14.

## O que implementar

Substituir a composição histórica de checks por um registro explícito de
propriedades, responsáveis, escopo, dependências e modo de execução. Propriedades
distintas de unidade, integração, estado instalado e preservação histórica
continuam distintas; o mesmo comando ou nome não basta para comprovar duplicação.

Dar a cada propriedade obrigatória um dono na CI. A suíte completa é executada
uma vez por revisão pelo workflow responsável. Separar, no aceite modular,
validação de contratos e execução dos nove testes ancorados, evitando que
`--sem-testes` disfarce uma segunda execução da mesma cobertura. Se o dono não
executou ou falhou, o gate continua bloqueado.

Desmembrar a auditoria final: consolidar as chamadas repetidas e preservar seus
ensaios próprios de retomada quente, overlay de pendências, privacidade e
ausência de mutação. O comando público pode continuar compondo um relatório,
sem repetir validações já concluídas no mesmo escopo verificável.

Aplicar a [matriz de aposentadorias](matriz-de-desativacao-2026-10-04.md),
atualizando registros de revisão histórica com propriedade, destino e evidência.
Conservar ferramentas de reparo legítimas fora do caminho obrigatório quando
seus checks permanentes forem substituídos. Antes de renomear ou retirar job,
validar os checks exigidos para merge.

## Por que corrige a causa

Repetir um check não amplia sua capacidade de detectar passividade ou erro de
medição. Donos e provas de sensibilidade permitem reduzir repetição sem retirar
proteção. Aceites comportamentais mais fortes substituem rituais históricos que
validavam a instalação de uma etapa, e não a finalidade atual do módulo.

## Prova de correção e aceite

- Registrar execuções e duração antes/depois em condições equivalentes; mostrar
  quais processos deixaram de repetir trabalho, sem prometer percentual prévio.
- Nenhuma propriedade obrigatória fica sem dono; perda, falha ou ausência do
  resultado desse dono bloqueia o gate.
- Reuso exige mesma revisão e hashes dos dados, código, configuração e ambiente
  relevantes. Mudança no escopo invalida o resultado; receipt antigo não aprova.
- Cada remoção demonstra que a mesma falha é detectada pela cobertura substituta,
  inclusive estado efetivo, não mutação, sigilo, transação e história.
- Suíte completa continua gate de merge; perfis de desenvolvimento não a substituem.
- Fluxo local completo continua disponível. `--sem-testes` passa a descrever
  corretamente o que não executa, sem testes aninhados ocultos.
- Atualizar política, perfis e manuais somente depois do novo fluxo entrar em vigor.

## Onde mudar e o que poderá sair

Preflight, auditoria, aceites, workflows e registros de cobertura. Podem sair
execuções duplicadas, verificações restritas ao piloto e fontes históricas já
substituídas. Não apagar baselines imutáveis, regressões úteis ou engines usados
pelo runtime para reduzir a contagem de arquivos.
