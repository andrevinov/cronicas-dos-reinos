# Task 16 — Incidental Presence

Presença incidental é uma coincidência determinística de rotina para NPCs recorrentes que já possuem âncora canônica em um local registrado.

A seleção usa local canônico, ecologia local, período do dia e uma janela estável derivada de seed + dia + período + local + NPC. `scene_id` não participa da janela, então renomear ou reabrir uma cena não permite pescar outro resultado.

Um candidato significa somente **avaliar se o NPC está incidentalmente presente**. Antes de narrar, o cânone forte deve ser consultado pela porta dirigida indicada no resultado. A camada não estabelece presença, não cria ação, diálogo, conhecimento, encontro, sidequest, scheduler ou estado próprio.

Presenças estratégicas e outros candidatos contextuais têm precedência. A camada usa somente a vaga restante dos tetos existentes: no máximo 2 presenças e 4 candidatos contextuais no total, com no máximo 1 presença incidental por cena.

A camada inicial é opt-in e cobre apenas NPCs leves com âncoras inequívocas em locais já canônicos: Kethra Dunn em Narwhal Manor, Bram Vask em sua loja, Silva Elkwood e Jack Mooney no circo, e Irmã Halessa Vorn na Casa de Tyr. Outros NPCs não recebem localização nova por inferência.
