"""Punto de entrada del servidor de aplicaciones.

Servidor TCP que implementa los patrones Proxy, Singleton y Observer sobre las
tablas ``CorporateData`` y ``CorporateLog``.
"""

from __future__ import annotations

import argparse
import logging
import socket
import socketserver
import sys
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from tpfi.config import DEFAULT_PORT, tcp_port
from tpfi.patterns.observer import ObservedSubject
from tpfi.protocol import (
    ACTION_GET,
    ACTION_LIST,
    ACTION_SET,
    ACTION_SUBSCRIBE,
    InvalidMessageError,
    JsonSocket,
    make_error,
    make_notification,
    make_response,
)
from tpfi.proxy import DataProxy, InvalidRequestError
from tpfi.repository import AuditRepository

__all__ = ["ApplicationServer", "ServerHandler", "main", "parse_args"]

logger = logging.getLogger(__name__)


class ServerHandler(socketserver.BaseRequestHandler):
    """Manejador de conexiones TCP del servidor de aplicaciones.

    Procesa cada requerimiento entrante, registra su auditoria en ``CorporateLog``
    y ejecuta la accion sobre ``CorporateData`` usando ``DataProxy``.
    """

    server: ApplicationServer

    def handle(self) -> None:
        """Atiende la conexion de un cliente."""
        channel = JsonSocket(self.request)
        try:
            request = channel.receive()
        except (InvalidMessageError, ConnectionError, OSError) as err:
            logger.warning("Error al recibir requerimiento del cliente: %s", err)
            return

        session_id = str(request.get("session_id") or uuid.uuid4())
        client_uuid = str(request.get("client_uuid") or uuid.getnode())
        action = request.get("action")
        record_id = request.get("id")
        data = request.get("data")
        timestamp = datetime.now(timezone.utc).isoformat()

        key = record_id if isinstance(record_id, str) and record_id.strip() else "*"

        # 1. Auditoria obligatoria para cada una de las 4 acciones
        try:
            self.server.audit_repo.record(
                action=str(action or "unknown"),
                client_uuid=client_uuid,
                session_id=session_id,
                timestamp=timestamp,
                key=key,
            )
        except Exception as err:
            logger.error("Error al registrar auditoria para %s: %s", action, err)

        # 2. Enrutamiento de acciones
        if action == ACTION_GET:
            self._handle_get(channel, session_id, record_id)
        elif action == ACTION_LIST:
            self._handle_list(channel, session_id)
        elif action == ACTION_SET:
            self._handle_set(channel, session_id, record_id, data)
        elif action == ACTION_SUBSCRIBE:
            self._handle_subscribe(channel, session_id, client_uuid)
        else:
            self._send_error(channel, session_id, f"Accion invalida: {action!r}")

    def _handle_get(self, channel: JsonSocket, session_id: str, record_id: Any) -> None:
        """Procesa una accion 'get'."""
        try:
            if not isinstance(record_id, str):
                raise InvalidRequestError("El identificador del registro es obligatorio para get")
            record = self.server.proxy.get(record_id)
            if record is None:
                response = make_error(session_id, f"El registro '{record_id}' no existe")
            else:
                response = make_response(session_id, record)
        except InvalidRequestError as err:
            response = make_error(session_id, str(err))
        except Exception as err:
            logger.exception("Error en get: %s", err)
            response = make_error(session_id, f"Error interno del servidor: {err}")
        self._safe_send(channel, response)

    def _handle_list(self, channel: JsonSocket, session_id: str) -> None:
        """Procesa una accion 'list'."""
        try:
            items = self.server.proxy.list()
            response = make_response(session_id, items)
        except Exception as err:
            logger.exception("Error en list: %s", err)
            response = make_error(session_id, f"Error interno del servidor: {err}")
        self._safe_send(channel, response)

    def _handle_set(
        self,
        channel: JsonSocket,
        session_id: str,
        record_id: Any,
        data: Any,
    ) -> None:
        """Procesa una accion 'set' con notificacion en cascada."""
        try:
            if not isinstance(record_id, str):
                raise InvalidRequestError("El identificador del registro es obligatorio para set")
            if not isinstance(data, dict):
                raise InvalidRequestError("El atributo 'data' debe ser un objeto JSON")

            updated = self.server.proxy.set(record_id, data)
            response = make_response(session_id, updated)
            self._safe_send(channel, response)

            # Notificacion en cascada a observadores si la actualizacion fue exitosa
            if updated is not None:
                notification = make_notification(session_id, updated)
                self.server.subject.notify(notification)

        except InvalidRequestError as err:
            self._send_error(channel, session_id, str(err))
        except Exception as err:
            logger.exception("Error en set: %s", err)
            self._send_error(channel, session_id, f"Error interno del servidor: {err}")

    def _handle_subscribe(
        self,
        channel: JsonSocket,
        session_id: str,
        client_uuid: str,
    ) -> None:
        """Procesa una accion 'subscribe' y mantiene abierto el socket."""
        try:
            if not isinstance(self.request, socket.socket):
                self._send_error(channel, session_id, "Tipo de socket no valido")
                return
            self.server.subject.subscribe(client_uuid, self.request)
            response = make_response(
                session_id,
                {"subscribed": True, "client_uuid": client_uuid},
            )
            channel.send(response)
        except (ValueError, OSError) as err:
            logger.warning("No se pudo suscribir observador %s: %s", client_uuid, err)
            self._send_error(channel, session_id, str(err))
            return

        # Mantener el socket del observador abierto hasta desconexion
        try:
            while True:
                _ = channel.receive()
        except (ConnectionError, OSError, InvalidMessageError):
            logger.info("Cliente observador %s desconectado", client_uuid)
        finally:
            self.server.subject.unsubscribe(client_uuid)

    def _safe_send(self, channel: JsonSocket, message: dict[str, Any]) -> None:
        """Envia un mensaje ignorando fallos de red al escribir."""
        try:
            channel.send(message)
        except OSError as err:
            logger.warning("Fallo al enviar respuesta por el socket: %s", err)

    def _send_error(self, channel: JsonSocket, session_id: str, error_msg: str) -> None:
        """Envia un mensaje de error estandarizado."""
        self._safe_send(channel, make_error(session_id, error_msg))


