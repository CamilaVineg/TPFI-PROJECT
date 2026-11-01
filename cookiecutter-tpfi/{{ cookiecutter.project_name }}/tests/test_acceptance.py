"""Casos de aceptacion exigidos por la consigna del {{ cookiecutter.package_name }}.

Cada prueba reproduce un escenario de uso completo sobre un servidor real
levantado en un puerto efimero, con repositorios simulados para no depender de
AWS. Los casos cubren el camino feliz, los argumentos malformados, los
requerimientos incompletos y las fallas de disponibilidad.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from {{ cookiecutter.package_name }} import observerclient, singletonclient
from {{ cookiecutter.package_name }}.config import CORPORATE_FIELDS
from {{ cookiecutter.package_name }}.patterns.observer import ObservedSubject
from {{ cookiecutter.package_name }}.protocol import (
    STATUS_ERROR,
    STATUS_OK,
    TYPE_NOTIFICATION,
    TYPE_RESPONSE,
    JsonSocket,
)
from {{ cookiecutter.package_name }}.proxy import DataProxy
from {{ cookiecutter.package_name }}.singletonproxyobserver import (
    ApplicationServer,
    ServerHandler,
)
from {{ cookiecutter.package_name }}.singletonproxyobserver import (
    parse_args as server_parse_args,
)

pytestmark = pytest.mark.acceptance


class _StopRunError(RuntimeError):
    """Senal para detener el bucle infinito de ``observerclient.run``."""


class FakeAuditRepository:
    """Pista de auditoria en memoria para los casos de aceptacion."""

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
        """Agrega una entrada de auditoria.

        Args:
            action: Accion solicitada.
            client_uuid: UUID de la CPU cliente.
            session_id: Sesion generada por el servidor.
            timestamp: Marca de tiempo ISO 8601.
            key: Registro afectado o ``*``.

        Returns:
            La entrada almacenada.
        """
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
    """Tabla ``CorporateData`` en memoria."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {
            "REC-001": {"id": "REC-001", "sede": "FCyT", "domicilio": "Mayo 385"}
        }

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Devuelve una copia del registro o ``None``."""
        item = self.items.get(record_id)
        return dict(item) if item is not None else None

    def scan(self) -> Iterator[dict[str, Any]]:
        """Recorre todos los registros."""
        yield from (dict(item) for item in self.items.values())

    def merge(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Aplica una actualizacion parcial con el tuple completo."""
        current = self.items.get(record_id)
        if current is None:
            merged: dict[str, Any] = dict.fromkeys(CORPORATE_FIELDS)
            merged.update(values)
            merged["id"] = record_id
        else:
            merged = {**current, **values}
        self.items[record_id] = merged
        return dict(merged)


ServerFixture = tuple[ApplicationServer, int, FakeAuditRepository, FakeDataRepository]


