# Histórico frio

`historico/` guarda material que não participa da leitura operacional normal da campanha.

A história corrente deve ser consultada primeiro em `sessoes/`: resumos e alterações de estado antes de transcrições completas.

## Histórico por entidade — Etapa 6

`historico/relacoes/<id>.yaml` contém a relação completa preservada por entidade no momento da fragmentação. O arquivo corrente correspondente fica em `estado/relacoes/<id>.yaml` e registra somente o recorte necessário para o presente.

Durante uma pergunta como "como Kethra vê Ren agora?", usar `contexto.py relacao kethra`. O histórico da entidade é L4: só deve ser consultado quando a pergunta exigir a evolução da relação, uma interação antiga ou a resolução de uma contradição.

## Legado de migração

`historico/legado/` preserva depósitos antigos integralmente para auditoria e recuperação excepcional.

Da Etapa 5:

- `estado-acumulado-pre-etapa-5.yaml`;
- `tempo-acumulado-pre-etapa-5.yaml`;
- `migracao-estado-v1.yaml`.

Da Etapa 6:

- `relacoes-acumuladas-pre-etapa-6.yaml`;
- `medidores-npcs-pre-etapa-6.yaml`;
- `conhecimento-acumulado-pre-etapa-6.md`;
- `migracao-memorias-v1.yaml`.

Os depósitos acumulados mantêm os blobs anteriores à migração. No caso do conhecimento, os novos fragmentos Markdown também reconstroem byte a byte o arquivo legado quando concatenados na ordem do manifesto.

Esses arquivos **não** são a fonte normal de consulta histórica. Eles existem para provar ausência de perda durante a refatoração e recuperar algo caso uma migração futura apresente defeito.

## Ordem para uma dúvida histórica

1. runtime/estado atual, se a pergunta ainda for sobre o presente;
2. `contexto.py relacao|npc|conhecimento`, se houver consulta dirigida;
3. resumo e alterações da sessão relevante;
4. `contexto.py buscar "termo" --historico`;
5. histórico específico de entidade ou transcrição específica;
6. `historico/legado/` apenas para auditoria ou recuperação excepcional.

Verificações:

```bash
python3 ferramentas/migrar-estado-atual.py --check
python3 ferramentas/migrar-memorias-fragmentadas.py --check
python3 ferramentas/reindexar-conhecimento.py --check
```
