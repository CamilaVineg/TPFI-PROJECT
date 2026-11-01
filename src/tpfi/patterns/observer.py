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
    expone ``subscribe`` y ``unsubscribe``, y mantiene los sockets persistentes
    asociados a cada UUID suscripto. Un mismo UUID puede tener varios sockets,
    porque la consigna admite tantos requerimientos de subscripcion como reciba
    el servidor (por ejemplo, dos procesos del observador en la misma CPU, que
    comparten el UUID de ``uuid.getnode()``).
    """

    def __init__(self) -> None:
        """Inicializa el sujeto en estado ``IDLE`` y sin observadores."""
        self._observers: dict[str, list[SocketObserver]] = {}
        self._lock = threading.Lock()
        self._state = SubjectState.IDLE

    @property
    def state(self) -> SubjectState:
        """Estado actual del sujeto observable."""
        return self._state

    def subscribe(self, uuid: str, sock: socket.socket) -> None:
        """Registra el socket de ``uuid`` como observador.

        Cada llamada agrega un socket nuevo: no se rechazan las subscripciones
        repetidas del mismo UUID.

        Args:
            uuid: Identificador unico de la CPU del cliente suscripto.
            sock: Socket TCP que permanecera abierto para las notificaciones.
        """
        observer = SocketObserver(sock)
        with self._lock:
            self._observers.setdefault(uuid, []).append(observer)
            self._state = SubjectState.SUBSCRIBED
        logger.info("Observador subscripto: %s", uuid)

    def unsubscribe(self, uuid: str, sock: socket.socket | None = None) -> None:
        """Elimina uno o todos los observadores de ``uuid``.

        Args:
            uuid: Identificador del observador a eliminar.
            sock: Socket concreto a eliminar. Si se omite se eliminan todos los
                sockets registrados para ``uuid``.
        """
        removed: list[SocketObserver] = []
        with self._lock:
            observers = self._observers.get(uuid)
            if not observers:
                if not self._observers:
                    self._state = SubjectState.IDLE
                return
            if sock is None:
                removed = list(observers)
                del self._observers[uuid]
            else:
                for observer in observers:
                    if observer.sock is sock:
                        observers.remove(observer)
                        removed = [observer]
                        if not observers:
                            del self._observers[uuid]
                        break
                else:
                    return
            if not self._observers:
                self._state = SubjectState.DISCONNECTED
        for observer in removed:
            close_socket(observer.sock)
        logger.info("Observador desuscripto: %s", uuid)

    def notify(self, payload: dict[str, Any]) -> None:
        """Envia ``payload`` a todos los observadores registrados.

        Los observadores que fallen se eliminan del registro para no volver a
        intentar la entrega en notificaciones posteriores.

        Args:
            payload: Registro JSON a retransmitir.
        """
        with self._lock:
            targets = [
                (uuid, observer)
                for uuid, observers in self._observers.items()
                for observer in observers
            ]

        for uuid, observer in targets:
            try:
                observer.update(payload)
                logger.info("Notificacion enviada a %s", uuid)
            except SocketDeliveryError as err:
                logger.warning("Fallo la notificacion a %s: %s", uuid, err)
                self.unsubscribe(uuid, observer.sock)

    @property
    def subscriber_count(self) -> int:
        """Cantidad de observadores actualmente registrados."""
        with self._lock:
            return sum(len(sockets) for sockets in self._observers.values())

    def shutdown(self) -> None:
        """Cierra todos los sockets de observadores y libera el registro."""
        with self._lock:
            observers = [observer for group in self._observers.values() for observer in group]
            self._observers.clear()
            self._state = SubjectState.DISCONNECTED
        for observer in observers:
            close_socket(observer.sock)


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

    @property
    def sock(self) -> socket.socket:
        """Socket asociado al observador."""
        return self._sock

    def update(self, payload: dict[str, Any]) -> None:
        """Envia ``payload`` al cliente suscripto.

        Args:
            payload: Registro JSON con la actualizacion.

        Raises:
            SocketDeliveryError: Si el socket no acepta el envio.
        """
        try:
            message = (json.dumps(payload, default=str) + "\n").encode("utf-8")
            self._sock.sendall(message)
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
