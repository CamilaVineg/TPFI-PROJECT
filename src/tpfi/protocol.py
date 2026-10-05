r"""Protocolo de mensajes entre el servidor TCP y los clientes.

Define el formato de intercambio que comparten el servidor
``singletonproxyobserver`` y los clientes ``singletonclient`` y
``observerclient``. El canal de transporte es un stream TCP en el que cada
mensaje es un objeto JSON serializado en una unica linea, terminada con el
caracter de nueva linea (``\\n``). Este encuadre permite delimitar los
mensajes sin necesidad de cerrar la conexion entre uno y otro.

Se distinguen tres tipos de mensaje:

* ``request``: enviado por un cliente hacia el servidor con la accion a
  resolver (``get``, ``list``, ``set`` o ``subscribe``).
* ``response``: respuesta puntual del servidor al solicitante de una accion.
* ``notification``: retransmision en cascada hacia todos los observadores
  subscriptos, producida cuando un ``set`` modifica ``CorporateData``.
"""

from __future__ import annotations

import contextlib
import json
import socket
import uuid
from typing import Any

__all__ = [
    "ACTION_GET",
    "ACTION_LIST",
    "ACTION_SET",
    "ACTION_SUBSCRIBE",
    "ACTIONS",
    "STATUS_ERROR",
    "STATUS_OK",
    "TYPE_NOTIFICATION",
    "TYPE_REQUEST",
    "TYPE_RESPONSE",
    "InvalidMessageError",
    "JsonSocket",
    "build_request",
    "decode_message",
    "encode_message",
    "make_error",
    "make_notification",
    "make_response",
]

ACTION_GET = "get"
ACTION_LIST = "list"
ACTION_SET = "set"
ACTION_SUBSCRIBE = "subscribe"
ACTIONS = (ACTION_GET, ACTION_LIST, ACTION_SET, ACTION_SUBSCRIBE)

STATUS_OK = "ok"
STATUS_ERROR = "error"

TYPE_REQUEST = "request"
TYPE_RESPONSE = "response"
TYPE_NOTIFICATION = "notification"

MESSAGE_TERMINATOR = "\n"
_TERMINATOR = MESSAGE_TERMINATOR.encode("utf-8")
_BUFFER_SIZE = 4096


class InvalidMessageError(Exception):
    """Se lanza cuando un mensaje recibido no es un objeto JSON valido."""


def encode_message(message: dict[str, Any]) -> bytes:
    r"""Serializa ``message`` como una linea JSON terminada en ``\n``.

    Args:
        message: Diccionario con el contenido del mensaje.

    Returns:
        Los bytes listos para enviar por el socket.
    """
    payload = json.dumps(message, ensure_ascii=False, default=str)
    return (payload + MESSAGE_TERMINATOR).encode("utf-8")


def decode_message(raw: bytes | str) -> dict[str, Any]:
    """Interpreta una linea JSON y la devuelve como diccionario.

    Args:
        raw: Bytes o texto con el contenido JSON del mensaje.

    Returns:
        El mensaje interpretado como diccionario.

    Raises:
        InvalidMessageError: Si ``raw`` no contiene un objeto JSON valido.
    """
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    text = text.strip()
    if not text:
        raise InvalidMessageError("El mensaje recibido esta vacio")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise InvalidMessageError(f"El mensaje no es un JSON valido: {err}") from err
    if not isinstance(parsed, dict):
        raise InvalidMessageError("El mensaje debe ser un objeto JSON")
    return parsed


def build_request(
    action: str,
    *,
    record_id: str | None = None,
    data: dict[str, Any] | None = None,
    client_uuid: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Construye un mensaje de tipo ``request``.

    El ``session_id`` identifica la sesion (un UUID unico por requerimiento) y
    ``client_uuid`` identifica la CPU que origina la peticion. Ambos se generan
    automaticamente si no se suministran, para que el servidor pueda registrarlos
    en ``CorporateLog``.

    Args:
        action: Accion solicitada (``get``, ``list``, ``set`` o ``subscribe``).
        record_id: Clave primaria del registro afectado, si aplica.
        data: Campos a escribir, solo para la accion ``set``.
        client_uuid: UUID de la CPU cliente. Si es ``None`` se obtiene con
            :func:`uuid.getnode`.
        session_id: Identificador de sesion. Si es ``None`` se genera un UUID4.

    Returns:
        El mensaje de requerimiento listo para enviar.
    """
    request: dict[str, Any] = {
        "type": TYPE_REQUEST,
        "action": action,
        "session_id": session_id or str(uuid.uuid4()),
        "client_uuid": client_uuid or str(uuid.getnode()),
    }
    if record_id is not None:
        request["id"] = record_id
    if data is not None:
        request["data"] = data
    return request


def make_response(session_id: str, data: Any) -> dict[str, Any]:
    """Construye una respuesta exitosa para el solicitante.

    Args:
        session_id: Identificador de sesion del requerimiento respondido.
        data: Resultado de la accion (registro, listado o confirmacion).

    Returns:
        El mensaje de respuesta con estado ``ok``.
    """
    return {"type": TYPE_RESPONSE, "status": STATUS_OK, "session_id": session_id, "data": data}


def make_error(session_id: str, message: str) -> dict[str, Any]:
    """Construye una respuesta de error para el solicitante.

    Args:
        session_id: Identificador de sesion del requerimiento rechazado.
        message: Descripcion legible del error.

    Returns:
        El mensaje de respuesta con estado ``error``.
    """
    return {
        "type": TYPE_RESPONSE,
        "status": STATUS_ERROR,
        "session_id": session_id,
        "error": message,
    }


def make_notification(session_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Construye una notificacion de actualizacion para los observadores.

    Args:
        session_id: Identificador de sesion del ``set`` que origino el cambio.
        data: Registro actualizado de ``CorporateData``.

    Returns:
        El mensaje de notificacion en cascada.
    """
    return {
        "type": TYPE_NOTIFICATION,
        "action": ACTION_SET,
        "session_id": session_id,
        "data": data,
    }


class JsonSocket:
    """Envoltorio de un socket TCP que envia y recibe mensajes JSON.

    Mantiene un buffer interno de recepcion para recomponer mensajes que
    lleguen fragmentados en varios ``recv``, y delimita cada mensaje por el
    caracter de nueva linea.
    """

    def __init__(self, sock: socket.socket) -> None:
        """Envuelve el socket ya conectado ``sock``.

        Args:
            sock: Socket TCP conectado al par remoto.
        """
        self._sock = sock
        self._buffer = b""

    def send(self, message: dict[str, Any]) -> None:
        """Envia ``message`` serializado como una linea JSON.

        Args:
            message: Diccionario con el mensaje a enviar.
        """
        self._sock.sendall(encode_message(message))

    def receive(self) -> dict[str, Any]:
        """Lee el proximo mensaje JSON del stream.

        Returns:
            El mensaje recibido como diccionario.

        Raises:
            ConnectionError: Si el par remoto cerro la conexion sin enviar un
                mensaje completo.
            InvalidMessageError: Si el mensaje recibido no es JSON valido.
        """
        while _TERMINATOR not in self._buffer:
            chunk = self._sock.recv(_BUFFER_SIZE)
            if not chunk:
                break
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(_TERMINATOR)
        if not line:
            raise ConnectionError("El servidor cerro la conexion")
        return decode_message(line)

    def close(self) -> None:
        """Cierra el socket subyacente ignorando errores de cierre."""
        with contextlib.suppress(OSError):
            self._sock.close()