@pytest.fixture
def acceptance_server() -> Iterator[ServerFixture]:
    """Levanta el servidor de aplicaciones en un puerto efimero."""
    fake_repo = FakeDataRepository()
    audit_repo = FakeAuditRepository()
    server = ApplicationServer(
        ("127.0.0.1", 0),
        ServerHandler,
        proxy=DataProxy(repository=fake_repo),  # type: ignore[arg-type]
        audit_repo=audit_repo,  # type: ignore[arg-type]
        subject=ObservedSubject(),
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


def _send(port: int, request: dict[str, Any]) -> dict[str, Any]:
    """Envia un requerimiento y devuelve la respuesta del servidor.

    Args:
        port: Puerto del servidor.
        request: Mensaje de requerimiento.

    Returns:
        La respuesta recibida.
    """
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        channel = JsonSocket(sock)
        channel.send(request)
        return channel.receive()


def test_acceptance_happy_path_with_audit(acceptance_server: ServerFixture) -> None:
    """Get, list, set y subscribe funcionan y quedan auditados."""
    _, port, audit_repo, fake_repo = acceptance_server

    observer = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    try:
        observer_channel = JsonSocket(observer)
        observer_channel.send({"type": "request", "action": "subscribe", "client_uuid": "cpu-obs"})
        ack = observer_channel.receive()
        assert ack["type"] == TYPE_RESPONSE
        assert ack["status"] == STATUS_OK
        assert ack["data"]["subscribed"] is True

        get_response = _send(
            port,
            {"type": "request", "action": "get", "id": "REC-001", "client_uuid": "cpu-1"},
        )
        assert get_response["status"] == STATUS_OK
        assert get_response["data"]["sede"] == "FCyT"
        uuid.UUID(get_response["session_id"])

        list_response = _send(port, {"type": "request", "action": "list", "client_uuid": "cpu-1"})
        assert list_response["status"] == STATUS_OK
        assert [item["id"] for item in list_response["data"]] == ["REC-001"]

        set_response = _send(
            port,
            {
                "type": "request",
                "action": "set",
                "id": "REC-001",
                "data": {"telefono": "03442 43-1442"},
                "client_uuid": "cpu-1",
            },
        )
        assert set_response["status"] == STATUS_OK
        assert set_response["data"]["sede"] == "FCyT"
        assert set_response["data"]["telefono"] == "03442 43-1442"
        assert fake_repo.get("REC-001")["telefono"] == "03442 43-1442"

        notification = observer_channel.receive()
        assert notification["type"] == TYPE_NOTIFICATION
        assert notification["data"]["id"] == "REC-001"
        assert notification["session_id"] == set_response["session_id"]
    finally:
        observer.close()

    assert [entry["action"] for entry in audit_repo.records] == [
        "subscribe",
        "get",
        "list",
        "set",
    ]
    assert all(entry["session_id"] for entry in audit_repo.records)
    assert len({entry["session_id"] for entry in audit_repo.records}) == 4


def test_acceptance_server_rejects_client_session_id(
    acceptance_server: ServerFixture,
) -> None:
    """El servidor no acepta el ``session_id`` elegido por el cliente."""
    _, port, audit_repo, _ = acceptance_server

    response = _send(
        port,
        {
            "type": "request",
            "action": "list",
            "client_uuid": "cpu-1",
            "session_id": "sesion-elegida-por-el-cliente",
        },
    )

    assert response["status"] == STATUS_OK
    assert response["session_id"] != "sesion-elegida-por-el-cliente"
    assert audit_repo.records[0]["session_id"] == response["session_id"]


def test_acceptance_malformed_cli_arguments() -> None:
    """Los argumentos malformados se rechazan con error de linea de comandos."""
    with pytest.raises(SystemExit):
        server_parse_args(["--port", "no-es-un-puerto"])
    with pytest.raises(SystemExit):
        singletonclient.parse_args([])
    with pytest.raises(SystemExit):
        observerclient.parse_args(["--retry-interval", "0"])


def test_acceptance_malformed_input_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Un archivo de entrada que no es JSON hace salir al cliente con 1."""
    input_path = tmp_path / "input.json"
    input_path.write_text("{no es json", encoding="utf-8")

    with caplog.at_level("ERROR"):
        exit_code = singletonclient.main(["-i", str(input_path)])

    assert exit_code == 1
    assert "Fallo el requerimiento" in caplog.text


def test_acceptance_requirement_without_minimum_data(
    acceptance_server: ServerFixture,
) -> None:
    """Get sin id y set sin id o sin campos se rechazan con error."""
    _, port, _, _ = acceptance_server

    get_response = _send(port, {"type": "request", "action": "get", "client_uuid": "cpu-1"})
    assert get_response["status"] == STATUS_ERROR
    assert "obligatorio para get" in get_response["error"]

    set_without_id = _send(
        port,
        {"type": "request", "action": "set", "data": {"sede": "FCyT"}},
    )
    assert set_without_id["status"] == STATUS_ERROR
    assert "obligatorio para set" in set_without_id["error"]

    set_without_fields = _send(
        port,
        {"type": "request", "action": "set", "id": "REC-001", "data": {}},
    )
    assert set_without_fields["status"] == STATUS_ERROR
    assert "ningun campo" in set_without_fields["error"]


def test_acceptance_client_when_server_is_down(tmp_path: Path) -> None:
    """Si el servidor no esta disponible, el cliente Singleton sale con 1."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()

    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps({"action": "list", "id": "x"}),
        encoding="utf-8",
    )

    exit_code = singletonclient.main(
        ["-i", str(input_path), "-p", str(free_port), "-s", "127.0.0.1"]
    )

    assert exit_code == 1


def test_acceptance_observer_retries_when_server_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El observador espera y reintenta cuando el servidor no responde."""
    attempts: list[tuple[Any, ...]] = []
    sleeps: list[int] = []

    def fake_listen_once(*args: Any) -> None:
        attempts.append(args)
        raise OSError("servidor caido")

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)
        raise _StopRunError

    monkeypatch.setattr(observerclient, "listen_once", fake_listen_once)
    monkeypatch.setattr(observerclient.time, "sleep", fake_sleep)

    with pytest.raises(_StopRunError):
        observerclient.run("127.0.0.1", 1, 5, None, client_uuid="cpu-1")

    assert len(attempts) == 1
    assert sleeps == [5]


def test_acceptance_second_server_cannot_bind(
    acceptance_server: ServerFixture,
) -> None:
    """Levantar dos veces el servidor sobre el mismo puerto falla."""
    _, port, _, _ = acceptance_server

    with pytest.raises(OSError):
        ApplicationServer(("127.0.0.1", port), ServerHandler)
