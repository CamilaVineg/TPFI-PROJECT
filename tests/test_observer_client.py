"""Pruebas del cliente Observer."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from tpfi import observer_client
from tpfi.protocol import JsonSocket, make_notification


class FakeChannel:
    """Doble de ``JsonSocket`` que entrega mensajes enlatados."""

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        """Crea el doble con los mensajes que devolvera ``receive``.

        Args:
            messages: Mensajes a entregar en orden. Al agotarlos, ``receive``
                lanza ``ConnectionError`` para simular la caida del socket.
        """
        self.messages = list(messages)
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    def send(self, message: dict[str, Any]) -> None:
        """Registra el mensaje enviado.

        Args:
            message: Mensaje a registrar.
        """
        self.sent.append(message)

    def receive(self) -> dict[str, Any]:
        """Devuelve el proximo mensaje o simula el cierre.

        Returns:
            El proximo mensaje disponible.

        Raises:
            ConnectionError: Cuando no quedan mensajes.
        """
        if not self.messages:
            raise ConnectionError("conexion cerrada")
        return self.messages.pop(0)

    def close(self) -> None:
        """Marca el canal como cerrado."""
        self.closed = True


class _StopRunError(RuntimeError):
    """Senal de prueba para detener el bucle infinito de ``run``."""


def test_build_subscription_includes_client_uuid() -> None:
    """La subscripcion transporta el UUID de CPU del observador."""
    request = observer_client.build_subscription("cpu-1")

    assert request["action"] == "subscribe"
    assert request["client_uuid"] == "cpu-1"


def test_emit_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Sin archivo de salida, la notificacion se muestra por stdout."""
    observer_client.emit({"type": "notification"}, None)

    assert "notification" in capsys.readouterr().out


def test_emit_appends_to_file(tmp_path: Path) -> None:
    """Con archivo de salida, cada notificacion se agrega al final."""
    path = tmp_path / "notif.json"

    observer_client.emit({"id": "a"}, str(path))
    observer_client.emit({"id": "b"}, str(path))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_listen_once_subscribes_and_emits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La subscripcion se envia y cada notificacion se emite en orden."""
    channel = FakeChannel(
        [
            make_notification("s-1", {"id": "a"}),
            make_notification("s-2", {"id": "b"}),
        ]
    )
    monkeypatch.setattr(observer_client, "connect", lambda *a, **k: channel)
    output = tmp_path / "notif.json"

    with pytest.raises(ConnectionError):
        observer_client.listen_once("localhost", 8080, "cpu-1", str(output))

    assert channel.sent[0]["action"] == "subscribe"
    assert channel.sent[0]["client_uuid"] == "cpu-1"
    assert channel.closed is True
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_connect_returns_json_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """La conexion devuelve un canal JSON envuelto sobre el socket."""
    sock = socket.socket()
    try:
        monkeypatch.setattr(socket, "create_connection", lambda *a, **k: sock)

        channel = observer_client.connect("localhost", 8080)

        assert isinstance(channel, JsonSocket)
    finally:
        sock.close()


def test_run_reconnects_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ante una caida, ``run`` espera el intervalo y reintenta."""
    attempts: list[tuple[Any, ...]] = []
    sleeps: list[int] = []

    def fake_listen_once(*args: Any) -> None:
        attempts.append(args)
        raise OSError("servidor caido")

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)
        raise _StopRunError()

    monkeypatch.setattr(observer_client, "listen_once", fake_listen_once)
    monkeypatch.setattr(observer_client.time, "sleep", fake_sleep)

    with pytest.raises(_StopRunError):
        observer_client.run("localhost", 8080, 30, None, client_uuid="cpu-1")

    assert attempts == [("localhost", 8080, "cpu-1", None)]
    assert sleeps == [30]


def test_run_resolves_client_uuid_when_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin UUID de CPU, ``run`` lo releva automaticamente del equipo."""
    attempts: list[tuple[Any, ...]] = []

    def fake_listen_once(*args: Any) -> None:
        attempts.append(args)
        raise OSError("servidor caido")

    def fake_sleep(seconds: int) -> None:
        raise _StopRunError()

    monkeypatch.setattr(observer_client, "listen_once", fake_listen_once)
    monkeypatch.setattr(observer_client.time, "sleep", fake_sleep)

    with pytest.raises(_StopRunError):
        observer_client.run("localhost", 8080, 30, None)

    assert attempts[0][2].isdigit()
