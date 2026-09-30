"""Pruebas de la configuracion y del versionado del proyecto."""

from __future__ import annotations

import pytest

from tpfi import __build__, __version__, get_build
from tpfi.config import CORPORATE_FIELDS, DEFAULT_PORT, get_region


def test_version_is_defined() -> None:
    """El paquete expone una version semantica."""
    assert __version__.count(".") >= 1


def test_build_is_numeric() -> None:
    """El build se expone como texto sin espacios y es numerico."""
    assert __build__.isdigit()


def test_get_build_matches_attribute() -> None:
    """``get_build`` es consistente con el atributo del paquete."""
    assert get_build() == __build__


def test_default_port_is_valid() -> None:
    """El puerto por defecto esta en el rango de los puertos TCP."""
    assert 1 <= DEFAULT_PORT <= 65535


def test_corporate_fields_are_listed() -> None:
    """Se enumeran todos los campos del tuple CorporateData."""
    assert "id" in CORPORATE_FIELDS
    assert "CUIT" in CORPORATE_FIELDS
    assert "web" in CORPORATE_FIELDS


def test_get_region_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """La region se toma de ``AWS_DEFAULT_REGION`` si esta definida."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    assert get_region() == "us-east-1"


def test_get_region_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin la variable de entorno se devuelve la region de la plantilla."""
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    assert get_region() == "us-west-2"
