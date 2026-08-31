# Personagem do jogador

Personagem atual: **Ren Kagehira**.

Arquivos principais:

* `conceito.md`: conceito, identidade e papel na campanha;
* `ficha.yaml`: ficha mecânica em D&D 5e;
* `resumo-de-poderes.md`: leitura rápida do que o personagem consegue fazer;
* `historia.md`: histórico e motivação;
* `conhecimento.md`: roteador curto para o conhecimento do personagem;
* `conhecimento/ativo.yaml`: ponteiros para tópicos prioritários e descobertas recentes;
* `conhecimento/index.yaml`: índice dos fragmentos de conhecimento;
* `conhecimento/topicos/`: conhecimento estável por assunto;
* `conhecimento/descobertas/`: descobertas registradas por sessão quando existe cabeçalho explícito `Sessão NNN`.

Para descobrir o que Ren sabe, preferir:

```bash
python3 ferramentas/contexto.py conhecimento "assunto"
```

Não abrir todos os fragmentos de `conhecimento/` preventivamente. A cópia monolítica anterior à Etapa 6 permanece somente em `historico/legado/` para auditoria e recuperação excepcional.

Ren é um humano de Kozakura, monge do Guerreiro das Sombras, vindo a Ravens Bluff para caçar um traidor de seu clã.
