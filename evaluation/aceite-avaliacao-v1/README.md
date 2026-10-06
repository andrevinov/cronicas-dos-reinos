# Referência de aceite da avaliação — AMV-01

**Data:** 2026-10-04. **Estado:** referências congeladas antes das correções.
**G0 na fotografia AMV-01:** pendente. As referências abaixo continuam congeladas.
**Atualização AMV-05:** G0 demonstrado na 024 existente, com 19/19 checks e provas
no navegador. [Entrega e limites](../../docs/roadmaps/auditoria-e-mundo-vivo/amv05-dashboard-e-series.md).
Não é aprovação dos módulos de runtime nem uma nova sessão de jogo.

## Entrega AMV-05

- [Revisão da mesma 024](../sessions/024/revisoes/amv05/manifest.json): origem e versões históricas preservadas, selecionável no dashboard.
- [Entrada congelada](entrada-s024-amv05.json): configurações e hashes do código/interface, sem rollout privado.
- [Aceite final](resultado-amv05-final.json): 19/19 checks; `resultado-amv05.json` preserva uma medição intermediária da implementação.
- [Integridade e reprodução](integridade-s024-amv05.json): original intacto e duas reproduções idênticas.
- [Verificação final](verificacao-amv05.json): 366 testes de domínio, 2 em Chrome, 226 checks anteriores, schemas e save preservados.

O painel distingue operação, cobertura e experiência: 13 pareceres, 8 conclusões
verificadas, 5 indeterminadas revisadas e 395 unidades ainda sem parecer.
Uma violação de agência em `S024-I0011` tem prova, diagnóstico e correção proposta
acessíveis. O G0 aceita esta demonstração utilizável, sem generalizar desempenho
dos doze módulos ou fingir execução de runtime posterior.

## Entregas e limites

O [catálogo instalado](../catalogo-modulos-v2.json) tem contratos para as **34
capacidades dos 12 módulos**. Cada contrato identifica objetivo de jogo, gatilho
legítimo, fontes, resultado verificável, negativa válida, falha observável,
responsável, unidade, guardrails e tratamento de ausência de evidência.
Operação, oportunidade, efeito persistente e experiência são dimensões distintas.
Os contratos são validados por `catalogo_avaliacao.py`; o avaliador ainda precisa
consumi-los na AMV-04. As versões das implementações e da régua operacional não
mudam nesta tarefa, pois seu comportamento de avaliação permanece o anterior.

Uma evidência permite uma conclusão provisória sobre aquela unidade. A política
de três sessões comparáveis e dez oportunidades por módulo delimita o processo
longitudinal; não é garantia estatística nem condição para corrigir a visualização
da sessão 024. Guardrails não podem ser compensados pela média. Fonte insuficiente
produz indeterminação fora do denominador, sem transformar silêncio em aprovação.

Este pacote contém:

- [Manifesto](manifest.json): seleção dos casos, expectativas justificadas e hashes.
- [Resultado inicial](resultado-inicial.json): observações do código anterior às
  correções, separadas do gabarito, com identificação do código medido.
- [Gabarito histórico da 024](gabarito-s024.json): fontes verificáveis, julgamentos
  confirmados ou pendentes e limites da reconstrução de contexto.
- [Inventário de cobertura](inventario-cobertura.json): checks diretos, composição,
  wrappers históricos, propriedades, testes candidatos, CI, custo e destinos.
- `config/`: cópias deliberadamente congeladas do catálogo e das metas aplicáveis
  ao experimento. Não descrevem obrigatoriamente versões futuras.
- `entradas/`: cenários sintéticos isolados; não são episódios realmente jogados.

## O que a medição inicial demonstra

Foram medidos **11 casos de desenvolvimento, com 17 verificações: 7 falharam**.

