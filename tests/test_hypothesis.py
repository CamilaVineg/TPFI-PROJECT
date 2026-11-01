"""Propiedades del protocolo y del proxy verificadas con Hypothesis.

Estas pruebas generan entradas aleatorias para comprobar invariantes que los
ejemplos puntuales no alcanzan a cubrir: serializacion, robustez del
decodificador y validacion de identificadores y campos.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tpfi.protocol import (
    ACTIONS,
    InvalidMessageError,
    build_request,
    decode_message,
    encode_message,
)
from tpfi.proxy import ALLOWED_FIELDS, DataProxy, InvalidRequestError

JSON_SCALARS = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text()
JSON_VALUES = st.recursive(
    JSON_SCALARS,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=20,
)
JSON_OBJECTS = st.dictionaries(st.text(), JSON_VALUES, max_size=8)


class _UnusedRepository:
    """Repositorio que falla si el proxy intenta acceder a la base."""

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Falla: el proxy no deberia llegar a la base en estas pruebas."""
        raise AssertionError("get no deberia invocarse")

    def scan(self) -> list[dict[str, Any]]:
        """Falla: el proxy no deberia recorrer la base en estas pruebas."""
        raise AssertionError("scan no deberia invocarse")

    def merge(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Falla: el proxy no deberia escribir en estas pruebas."""
        raise AssertionError("merge no deberia invocarse")


@settings(max_examples=100)
@given(JSON_OBJECTS)
def test_encode_decode_roundtrip(message: dict[str, Any]) -> None:
    """Todo objeto JSON sobrevive al viaje por el protocolo."""
    assert decode_message(encode_message(message)) == message


@settings(max_examples=100)
@given(st.binary(max_size=512))
def test_decode_only_raises_invalid_message(raw: bytes) -> None:
    """Cualquier byte de entrada se rechaza con ``InvalidMessageError``."""
    with contextlib.suppress(InvalidMessageError):
        decode_message(raw)


@settings(max_examples=50)
@given(st.sampled_from(ACTIONS), st.text(), st.text())
def test_build_request_always_includes_control_fields(
    action: str,
    client_uuid: str,
    session_id: str,
) -> None:
    """La sesion y el UUID de CPU siempre viajan en el requerimiento."""
    request = build_request(action, client_uuid=client_uuid, session_id=session_id)

    assert request["action"] == action
    if client_uuid:
        assert request["client_uuid"] == client_uuid
    else:
        assert request["client_uuid"].isdigit()
    if session_id:
        assert request["session_id"] == session_id
    else:
        uuid.UUID(request["session_id"])


@settings(max_examples=50)
@given(st.text())
def test_build_request_generates_a_valid_uuid(value: str) -> None:
    """Cuando no se informa la sesion, se genera un UUID4 valido."""
    request = build_request("get", client_uuid=value)

    uuid.UUID(request["session_id"])


@settings(max_examples=100)
@given(st.text())
def test_record_id_validation(value: str) -> None:
    """Solo los identificadores con texto no vacio son aceptables."""
    if value.strip():
        assert DataProxy._validate_id(value) == value
    else:
        with pytest.raises(InvalidRequestError, match="obligatorio"):
            DataProxy._validate_id(value)


@settings(max_examples=100)
@given(st.dictionaries(st.text(min_size=1), st.integers(), min_size=1))
def test_set_rejects_fields_outside_the_tuple(fields: dict[str, int]) -> None:
    """Cualquier atributo ajeno al tuple se rechaza antes de tocar DynamoDB."""
    if set(fields) <= ALLOWED_FIELDS:
        return

    proxy = DataProxy(_UnusedRepository())  # type: ignore[arg-type]
    with pytest.raises(InvalidRequestError):
        proxy.set("REC-1", fields)
