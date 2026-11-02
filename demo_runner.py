"""Script interactivo de prueba y demostracion paso a paso para el TPFI IS2.

Permite simular o ejecutar en vivo:
1. Inicio del servidor multihilo TCP (SingletonProxyObserverTPFI).
2. Conexion del cliente observador (ObserverClient) para recibir cambios en tiempo real.
3. Envio de operaciones con el cliente (SingletonClient):
   - Lectura (get)
   - Modificacion / Creacion (set) con notificacion en cascada al observador
   - Listado paginado (list) con el patron Iterator
4. Registro de auditoria en CorporateLog.

Puede ejecutarse en modo 'mock' (sin necesidad de credenciales AWS) o en modo real.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Asegurar que Python encuentre el paquete 'tpfi' dentro de 'src/' sin requerir pip install
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Mock defensivo de boto3/botocore en caso de no tener instalada la librería en el entorno
try:
    import boto3  # noqa: F401
except ModuleNotFoundError:
    from unittest.mock import MagicMock

    mock_boto3 = MagicMock()
    sys.modules["boto3"] = mock_boto3
    mock_botocore = MagicMock()
    sys.modules["botocore"] = mock_botocore
    mock_exceptions = MagicMock()

    class BotoCoreError(Exception):
        """Error base simulado de botocore."""

    class ClientError(Exception):
        """Error simulado devuelto por un cliente de AWS."""

    mock_exceptions.BotoCoreError = BotoCoreError
    mock_exceptions.ClientError = ClientError
    sys.modules["botocore.exceptions"] = mock_exceptions

from tpfi.patterns.observer import ObservedSubject
from tpfi.protocol import JsonSocket
from tpfi.proxy import DataProxy
from tpfi.singletonproxyobserver import ApplicationServer, ServerHandler


class MemoryAuditRepository:
    """Repositorio de auditoria en memoria para demostracion sin AWS."""

    def __init__(self) -> None:
        """Inicializa la lista de entradas de auditoria vacia."""
        self.logs: list[dict[str, Any]] = []

    def record(
        self,
        action: str,
        client_uuid: str,
        session_id: str,
        timestamp: str,
        key: str = "*",
    ) -> dict[str, Any]:
        """Agrega una entrada de auditoria en memoria.

        Args:
            action: Accion solicitada por el cliente.
            client_uuid: UUID de la CPU que origina el requerimiento.
            session_id: Identificador unico de la sesion.
            timestamp: Marca de tiempo en formato ISO 8601.
            key: Identificador del registro afectado o ``"*"`` si no aplica.

        Returns:
            La entrada de auditoria almacenada.
        """
        entry = {
            "session_id": session_id,
            "action": action,
            "client_uuid": client_uuid,
            "key": key,
            "timestamp": timestamp,
        }
        self.logs.append(entry)
        return entry

    def list(self) -> list[dict[str, Any]]:
        """Devuelve una copia de todas las entradas de auditoria.

        Returns:
            La lista de entradas registradas.
        """
        return list(self.logs)


class MemoryDataRepository:
    """Repositorio de datos en memoria para demostracion sin AWS."""

    def __init__(self) -> None:
        """Carga un registro corporativo de ejemplo."""
        self.data: dict[str, dict[str, Any]] = {
            "UADER-FCyT-IS2": {
                "id": "UADER-FCyT-IS2",
                "sede": "FCyT Central",
                "localidad": "Concepcion del Uruguay",
                "provincia": "Entre Rios",
            }
        }

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Lee un registro por su clave primaria.

        Args:
            record_id: Clave del registro buscado.

        Returns:
            Una copia del registro o ``None`` si no existe.
        """
        item = self.data.get(record_id)
        return dict(item) if item is not None else None

    def scan(self) -> Iterator[dict[str, Any]]:
        """Recorre todos los registros almacenados.

        Yields:
            Copias de los registros, en el orden del diccionario interno.
        """
        yield from (dict(v) for v in self.data.values())

    def put(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Escribe un registro completo en memoria.

        Args:
            record_id: Clave primaria del registro.
            values: Atributos a escribir.

        Returns:
            El registro almacenado.
        """
        item = {"id": record_id, **values}
        self.data[record_id] = item
        return item

    def merge(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Actualiza un registro conservando los atributos previos en memoria.

        Args:
            record_id: Clave primaria del registro.
            values: Atributos a modificar o agregar.

        Returns:
            El registro resultante tras la actualizacion.
        """
        current = self.data.get(record_id, {"id": record_id})
        updated = {**current, **values}
        self.data[record_id] = updated
        return dict(updated)


def print_step(title: str) -> None:
    """Imprime el encabezado de un paso de la demostracion.

    Args:
        title: Texto que describe el paso.
    """
    print("\n" + "=" * 70)
    print(f" >>> {title}")
    print("=" * 70)


def run_demo() -> None:
    """Ejecuta la demostracion completa contra repositorios en memoria."""
    print_step("PASO 1: Inicializando Servidor TCP con Patrones Proxy + Singleton + Observer")
    mem_data = MemoryDataRepository()
    mem_audit = MemoryAuditRepository()
    proxy = DataProxy(repository=mem_data)  # type: ignore[arg-type]
    subject = ObservedSubject()

    port = 8888
    server = ApplicationServer(
        ("127.0.0.1", port),
        ServerHandler,
        proxy=proxy,
        audit_repo=mem_audit,  # type: ignore[arg-type]
        subject=subject,
    )

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    print(f"[*] Servidor escuchando exitosamente en 127.0.0.1:{port}")

    print_step("PASO 2: Conectando ObserverClient y enviando suscripcion")
    obs_sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    obs_channel = JsonSocket(obs_sock)
    obs_channel.send(
        {
            "type": "request",
            "action": "subscribe",
            "client_uuid": "CPU-OBSERVADOR-1",
            "session_id": "sesion-obs-1",
        }
    )
    sub_resp = obs_channel.receive()
    print("[ObserverClient] Respuesta del servidor:", json.dumps(sub_resp, indent=2))
    print("[*] ObserverClient suscrito y a la espera de eventos en cascada...")

    # Hilo para que el observador escuche notificaciones
    def observer_listener() -> None:
        try:
            notif = obs_channel.receive()
            print("\n[!] >>> NOTIFICACION EN CASCADA RECIBIDA POR ObserverClient! <<<")
            print(json.dumps(notif, indent=2))
        except (OSError, ConnectionResetError):
            pass
        except Exception as e:
            print("[Observer error]:", e)

    listener_thread = threading.Thread(target=observer_listener, daemon=True)
    listener_thread.start()

    time.sleep(0.3)

    print_step("PASO 3: Ejecutando SingletonClient para 'get' sobre UADER-FCyT-IS2")
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as sock:
        ch = JsonSocket(sock)
        req_get = {
            "type": "request",
            "action": "get",
            "id": "UADER-FCyT-IS2",
            "client_uuid": "CPU-CLIENTE-1",
            "session_id": "sesion-cli-get",
        }
        print("[SingletonClient] Enviando:", json.dumps(req_get, indent=2))
        ch.send(req_get)
        resp_get = ch.receive()
        print("[SingletonClient] Recibido:", json.dumps(resp_get, indent=2))

    time.sleep(0.3)

    print_step("PASO 4: Ejecutando SingletonClient para 'set' (Modificacion parcial)")
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as sock:
        ch = JsonSocket(sock)
        req_set = {
            "type": "request",
            "action": "set",
            "id": "UADER-FCyT-IS2",
            "data": {
                "telefono": "03442 43-1442",
                "web": "http://fcyt.uader.edu.ar",
            },
            "client_uuid": "CPU-CLIENTE-1",
            "session_id": "sesion-cli-set",
        }
        print("[SingletonClient] Enviando actualizacion:", json.dumps(req_set, indent=2))
        ch.send(req_set)
        resp_set = ch.receive()
        print("[SingletonClient] Respuesta recibida:", json.dumps(resp_set, indent=2))

    listener_thread.join(timeout=1.0)
    time.sleep(0.3)

    print_step("PASO 5: Ejecutando SingletonClient para 'list' (Recorrido con Iterator)")
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as sock:
        ch = JsonSocket(sock)
        req_list = {
            "type": "request",
            "action": "list",
            "client_uuid": "CPU-CLIENTE-1",
            "session_id": "sesion-cli-list",
        }
        ch.send(req_list)
        resp_list = ch.receive()
        print("[SingletonClient] Listado recibido:", json.dumps(resp_list, indent=2))

    print_step("PASO 6: Verificacion de la Auditoria Obligatoria (CorporateLog)")
    print(f"Total registros de auditoria guardados: {len(mem_audit.logs)}")
    for i, log in enumerate(mem_audit.logs, 1):
        print(f" {i}. Accion: {log['action']} | Clave: {log['key']} | Sesion: {log['session_id']}")

    print_step("DEMOSTRACION FINALIZADA CON EXITO")
    obs_sock.close()
    server.subject.shutdown()
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    run_demo()
