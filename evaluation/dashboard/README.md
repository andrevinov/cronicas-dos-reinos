# Painel de desempenho modular

O painel é estático, sem dependências externas e sem backend. Sirva a raiz do
repositório para que os caminhos relativos dos pacotes de sessão permaneçam
acessíveis:

```bash
cd /home/andre/Projects/cronicas-dos-reinos
python3 -m http.server 8765
```

Abra:

```text
http://127.0.0.1:8765/evaluation/dashboard/
```

O seletor usa `evaluation/sessions/index.json`, reconstruído automaticamente por
`ferramentas/gerar-avaliacao-sessao.py`. Portanto uma nova sessão aparece no
painel após a geração normal de seus artefatos.

## Feedback do jogador

As respostas são salvas em `localStorage`, separadas por sessão. O navegador não
consegue sobrescrever arquivos locais quando é servido por `http.server`.
As notas globais atualizam imediatamente a prévia da sessão; a nota de resultado
de cada módulo atualiza sua prévia modular. Percepção de ativação, impacto e
comentários permanecem registrados para a auditoria humana.

Use **Exportar feedback CSV**, substitua
`evaluation/sessions/<id>/feedback-jogador.csv` pelo arquivo exportado e rode o
gerador novamente. O novo `scorecard.json` incorporará a nota histórica do
jogador. Também é possível importar um CSV no painel sem alterar o repositório.

Módulos reservados e puramente técnicos não são exibidos no formulário, embora
continuem disponíveis na visão interna de desempenho modular.
