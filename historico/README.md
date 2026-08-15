# Histórico frio

`historico/` guarda material que não participa da leitura operacional normal da campanha.

A história corrente deve ser consultada primeiro em `sessoes/`: resumos e alterações de estado antes de transcrições completas.

## Legado da Etapa 5

`historico/legado/` preserva integralmente os antigos arquivos que misturavam presente e cronologia:

- `estado-acumulado-pre-etapa-5.yaml`
- `tempo-acumulado-pre-etapa-5.yaml`
- `migracao-estado-v1.yaml`

Os dois arquivos acumulados mantêm exatamente os blobs anteriores à migração. Servem para auditoria e recuperação, não para leitura preventiva durante narração.

Ordem para dúvida histórica:

1. runtime/estado atual, quando ainda for assunto do presente;
2. resumo e alterações da sessão relevante;
3. `contexto.py ... --historico`;
4. transcrição específica;
5. `historico/legado/` apenas para auditoria ou recuperação de informação da migração.

Verificação:

```bash
python3 ferramentas/migrar-estado-atual.py --check
```
