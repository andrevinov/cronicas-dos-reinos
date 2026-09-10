# NV-16 — iniciativa explicitamente decidida para o elenco presente

## Objetivo

A NV-16 fecha a diferença entre **ter memória de um NPC na cena** e **avaliar se
ele realmente pode iniciar uma interação**. O sistema não transforma memória em
fala automática: ele exige um subconjunto explícito de interlocutores e dá a
cada um uma decisão verificável.

## Três conceitos separados

1. **Participante da memória** — NPC cujo estado relevante deve ser carregado
   para a cena. `--participante` governa a memória/elenco prospectivo, mas não é
   prova suficiente de presença física durante o mesmo preparo.
2. **Presença/contactabilidade** — a presença física vem do elenco corrente já
   persistido e ainda ancorado ao local atual; alternativamente, um canal de
   contato pode estabelecer contactabilidade depois de passar pelos gates
   próprios. A NV-16 não cria nenhuma das duas coisas.
3. **Interlocutor** — subconjunto explicitamente indicado com
   `--interlocutor <id>`. Só esse subconjunto recebe avaliação de iniciativa.

Ser participante não abre conversa nem prova sozinho presença. Ser interlocutor
não cria encontro, canal, conhecimento, side quest ou ação de Ren.

## Porta operacional

A mesma porta permanece autoritativa:

```text
poetry run cronica preparar --cena-id <id> ... --interlocutor <npc-id>
poetry run cronica concluir --ticket '<ticket>'
```

`--interlocutor` é repetível, aceita no máximo seis IDs canônicos e não faz
resolução aproximada. Omissão da flag mantém o caminho anterior sem custo NV-16.

Em convivência/permanência, indique apenas interlocutores cuja presença já esteja
consolidada ou cujo contato tenha sido validado e combine com
`--permanencia-local`. A identidade da janela social herda a janela NV-15 e,
portanto, usa **local + data + período**, não `scene_id`. Em cena curta sem
permanência, a janela é o próprio `scene_id`.

Uma lista nova passada por `--participante` no mesmo `preparar` pode carregar a
memória necessária e preparar o elenco a ser consolidado, mas não retroage como
prova de que aquele NPC já estava fisicamente presente. Após o writer consolidar
a presença, a janela seguinte pode avaliá-lo normalmente.

## Projeção

A memória de cena já carrega relação, medidores e `iniciativa_social`. A NV-16
reutiliza exatamente esses documentos antes da compactação pública; não reabre
uma ficha por interlocutor.

Para cada interlocutor declarado, o preparo registra uma linha explícita:

- `nao_elegivel` por ausência/indisponibilidade quando a presença ou o estado
  necessário não existe;
- `silencio_justificado` quando a política social exige motivo concreto e nenhum
  motivo já estabelecido está disponível;
- `adiada_por_pressao_superior` quando uma pressão de maior prioridade ocupa a
  janela;
- `requer_decisao=true` para no máximo uma iniciativa plausível.

Compromissos já carregados pela memória podem servir de motivo concreto quando
o NPC é envolvido e a janela não é futura. Nenhuma causa é inventada.

A seleção reutiliza `iniciativa_social.project` e
`pressao_narrativa.project_social_pressure`; não existe tabela paralela de
personalidade ou prioridade. Entre candidatas equivalentes, a ordenação é
determinística.

## Conclusão

Quando `iniciativa_elenco.selecionada` for `null`, a transação deve **omitir** o
bloco `iniciativa_elenco`. As decisões automáticas são instaladas somente depois
do writer normal do turno terminar com sucesso.

Quando houver seleção, `cronica concluir` exige exatamente uma decisão para o
`decisao_id` indicado:

### Iniciativa apresentada

```yaml
iniciativa_elenco:
  decisao_id: ini-...
  resultado: apresentada
  evidencia_literal: trecho que aparece na narração ou no resumo
```

### Silêncio justificado

```yaml
iniciativa_elenco:
  decisao_id: ini-...
  resultado: silencio_justificado
  motivo_codigo: risco
  motivo: razão concreta e curta
```

