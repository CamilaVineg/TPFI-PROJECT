"""Punto de entrada del cliente Observer.

Cliente que se suscribe a las actualizaciones de la tabla
``CorporateData`` y permanece escuchando las notificaciones
que el servidor le retransmite.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from tpfi.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    RETRY_INTERVAL,
    positive_int,
    tcp_port,
)

logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de linea de comandos del observador.

    Args:
        argv: Argumentos a procesar. Si es ``None`` usa ``sys.argv``.

    Returns:
        El namespace con los argumentos interpretados.
    """
    parser = argparse.ArgumentParser(
        prog="observerclient",
        description="Cliente Observer del TPFI IS2.",
    )
    parser.add_argument(
        "-s",
        "--host",
        default=DEFAULT_HOST,
        help="Host del servidor (por defecto: %(default)s).",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=tcp_port,
        default=DEFAULT_PORT,
        help="Puerto del servidor (por defecto: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT.JSON",
        default=None,
        help="Archivo JSON donde se graba cada notificacion. Si se omite, va a stdout.",
    )
    parser.add_argument(
        "-r",
        "--retry-interval",
        type=positive_int,
        default=RETRY_INTERVAL,
        help="Segundos entre reintentos de conexion (por defecto: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Habilita los mensajes de traza y debug por salida estandar.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Ejecuta el cliente Observer.

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
    logger.info("Iniciando observerclient contra %s:%s", args.host, args.port)
    logger.info("Implementacion pendiente: ver consigna del TPFI, seccion de componentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
