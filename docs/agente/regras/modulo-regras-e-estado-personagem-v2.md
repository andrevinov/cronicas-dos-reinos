# Módulo de regras e estado do personagem v2

`rules_and_character_state` reúne a resolução de regras, a execução de rolagens
e os deltas persistentes de Ren e do instante canônico. É uma fachada sobre as
autoridades existentes: não possui RNG, writer, ficha, relógio ou estado
paralelo.

## Escopo

O módulo tem três subcapacidades:

- `rules_resolution`: consulta a regra aplicável e congela dificuldade,
  modificadores e obrigações antes do dado;
- `roll_execution`: executa o dado pela porta pública e preserva o resultado;
- `character_time_state`: correlaciona recursos, ficha, condições de Ren e
  tempo com o commit autorizado.

Ele é elegível somente quando a ficção pede regra, rolagem, gasto persistente,
mudança de personagem ou avanço temporal. Narração sem mecânica e deltas de
mundo, localização, relação ou elenco não o ativam.

## Autoridades preservadas

| Responsabilidade | Fonte ou porta existente |
| --- | --- |
| ruleset ativo | `campanha.yaml:sistema.ruleset` |
| índice dirigido de regras | `regras/catalogo.yaml` |
| números de Ren | `personagens/jogador/ficha.yaml` |
| estado corrente | `estado/estado-atual.yaml` |
| tempo canônico | `estado/tempo.yaml` |
| projeção derivada | `runtime/contexto.yaml` e `runtime/cena.yaml` |
| rolagem | `poetry run dados` / `poetry run dados-lote` |
| escrita | `cronica concluir` e o writer transacional já existente |

`ferramentas/rules_and_character_state.py` agrega checks dessas relações e
publica observabilidade. Ela nunca substitui nenhum dos donos acima.

## Fluxo mecânico

```text
gatilho ficcional
    → regra/contrato e alvo definidos no preparar
    → dados executa a rolagem real
    → mecanica.resolucoes confirma o resultado
    → concluir valida regra, resultado, recurso e consequência
    → writer persiste exatamente uma vez
    → fachada anexa o recibo pós-writer
```

Focus permanece protegido: o gasto nasce como obrigação no ticket e o concluir
precisa confirmar a mesma obrigação e o delta correspondente. Data e hora
continuam sendo um único delta `tempo/instante`. Retry não rola novamente nem
reaplica recurso.

## Recibo observável

Quando há obrigação mecânica ou delta de personagem/tempo, o output de
`cronica concluir` recebe `regras_estado_personagem` com:

- `evento_id` determinístico e correlação com ticket, transação e sessão;
- contagens de regras, obrigações d20/recurso, resoluções e recursos aplicados;
- categorias e quantidade de deltas relevantes;
- confirmação de validação antes do writer e commit exactly-once;
- integridade de rolagem e consistência canônica como guardrails separados.

Um turno puramente narrativo não recebe esse bloco. O recibo não copia valores
da ficha, prosa, segredo ou ação de Ren, não escreve cânone e não executa o
analisador de rollout no hot path.

## Telemetria pós-hoc

O detector registra separadamente:

- consultas úteis e consultas repetidas de regra;
- redescoberta de assinatura por `--help` ou leitura de implementação;
- rolagens com CD/CA prévia quando o alvo é aplicável;
- sucesso técnico da CLI e integridade correlacionada pelo recibo;
- obrigações de recurso versus aplicações;
- deltas de personagem/tempo, instantes atômicos e retries sem novo efeito;
- bloqueios explícitos de guardrail;
- correções mecânicas pedidas pelo jogador no turno seguinte.

Ausência de evidência permanece N/D. A telemetria não infere justiça da regra a
partir do resultado e não trata uma vitória ou falha como sinal de qualidade.

## Guardrails

- dificuldade, capacidade e resultado não mudam depois do dado;
- consequência precisa continuar compatível com o contrato prévio;
- gasto protegido exige obrigação no ticket;
- direção canônica nunca é convertida em ação voluntária de Ren;
- estado vivo só muda pelo concluir autorizado;
- agência, integridade da rolagem e consistência canônica não são compensáveis
  por notas altas em outras dimensões.

## Verificação

```bash
poetry run python ferramentas/rules_and_character_state.py check
poetry run test-domain mecanica cronica
poetry run test-full
poetry run preflight
```
