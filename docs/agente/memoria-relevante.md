# NV-03 — Memória relevante depois do estado efetivo

## Contrato

As consultas `contexto.py npc` e `contexto.py relacao` carregam os fragmentos dirigidos **inteiros**, aplicam as pendências e só então selecionam a saída. O diálogo relacional também recebe o medidor efetivo integral. As funções Python `command_npc` e `command_relation` retornam o estado efetivo, não uma representação apta a receber novos deltas após truncamento; a projeção pertence a `fit_budget`.

`memoria_relevante.py` é uma transformação pura em memória. Não cria arquivo canônico, cache, chamada de IA, busca no histórico ou consulta de todos os personagens. A porta operacional continua sendo `contexto.py`; `contexto_core.py` isolado não aplica os overlays do wrapper.

A seleção reconhece identidade/personalidade, vínculo, acordos/compromissos/promessas, conhecimento recebido, canais e ressalvas, momentos de vínculo e marcos. Medidores e textura já carregados continuam disponíveis. É uma classificação **estrutural por campo**, não uma avaliação semântica da cena nem prova de que o narrador utilizou tudo corretamente. Não inventa traços, resumo, recebimento de mensagem, presença ou intenção.

Os candidatos são intercalados por campo: uma lista longa não recebe sua segunda oportunidade antes de todos os campos terem a primeira. Em listas, começa-se pelo último item armazenado, favorecendo os deltas anexados; isso não infere datas. A saída conserva a ordem original dos itens escolhidos e informa `indices_origem` quando há seleção parcial. Strings e itens estruturados são indivisíveis: não se corta uma ressalva no meio de um fato.

## Orçamento e aprofundamento

O limite incide sobre os bytes UTF-8 **serializados**, incluindo fontes, política, wrappers e avisos, em YAML ou JSON. A política L2 permanece com teto de 8 KiB; não foi afrouxada. A implementação geral mantém o teto duro anterior de 16 KiB para seus consumidores internos.

`memoria_relevante.aprofundamento_necessario` e `truncado_por_orcamento` indicam que algum campo prioritário ficou incompleto. `campos_prioritarios_pendentes` conta todos os campos nessa condição; `pendentes` mostra até quatro ponteiros curtos, sem fingir que são a lista completa. Campos fora da classificação principal ficam contabilizados em `campos_secundarios` e disponíveis por consulta dirigida; não são declarados semanticamente irrelevantes. Ausência da projeção nunca prova ausência no cânone.

Não narrar uma conclusão que dependa de informação marcada como faltante. Aprofundar apenas a lacuna necessária, usando a mesma entidade:

```bash
poetry run python ferramentas/contexto.py npc silva
poetry run python ferramentas/contexto.py npc silva --campos
poetry run python ferramentas/contexto.py npc silva --campo /relacao/dados/acordos
poetry run python ferramentas/contexto.py relacao nera --campo /relacao/marcos_da_relacao
```

Os ponteiros referem-se ao `resultado` efetivo, não a caminhos de arquivos. `~1` representa `/` e `~0` representa `~` em uma chave. `--campos` lista os campos disponíveis sem ler fontes adicionais e sem devolver seus valores. Essa lista também é paginada.

Na consulta dirigida, `itens` contém valores completos e seus índices/chaves; `proximo_inicio` indica o próximo `--inicio N`. Índices começam em zero e valem para aquele estado efetivo: se a base mudar entre páginas, reiniciar a consulta. `--campo` e `--campos` são mutuamente exclusivos. Um item indivisível maior que o orçamento retorna `item_nao_cabe`, necessidade explícita e, quando aplicável, `campo_nao_cabe`; não devolve cursor infinito nem texto mutilado. Refinar o ponteiro ou consultar a fonte já identificada, respeitando a política de acesso. Se até os metadados excederem o limite, a saída é um aviso mínimo e explícito de memória incompleta.

## Evidência de componentes e limites

As fixtures de Silva, Nera e Luath são **sintéticas**, declaradas em `tests/fixtures/memoria-relevante-v1.json`. Seus acontecimentos não pertencem à campanha. Os testes acrescentam trinta campos secundários longos antes dos fatos importantes para reproduzir a perda por posição, profundidade e tamanho.

Medição local do mesmo caminho `contexto_core.command_npc` + `fit_budget(8192, YAML)`, nas mesmas fixtures temporárias, comparando o código-base de `67c0636badd81c032852d83f2b337850fb259c30` (blob original `2aa34f4b8888128bf2a3e5a23ceecc495fcedcd4`) com NV-03:

| Fixture | Bytes antes | Bytes depois | Campos prioritários íntegros antes → depois |
| --- | ---: | ---: | --- |
| Silva | 5.455 | 1.061 | 1/8 → 8/8 |
| Nera | 5.439 | 1.051 | 1/7 → 7/7 |
| Luath | 5.423 | 1.120 | 1/8 → 8/8 |

Estes números medem **saída de componentes em fixtures**, não tokens nativos, qualidade literária ou consumo de episódios narrados. Não há ensaio de IA novo nesta tarefa. A comparação de episódios continua pertencendo ao benchmark NV-02; dados ausentes não contam como economia. A integração verifica também a sonda de reencontro da NV-02, exigindo promessa e vínculo visíveis.

## Validação e fronteira de escopo

```bash
poetry run python -m unittest discover -s tests -p 'test_memoria_relevante*.py' -v
poetry run python -m unittest discover -s tests -v
```

Há testes de preservação das três fixtures, tipos e profundidade, estado efetivo antes da seleção, append/remove/set/inc, medidor efetivo antes do projetor, deltas reservados, leitura dirigida sem histórico, paginação, UTF-8 e tetos, erro de CLI e imutabilidade dos arquivos temporários. A projeção pura e o núcleo foram validados localmente; overlays reais e suíte integral são verificados pelos workflows existentes no PR. O resultado final dessas execuções deve ser consultado no PR, não presumido por este manual.

Não foram alterados o save, o cânone, as transcrições, os validadores, os workflows, `cronica preparar` ou `cronica concluir`. Esta tarefa não captura fatos novos da prosa nem injeta automaticamente memória dos participantes no turno: essas integrações são NV-04 e NV-05.
