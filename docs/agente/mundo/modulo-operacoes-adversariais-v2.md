# Operações adversariais v2

## Contrato público

`adversarial_operations.py` é a única fachada pública do domínio. Ela reúne:

- integridade do contrato adversarial: capacidade, conhecimento, risco, limites
  e consequências congelados;
- operações simples ou simultâneas: janela, frentes, recursos exclusivos,
  encontros, execução e entrega de informação.

`integridade_adversarial.py` e `operacoes_concorrentes.py` continuam como motores
internos e portas de compatibilidade. Seus contratos, índices, estados,
encontros e journals não foram migrados nem reescritos. A fachada não cria
estado, scheduler, RNG ou writer paralelo.

## Lifecycle

Toda operação percorre o mesmo contrato, tenha uma ou várias frentes:

```text
proposta read-only
→ materialização do plano reservado
→ compromisso e reserva de recursos
→ encontro/mecânica congelados
→ execução factual por frente
→ consequência ou informação entregue por canal
```

`materializar` registra a proposta e sua pendência; ainda não autoriza o efeito.
`comprometer` revalida capacidade, conhecimento, presença, recursos e janela,
reserva cada frente e congela seu encontro antes de narração ou rolagem.
Alternativa bloqueada recebe bloqueio causal e não vira fato.

Operações simultâneas continuam identificáveis pela subcapacidade
`concurrent_operations`. Ator, célula, recurso ou capacidade exclusiva não pode
ser reservado por duas frentes. A ordem técnica é determinística, mas não define
prioridade ficcional nem muda resultados já comprometidos.

## Autoridade e conhecimento

Direção canônica é destino, nunca autorização para agir. Uma operação nasce de
reação causal ou passo de plano estratégico validado. Poder, recurso,
implantação e conhecimento precisam existir antes da proposta e são revalidados
antes do compromisso.

Presença de Ren em uma frente não encerra as demais nem concede conhecimento
remoto. A visão do jogador passa somente por percepção direta no mesmo local ou
por canal declarado que cumpriu seu atraso. O snapshot reservado de contrato e
ameaça nunca deve ser anexado diretamente à projeção do jogador.

Dificuldade, composição, rotas, risco e consequências ficam congelados. Sucesso
de Ren ou primeira rolagem não autoriza aumentar dificuldade, trocar composição
ou escolher retrospectivamente uma consequência mais severa.

## Eventos e telemetria

A fachada anexa um recibo observacional aos resultados existentes:

- `evento_modular: consulta`: proposta, projeção, reavaliação ou retry sem nova
  mutação;
- `evento_modular: compromisso`: reserva efetiva ou mecânica congelada;
- `evento_modular: efeito_material`: operação resolvida ou informação entregue
  pela primeira vez.

`quantidade_frentes` e `operacoes_simultaneas` distinguem operação simples de
concorrência. Os aliases v1 resolvem para subcapacidades do mesmo pai e o custo
aditivo fecha uma única vez em `adversarial_operations`.

Integridade também é publicada em `avaliacao_guardrail`, sempre com
`participa_media_modular: false`. Uma violação permanece visível e não pode ser
compensada por nota alta do módulo.

## Operação e manutenção

No jogo comum, operações comprometidas continuam chegando por `cronica
preparar/concluir`; a barreira usa `world_boundary_resolution.py`. A fachada
direta é uma porta dirigida de manutenção e reparo:

```bash
poetry run python ferramentas/adversarial_operations.py check
poetry run python ferramentas/adversarial_operations.py agente <ator> <capacidade>
poetry run python ferramentas/adversarial_operations.py percepcao-ren <grupo> --local <local>
```

O preflight chama somente o check da fachada. Os validadores internos aparecem
no diagnóstico por subcapacidade, sem virar módulos ou custos separados. Os
perfis `cronica`, `sidequests` e `mundo` incluem a regressão modular.
