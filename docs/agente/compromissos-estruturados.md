# Compromissos e encontros futuros estruturados

Esta camada guarda **obrigações futuras já estabelecidas na ficção** sem transformar a campanha em calendário automático. Ela existe para impedir que encontros marcados, promessas e retornos combinados fiquem enterrados em prosa de `prazo_relevante`, efeitos temporários, objetivos ou coberturas.

## Princípio

Compromisso é estado corrente, não scheduler.

- não cria evento sozinho;
- não avança o relógio;
- não move Ren nem NPC;
- não conclui nem fracassa automaticamente;
- não abre agente, fragmento, side quest ou Mundo Vivo;
- apenas mantém uma obrigação concreta visível no contexto quente.

Possibilidade, intenção vaga ou plano ainda não acertado **não** vira compromisso estruturado.

## Forma canônica

Compromissos ativos vivem em `estado/estado-atual.yaml:compromissos`:

```yaml
compromissos:
  resposta_sella:
    tipo: encontro
    resumo: Encontrar Sella no mercador de cal para receber a resposta autorizada por Kethra.
    envolvidos:
    - ren
    - sella_rove
    janela:
      inicio:
        data: 14 Eleasis, 1372 DR
        hora: '21:20'
      fim:
        data: 14 Eleasis, 1372 DR
        hora: '21:50'
      descricao: partir se Sella não aparecer em meia hora
```

`tipo` pode ser:

- `encontro`: exige alguma janela temporal;
- `compromisso`: pode existir sem data exata, como uma promessa condicionada.

O registro é deliberadamente curto. Não copie conversa, justificativas longas ou cronologia para dentro dele.

A v1 **não possui `local_id`**. Enquanto não houver integração repo-aware com o Canonical Location Registry, o local fica no resumo/descrição. Aceitar um identificador de local apenas porque ele “parece” snake_case reabriria a classe de inconsistência eliminada pela Task 1. Uma extensão futura só deve adicionar local estruturado passando pela mesma resolução canônica obrigatória.

## Escrita durante a sessão

Criar ou reagendar substitui **o registro inteiro** no mesmo JSON enviado a `turno.py registrar`:

```json
{
  "alvo": "estado",
  "op": "set",
  "caminho": "compromissos.resposta_sella",
  "valor": {
    "tipo": "encontro",
    "resumo": "Encontrar Sella no mercador de cal para receber a resposta de Kethra.",
    "envolvidos": ["ren", "sella_rove"],
    "janela": {
      "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "21:20"},
      "fim": {"data": "14 Eleasis, 1372 DR", "hora": "21:50"}
    }
  }
}
```

Não usar `append`, `inc` nem escrita em subcampo como `compromissos.x.janela`. A troca atômica impede combinações intermediárias incoerentes.

Cumprimento, cancelamento ou outra resolução explícita remove o item do estado corrente **na própria transação que estabelece essa resolução**:

```json
{"alvo":"estado","op":"remove","caminho":"compromissos.resposta_sella"}
```

Não existe coleção acumulativa de compromissos encerrados. A transcrição, o registro transacional e o ledger já preservam que o compromisso existiu e como terminou.

## L1/L2

`runtime/contexto.yaml` projeta os compromissos ativos e calcula `situacao_temporal` sem escrita canônica. `contexto.py status` (L1) e `contexto.py cena` (L2) recebem essa informação pela mesma fonte quente; `runtime/cena.yaml` não duplica o pacote.

As situações são derivadas:

- `futuro`;
- `em_janela`;
- `devido`;
- `ate_limite`;
- `janela_encerrada`;
- `sem_instante_exato`;
- `sem_data`.

**`janela_encerrada` não significa fracasso.** Significa apenas que o relógio canônico ultrapassou a janela enquanto o compromisso ainda está aberto. O narrador deve resolver o fato na ficção: talvez Ren tenha comparecido, talvez a outra parte tenha faltado, talvez o encontro tenha sido interrompido. Só depois registrar a consequência e remover/reagendar o compromisso.

O pacote quente carrega no máximo quatro registros completos, ordenados por urgência e instante; excedentes aparecem apenas por ID até o próximo checkpoint. Isso limita o custo sem apagar o estado canônico completo.

## Relação com tempo livre e efeitos

`estado/tempo.yaml:prazo_relevante` continua útil para **alertas textuais gerais**, duração de efeitos e material legado. Ele não deve ser usado como substituto para novos encontros e promessas concretas que possuam identidade própria.

`efeitos_temporarios` descreve condições que persistem ou expiram; compromisso descreve algo que alguém se comprometeu a fazer, observar, entregar, encontrar ou aguardar. Não duplicar o mesmo fato nas duas estruturas sem necessidade.

## Custo

A camada não lê histórico, transcrição, agenda nem agentes para o turno comum. Um compromisso entra como mais um delta na mesma chamada de `turno.py registrar`; portanto não adiciona escrita operacional. O runtime deriva a situação a partir do relógio que já está no pacote quente.
