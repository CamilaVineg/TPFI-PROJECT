"""Pruebas integrales y unitarias del servidor de aplicaciones TCP."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from tpfi.patterns.observer import ObservedSubject
from tpfi.protocol import (
    STATUS_ERROR,
    STATUS_OK,
    TYPE_NOTIFICATION,
    TYPE_RESPONSE,
    JsonSocket,
)
from tpfi.proxy import DataProxy
from tpfi.server import ApplicationServer, ServerHandler, main, parse_args


class FakeAuditRepository:
    """Doble de prueba para el repositorio de auditoria."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        action: str,
        client_uuid: str,
        session_id: str,
        timestamp: str,
        key: str = "*",
    ) -> dict[str, Any]:
        entry = {
            "action": action,
            "client_uuid": client_uuid,
            "session_id": session_id,
            "timestamp": timestamp,
            "key": key,
        }
        self.records.append(entry)
        return entry


class FakeDataRepository:
    """Doble de prueba para el repositorio de datos corporativos."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {
            "REC-001": {"id": "REC-001", "sede": "FCyT", "domicilio": "Mayo 385"}
        }

    def get(self, record_id: str) -> dict[str, Any] | None:
        item = self.items.get(record_id)
        return dict(item) if item is not None else None

    def list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.items.values()]

    def put(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        item = {"id": record_id, **values}
        self.items[record_id] = item
        return item


@pytest.fixture
def test_server() -> (
    Iterator[tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository]]
):
    """Crea e inicia un servidor de aplicaciones en un puerto efimero (0)."""
    fake_repo = FakeDataRepository()
    proxy = DataProxy(repository=fake_repo)  # type: ignore[arg-type]
    audit_repo = FakeAuditRepository()
    subject = ObservedSubject()

    server = ApplicationServer(
        ("127.0.0.1", 0),
        ServerHandler,
        proxy=proxy,
        audit_repo=audit_repo,  # type: ignore[arg-type]
        subject=subject,
    )
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    yield server, port, audit_repo, fake_repo

    server.subject.shutdown()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2.0)


def test_server_parse_args_defaults() -> None:
    """El servidor asigna puerto 8080 por defecto."""
    args = parse_args([])
    assert args.port == 8080
    assert args.verbose is False


def test_server_get_action_success(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """La accion get devuelve el registro y genera auditoria."""
    _, port, audit_repo, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "get",
                "id": "REC-001",
                "client_uuid": "cpu-123",
                "session_id": "sess-get-1",
            }
        )
        response = channel.receive()

    assert response["type"] == TYPE_RESPONSE
    assert response["status"] == STATUS_OK
    assert response["session_id"] == "sess-get-1"
    assert response["data"]["id"] == "REC-001"
    assert response["data"]["sede"] == "FCyT"

    assert len(audit_repo.records) == 1
    assert audit_repo.records[0]["action"] == "get"
    assert audit_repo.records[0]["key"] == "REC-001"
    assert audit_repo.records[0]["client_uuid"] == "cpu-123"


def test_server_get_action_not_found(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """La accion get sobre un registro inexistente devuelve error y audita."""
    _, port, audit_repo, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "get",
                "id": "REC-999",
                "client_uuid": "cpu-123",
                "session_id": "sess-get-2",
            }
        )
        response = channel.receive()

    assert response["type"] == TYPE_RESPONSE
    assert response["status"] == STATUS_ERROR
    assert "no existe" in response["error"]

    assert len(audit_repo.records) == 1
    assert audit_repo.records[0]["action"] == "get"
    assert audit_repo.records[0]["key"] == "REC-999"


def test_server_list_action_success(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """La accion list devuelve todos los registros y audita."""
    _, port, audit_repo, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "list",
                "client_uuid": "cpu-list-1",
                "session_id": "sess-list-1",
            }
        )
        response = channel.receive()

    assert response["type"] == TYPE_RESPONSE
    assert response["status"] == STATUS_OK
    assert isinstance(response["data"], list)
    assert len(response["data"]) == 1
    assert response["data"][0]["id"] == "REC-001"

    assert len(audit_repo.records) == 1
    assert audit_repo.records[0]["action"] == "list"
    assert audit_repo.records[0]["key"] == "*"


def test_server_set_action_and_cascade_notification(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """El set responde al solicitante y notifica en cascada a observadores."""
    _, port, audit_repo, fake_repo = test_server

    obs_sock = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    obs_channel = JsonSocket(obs_sock)
    obs_channel.send(
        {
            "type": "request",
            "action": "subscribe",
            "client_uuid": "obs-uuid-1",
            "session_id": "sess-sub-1",
        }
    )
    sub_resp = obs_channel.receive()
    assert sub_resp["status"] == STATUS_OK
    assert sub_resp["data"]["subscribed"] is True

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as set_sock:
        set_channel = JsonSocket(set_sock)
        set_channel.send(
            {
                "type": "request",
                "action": "set",
                "id": "REC-002",
                "data": {"sede": "Central", "telefono": "4321"},
                "client_uuid": "cpu-set-1",
                "session_id": "sess-set-1",
            }
        )
        set_resp = set_channel.receive()

    assert set_resp["status"] == STATUS_OK
    assert set_resp["data"]["id"] == "REC-002"
    assert set_resp["data"]["sede"] == "Central"

    # Verificar notificacion recibida por el observador
    notification = obs_channel.receive()
    assert notification["type"] == TYPE_NOTIFICATION
    assert notification["action"] == "set"
    assert notification["data"]["id"] == "REC-002"

    obs_sock.close()

    assert fake_repo.get("REC-002") is not None
    assert len(audit_repo.records) == 2  # subscribe + set


def test_server_set_invalid_data(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Un set con data invalida rechaza el requerimiento con error."""
    _, port, _, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "set",
                "id": "REC-001",
                "data": "no-es-un-dict",
                "client_uuid": "cpu-err",
                "session_id": "sess-set-err",
            }
        )
        response = channel.receive()

    assert response["status"] == STATUS_ERROR
    assert "debe ser un objeto JSON" in response["error"]


