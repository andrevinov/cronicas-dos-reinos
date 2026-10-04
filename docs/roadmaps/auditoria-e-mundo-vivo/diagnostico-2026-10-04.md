# Diagnóstico que fundamenta o roadmap

**Data:** 2026-10-04. **Natureza:** inspeção de código e artefatos existentes,
com reproduções isoladas. Não descreve uma implementação deste roteiro.

## Defeitos comprovados na avaliação

| Evidência | O que foi observado | Correção |
| --- | --- | --- |
| Dois classificadores operacionais | Um resultado YAML com `estado: concluido` é sucesso no ledger moderno, mas fica desconhecido no contador herdado de escrita. A reprodução mínima resultou em sucesso operacional e zero escritas bem-sucedidas. | AMV-02 |
| Fase legítima de NPC sem associação | O produtor emite `concluir_iniciativa`; o detector espera `concluir`. Um recibo adicional legítimo bloqueia a cobertura como órfão. | AMV-03 |
| Scorecard 024 | Registra 85,1 e faixa `saudavel`, embora a medição esteja bloqueada e apenas 2 de 12 módulos participem da agregação. | AMV-05 |
| Qualidade da sessão 024 | `avaliacoes-qualidade.json` tem `assessments: []`. Os denominadores de qualidade dos módulos estão vazios. | AMV-04 |
| Qualidade não determina o eixo operacional | Na reprodução controlada, qualidade adequada → inadequada mudou qualidade de 100 para 0, mas manteve nota operacional 100 e rótulo operacional positivo. | AMV-04–05 |
| Indicadores estruturais de narração | Rodapé correto e presença de bloco mecânico alimentam efeitos positivos. Isso prova entrega estrutural, mas não continuidade, iniciativa, coesão ou dramaticidade. | AMV-01, AMV-04 |
| Cobertura sem atividade reconhecida | Recibos órfãos de um módulo sem atividade detectada podem terminar como ausência de atividade, em vez de erro explícito de instrumentação. | AMV-03 |

Fontes: [classificador herdado](../../../ferramentas/_analisar_rollout_core.py),
[detector atual](../../../ferramentas/analisar-rollout.py),
[produtor de NPC](../../../ferramentas/npc_continuity_and_social_behavior.py),
[gerador](../../../ferramentas/gerar-avaliacao-sessao.py),
[scorecard 024](../../../evaluation/sessions/024/scorecard.json),
[qualidade 024](../../../evaluation/sessions/024/avaliacoes-qualidade.json) e
[dashboard](../../../evaluation/dashboard/app.js).

A nota 85,1 não demonstra que a experiência foi boa ou ruim. Demonstra que um
número operacional parcial está sendo apresentado com destaque e classificação
que permitem uma leitura mais forte do que os dados sustentam.

**Verificação adicional para reanálise:** o rollout original da 024 foi localizado
no armazenamento local do Codex. Seu corte de 2.098.214 bytes tem o mesmo hash do
manifest e termina em linha completa. O nome `fonte-congelada.jsonl` no manifest
é o descritor do recorte temporário usado pelo gerador; não significa que o bruto
está versionado em `evaluation/sessions/024`. É possível reprocessar esse corte
sem jogar novamente, preservando o pacote original e suas limitações históricas.

## Limitações de ativação observadas no código

- A iniciativa social pode retornar sem avaliar candidatos quando não existe
  seleção explícita de interlocutor. Participante prospectivo, presença física
  e canal de contato são conceitos distintos e devem continuar separados.
- O motivo social estruturado é estreito, e o perfil decisório curado depende de
  três pilotos e de correspondência com papéis textuais específicos. O mecanismo
  não generaliza automaticamente para o elenco relevante.
- A causa de sidequest viva é descoberta a partir de causas e planos já
  estruturados. Recusar oportunidade manualmente não deve esconder uma causa
  vencida, mas a existência desse gate não prova oferta suficiente de aventuras.
- Vários componentes são compostos por `exec` de versões anteriores e alteração
  de funções globais. Isso dificulta saber qual caminho foi executado e eliminar
  código antigo sem alterar contratos instalados.

