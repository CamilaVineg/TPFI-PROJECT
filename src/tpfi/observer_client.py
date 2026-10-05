"""Punto de entrada del cliente Observer.

Cliente que se suscribe a las actualizaciones de la tabla
``CorporateData`` y permanece escuchando las notificaciones
que el servidor le retransmite.

Cada vez que la conexion se cae, el cliente vuelve a conectarse y a
subscribirse transcurrido un intervalo configurable de reintento.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import time
import uuid
from collections.abc import Sequence
from typing import Any

from tpfi.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    RETRY_INTERVAL,
    positive_int,
    tcp_port,
)
from tpfi.protocol import (
    ACTION_SUBSCRIBE,
    InvalidMessageError,
    JsonSocket,
    build_request,
)

logger = logging.getLogger(__name__)

CONNECTION_TIMEOUT = 10.0


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


def build_subscription(client_uuid: str, session_id: str | None = None) -> dict[str, Any]:
    """Construye el requerimiento ``subscribe`` del observador.

    Args:
        client_uuid: UUID de la CPU que se subscribe.
        session_id: Identificador de sesion, o ``None`` para generarlo.

    Returns:
        El mensaje de subscripcion listo para enviar.
    """
    return build_request(ACTION_SUBSCRIBE, client_uuid=client_uuid, session_id=session_id)


def connect(host: str, port: int) -> JsonSocket:
    """Abre una conexion TCP con el servidor.

    Args:
        host: Host del servidor.
        port: Puerto del servidor.

    Returns:
        El canal JSON envuelto sobre el socket conectado.

    Raises:
        OSError: Si no se puede establecer la conexion.
    """
    sock = socket.create_connection((host, port), timeout=CONNECTION_TIMEOUT)
    return JsonSocket(sock)


def emit(message: dict[str, Any], output_path: str | None) -> None:
    """Muestra ``message`` por stdout o lo agrega al archivo de salida.

    Args:
        message: Mensaje recibido del servidor.
        output_path: Archivo donde acumular las notificaciones, o ``None``.
    """
    text = json.dumps(message, ensure_ascii=False, default=str)
    if output_path is None:
        print(text)
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def listen_once(
    host: str,
    port: int,
    client_uuid: str,
    output_path: str | None,
) -> None:
    """Mantiene una subscripcion activa hasta que se cae la conexion.

    Conecta, envia la subscripcion y permanece mostrando cada mensaje que llega
    del servidor. Devuelve (o propaga la excepcion) cuando el socket se cierra.

    Args:
        host: Host del servidor.
        port: Puerto del servidor.
        client_uuid: UUID de la CPU que se subscribe.
        output_path: Archivo de salida, o ``None`` para stdout.

    Raises:
        OSError: Si se pierde la conexion durante la escucha.
        InvalidMessageError: Si el servidor envia un mensaje malformado.
    """
    channel = connect(host, port)
    logger.info("Conectado a %s:%s como %s", host, port, client_uuid)
    try:
        channel.send(build_subscription(client_uuid))
        while True:
            emit(channel.receive(), output_path)
    finally:
        channel.close()


def run(
    host: str,
    port: int,
    retry_interval: int,
    output_path: str | None,
    client_uuid: str | None = None,
) -> int:
    """Escucha notificaciones reconectando indefinidamente ante cada caida.

    Args:
        host: Host del servidor.
        port: Puerto del servidor.
        retry_interval: Segundos de espera entre reintentos.
        output_path: Archivo de salida, o ``None`` para stdout.
        client_uuid: UUID de la CPU, o ``None`` para relevarlo del equipo.

    Returns:
        Nunca retorna en operacion normal: solo al interrumpir el proceso.
    """
    resolved_uuid = client_uuid or str(uuid.getnode())
    while True:
        try:
            listen_once(host, port, resolved_uuid, output_path)
        except (OSError, InvalidMessageError) as err:
            logger.warning("Conexion perdida (%s); reintentando en %ss", err, retry_interval)
        time.sleep(retry_interval)


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
    return run(args.host, args.port, args.retry_interval, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
