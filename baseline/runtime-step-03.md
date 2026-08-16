# Etapa 3 — camada runtime

A camada `runtime/` foi introduzida como projeção operacional descartável das fontes canônicas.

Critérios protegidos por teste/CI:

- `runtime/contexto.yaml` e `runtime/cena.yaml` devem corresponder às fontes canônicas atuais;
- ambos devem permanecer abaixo de 8 KiB;
- sessão, personagem, PV, Ki, CA, dinheiro, data, hora e localização precisam coincidir com o estado canônico;
- `runtime/eventos-pendentes.jsonl` deve conter apenas objetos JSON válidos quando receber eventos;
- `ferramentas/gerar-runtime.py --check` deve passar antes de narração baseada no runtime;
- a baseline lógica pré-refatoração continua passando sem alteração dos fatos canônicos.

Nesta etapa, `eventos-pendentes.jsonl` é apenas infraestrutura reservada. O fluxo transacional que passará a utilizá-lo será implantado posteriormente.
