"""Pruebas del cliente Observer."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from {{ cookiecutter.package_name }} import observerclient
from {{ cookiecutter.package_name }}.protocol import (
    InvalidMessageError,
    JsonSocket,
    make_error,
    make_notification,
    make_response,
)


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


class TimeoutOnceChannel(FakeChannel):
    """Canal que vence algunas lecturas antes de entregar los mensajes."""

    def __init__(self, messages: list[dict[str, Any]], timeouts: int = 1) -> None:
        """Crea el canal con la cantidad de timeouts previos a los mensajes.

        Args:
            messages: Mensajes a entregar en orden.
            timeouts: Cantidad de lecturas que deben vencer antes de entregar
                el proximo mensaje.
        """
        super().__init__(messages)
        self.pending_timeouts = timeouts

    def receive(self) -> dict[str, Any]:
        """Simula un vencimiento de lectura o entrega el proximo mensaje.

        Returns:
            El proximo mensaje disponible.

        Raises:
            TimeoutError: Mientras queden vencimientos pendientes.
        """
        if self.pending_timeouts > 0:
            self.pending_timeouts -= 1
            raise TimeoutError("sin datos")
        return super().receive()


def test_build_subscription_includes_client_uuid() -> None:
    """La subscripcion transporta el UUID de CPU del observador."""
    request = observerclient.build_subscription("cpu-1")

    assert request["action"] == "subscribe"
    assert request["client_uuid"] == "cpu-1"


def test_emit_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Sin archivo de salida, la notificacion se muestra por stdout."""
    observerclient.emit({"type": "notification"}, None)

    assert "notification" in capsys.readouterr().out


def test_emit_appends_to_file_and_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Con archivo de salida, la notificacion se graba y ademas va a stdout."""
    path = tmp_path / "notif.json"

    observerclient.emit({"id": "a"}, str(path))
    observerclient.emit({"id": "b"}, str(path))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    printed = capsys.readouterr().out
    assert '"id": "a"' in printed
    assert '"id": "b"' in printed


def test_listen_once_subscribes_emits_and_ignores_other_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Se consume el ACK y solo se emiten los mensajes de tipo notificacion."""
    channel = FakeChannel(
        [
            make_response("ack-1", {"subscribed": True}),
            make_notification("s-1", {"id": "a"}),
            make_response("ack-2", {"ignored": True}),
            make_notification("s-2", {"id": "b"}),
        ]
    )
    monkeypatch.setattr(observerclient, "connect", lambda *a, **k: channel)
    output = tmp_path / "notif.json"

    with pytest.raises(ConnectionError):
        observerclient.listen_once("localhost", 8080, "cpu-1", str(output))

    assert channel.sent[0]["action"] == "subscribe"
    assert channel.sent[0]["client_uuid"] == "cpu-1"
    assert channel.closed is True
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"id": "a"' in lines[0]
    assert '"id": "b"' in lines[1]
    printed = capsys.readouterr().out
    assert '"id": "a"' in printed
    assert '"id": "b"' in printed
    assert "ignored" not in printed


def test_listen_once_raises_when_subscription_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un ACK con estado error corta la escucha y permite reintentar."""
    channel = FakeChannel([make_error("ack-1", "suscripcion rechazada")])
    monkeypatch.setattr(observerclient, "connect", lambda *a, **k: channel)

    with pytest.raises(InvalidMessageError, match="rechazo la subscripcion"):
        observerclient.listen_once("localhost", 8080, "cpu-1", None)

    assert channel.closed is True


def test_connect_returns_json_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """La conexion devuelve un canal JSON envuelto sobre el socket."""
    sock = socket.socket()
    try:
        monkeypatch.setattr(socket, "create_connection", lambda *a, **k: sock)

        channel = observerclient.connect("localhost", 8080)

        assert isinstance(channel, JsonSocket)
    finally:
        sock.close()


def test_connect_sets_a_polling_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras conectar, la escucha usa un timeout corto para atender Ctrl+C.

    El timeout no marca una desconexion: solo limita cuanto tiempo puede pasar
    el hilo principal bloqueado en ``recv`` antes de procesar la senal.
    """
    sock = socket.socket()
    sock.settimeout(observerclient.CONNECTION_TIMEOUT)
    try:
        monkeypatch.setattr(socket, "create_connection", lambda *a, **k: sock)

        observerclient.connect("localhost", 8080)

        assert sock.gettimeout() == observerclient.RECEIVE_TIMEOUT
    finally:
        sock.close()


def test_listen_once_survives_receive_timeouts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Los vencimientos de lectura no cortan la escucha ni pierden mensajes."""
    channel = TimeoutOnceChannel(
        [
            make_response("ack-1", {"subscribed": True}),
            make_notification("s-1", {"id": "a"}),
            make_notification("s-2", {"id": "b"}),
        ],
        timeouts=2,
    )
    monkeypatch.setattr(observerclient, "connect", lambda *a, **k: channel)

    with pytest.raises(ConnectionError):
        observerclient.listen_once("localhost", 8080, "cpu-1", None)

    printed = capsys.readouterr().out
    assert '"id": "a"' in printed
    assert '"id": "b"' in printed


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

    monkeypatch.setattr(observerclient, "listen_once", fake_listen_once)
    monkeypatch.setattr(observerclient.time, "sleep", fake_sleep)

    with pytest.raises(_StopRunError):
        observerclient.run("localhost", 8080, 30, None, client_uuid="cpu-1")

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

    monkeypatch.setattr(observerclient, "listen_once", fake_listen_once)
    monkeypatch.setattr(observerclient.time, "sleep", fake_sleep)

    with pytest.raises(_StopRunError):
        observerclient.run("localhost", 8080, 30, None)

    assert attempts[0][2].isdigit()


def test_run_terminates_on_non_socket_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una excepcion que no es de socket termina el bucle de escucha."""

    def fake_listen_once(*args: Any) -> None:
        raise InvalidMessageError("mensaje corrupto")

    monkeypatch.setattr(observerclient, "listen_once", fake_listen_once)

    with pytest.raises(InvalidMessageError, match="mensaje corrupto"):
        observerclient.run("localhost", 8080, 30, None)


def test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """La cancelacion manual del usuario finaliza el proceso con codigo 0."""

    def fake_run(*args: Any) -> int:
        raise KeyboardInterrupt()

    monkeypatch.setattr(observerclient, "run", fake_run)
    assert observerclient.main([]) == 0
