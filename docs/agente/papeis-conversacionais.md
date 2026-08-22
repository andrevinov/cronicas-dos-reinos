# Papéis conversacionais de NPCs

Esta camada existe para evitar que NPCs recorrentes respondam todos do mesmo jeito quando Ren pede opinião, consolo, censura ou conselho. Ela **não escreve falas prontas** e não transforma personalidade em máquina de decisão.

## Princípio

Um papel conversacional responde à pergunta: **“de que ângulo este NPC tende a pensar quando Ren lhe pede uma opinião?”**

Ele não responde:

- o que é objetivamente correto;
- o que o NPC sabe;
- o que o NPC fará;
- qual decisão Ren deve tomar;
- qual segredo precisa ser revelado.

Conhecimento continua vindo do estado, da relação, da cena e das fontes canônicas. O papel só organiza a interpretação depois que esses limites já estão conhecidos.

## Onde vive

Os perfis opt-in ficam inline em `cenario/texturas/index.yaml:npcs.<id>.papel_conversacional`. `contexto.py npc "Nome"` já consulta esse índice para paleta narrativa; portanto o papel viaja na **mesma consulta L2**, sem ferramenta nova e, para perfis sem textura longa, sem abrir fragmento adicional.

A resposta chega em `resultado.textura_narrativa.papel_conversacional` com cinco componentes:

- `papel`: rótulo estável do ângulo;
- `prioriza`: até três preocupações que tendem a vir primeiro;
- `forma_de_responder`: até três movimentos de conversa plausíveis;
- `evita`: atalhos de interpretação que achatariam o NPC;
- `limite_de_autoridade`: trava explícita contra conhecimento ou competência inventados.

## Como usar

Se Ren pergunta a Nera o que deveria fazer, o perfil `espelho_afetivo` não significa que Nera possui a resposta correta. Significa que, **entre respostas compatíveis com o que Nera sabe e com a relação atual**, ela tende a devolver questões de autonomia, verdade e promessa em vez de elaborar um plano tático que não domina.

Da mesma forma:

- Silva tende a segurança concreta e verificabilidade;
- Maerra tende a vulneráveis, meios e enquadramento moral;
- Luath tende a prova, preparação e risco público;
- Halessa tende a cadeia de custódia, limites e coordenação prévia;
- Jack tende a filtros, acesso, preço e exposição do circo;
- Kethra tende a sobrevivência civil e padrões de contato;
- Iria tende a sinais físicos, risco e cuidado prático.

Esses rótulos são heurísticas, não bordões. Não repetir a mesma pergunta, frase ou estrutura em todas as cenas.

## Relação com estado e agentes

A ordem é:

1. usar estado/relação para saber como o NPC está com Ren agora;
2. respeitar estritamente o que o NPC sabe;
3. usar o papel conversacional apenas para escolher o ângulo entre respostas plausíveis;
4. consultar agente estratégico **somente** quando a decisão realmente depender de objetivo, plano, recurso ou segredo do agente.

Um papel conversacional nunca promove NPC a agente, nunca cria agenda e nunca acorda Mundo Vivo. Também não substitui `papel_conversacional` por “personalidade fixa”: medo, confiança, raiva, vínculo e acontecimentos da cena podem mudar a resposta concreta.

## População inicial

A Task 7 começa deliberadamente com oito perfis sustentados pelo cânone atual: Iria Doss, Nera Vell, Silva Elkwood, Irmã Maerra Thandrel, Luath, Irmã Halessa Vorn, Jack Mooney e Kethra Dunn.

NPC sem perfil continua exatamente como antes. Não preencher os 35 relacionamentos por completude; novo perfil só entra quando recorrência e evidência canônica justificarem o custo e a utilidade.

## Custo

Os perfis são pequenos e ficam no roteador de texturas que `contexto.py npc` já lê. Para NPCs com perfil inline e sem textura longa:

- 0 ferramentas extras;
- 0 fragmentos narrativos extras;
- 0 leitura em `status` ou `cena`;
- 0 scheduler;
- 0 escrita;
- nenhuma abertura de `narrador/agentes/`.

O ganho esperado é reduzir inferência improvisada: a mesma NPC não precisa ser “redescoberta” a cada conversa, e o narrador recebe um ângulo curto em vez de buscar histórico para reconstruir como ela costuma aconselhar.