class ApplicationServer(socketserver.ThreadingTCPServer):
    """Servidor TCP multihilo para el TPFI IS2."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[socketserver.BaseRequestHandler],  # noqa: N803
        proxy: DataProxy | None = None,
        audit_repo: AuditRepository | None = None,
        subject: ObservedSubject | None = None,
        bind_and_activate: bool = True,
    ) -> None:
        """Inicializa el servidor TCP con sus dependencias.

        Args:
            server_address: Tupla (host, port) en la que se escuchan conexiones.
            RequestHandlerClass: Clase manejadora de peticiones.
            proxy: Proxy de datos corporativos. Si se omite, usa :class:`DataProxy`.
            audit_repo: Repositorio de auditoria. Si se omite, usa :class:`AuditRepository`.
            subject: Sujeto observable. Si se omite, usa :class:`ObservedSubject`.
            bind_and_activate: Si es ``True`` enlaza y activa el puerto inmediatamente.
        """
        self.proxy = proxy if proxy is not None else DataProxy()
        self.audit_repo = audit_repo if audit_repo is not None else AuditRepository()
        self.subject = subject if subject is not None else ObservedSubject()
        super().__init__(server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)


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
    try:
        server = ApplicationServer(("0.0.0.0", args.port), ServerHandler)  # nosec B104
    except OSError as err:
        logger.error("No se pudo iniciar el servidor en el puerto %s: %s", args.port, err)
        return 1

    try:
        logger.info("Servidor listo y escuchando en el puerto %s", args.port)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Servidor interrumpido por el usuario")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