Fontes: [iniciativa](../../../ferramentas/iniciativa_elenco.py),
[anexo de memória e iniciativa](../../../ferramentas/memoria_cena_iniciativa.py),
[perfis decisórios](../../../ferramentas/personalidade_decisoria.py),
[causas de sidequest](../../../ferramentas/sidequests_vivas.py),
[orquestrador](../../../ferramentas/cronica.py) e
[planos de personagens](../../../ferramentas/planos_personagens.py).

**Inferência a validar:** essas restrições ajudam a explicar passividade e baixa
oferta de aventuras. Elas não provam que toda ausência de iniciativa foi erro.
AMV-04 e AMV-14 devem separar oportunidade perdida de silêncio coerente.

## Estado instalado e cobertura comportamental

Na inspeção dirigida do estado consolidado reservado, havia agentes ativos,
mas nenhum `planos_personagens` naquele arquivo de mundo; a agenda tinha
agendamentos de outras categorias, sem avaliação de plano de personagem nessa
categoria específica. O estado de oportunidades tinha três missões terminais
e nenhuma ativa. Havia clima regional registrado; não havia a raiz de política
cívica naquele estado.

Esses dados são uma fotografia do diagnóstico. **Não demonstram ausência em
toda a história nem incluem, sozinhos, pendências ainda não consolidadas.**
AMV-07 deve reconciliar o estado efetivo e as fontes necessárias antes de
qualquer migração. Zero missões ativas também pode decorrer de escolhas legítimas.

Acesso reservado foi motivado por verificar se as capacidades de autonomia,
agenda, sidequest e instituições estavam de fato instaladas. Este documento
não reproduz planos secretos nem eventos futuros.

## O que já existe e deve ser aproveitado

- Intenções canônicas admitem satisfazer, transformar, adiar e reancorar, com
  núcleo protegido. Eventos devidos não podem virar no-op.
- Planos, operações adversariais, compromissos, memória durável, recompensas
  transacionais e frontiers já oferecem primitivas causais.
- Clima diário tem reserva determinística; política cívica distingue medida,
  publicação e entrega; permanência espacial consegue projetar contexto local.
- O benchmark narrativo já dispõe de episódios sobre reencontro, promessa,
  confiança, iniciativa fora de cena, frentes adversárias e retomada fria.

O roteiro deve tornar essas capacidades alcançáveis e demonstradas em conjunto.
Criar outra agenda ou outro writer acrescentaria divergência ao problema.

## Aceites atuais: alcance e limites

O corpus de avaliação passou **226/226**, em 19 casos, e a amostra externa passou
**6/6** no diagnóstico. Isso é evidência positiva dos recortes exercitados, mas
a amostra externa é operacional e pequena; não avalia os objetivos narrativos.

`experiencia_integrada.py check` valida piloto, perfis e instruções. Não executa
a avaliação de um novo episódio narrado. `aceitacao_vivacidade.py check` avalia
candidatas e cobertura previamente fornecidas em cenários; sua cadeia de rollout
usa a fixture operacional antiga `rollout-step11-mini.jsonl`. O aceite modular
v2 exerce integração técnica e distingue fixture de sessão real, o que deve ser
preservado; ele não substitui avaliação semântica independente.

Consequentemente, é possível ter checks verdes sem a prova necessária de que o
modelo viu a causa, decidiu de modo coerente, narrou o efeito e o lembrou depois.

## Preflight e CI

O inventário efetivo de `preflight.checks(incluir_testes=False)` contém **31
verificações diretas**. Não é a contagem total de processos ou assertions:
fachadas chamam validadores internos; a auditoria final chama outros comandos.

`gate_baseline_and_regressions` da auditoria executa **11 comandos**, mesmo com
`--sem-testes`: sete aparecem também como comandos diretos do preflight; quatro
precisam de comparação de cobertura com as fachadas de operação e memória.
O workflow de Integridade repete parte desses comandos e o de Preflight adiciona
um benchmark sobre a fixture antiga. O aceite modular também executa nove testes
ancorados, já alcançados pela suíte integral.

Há oportunidade concreta de reduzir execuções. A
[matriz de desativação](matriz-de-desativacao-2026-10-04.md) identifica o que pode
sair, o que precisa ser substituído e o que deve continuar protegido.
