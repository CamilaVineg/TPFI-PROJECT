"""Implementacion del patron Observer.

El servidor de aplicaciones actua como sujeto observable: cada vez que se
produce una actualizacion de la tabla ``CorporateData`` debe
avisar a todos los clientes previamente subscriptos mediante la accion
``subscribe``.

El sujeto mantiene el registro de observadores y los notifica en cascada.
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import threading
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ObservedSubject",
    "ObserverProtocol",
    "SocketDeliveryError",
    "SocketObserver",
    "SubjectState",
]

logger = logging.getLogger(__name__)


class SocketDeliveryError(Exception):
    """Se lanza cuando un observador no puede recibir la notificacion."""


class SubjectState(Enum):
    """Estados posibles del sujeto observable.

    Attributes:
        IDLE: Sin observadores registrados.
        SUBSCRIBED: Con al menos un observador activo.
        DISCONNECTED: Se perdieron todos los observadores por fallo de socket.
    """

    IDLE = "IDLE"
    SUBSCRIBED = "SUBSCRIBED"
    DISCONNECTED = "DISCONNECTED"


@runtime_checkable
class ObserverProtocol(Protocol):
    """Contrato que debe cumplir todo observador registrado en el sujeto."""

    def update(self, payload: dict[str, Any]) -> None:
        """Recibe la notificacion de una actualizacion.

        Args:
            payload: Registro JSON con los datos actualizados.
        """
        ...  # pragma: no cover


class ObservedSubject:
    """Sujeto que notifica actualizaciones a sus observadores.

    La gestion de subscripciones se resuelve con el patron Observer: el sujeto
    expone ``subscribe`` y ``unsubscribe``, y mantiene un conjunto de sockets
    persistentes asociados a cada UUID suscripto.
    """

    def __init__(self) -> None:
        """Inicializa el sujeto en estado ``IDLE`` y sin observadores."""
        self._observers: dict[str, socket.socket] = {}
        self._lock = threading.Lock()
        self._state = SubjectState.IDLE

    @property
    def state(self) -> SubjectState:
        """Estado actual del sujeto observable."""
        return self._state

    def subscribe(self, uuid: str, sock: socket.socket) -> None:
        """Registra el socket de ``uuid`` como observador.

        Args:
            uuid: Identificador unico de la CPU del cliente suscripto.
            sock: Socket TCP que permanecera abierto para las notificaciones.

        Raises:
            ValueError: Si ``uuid`` ya se encuentra subscripto.
        """
        with self._lock:
            if uuid in self._observers:
                raise ValueError(f"El UUID {uuid} ya se encuentra subscripto")
            self._observers[uuid] = sock
            self._state = SubjectState.SUBSCRIBED
        logger.info("Observador subscripto: %s", uuid)

    def unsubscribe(self, uuid: str) -> None:
        """Elimina el observador ``uuid`` y cierra su socket.

        Args:
            uuid: Identificador del observador a eliminar.
        """
        with self._lock:
            sock = self._observers.pop(uuid, None)
            if not self._observers:
                self._state = SubjectState.DISCONNECTED if sock else SubjectState.IDLE
        if sock is not None:
            close_socket(sock)
            logger.info("Observador desuscripto: %s", uuid)

    def notify(self, payload: dict[str, Any]) -> None:
        """Envia ``payload`` a todos los observadores registrados.

        Los observadores que fallen se eliminan del registro para no volver a
        intentar la entrega en notificaciones posteriores.

        Args:
            payload: Registro JSON a retransmitir.
        """
        message = json.dumps(payload, default=str).encode("utf-8")
        with self._lock:
            targets = dict(self._observers)

        for uuid, sock in targets.items():
            try:
                sock.sendall(message)
                logger.info("Notificacion enviada a %s", uuid)
            except OSError as err:
                logger.warning("Fallo la notificacion a %s: %s", uuid, err)
                self.unsubscribe(uuid)

    @property
    def subscriber_count(self) -> int:
        """Cantidad de observadores actualmente registrados."""
        with self._lock:
            return len(self._observers)

    def shutdown(self) -> None:
        """Cierra todos los sockets de observadores y libera el registro."""
        with self._lock:
            observers = list(self._observers.values())
            self._observers.clear()
            self._state = SubjectState.DISCONNECTED
        for sock in observers:
            close_socket(sock)


class SocketObserver:
    """Observador que entrega la notificacion a traves de un socket TCP.

    Cumple el contrato de :class:`ObserverProtocol` y encapsula el envio de
    modo que el sujeto no necesite conocer detalles de transporte.
    """

    def __init__(self, sock: socket.socket) -> None:
        """Guarda el socket asociado al cliente.

        Args:
            sock: Socket ya conectado al servidor.
        """
        self._sock = sock

    def update(self, payload: dict[str, Any]) -> None:
        """Envia ``payload`` al cliente suscripto.

        Args:
            payload: Registro JSON con la actualizacion.

        Raises:
            SocketDeliveryError: Si el socket no acepta el envio.
        """
        try:
            self._sock.sendall(json.dumps(payload, default=str).encode("utf-8"))
        except OSError as err:
            raise SocketDeliveryError(f"No se pudo entregar la notificacion: {err}") from err


def close_socket(sock: socket.socket) -> None:
    """Cierra ``sock`` ignorando errores por socket ya cerrado.

    Args:
        sock: Socket a cerrar.
    """
    with contextlib.suppress(OSError):
        sock.shutdown(socket.SHUT_RDWR)
    try:
        sock.close()
    except OSError as err:  # pragma: no cover - defensa ante cierres anormales
        logger.debug("Socket ya cerrado: %s", err)
