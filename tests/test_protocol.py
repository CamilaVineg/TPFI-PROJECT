"""Pruebas del protocolo de mensajes entre servidor y clientes."""

from __future__ import annotations

import socket

import pytest

from tpfi.protocol import (
    ACTION_GET,
    ACTION_SET,
    InvalidMessageError,
    JsonSocket,
    build_request,
    decode_message,
    encode_message,
    make_error,
    make_notification,
    make_response,
)


def test_encode_adds_newline_terminator() -> None:
    """Cada mensaje se serializa como una linea JSON terminada en ``\\n``."""
    encoded = encode_message({"action": "get"})

    assert encoded.endswith(b"\n")
    assert decode_message(encoded) == {"action": "get"}


def test_decode_accepts_string() -> None:
    """El decodificador admite tanto texto como bytes."""
    assert decode_message('{"a": 1}') == {"a": 1}


def test_decode_rejects_empty_message() -> None:
    """Un mensaje vacio no es valido."""
    with pytest.raises(InvalidMessageError, match="vacio"):
        decode_message("")


def test_decode_rejects_invalid_json() -> None:
    """Un contenido que no es JSON produce ``InvalidMessageError``."""
    with pytest.raises(InvalidMessageError, match="no es un JSON valido"):
        decode_message("{no es json")


def test_decode_rejects_non_object() -> None:
    """Solo se admiten objetos JSON, no arreglos ni escalares."""
    with pytest.raises(InvalidMessageError, match="objeto JSON"):
        decode_message("[1, 2, 3]")


def test_build_request_generates_session_and_client() -> None:
    """El requerimiento genera automaticamente sesion y UUID de CPU."""
    request = build_request(ACTION_GET, record_id="UADER-FCyT-IS2")

    assert request["type"] == "request"
    assert request["action"] == "get"
    assert request["id"] == "UADER-FCyT-IS2"
    assert request["session_id"]
    assert request["client_uuid"].isdigit()


def test_build_request_respects_provided_ids() -> None:
    """Si se proveen sesion y UUID de CPU, se conservan."""
    request = build_request(ACTION_SET, session_id="SES-1", client_uuid="CPU-1")

    assert request["session_id"] == "SES-1"
    assert request["client_uuid"] == "CPU-1"
    assert "id" not in request
    assert "data" not in request


def test_build_request_includes_data_for_set() -> None:
    """La accion ``set`` transporta los campos a escribir en ``data``."""
    request = build_request(ACTION_SET, record_id="x", data={"sede": "FCyT"})

    assert request["id"] == "x"
    assert request["data"] == {"sede": "FCyT"}


def test_make_response_shape() -> None:
    """La respuesta exitosa lleva estado ``ok`` y el resultado."""
    response = make_response("SES-1", {"id": "x"})

    assert response == {
        "type": "response",
        "status": "ok",
        "session_id": "SES-1",
        "data": {"id": "x"},
    }


def test_make_error_shape() -> None:
    """La respuesta de error lleva estado ``error`` y el mensaje."""
    response = make_error("SES-1", "rechazado")

    assert response["type"] == "response"
    assert response["status"] == "error"
    assert response["error"] == "rechazado"


def test_make_notification_shape() -> None:
    """La notificacion identifica la accion ``set`` que la origino."""
    notification = make_notification("SES-1", {"id": "x"})

    assert notification["type"] == "notification"
    assert notification["action"] == ACTION_SET
    assert notification["data"] == {"id": "x"}


def test_json_socket_roundtrip() -> None:
    """Un mensaje enviado por un extremo llega intacto al otro."""
    left, right = socket.socketpair()
    try:
        sender = JsonSocket(left)
        receiver = JsonSocket(right)

        sender.send({"action": "list"})

        assert receiver.receive() == {"action": "list"}
    finally:
        left.close()
        right.close()


def test_json_socket_reassembles_fragmented_message() -> None:
    """Los mensajes que llegan fragmentados se recomponen."""
    left, right = socket.socketpair()
    try:
        receiver = JsonSocket(right)

        left.sendall(b'{"a":')
        left.sendall(b"1}\n")

        assert receiver.receive() == {"a": 1}
    finally:
        left.close()
        right.close()


def test_json_socket_receive_on_closed_socket() -> None:
    """Un cierre sin mensaje pendiente produce ``ConnectionError``."""
    left, right = socket.socketpair()
    try:
        receiver = JsonSocket(right)
        left.close()

        with pytest.raises(ConnectionError):
            receiver.receive()
    finally:
        right.close()


def test_json_socket_close_tolerates_closed_socket() -> None:
    """Cerrar dos veces no lanza excepcion."""
    left, _ = socket.socketpair()
    channel = JsonSocket(left)
    channel.close()
    channel.close()