Silêncio escolhido no `concluir` aceita somente `risco` ou
`indisponibilidade`. `sem_motivo_concreto`, `janela_ocupada` e repetição são
resultados derivados pelo preparo e não podem ser fabricados manualmente.

### NPC não elegível

```yaml
iniciativa_elenco:
  decisao_id: ini-...
  resultado: nao_elegivel
  motivo_codigo: indisponibilidade
  motivo: razão concreta e curta
```

Inelegibilidade escolhida no `concluir` aceita `falta_conhecimento`, `risco` ou
`indisponibilidade`. `ausencia` é consequência do gate de presença e não pode
ser alegada para uma iniciativa que já foi selecionada como presente/contactável.

`adiada_por_pressao_superior` também não pode ser escolhida livremente pelo
narrador: é uma decisão automática derivada da prioridade já projetada.

## Frescor e idempotência

Os recibos ficam em `narrador/iniciativas-elenco/estado.yaml`, domínio reservado.
A identidade de uma tentativa combina janela + NPC + digest da proposta social.

- uma iniciativa apresentada não reaparece na mesma janela;
- silêncio/inelegibilidade iguais permanecem decididos até mudar a janela ou a
  causa material;
- repetição de uma abertura já apresentada vira silêncio estrutural, não uma
  segunda fala;
- adiamento por pressão superior pode ser reavaliado quando a pressão deixa de
  ocupar a janela;
- uma janela aceita no máximo uma iniciativa apresentada;
- retry do mesmo `cronica concluir` não duplica recibo;
- se o writer concluir e a instalação do recibo falhar, repetir o mesmo concluir
  repara a etapa reservada sem duplicar o turno.

O comando `confirmar`/`registrar` separado é recusado para tickets NV-16: a
decisão precisa atravessar a mesma conclusão para não se perder.

## Economia

O contrato congelado está em
`baseline/present-cast-initiative-orcamento.yaml`:

- até 6 interlocutores explícitos;
- no máximo 1 abertura por janela;
- 0 consultas adicionais por NPC quando memória/relação já foram carregadas;
- 0 chamadas de IA por NPC;
- 0 RNG novo;
- 0 scheduler novo;
- 0 scan global de NPCs;
- projeção pública até 3 KiB;
- ticket NV-16 até 4 KiB;
- estado reservado até 128 KiB / 256 decisões.

O orçamento total da preparação **não aumenta**. A memória de cena é compactada
com o espaço restante depois da decisão NV-16; se o conjunto indispensável não
couber, o preparo falha em vez de elevar o teto.

## Relação com outras camadas

- **NV-14:** continua podendo observar capacidade de iniciativa do elenco, mas
  não inventa interlocutor nem assunto. A decisão concreta nasce apenas do
  subconjunto explícito da NV-16.
- **NV-15:** fornece a identidade estável local/data/período para convivência
  longa; mudar `scene_id` não reabre a mesma iniciativa e não invalida por si a
  presença já consolidada no mesmo local.
- **contatos sociais:** contato previamente validado pode estabelecer
  contactabilidade; o contato solicitado tem precedência sobre iniciativa
  incidental.
- **pressão narrativa:** matérias de prioridade superior adiam a abertura social
  sem apagá-la.
- **side quests:** nenhuma iniciativa desta camada cria oferta ou causa de side
  quest. Esse domínio continua sob seus contratos próprios.

## Critérios cobertos

- Nera, Silva, Jack ou qualquer outro NPC recebem decisão somente quando
  explicitamente declarados como interlocutores; presença/contactabilidade
  determina elegibilidade sem ser inventada pela memória;
- participante sem `--interlocutor` continua apenas memória;
- novo `--participante` não vira presença retroativa no mesmo preparo;
- interlocutor ausente produz inelegibilidade, nunca encontro;
- no máximo uma abertura é selecionada por janela;
- silêncio válido permanece possível e auditável;
- retries e renomeação de cena dentro da mesma permanência preservam frescor;
- nenhum fluxo curto sem interlocutores ganha leitura social nova.
