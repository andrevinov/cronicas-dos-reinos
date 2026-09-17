# Validação externa e aceite fail-closed

A atividade 10 fecha o reparo técnico do instrumento com três conjuntos que têm
papéis diferentes:

1. `evaluation/regressoes-rollout-v1/` é o corpus de desenvolvimento. Ele fixa
   226 verificações sobre casos mínimos e relações metamórficas;
2. `evaluation/validacao-externa-v1/` é uma amostra histórica real da sessão
   022, separada do corpus usado nas correções das atividades 3–9;
3. um pacote real pós-correção é o único artefato que pode inaugurar a baseline
   operacional.

Essas camadas impedem que um teste sintético, um pacote antigo ou a sessão 023
usada no diagnóstico sejam promovidos a evidência que não possuem.

## Amostra externa

O manifesto externo ancora o rollout integral da sessão 022 por nome, tamanho e
SHA-256. O repositório guarda onze registros exatos do JSONL, cada um ligado ao
número e ao hash de sua linha de origem. O recorte cobre seis operações:

- um preparo com estado terminal de sucesso;
- uma consulta com falha operacional explícita;
- duas operações agrupadas sem correlação individual recuperável;
- uma rolagem cujo resultado de domínio é falha;
- um lote cujos resultados de domínio são sucessos.

O gabarito foi formulado sobre a evidência bruta. `Sucesso` ou `Falha` de uma
rolagem não se converte em estado do processo. Quando o envelope não conserva
código terminal, o resultado operacional permanece `evidencia_insuficiente`.
Quando uma chamada agrupada encaminha textos sem índice por resultado, cada
operação permanece `resultado_ausente`. Essas lacunas bloqueiam conclusões; o
detector não completa o dado por inferência.

Executar a validação autocontida:

```bash
poetry run python ferramentas/validar_amostra_externa_avaliacao.py
```

Quando o rollout integral ainda estiver disponível, a extração também pode ser
conferida byte a byte:

```bash
poetry run python ferramentas/validar_amostra_externa_avaliacao.py \
  --fonte /caminho/para/rollout-s022.jsonl
```

Alterar a amostra ou o gabarito quebra os hashes. Uma mudança intencional da
semântica cria outra versão da validação, com novo manifesto e justificativa;
ela não reescreve esta evidência para fazê-la concordar com o código.

## Aceite de um pacote real

`first_real_session_status` agora concede `aceite_final: true` somente quando o
mesmo pacote satisfaz todos estes critérios:

- doze módulos e ausência de nota numérica direta do jogador;
- respostas observadas com `interaction_ref` visível exatamente uma vez;
- manifesto e artefato `proveniencia-medicao.json` concordantes, com entrada
  congelada, `entrada_id` válido e reprodução autorizada;
- `scorecard.conclusao_medicao` schema 1, sem bloqueios e com conclusão
  permitida;
- `scorecard.agregacao_modular` completa, sem módulo bloqueado por
  instrumentação;
- nenhuma violação crítica ou status de avaliação bloqueado.

Qualquer ausência ou divergência produz códigos em `bloqueios` e mantém o
pacote `pendente`. Corrigir apenas as referências visíveis já não basta para
aprovar um pacote com instrumentação inválida.

O pacote arquivado da sessão 023 continua histórico e pendente. Ele antecede os
novos contratos de proveniência, conclusão e agregação, contém falhas de
instrumentação e foi usado para diagnosticar o avaliador. A amostra da sessão
022 prova o comportamento do detector em dados reais independentes do corpus,
mas também antecede a correção. Por isso ela não inaugura a baseline.

## Gate final

O `preflight` executa a aceitação integrada e o corpus completo. O estado
técnico esperado é:

```text
validação externa: 6/6
corpus de regressão: 226/226
aceite da sessão 023: pendente
```

A próxima sessão real pós-correção será o teste prospectivo. Se o rollout não
preservar evidência suficiente, o resultado correto é continuar bloqueado e
explicar a lacuna. Um novo pacote só vira baseline quando passar pelos mesmos
critérios sem edição retroativa do histórico.
