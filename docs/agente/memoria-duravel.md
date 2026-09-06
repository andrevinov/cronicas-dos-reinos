# NV-04 — Acontecimentos como memória durável

## Autoridade e fluxo

No mesmo JSON de `cronica concluir`, o narrador anota os fatos novos no bloco
`memoria`. `memoria_duravel.prepare_transaction` valida a anotação e a compila
para os deltas existentes **antes** dos writers e journals de sidequest/pressão.
Não há extrator de IA adicional, scheduler, terceira chamada ritual ou novo
arquivo de verdade. Sem fatos novos, **omitir o bloco**; a entrada e o caminho
anterior permanecem inalterados, sem leituras adicionais da camada de memória.

O bloco é um contrato de entrada, não um armazenamento. O writer existente grava
transcrição + buffer; a consulta existente aplica os deltas pendentes, e o
checkpoint existente consolida estado, relações, medidores e conhecimento.
A integração automática da memória na preparação/retomada é a NV-05, não esta tarefa.

## Forma comum

`memoria` contém somente `versao: 1` e `fatos: [...]`. Cada fato tem:

- `id`: identificador local à transação, snake_case, até 64 caracteres;
- `tipo`: `promessa`, `informacao`, `relacao` ou `marco`;
- `participantes`: 2 a 6 IDs distintos, incluindo `ren` (o personagem do jogador);
  os demais são IDs exatos já indexados em `estado/relacoes/index.yaml`;
- `evidencia`: `{campo: jogador|narracao, trecho: <trecho literal>}`; 20 a 600
  caracteres presentes no campo indicado do mesmo turno, nunca só no resumo.

No máximo 8 fatos e 8 KiB de JSON compacto no bloco; a transação compilada
continua sujeita ao teto existente de deltas. Campos desconhecidos, versão
inválida, IDs repetidos e prova não literal falham antes das escritas. Não usar
aliases aproximados, criar NPCs implicitamente ou incluir conhecimento reservado.
Novas identidades devem ser estabelecidas pelo fluxo canônico anterior.

## Promessas e encontros

Exemplo **sintético**, não um fato da campanha. `silva_fixture` só existe nos testes:

```json
{
  "id": "exemplo-promessa",
  "jogador": "Prometo entregar o mapa a Silva antes do anoitecer.",
  "narracao": "Silva aceita o acordo e guarda o estojo vazio.",
  "resumo": "Ren promete entregar o mapa a Silva.",
  "modo": "interação",
  "deltas": [],
  "memoria": {
    "versao": 1,
    "fatos": [{
      "id": "mapa",
      "tipo": "promessa",
      "participantes": ["ren", "silva_fixture"],
      "evidencia": {
        "campo": "jogador",
        "trecho": "Prometo entregar o mapa a Silva antes do anoitecer."
      },
      "operacao": "registrar",
      "compromisso": {"tipo": "compromisso", "resumo": "Entregar o mapa a Silva."}
    }]
  }
}
```

`compromisso` reutiliza `compromissos.py`: `tipo` (`compromisso`/`encontro`),
`resumo` e `janela` opcional. Encontro exige janela. `envolvidos` é derivado de
`participantes`, não enviado duas vezes. `janela.inicio/fim` usa `{data, hora}`;
`janela.descricao` conserva condições sem inventar um instante. Não inventar
horários, obrigações ou decisões do jogador que a ficção não estabeleceu.

O ID novo é `mem_<hash da sessão, transação e id local>`; aparece na consulta seguinte
`contexto.py status`, mesmo antes do checkpoint. O registro ativo fica **apenas**
em `estado.compromissos`. As relações recebem uma marca histórica da declaração,
com fonte `transacao:<id>` e referência ao compromisso, não outro estado ativo.

Para `cumprir` ou `cancelar`, usar o mesmo tipo de fato, com nova evidência real,
`operacao`, `compromisso_id` e `anterior` (registro completo consultado, sem
`situacao_temporal`, que é derivada). O registro anterior inteiro precisa coincidir
com o estado efetivo. Vontade de cumprir não significa cumprimento.

Para `substituir`, acrescentar `compromisso` novo. A operação remove o antigo e
registra um novo ID no mesmo lote; nunca altera o passado. Os participantes
precisam coincidir com os envolvidos anteriores. Mudança de participantes usa
cancelamento e nova promessa explícitos, não substituição silenciosa. Prazo
vencido sozinho não encerra compromisso. Nenhuma dessas operações cria scheduler.

## Informação transmitida

Acrescentar `emissor`, `destinatario`, `canal`, `estatuto` e `texto` ao fato comum.
Emissor e destinatário devem ser participantes distintos; um deles precisa ser
`ren`. `canal` aceita `presencial` ou `mensagem_entregue`: enviar futuramente não
é entregar. `estatuto` aceita `relato` ou `rumor`, sem confirmar automaticamente
seu conteúdo. `texto`, com até 220 caracteres, deve estar na evidência literal.

