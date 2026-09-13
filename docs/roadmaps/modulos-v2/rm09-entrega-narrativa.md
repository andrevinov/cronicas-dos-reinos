# RM-09 — Entrega narrativa

## Status e dependências

**Proposta.** Depende das RM-01–RM-02.

## Problema

O catálogo atual mede a infraestrutura que prepara a cena, mas não possui um
módulo para o produto final recebido pelo jogador. Ritmo, clareza, densidade,
naturalidade e qualidade de diálogo ficam apenas no feedback global.

## Objetivo

Criar `narrative_delivery`, responsável por converter o estado autorizado em
prosa jogável sem escolher por Ren e sem esconder mecânicas ou consequências.

## Escopo

- progressão perceptível da cena;
- densidade proporcional ao momento;
- voz e diálogo coerentes com o contexto fornecido;
- distinção entre fato percebido, hipótese e informação reservada;
- mecânica diegética e rodapé canônico;
- conclusão aberta para decisão do jogador;
- custo e latência da resposta final.

## Medição

Não criar juiz literário baseado em palavras-chave. A nota combina:

- verificações estruturais objetivas;
- auditoria semântica pós-hoc;
- percepção do jogador;
- sinais de retrabalho, correção ou contestação no turno seguinte.

Agência, vazamento de segredo e alteração de resultado são guardrails críticos,
não componentes compensáveis da média literária.

## Indicadores

- turnos com avanço, resolução ou pergunta jogável clara;
- correções factuais e retrabalho provocado pela resposta;
- compressão narrativa contestada;
- proporção de exposição procedimental sem efeito ficcional;
- tamanho e latência por classe de turno;
- notas do jogador para ritmo, naturalidade, profundidade e agência;
- violações críticas separadas.

## Testes

- contratos estruturais usam fixtures e propriedades, não gosto literário falso;
- narração não cria fala, emoção ou ação voluntária de Ren;
- fato reservado não aparece na saída pública;
- mecânica explícita e rodapé seguem o contrato;
- turno curto não é penalizado por não conter evento grande;
- ausência de nota humana permanece N/D.

## Definition of done

- todo turno narrativo possui evento de entrega correlacionado;
- feedback do jogador entra neste módulo sem dominar guardrails;
- avaliação automática não tenta substituir julgamento humano de prosa;
- nenhuma escrita canônica é feita pelo módulo de entrega;
- regressões de narrativa e protocolo ficam verdes.
