"""Pruebas del cliente Singleton."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from tpfi import singleton_client
from tpfi.protocol import decode_message, encode_message, make_response


def test_load_input_reads_object(tmp_path: Path) -> None:
    """Un archivo JSON valido se lee como diccionario."""
    path = tmp_path / "input.json"
    path.write_text('{"action": "get", "id": "x"}', encoding="utf-8")

    assert singleton_client.load_input(str(path)) == {"action": "get", "id": "x"}


def test_load_input_rejects_non_object(tmp_path: Path) -> None:
    """Un arreglo JSON de entrada no es un requerimiento valido."""
    path = tmp_path / "input.json"
    path.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(ValueError, match="objeto JSON"):
        singleton_client.load_input(str(path))


def test_load_input_missing_file_raises() -> None:
    """Un archivo inexistente produce ``OSError``."""
    with pytest.raises(OSError):
        singleton_client.load_input("no-existe.json")


def test_build_request_from_input_get() -> None:
    """Un requerimiento ``get`` se traduce a un mensaje de protocolo."""
    request = singleton_client.build_request_from_input({"action": "get", "id": "x"})

    assert request["action"] == "get"
    assert request["id"] == "x"


def test_build_request_from_input_rejects_unknown_action() -> None:
    """Una accion no admitida produce ``ValueError``."""
    with pytest.raises(ValueError, match="Accion no admitida"):
        singleton_client.build_request_from_input({"action": "borrar"})


def test_write_output_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Sin archivo de salida, la respuesta se emite por stdout."""
    singleton_client.write_output(None, {"status": "ok"})

    assert '"status": "ok"' in capsys.readouterr().out


def test_write_output_to_file(tmp_path: Path) -> None:
    """Con archivo de salida, la respuesta se graba en el archivo."""
    path = tmp_path / "output.json"

    singleton_client.write_output(str(path), {"status": "ok"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "ok"}


def test_run_request_sends_and_receives(monkeypatch: pytest.MonkeyPatch) -> None:
    """El requerimiento viaja y la respuesta se devuelve como diccionario."""
    left, right = socket.socketpair()
    try:
        monkeypatch.setattr(socket, "create_connection", lambda *a, **k: left)
        request = {"type": "request", "action": "get", "session_id": "s", "id": "x"}
        response = make_response("s", {"id": "x", "sede": "FCyT"})
        right.sendall(encode_message(response))

        result = singleton_client.run_request("localhost", 8080, request)

        assert result == response
        assert decode_message(right.recv(4096)) == request
    finally:
        right.close()


def test_main_writes_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """El flujo completo escribe la respuesta en el archivo de salida."""
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text('{"action": "get", "id": "x"}', encoding="utf-8")

    monkeypatch.setattr(
        singleton_client,
        "run_request",
        lambda host, port, request: make_response(request["session_id"], {"id": "x"}),
    )

    exit_code = singleton_client.main(["-i", str(input_path), "-o", str(output_path)])

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "ok"


def test_main_returns_error_on_bad_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Un requerimiento invalido hace que el proceso salga con codigo 1."""
    input_path = tmp_path / "input.json"
    input_path.write_text('{"action": "borrar"}', encoding="utf-8")

    exit_code = singleton_client.main(["-i", str(input_path)])

    assert exit_code == 1
