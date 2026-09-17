# Painel de desempenho modular

Em pacotes gerados a partir da versão 4.1.0, o painel lê
`scorecard.agregacao_modular`. Uma falha de instrumentação identifica a nota
como parcial, mostra quantos módulos foram incluídos e expõe o número de
componentes válidos em cada eixo. Pacotes históricos sem esse bloco preservam a
renderização anterior.

Em pacotes 4.2.0, cada cartão separa qualidade adjudicada de conformidade
operacional. O diagnóstico mostra quantas avaliações e oportunidades entram nos
denominadores, quantas permanecem pendentes e quantas oportunidades elegíveis
ficaram sem ativação. Ausência de adjudicação aparece como qualidade N/D.

Em pacotes 4.3.0, o ranking global dá lugar a três filas: reparo do medidor,
problemas da experiência e investigação de custo. O seletor e os cartões mostram
os ranks separadamente. Tokens são identificados como atribuição contábil por
rateio e não alteram as filas de reparo ou experiência.

Em pacotes 4.4.0, o painel lê `scorecard.conclusao_medicao`. Entrada não
congelada, correlação ambígua, resultado ausente, evidência insuficiente, erro
do detector ou falha modular aparecem como conclusão bloqueada. A nota parcial
continua visível como diagnóstico e não é apresentada como conclusão válida.

O painel é estático, sem backend ou dependências externas:

```bash
cd /home/andre/Projects/cronicas-dos-reinos
poetry run servidor
```

Abra `http://127.0.0.1:18765/evaluation/dashboard/`. O comando usa a raiz do
repositório mesmo quando chamado de uma subpasta e atende somente nesta máquina.
Encerre com `Ctrl+C`.

A porta padrão 18765 reduz conflitos com portas comuns de desenvolvimento. Se
estiver ocupada, o comando avisa; para usar outra, execute
`poetry run servidor --porta 18766`. Após atualizar o checkout, execute
`poetry install --only-root` uma vez para instalar o novo atalho no `.venv`.

O seletor lê `evaluation/sessions/index.json`, reconstruído pelo gerador. O
painel mantém a sessão 021 como referência `legacy-v1`; sessões novas usam
`modules-v2`, mostram somente os doze módulos-pai no ranking e abrem suas
subcapacidades no diagnóstico. Versões de implementação e avaliação aparecem
em cada cartão, e a tendência não mistura chaves de comparabilidade. Na régua
4.0.0, cada cartão também mostra a cobertura fail-closed: N/D significa zero
atividade; N/A exige recibo explícito; recibo ausente, incompleto ou duplicado
aparece como falha de instrumentação e bloqueia a nota.

## Manifestação do jogador

Na série v2 não há nota de 1 a 5. O jogador relata uma ocorrência concreta
ligada a uma `interaction_ref`, por exemplo:

```text
[AVALIAÇÃO S022-I0049 — havia uma boa oportunidade para um NPC interagir com
Ren, mas ele não tomou iniciativa.]
```

O canal primário é o próprio Codex. O formulário do painel é secundário para
registro retroativo: salva rascunhos em `localStorage` e exporta
`manifestacoes-jogador-sessao-<id>.json`. Esse arquivo deve ser selecionado com
`entrada_medicao.py preparar --interacoes` antes da geração. O texto começa
como percepção `pendente`; detector ou auditor sugerem o módulo e a adjudicação
separadamente.

O navegador servido por `http.server` não escreve no repositório. A sessão 021
continua exibindo seu formulário numérico legado, sem convertê-lo em evidência
v2.