| Problema | Resultado observado | Resultado exigido |
| --- | --- | --- |
| Conclusão YAML | Resultado terminal é sucesso, mas escrita bem-sucedida é zero | Uma escrita bem-sucedida |
| Subfase legítima de NPC | Um órfão e cobertura incompleta | Nenhum órfão; cobertura completa |
| Recibo órfão sem atividade reconhecida | `sem_atividade` | `falha_instrumentacao` |
| Iniciativa omitida com causa e canal elegíveis | Nenhuma omissão avaliada | Omissão identificada independentemente de recibo |
| Painel com medição bloqueada da 024 | Faixa saudável e nota principal numérica | Bloqueio impede conclusão de saúde e nota conclusiva |

Os controles de saída com erro, resultado ausente e fase inventada passam.
Uma consulta inteiramente OFF também preserva a inatividade legítima do NPC,
com qualidade indeterminada, em contraste com a iniciativa elegível omitida.
Os cenários mínimos de qualidade inadequada e ausente também passam: preservam
zero e indeterminação, respectivamente, e não aprovam a sessão mínima. **Esses
controles não reproduzem, por si sós, toda a falha de apresentação de qualidade.**
A regressão do painel executa suas funções reais de apresentação sobre o
scorecard bloqueado; não é um teste completo do navegador ou da geração da 024.

O resultado vermelho é a prova inicial solicitada pela AMV-01. Não foi conectado
como mais um gate do preflight. AMV-02 corrige contagens; AMV-03 corrige associação
de recibos; AMV-04 avalia finalidade e omissões; AMV-05 demonstra a entrega no painel.

## Reprodução

```bash
# Valida fontes, contratos, hashes e justificativas; não aprova o avaliador.
poetry run python ferramentas/verificar_aceite_avaliacao.py --validar

# Compara o código atual com expectativas congeladas; exit 1 = divergência.
poetry run python ferramentas/verificar_aceite_avaliacao.py --medir

# Salva uma nova observação sem sobrescrever medições anteriores.
poetry run python ferramentas/verificar_aceite_avaliacao.py --medir \
  --saida /tmp/avaliacao-regressoes-nova.json
```

A observação do painel requer Node.js. Fonte ou dependência ausente impede
confirmar o caso; não conta como acerto. `--validar` verifica os artefatos, enquanto
`--medir` executa o avaliador existente em diretórios temporários. Nenhum comando
altera estado, runtime, sessão ou pacotes históricos.

Para conferir também a fonte histórica, usar `--validar --fonte <rollout-local>`.
Localizar no armazenamento local do Codex a sessão
`01a0aac8-9b23-7c12-9520-be10b50ed451`. O verificador lê somente o prefixo de
**2.098.214 bytes**, confere o SHA-256 registrado e as **7 âncoras de texto**.
O bruto não é copiado nem versionado. O pacote antigo da 024 permanece preservado.

## Reserva e independência do gabarito

Existe um caso sintético reservado e um recorte histórico reservado. Foram
validados para integridade, mas não medidos contra o detector nesta entrega.
O desenvolvimento usa o conjunto padrão; `--conjunto reservado` ou `todos`
fica para a verificação após os ajustes, com resultado novo e identificado.

Expectativas foram definidas por contrato e leitura das fontes, antes de corrigir
o medidor; observações foram extraídas separadamente. Isso **não equivale a
validação cega por um terceiro**. A reserva é de uso, não uma alegação de autoria
independente. Um julgamento pendente, como a necessidade do teste contestado na
024, não se torna falha confirmada pela reclamação nem sucesso pela ferramenta.
Não completar lacunas históricas com o estado atual da campanha.

Depois do congelamento, não alterar expectativas para acompanhar resultados.
Correção justificada de referência exige versão nova, motivo e preservação da
anterior; comparar sempre manifesto e código identificados.

## Inventário do preflight

Os **31 checks diretos passaram em 19,727 segundos** na medição local anterior
às mudanças. O hash protegido do save permaneceu igual. O custo inclui chamadas
internas e nove testes do aceite modular, mas não a suíte integral. Não mede tokens
nem custo da CI. O mapa estático foi concluído nesta tarefa e declara esse escopo.

