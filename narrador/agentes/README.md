# Agentes autônomos

Camada operacional reservada para NPCs, facções e instituições capazes de agir fora da presença de Ren.

Ela **não substitui** `narrador/masao/`, `narrador/juppongatana/`, relógios, relações, sessões ou qualquer outra fonte canônica. Os fragmentos daqui apenas condensam o estado de agência necessário para responder rapidamente: objetivo, recursos, restrições, presença, mobilidade, atuação local, conhecimento e plano corrente.

## Presença e mobilidade

`presenca.estado` pode ser `presente`, `presente_oculto`, `fora_da_area`, `em_viagem`, `indeterminado`, `distribuida` ou `ancorada`. Presença concreta de NPC (`presente`, `presente_oculto`, `fora_da_area`, `em_viagem`) exige `fonte` e `evidencia`, para impedir que uma suspeita vire chegada canônica apenas por conveniência narrativa.

`mobilidade.estado` pode ser `sem_deslocamento_registrado`, `chegada_planejada`, `saida_planejada`, `em_deslocamento` ou `nao_aplicavel`. Chegada, saída e viagem são estado do mundo. Se Kurobane sair para outra cidade, por exemplo, a mobilidade deve ser registrada e ele deixa de estar elegível para ação física em Ravens Bluff durante a ausência.

## Elegibilidade local

`atuacao_local.regra` define a relação entre presença e agência: `exige_presenca_fisica`, `permite_rede`, `estrutura_local` ou `depende_de_membros_presentes`. `ferramentas/agentes.py mostrar` calcula `elegibilidade_local` como `sim`, `nao` ou `condicional`; o valor é derivado, não persistido.

Membro individual da Juppongatana só pode executar ação física em Ravens Bluff se estiver `presente` ou `presente_oculto`. Estado `indeterminado`, `fora_da_area` ou `em_viagem` bloqueia essa ação. Agentes `latente` ou `inativo` também ficam inelegíveis.

## Presença não é conhecimento de Ren

`presenca` pertence ao domínio reservado do narrador. Marcar alguém como `presente_oculto` não cria conhecimento para Ren e não exige que a narração anuncie a chegada. Ren só passa a saber por percepção, descoberta, comunicação ou inferência legítima registrada pelas camadas normais de conhecimento.

## Juppongatana

Os dez membros possuem fragmentos individuais. Kurobane já tem presença canonicamente estabelecida em Ravens Bluff. A presença de Shizune permanece indeterminada: os sinais atuais não são promovidos a confirmação. Os demais começam `latente` e `indeterminado`; isso não afirma onde estão, apenas impede ação física local antes que chegada/presença seja estabelecida.

O coletivo `juppongatana` usa `depende_de_membros_presentes`: sua existência não significa que todos estejam na cidade nem autoriza operações individuais sem consultar o membro correspondente.

## Economia de contexto

`index.yaml` guarda apenas metadados mínimos, presença resumida e regra de atuação local. A consulta dirigida continua abrindo somente índice + fragmento:

```bash
python3 ferramentas/agentes.py mostrar shizune
python3 ferramentas/agentes.py mostrar pan_chu
```

Quando o resumo declarar detalhes fragmentados e a decisão concreta exigir uma
única camada adicional, abrir exatamente uma seção:

```bash
python3 ferramentas/agentes.py detalhar shizune metodos_operacionais
python3 ferramentas/agentes.py detalhar shizune autonomia_estrategica
```

`mostrar` e cada `detalhar` têm teto individual de 8 KiB. A recomposição completa
existe somente para validadores frios e não é interface de narração.

A validação ampla permanece fora do loop narrativo:

```bash
python3 ferramentas/agentes.py validar
```

## Limite desta etapa

Esta camada registra agência possível, presença e mobilidade, mas ainda não decide quando o mundo deve processar ações, iniciar viagens ou consumar chegadas. O agendamento temporal e o futuro `mundo.py` pertencem à etapa seguinte.
