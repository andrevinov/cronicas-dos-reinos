# Mundo reservado

Controle determinístico do mundo que continua fora da presença de Ren. Existir
no mundo não significa entrar no contexto nem no conhecimento do personagem.

## Estrutura

- `agenda.yaml` e `estado.yaml`: cadências, cursor e pendências de avaliação;
- `eventos/`: baralho mundial e interação causal;
- `incidentes/` e `microeventos-locais/`: projeções espaciais;
- `obrigacoes-temporais/`: fatos com prazo e suas evidências;
- `permanencia-espacial/`: recibos determinísticos por janela;
- `relogios/`: pressão derivada de agentes e operações;
- `rastros/`: manifestações observáveis separadas da origem reservada;
- `ciclo-npcs.yaml` e `CICLO-NPCS.md`: lifecycle terminal de NPCs.

Os índices globais de população ficam em `../indices/`; agentes e entradas ficam
em `../elenco/`; direções e side quests ficam em `../tramas/`.

## Invariantes

- pendência significa “avaliar”, não “aconteceu”;
- sorteio não é cânone;
- relógio não possui agência: agente → operação → pressão → consequência;
- movimento vencido não teletransporta ninguém;
- fato reservado não cria conhecimento automaticamente;
- descoberta de rastro consolida evidência pública e recibo reservado na mesma
  transação;
- checkpoint trabalha sobre tempo e fatos já consolidados.

## Consulta dirigida

```bash
python3 ferramentas/agentes.py mostrar <id>
python3 ferramentas/eventos_mundo.py mostrar <id>
python3 ferramentas/relogios.py por-agente <id>
python3 ferramentas/rastros.py mostrar <id>
```

Consultas amplas, população canônica e auditorias pertencem a manutenção/CI, não
ao hot path da narração.
