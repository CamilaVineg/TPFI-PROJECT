"""Pruebas del parseo de argumentos de los tres programas."""

from __future__ import annotations

import pytest

from tpfi import observer_client, server, singleton_client


def test_server_default_port() -> None:
    """El servidor usa el puerto configurado por defecto."""
    args = server.parse_args([])

    assert args.port == 8080
    assert args.verbose is False


def test_server_accepts_port_and_verbose() -> None:
    """El servidor acepta puerto y bandera de verbose."""
    args = server.parse_args(["-p", "9090", "-v"])

    assert args.port == 9090
    assert args.verbose is True


def test_server_rejects_invalid_port() -> None:
    """Un puerto no numerico se rechaza."""
    with pytest.raises(SystemExit):
        server.parse_args(["-p", "no-es-un-puerto"])


def test_server_requires_known_arguments() -> None:
    """Los argumentos malformados se rechazan."""
    with pytest.raises(SystemExit):
        server.parse_args(["--inexistente"])


def test_client_requires_input() -> None:
    """El cliente Singleton exige el archivo de entrada."""
    with pytest.raises(SystemExit):
        singleton_client.parse_args([])


def test_client_accepts_input_and_output() -> None:
    """El cliente acepta entrada, salida y verbose."""
    args = singleton_client.parse_args(["-i", "in.json", "-o", "out.json", "-v"])

    assert args.input == "in.json"
    assert args.output == "out.json"
    assert args.verbose is True


def test_client_output_is_optional() -> None:
    """La salida es opcional y por defecto es ``None``."""
    args = singleton_client.parse_args(["-i", "in.json"])

    assert args.output is None


def test_observer_defaults() -> None:
    """El observador aplica host, puerto y reintento por defecto."""
    args = observer_client.parse_args([])

    assert args.host == "localhost"
    assert args.port == 8080
    assert args.retry_interval == 30


def test_observer_accepts_host_and_port() -> None:
    """El observador acepta host, puerto e intervalo de reintento."""
    args = observer_client.parse_args(["-s", "example.com", "-p", "9000", "-r", "5"])

    assert args.host == "example.com"
    assert args.port == 9000
    assert args.retry_interval == 5


def test_observer_rejects_negative_retry() -> None:
    """Un intervalo de reintento negativo se rechaza."""
    with pytest.raises(SystemExit):
        observer_client.parse_args(["--retry-interval=-1"])