Somente o destinatário NPC recebe `relacao:<id>.informacoes_recebidas`. Outros
participantes não ganham conhecimento por estarem listados. Quando Ren recebe,
o delta usa `conhecimento/registrar`; o texto durável conserva emissor, canal e
estatuto mesmo na representação Markdown do conhecimento. Uma marca na relação
com o emissor conserva a proveniência e a identidade da transação.

Trocas exclusivamente entre NPCs, fatos reservados e confirmações Ren/Shinta/Kage
continuam nos seus domínios próprios. A NV-04 não transforma rumor em verdade,
mensagem não entregue em conhecimento, nem divulga segredo a terceiros.

## Relação e marco

`relacao` acrescenta `npc`, `eixo` (`afinidade`/`confianca`), `anterior` e
`variacao` (+1 ou -1). Reutiliza `estado_relacional.py`: afinidade é o campo
legado `medidores.vinculo`; confiança usa `medidores.confianca`. O valor anterior
é conferido **após** aplicar as pendências; limites 0..10 continuam valendo.
Eixos desconhecidos não são inicializados por inferência. Dois fatos não podem
produzir um salto duplo no mesmo eixo. A causa fica em `memorias_importantes`.

`marco` acrescenta somente `texto`, até 220 caracteres contidos na evidência.
Registra o acontecimento em `memorias_importantes` dos NPCs participantes, sem
mudar medidores automaticamente. Relação numérica e interpretação narrativa
continuam distintas. Os nomes dos campos são reconhecidos pela projeção NV-03.

## Repetição, conflito e recuperação

Não enviar deltas manuais para os mesmos caminhos compilados; isso poderia
aplicar o fato duas vezes. Deltas independentes continuam permitidos, inclusive `conhecimento/registrar`
sem caminho: dois registros aditivos distintos não conflitam pelo domínio comum.
A cópia do mesmo ID ou texto compilado continua proibida. Repetir o
mesmo `cronica concluir`, com o mesmo ticket e JSON, não duplica fato, promessa,
conhecimento ou incremento. Divergência de conteúdo com ID repetido é recusada.

Nas transações com `memoria`, o ID informado é uma referência do cliente:
o compilador o coloca no namespace `sNNN-nv04-<hash>` da sessão corrente, antes
de chegar ao writer. O ID devolvido também pode ser repetido na mesma sessão.
Reutilizar uma referência de cliente em outra sessão gera outra transação e
outros fatos, sem colidir nos compromissos ou na deduplicação dos históricos.
Sem o bloco `memoria`, os IDs legados permanecem exatamente como antes.

Após checkpoint, o ledger existente identifica a transação consolidada e as
marcas de memória verificam sua assinatura. Se já arquivadas, a conferência abre
somente o histórico conhecido daquela relação. Não relê a transcrição para
extrair memória. O writer normal mantém sua própria leitura da transcrição para
verificar/reparar o marcador transacional. Uma promessa antiga não ressuscita ao
repetir sua criação depois de cumprida.

Interrupção depois do buffer e antes da transcrição usa a recuperação existente:
repetir o mesmo concluir. O comando separado `cronica registrar` recusa `memoria`;
primitivas de reparo não são a porta de captura da NV-04.

Os fragmentos resultantes são verificados antes do writer contra os mesmos
12 KiB da consolidação. Excesso exige manutenção explícita com preservação do
histórico; não há descarte automático nem aumento dos tetos. O save instalado
não é migrado nem usado como fixture por esta tarefa.

## Validação e orçamento

Testes permanentes: `test_memoria_duravel.py` (contrato puro) e
`test_memoria_duravel_integracao.py` (componentes reais em diretórios temporários).
O episódio anotado cobre promessa, informação, confiança, marco, checkpoint e
reconstrução em novo processo sem histórico de chat. Há testes de replay,
conflito, sigilo, prova inválida, limite e interrupção entre as duas escritas.

**Evidência literal prova correspondência textual, não compreensão nem captura
completa da narração.** Uma promessa sem anotação ainda pode não virar memória;
há teste explícito desse limite. Essas narrações anotadas não são novos episódios
gerados por IA nem substituem a avaliação narrada do benchmark NV-02/NV-12.

`preparar`, tickets e saída do turno sem fatos não recebem campos novos.
O roteador AGENTS ganha 276 bytes de orientação carregada na inicialização,
não um novo bloco repetido a cada preparo. Turnos com fatos pagam pela anotação e
pelos deltas/proveniência; não existe alegação de custo zero para essa persistência.
As leituras adicionais se limitam ao buffer/ledger e aos índices/fragmentos dos
participantes; histórico dirigido só no retry consolidado que precise dele.
Permanecem duas chamadas de orquestração e duas escritas no turno comum. Não foi
medida economia de tokens de episódios narrados; menos bytes em um componente
não demonstra essa economia.
