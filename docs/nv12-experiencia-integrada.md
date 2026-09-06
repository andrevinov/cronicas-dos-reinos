# NV-12 — experiência integrada e instruções operacionais únicas

## Resultado

A aceitação final deixa de inferir integração pela presença isolada de campos. Um
episódio controlado agora atravessa cinco turnos, passagem de tempo, mudança de
cena e retomada em processo novo. A prova exige que memória, personalidade,
iniciativa e consequência apareçam literalmente na narração gravada.

O ensaio usa uma cópia temporária do save. IDs, histórico e estado da campanha
real permanecem intactos; nenhuma fixture injeta fatos no cânone.

## Comparação

| Antes | Depois |
|---|---|
| Memória, personalidade, iniciativa e consequências eram exercitadas em componentes ou pares. | Um episódio único exige os quatro sistemas em sequência causal. |
| Retomada fria era comprovada separadamente. | A mesma história troca de cena, consolida e reabre em outro processo sem chat anterior nem transcrição. |
| Campos estruturados podiam demonstrar instalação sem provar o texto entregue ao jogador. | Cada sistema precisa de trecho literal na narração produzida; metadado ou resumo isolado falha. |
| Documentos ainda misturavam a porta pública atual com escritores e preparadores antigos. | O hot path usa `cronica preparar` e `cronica concluir`; primitivas diretas ficam explicitamente restritas a manutenção e reparo. |

A verificação literal prova que a evidência anotada chegou à prosa. Ela não atribui
qualidade semântica automaticamente: partidas reais continuam sujeitas a revisão
pós-hoc de rollouts.

## Adoção controlada

O contrato verifica apenas o pequeno elenco recorrente que já possui fontes e
perfil decisório curado:

- `silva_elkwood`;
- `nera_vell`;
- `luath`.

As fontes continuam em `estado/npcs`, `estado/relacoes` e
`cenario/texturas/index.yaml`. Lacunas permanecem declaradas; a adoção não cria
traços, acontecimentos, presença ou conhecimento retroativo.

## Cenário de regressão

O teste integrado executa estas etapas na mesma fixture temporária:

1. Silva toma iniciativa num reencontro; uma escolha apoiada pelo perfil favorece
   cuidado concreto e uma promessa é registrada.
2. O turno seguinte recupera a promessa pelo pacote de cena sem recontar o acordo
   e sem uma consulta manual a `contexto.py npc`.
3. Ren escolhe o deslocamento; tempo e local mudam por deltas transacionais.
4. Nera recebe um pacote distinto, age dentro de seu perfil e a cena é consolidada.
5. Um processo novo reconstrói a retomada sem chat anterior ou transcrição; depois,
   a promessa produz uma consequência, é cumprida e permanece no histórico.

O teste também verifica que a transcrição só cresce por append, que os IDs não
mudam e que as fontes protegidas do repositório real conservam o mesmo digest.

## Contratos executáveis

O contrato versionado vive em `baseline/nv12-experiencia-integrada.yaml`. O gate
read-only valida comparação, elenco e documentação ativa:

```bash
poetry run python ferramentas/experiencia_integrada.py check
```

Um episódio anotado pode ser avaliado separadamente:

```bash
poetry run python ferramentas/experiencia_integrada.py avaliar episodio.yaml
```

O preflight executa o primeiro comando automaticamente. O avaliador recusa
evidência presente apenas em YAML, cobertura incompleta, consulta manual
complementar, retomada que leu transcrição ou relato que não preservou IDs,
histórico e save original.
