# Identidade canônica de locais

`index.yaml` é o registro operacional único de locais conhecidos pela campanha.

- `local_id` é estável e deve ser usado por estado derivado, recompensas e ferramentas.
- nomes e grafias alternativas pertencem a `aliases`; alias nunca cria um segundo local.
- resolver um local não cria presença, descoberta, recompensa ou fato canônico.
- `python3 ferramentas/locais.py resolver <referência>` faz lookup dirigido sem scan.
- `python3 ferramentas/locais.py check` valida aliases e consumidores persistidos.

Ao renomear um lugar em prosa, preserve o `local_id` anterior e acrescente o novo nome como alias. Trocar o ID de um mapa já gerado altera a chave determinística e não é uma operação de apresentação.
