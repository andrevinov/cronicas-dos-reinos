# Relógios como pressão dos agentes

Os relógios de `narrador/relogios/` não são agentes e não tomam decisões. Eles medem **pressão/progresso produzido por uma operação** ou preservam a **consequência já materializada** quando o limite foi alcançado.

A cadeia conceitual é:

```text
AGENTE → OPERAÇÃO → PRESSÃO (relógio ativo) → CONSEQUÊNCIA (relógio resolvido)
```

## Vínculo agencial

Cada fragmento possui `vinculo_agencial`:

```yaml
vinculo_agencial:
  tipo: pressao
  estado: ativo
  operacao: red_sail_reconstruir_cadeia_colm
  agente_principal: red_sail
  papel_agente: explorador
  agentes_relacionados: []
```

`papel_agente` descreve a relação sem inventar causalidade:

- `origem`: o agente produziu diretamente a consequência;
- `explorador`: o agente pode fazer uma pista/pressão avançar por meio da sua operação;
- `executor`: o agente executou a operação registrada;
- `afetado`: a consequência recai sobre a operação/agente, mas a causa não é atribuída a ele;
- `alvo`: o agente é objeto da consequência/investigação, não seu causador.

Isso permite ligar `destino_de_edran_kells` à Casa de Tyr como **afetada** sem afirmar quem matou Edran, e ligar o relatório de Pell à Red Sail como **alvo** sem fingir que a Red Sail produziu o relatório.

## Estado operacional

Um relógio com `vinculo_agencial.estado: ativo` deve ser `tipo: pressao`, estar abaixo do limite e pertencer a uma operação. Ele só avança quando fatos canônicos justificarem progresso; passagem de tempo, sozinha, não aumenta nada.

Quando `progresso >= limite`, `ferramentas/relogios.py sincronizar` converte a pressão em `tipo: consequencia` e `estado: resolvido`.

A descrição e `consequencia_no_limite` permanecem no mesmo fragmento, preservando a história mecânica sem manter um “4/4” fingindo ser ameaça ainda viva.

## Roteador derivado

`narrador/relogios/vinculos.yaml` é um roteador pequeno, derivado dos fragmentos. Ele permite descobrir pressões por agente sem abrir todos os relógios:

```bash
python3 ferramentas/relogios.py por-agente red_sail
python3 ferramentas/relogios.py por-agente red_sail --todos
python3 ferramentas/relogios.py mostrar rastro_fraco_no_pomar
python3 ferramentas/relogios.py status
python3 ferramentas/relogios.py validar
```

A consulta exata `por-agente <id>` lê somente `vinculos.yaml`. Um relógio só é aberto quando sua pressão realmente importa para a decisão.

## Checkpoint

A sincronização ocorre no checkpoint de baixa frequência, depois do lifecycle de NPCs e antes das demais camadas do Mundo Vivo. Ela roda em Python e não devolve os sete fragmentos ao contexto do modelo.

O turno comum continua com as duas escritas já estabelecidas. Um delta `relogio:<id>` continua sendo consolidado normalmente; a transição pressão→consequência é manutenção determinística de checkpoint, não uma terceira escrita por fala.

## Migração dos sete relógios existentes

Pressões ainda ativas da operação `red_sail_reconstruir_cadeia_colm`:

- `rastro_fraco_no_pomar`;
- `exposicao_do_contato_de_kethra`;
- `exposicao_do_contato_de_pell`.

Consequências já resolvidas:

- `resposta_red_sail_ao_corpo` — consequência produzida pela Red Sail;
- `destino_de_edran_kells` — consequência que afeta a investigação da Casa de Tyr; a causa da morte não é atribuída;
- `operacao_preservacao_casa_pesos` — consequência da operação executada por Night Watch com Tyr;
- `relatorio_pell_ponto_morto` — consequência de inteligência cujo alvo era a Red Sail; Pell continua sendo o autor do relatório.

Assim, nenhum relógio legado permanece como entidade autônoma ou como “ameaça zumbi” depois de já ter chegado ao limite.
