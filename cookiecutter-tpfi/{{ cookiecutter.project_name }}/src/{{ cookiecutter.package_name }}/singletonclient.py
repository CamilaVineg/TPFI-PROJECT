"""Punto de entrada del cliente Singleton: ``singletonclient.py``.

Este es el programa que la consigna denomina ``SingletonClient``.
Cliente que consulta o modifica los datos de la tabla
``CorporateData`` a traves del servidor de aplicaciones.

Lee un requerimiento en formato JSON desde un archivo, se conecta al servidor,
le envia la accion y escribe la respuesta en un archivo de salida o por salida
estandar.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
from collections.abc import Sequence
from typing import Any

from {{ cookiecutter.package_name }}.config import DEFAULT_HOST, DEFAULT_PORT, tcp_port
from {{ cookiecutter.package_name }}.protocol import (
    ACTION_SET,
    ACTIONS,
    STATUS_ERROR,
    InvalidMessageError,
    JsonSocket,
    build_request,
)

logger = logging.getLogger(__name__)

CONNECTION_TIMEOUT = 10.0

# Claves con las que el archivo de entrada puede identificar cada dato. La
# consigna usa mayusculas (``UUID``, ``ID``, ``ACTION``) y el formato propio del
# proyecto usa minusculas: se aceptan ambas.
_ACTION_KEYS = ("ACTION", "action")
_RECORD_ID_KEYS = ("ID", "id")
_CLIENT_UUID_KEYS = ("UUID", "uuid", "client_uuid")
_METADATA_KEYS = frozenset(
    {
        "TYPE",
        "type",
        "ACTION",
        "action",
        "ID",
        "id",
        "UUID",
        "uuid",
        "CLIENT_UUID",
        "client_uuid",
        "SESSION_ID",
        "session_id",
        "DATA",
        "data",
    }
)


def _first_value(input_data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Devuelve el valor de la primera clave presente en ``input_data``.

    Args:
        input_data: Requerimiento leido del archivo de entrada.
        keys: Claves a buscar, en orden de precedencia.

    Returns:
        El valor encontrado o ``None`` si ninguna clave esta presente.
    """
    for key in keys:
        if key in input_data:
            return input_data[key]
    return None


def _tuple_fields(input_data: dict[str, Any]) -> dict[str, Any]:
    """Extrae los campos del tuple ``CorporateData`` del nivel raiz.

    La consigna indica que, para la accion ``set``, los campos del registro se
    agregan al mismo nivel que ``UUID``, ``ID`` y ``ACTION``.

    Args:
        input_data: Requerimiento leido del archivo de entrada.

    Returns:
        Los atributos del tuple informados, sin las claves de control.
    """
    return {key: value for key, value in input_data.items() if key not in _METADATA_KEYS}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de linea de comandos del cliente.

    Args:
        argv: Argumentos a procesar. Si es ``None`` usa ``sys.argv``.

    Returns:
        El namespace con los argumentos interpretados.
    """
    parser = argparse.ArgumentParser(
        prog="singletonclient",
        description="Cliente Singleton del {{ cookiecutter.package_name }} IS2.",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        metavar="INPUT.JSON",
        help="Archivo JSON de entrada con el requerimiento.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT.JSON",
        default=None,
        help="Archivo JSON de salida. Si se omite, se emite por salida estandar.",
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
        "-v",
        "--verbose",
        action="store_true",
        help="Habilita los mensajes de traza y debug por salida estandar.",
    )
    return parser.parse_args(argv)


def load_input(path: str) -> dict[str, Any]:
    """Carga el requerimiento desde el archivo JSON ``path``.

    Args:
        path: Ruta del archivo de entrada.

    Returns:
        El requerimiento interpretado como diccionario.

    Raises:
        OSError: Si el archivo no existe o no puede leerse.
        ValueError: Si el contenido no es un objeto JSON valido.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("El archivo de entrada debe contener un objeto JSON")
    return data


def build_request_from_input(input_data: dict[str, Any]) -> dict[str, Any]:
    """Convierte el requerimiento de entrada en un mensaje de protocolo.

    Acepta tanto el formato de la consigna (``UUID``, ``ID`` y ``ACTION`` en
    mayusculas, con los campos del tuple al nivel raiz para ``set``) como el
    formato propio del proyecto (minusculas y los campos dentro de ``data``).
    La accion se compara sin distinguir mayusculas de minusculas.

    Args:
        input_data: Requerimiento leido del archivo de entrada.

    Returns:
        El mensaje ``request`` listo para enviar.

    Raises:
        ValueError: Si la accion no esta entre las admitidas.
    """
    action = _first_value(input_data, _ACTION_KEYS)
    if isinstance(action, str):
        action = action.lower()
    if action not in ACTIONS:
        raise ValueError(f"Accion no admitida: {action!r}")

    data: Any = None
    if action == ACTION_SET:
        data = input_data["data"] if "data" in input_data else _tuple_fields(input_data)

    return build_request(
        action,
        record_id=_first_value(input_data, _RECORD_ID_KEYS),
        data=data,
        client_uuid=_first_value(input_data, _CLIENT_UUID_KEYS),
    )


def run_request(host: str, port: int, request: dict[str, Any]) -> dict[str, Any]:
    """Envia ``request`` al servidor y devuelve su respuesta.

    Args:
        host: Host del servidor.
        port: Puerto del servidor.
        request: Mensaje de requerimiento a enviar.

    Returns:
        La respuesta del servidor como diccionario.

    Raises:
        OSError: Si no se puede conectar o falla el envio.
        InvalidMessageError: Si la respuesta no es JSON valido.
    """
    with socket.create_connection((host, port), timeout=CONNECTION_TIMEOUT) as sock:
        channel = JsonSocket(sock)
        channel.send(request)
        return channel.receive()


def write_output(path: str | None, response: dict[str, Any]) -> None:
    """Escribe la respuesta en ``path`` o por salida estandar.

    Args:
        path: Ruta del archivo de salida, o ``None`` para stdout.
        response: Respuesta a escribir como JSON.
    """
    text = json.dumps(response, ensure_ascii=False, default=str, indent=2)
    if path is None:
        print(text)
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Ejecuta el cliente Singleton.

    Args:
        argv: Argumentos de linea de comandos.

    Returns:
        El codigo de salida del proceso: ``0`` si el servidor respondio ``ok``
        y ``1`` si fallo la comunicacion o la respuesta trae ``status=error``.
    """
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger.info("Iniciando singletonclient con la entrada %s", args.input)
    try:
        input_data = load_input(args.input)
        request = build_request_from_input(input_data)
        logger.info("Enviando accion %s a %s:%s", request["action"], args.host, args.port)
        response = run_request(args.host, args.port, request)
    except (OSError, ValueError, InvalidMessageError) as err:
        logger.error("Fallo el requerimiento: %s", err)
        return 1
    write_output(args.output, response)
    return 1 if response.get("status") == STATUS_ERROR else 0


if __name__ == "__main__":
    raise SystemExit(main())
