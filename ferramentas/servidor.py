"""Servidor HTTP local e estático para o painel de avaliação da campanha."""
from __future__ import annotations

import argparse
import errno
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORTA_PADRAO = 18765
ROOT = Path(__file__).resolve().parents[1]


def porta_valida(valor: str) -> int:
    try:
        porta = int(valor)
    except ValueError:
        raise argparse.ArgumentTypeError("a porta deve ser um inteiro entre 1 e 65535") from None
    if not 1 <= porta <= 65535:
        raise argparse.ArgumentTypeError("a porta deve ser um inteiro entre 1 e 65535")
    return porta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--porta", type=porta_valida, default=PORTA_PADRAO,
        help=f"porta local (padrão: {PORTA_PADRAO})",
    )
    args = parser.parse_args()
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    try:
        servidor = ThreadingHTTPServer((HOST, args.porta), handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(
                f"A porta {args.porta} já está em uso. Se o painel já estiver aberto, "
                "use o servidor existente; para outra porta, execute "
                "'poetry run servidor --porta <número>'.",
                file=sys.stderr,
            )
        else:
            print(f"Não foi possível iniciar o servidor: {exc}", file=sys.stderr)
        return 1

    with servidor:
        print(f"Painel: http://{HOST}:{args.porta}/evaluation/dashboard/", flush=True)
        print("Para encerrar, pressione Ctrl+C.", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