def test_server_unknown_action(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Una accion no reconocida devuelve error."""
    _, port, _, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "invalid_action",
                "client_uuid": "cpu-err",
                "session_id": "sess-err",
            }
        )
        response = channel.receive()

    assert response["status"] == STATUS_ERROR
    assert "Accion invalida" in response["error"]


def test_server_main_failed_bind() -> None:
    """Si el puerto esta ocupado, main devuelve codigo 1."""
    bound_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bound_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    bound_sock.bind(("0.0.0.0", 0))
    port = bound_sock.getsockname()[1]

    try:
        ret = main(["-p", str(port)])
        assert ret == 1
    finally:
        bound_sock.close()


def test_server_main_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyboardInterrupt en main finaliza ordenadamente con codigo 0."""

    def mock_serve_forever(self: Any) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(ApplicationServer, "serve_forever", mock_serve_forever)
    assert main(["-p", "8888"]) == 0


def test_server_invalid_json_message(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Enviar JSON invalido es ignorado sin colapsar el servidor."""
    _, port, _, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        sock.sendall(b"NOT_JSON_DATA\n")
        time.sleep(0.05)


def test_server_audit_exception(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Una falla en auditoria se registra pero permite continuar."""
    _, port, audit_repo, _ = test_server

    def fail_record(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Audit DB failure")

    audit_repo.record = fail_record  # type: ignore[assignment]

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send({"type": "request", "action": "list", "session_id": "s1"})
        resp = channel.receive()

    assert resp["status"] == STATUS_OK


def test_server_proxy_unexpected_exception(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Una falla no controlada en el proxy retorna un error 500 interno."""
    server, port, _, _ = test_server

    def fail_list() -> list[dict[str, Any]]:
        raise RuntimeError("DynamoDB down")

    server.proxy.list = fail_list  # type: ignore[assignment]

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send({"type": "request", "action": "list", "session_id": "s2"})
        resp = channel.receive()

    assert resp["status"] == STATUS_ERROR
    assert "DynamoDB down" in resp["error"]


def test_server_set_missing_record_id(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Un set sin id es rechazado con error."""
    _, port, _, _ = test_server

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(
            {
                "type": "request",
                "action": "set",
                "data": {"sede": "Central"},
                "session_id": "s3",
            }
        )
        resp = channel.receive()

    assert resp["status"] == STATUS_ERROR
    assert "obligatorio para set" in resp["error"]


def test_server_subscribe_duplicate_error(
    test_server: tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository],
) -> None:
    """Suscribir dos veces el mismo UUID devuelve error al segundo intento."""
    _, port, _, _ = test_server

    sock1 = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    ch1 = JsonSocket(sock1)
    ch1.send(
        {
            "type": "request",
            "action": "subscribe",
            "client_uuid": "dup-uuid",
            "session_id": "s-sub-1",
        }
    )
    r1 = ch1.receive()
    assert r1["status"] == STATUS_OK

    sock2 = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    ch2 = JsonSocket(sock2)
    ch2.send(
        {
            "type": "request",
            "action": "subscribe",
            "client_uuid": "dup-uuid",
            "session_id": "s-sub-2",
        }
    )
    r2 = ch2.receive()
    assert r2["status"] == STATUS_ERROR
    assert "ya se encuentra subscripto" in r2["error"]

    sock1.close()
    sock2.close()