Há **sete reexecuções exatas** dentro da auditoria final e **nove testes ancorados**
também alcançados pelo discovery integral. Outros quatro comandos internos da
auditoria precisam ser comparados semanticamente com as fachadas. A CI tem
repetições próprias, registradas por arquivo, job e passo.

Cada candidato tem propriedade, responsável atual, origem, destino condicional
e prova exigida antes de retirada. Relação por nome/componente ou AST é triagem,
não equivalência comprovada. A AMV-15 deve demonstrar a mesma falha no substituto.
Nenhum check, teste, workflow ou proteção foi desabilitado pela AMV-01.

## Verificação da implementação

Os 23 testes focados de catálogo e objetivos passaram. A suíte integral executou
2.352 testes: quatro falhas e um erro. Os mesmos cinco casos foram reproduzidos
numa cópia isolada da revisão anterior à AMV-01. A suíte integral continua
reprovada por problemas preexistentes; esta tarefa não a declara verde.
Os casos e a comparação estão registrados em
[verificacao-implementacao.json](verificacao-implementacao.json).

## Próximo aceite

**AMV-02 concluída:** a decisão operacional foi unificada. A
[nova observação](resultado-amv02.json) corrige a escrita YAML e deixa seis
divergências das AMV-03–05. A [reanálise operacional da 024](operacoes-s024-amv02.json)
identifica 11 sucessos, duas falhas e dois resultados desconhecidos entre as 15
escritas, preservando chamadas e tokens nativos. O
[registro de verificação](verificacao-amv02.json) declara o escopo dos testes.
Manifesto, entradas, expectativas e resultado inicial acima são históricos e
permanecem congelados; novos resultados usam arquivos próprios.

**AMV-03 concluída:** o [resultado novo](resultado-amv03.json) passa as três
verificações de associação e preserva o controle de fase inventada. Restam três
divergências das AMV-04–05. A [reanálise de atividades da 024](atividades-s024-amv03.json)
associa 131 passagens, incluindo duas conclusões de iniciativa, com zero órfãos.
As oito passagens cujo resultado operacional é inconclusivo conservam esse estado;
associação não significa execução aprovada nem qualidade medida. Versões de
produtor ausentes no histórico continuam ausentes. O
[registro de verificação](verificacao-amv03.json) documenta os 321 testes focados,
as 226 comparações do corpus anterior e a preservação do save. Nenhum gate foi
desabilitado. Detalhes e comando de reprodução estão na
[entrega AMV-03](../../docs/roadmaps/auditoria-e-mundo-vivo/amv03-atividades-e-recibos.md).

**AMV-04 concluída:** a [observação com ambos os conjuntos](resultado-amv04.json)
passa **17 de 19 verificações**, incluindo omissão sem recibo e o caso reservado.
Restam duas divergências de apresentação, previstas para AMV-05.
A [revisão da experiência da 024](experiencia-s024-amv04.json) verifica o prefixo
original e suas sete âncoras; entrega **13 pareceres**, oito confirmados e cinco
indeterminados, sem aprovar critérios carentes de fonte.

O [relatório legível](relatorio-s024-amv04.md) distingue os pontos confirmados da
reclamação sobre I0005, a iniciativa própria de Mori e a espera voluntária não
autorizada em I0011. A frustração declarada pelo jogador e a promessa limitada
continuam legítimas nos respectivos aspectos. A [verificação](verificacao-amv04.json)
registra **335 testes direcionados**, 226 comparações anteriores, schemas e
preservação das fontes/save. Os [pareceres de entrada](pareceres-s024-amv04.json)
são revisão pós-hoc por Codex, sem alegar validação cega por terceiro.

Manifesto, entradas, expectativas e resultados AMV-01–03 permanecem congelados.
Nenhum gate de preflight foi removido. O G0 aguarda apresentação da revisão
derivada no dashboard; não exige nova sessão. As mudanças de runtime continuam
condicionadas ao G0.
