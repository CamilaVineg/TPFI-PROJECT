"""Punto de entrada del servidor de aplicaciones.

Servidor TCP que implementa los patrones Proxy, Singleton y Observer sobre las
tablas ``CorporateData`` y ``CorporateLog``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from tpfi.config import DEFAULT_PORT, tcp_port

logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de linea de comandos del servidor.

    Args:
        argv: Argumentos a procesar. Si es ``None`` usa ``sys.argv``.

    Returns:
        El namespace con los argumentos interpretados.
    """
    parser = argparse.ArgumentParser(
        prog="singletonproxyobserver",
        description="Servidor Proxy/Singleton/Observer del TPFI IS2.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=tcp_port,
        default=DEFAULT_PORT,
        help="Puerto TCP en el que se escucha (por defecto: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Habilita los mensajes de traza y debug por salida estandar.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Arranca el servidor de aplicaciones.

    Args:
        argv: Argumentos de linea de comandos.

    Returns:
        El codigo de salida del proceso.
    """
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger.info("Iniciando singletonproxyobserver en el puerto %s", args.port)
    logger.info("Implementacion pendiente: ver consigna del TPFI, seccion de componentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
