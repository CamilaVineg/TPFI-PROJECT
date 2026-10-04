"""Pruebas de los repositorios Singleton sobre DynamoDB.

Se emplea un doble de la tabla de boto3 para verificar el uso de las
operaciones correctas sin efectuar llamadas reales a AWS.
"""

from __future__ import annotations

from typing import Any

import pytest

from tpfi.patterns.singleton import SingletonABCMeta
from tpfi.repository import AuditRepository, DataRepository, get_cpu_info


class FakeTable:
    """Doble de prueba que simula un ``Table`` de boto3."""

    def __init__(self) -> None:
        """Inicializa la tabla simulada sin elementos."""
        self.items: dict[str, dict[str, Any]] = {}
        self.get_calls: list[dict[str, Any]] = []
        self.put_calls: list[dict[str, Any]] = []
        self.scan_count = 0

    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Simula ``get_item``.

        Args:
            Key: Clave primaria solicitada.

        Returns:
            Un diccionario con ``Item`` si existe, vacio si no.
        """
        self.get_calls.append(Key)
        record_id = Key["id"]
        if record_id in self.items:
            return {"Item": dict(self.items[record_id])}
        return {}

    def put_item(self, Item: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Simula ``put_item``.

        Args:
            Item: Atributos a almacenar.

        Returns:
            Un diccionario vacio, como en la API real.
        """
        self.put_calls.append(Item)
        self.items[Item["id"]] = dict(Item)
        return {}

    def scan(self) -> dict[str, Any]:
        """Simula ``scan`` devolviendo todos los elementos.

        Returns:
            Un diccionario con la lista ``Items``.
        """
        self.scan_count += 1
        return {"Items": [dict(item) for item in self.items.values()]}


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    """Limpia las instancias cacheadas antes y despues de cada prueba."""
    SingletonABCMeta.reset_all()
    yield
    SingletonABCMeta.reset_all()


@pytest.fixture
def data_repo() -> DataRepository:
    """Repositorio de datos con la tabla simulada ya inyectada."""
    repo = DataRepository()
    repo._table = FakeTable()  # type: ignore[assignment]
    return repo


@pytest.fixture
def audit_repo() -> AuditRepository:
    """Repositorio de auditoria con la tabla simulada ya inyectada."""
    repo = AuditRepository()
    repo._table = FakeTable()  # type: ignore[assignment]
    return repo


def test_data_repository_is_singleton() -> None:
    """Dos instancias del repositorio de datos son el mismo objeto."""
    first = DataRepository()
    second = DataRepository()

    assert first is second


def test_audit_repository_is_singleton() -> None:
    """Dos instancias del repositorio de auditoria son el mismo objeto."""
    first = AuditRepository()
    second = AuditRepository()

    assert first is second


def test_repositories_are_independent_singletons() -> None:
    """Cada tabla tiene su propia instancia unica."""
    assert DataRepository() is not AuditRepository()


def test_table_name_defaults(data_repo: DataRepository) -> None:
    """El repositorio de datos apunta a la tabla configurada."""
    assert data_repo.table_name == "CorporateData"


def test_audit_table_name_defaults(audit_repo: AuditRepository) -> None:
    """El repositorio de auditoria apunta a la tabla configurada."""
    assert audit_repo.table_name == "CorporateLog"


def test_get_returns_item(data_repo: DataRepository) -> None:
    """Un registro existente se devuelve como diccionario."""
    data_repo._table.items["A"] = {"id": "A", "sede": "FCyT"}  # type: ignore[union-attr]

    assert data_repo.get("A") == {"id": "A", "sede": "FCyT"}


def test_get_returns_none_when_absent(data_repo: DataRepository) -> None:
    """Una clave inexistente devuelve ``None``."""
    assert data_repo.get("NO-EXISTE") is None


def test_get_copies_the_item(data_repo: DataRepository) -> None:
    """El repositorio devuelve una copia, no la referencia interna."""
    data_repo._table.items["A"] = {"id": "A"}  # type: ignore[union-attr]

    result = data_repo.get("A")
    assert result is not None
    result["id"] = "MODIFICADO"

    assert data_repo.get("A") == {"id": "A"}


def test_put_injects_key_attribute(data_repo: DataRepository) -> None:
    """La clave primaria se agrega automaticamente al escribir."""
    data_repo.put("A", {"sede": "FCyT"})

    assert data_repo.get("A") == {"id": "A", "sede": "FCyT"}


def test_list_returns_all_items(data_repo: DataRepository) -> None:
    """El listado devuelve todos los registros almacenados."""
    data_repo.put("A", {"sede": "FCyT"})
    data_repo.put("B", {"sede": "FQyT"})

    assert len(data_repo.list()) == 2


def test_list_on_empty_table(data_repo: DataRepository) -> None:
    """Una tabla vacia devuelve una lista vacia."""
    assert data_repo.list() == []


def test_audit_record_has_expected_schema(audit_repo: AuditRepository) -> None:
    """La pista de auditoria incluye todos los campos exigidos."""
    entry = audit_repo.record(
        action="get",
        client_uuid="CPU-1",
        session_id="SES-1",
        timestamp="2026-01-01T00:00:00",
        key="UADER-FCyT-IS2",
    )

    assert entry["id"] == "SES-1"
    assert entry["action"] == "get"
    assert entry["client_uuid"] == "CPU-1"
    assert entry["session_id"] == "SES-1"
    assert entry["timestamp"] == "2026-01-01T00:00:00"
    assert entry["key"] == "UADER-FCyT-IS2"
    assert "cpu_uuid" in entry["cpu_info"]


def test_audit_key_defaults_to_star(audit_repo: AuditRepository) -> None:
    """Las acciones sin registro afectado usan ``*`` como clave."""
    entry = audit_repo.record(
        action="subscribe",
        client_uuid="CPU-1",
        session_id="SES-2",
        timestamp="2026-01-01T00:00:00",
    )

    assert entry["key"] == "*"


def test_audit_record_is_persisted(audit_repo: AuditRepository) -> None:
    """La entrada de auditoria queda almacenada en la tabla."""
    audit_repo.record(
        action="set",
        client_uuid="CPU-1",
        session_id="SES-3",
        timestamp="2026-01-01T00:00:00",
    )

    assert len(audit_repo.list()) == 1


def test_audit_list_on_empty_table(audit_repo: AuditRepository) -> None:
    """Sin acciones registradas la pista esta vacia."""
    assert audit_repo.list() == []


def test_cpu_info_contains_platform_data() -> None:
    """La informacion de CPU incluye los datos de plataforma exigidos."""
    info = get_cpu_info()

    assert set(info) >= {
        "cpu_uuid",
        "node",
        "system",
        "machine",
        "processor",
        "release",
        "version",
    }


def test_cpu_uuid_is_numeric() -> None:
    """El UUID de CPU se obtiene de ``uuid.getnode()``."""
    assert get_cpu_info()["cpu_uuid"].isdigit()


def test_table_is_built_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    """El recurso de tabla se crea en el primer uso, no en el constructor."""
    repo = DataRepository()
    assert repo._table is None

    monkeypatch.setattr("tpfi.repository._build_table", lambda name: FakeTable())
    assert isinstance(repo.table, FakeTable)


def test_table_is_cached_after_first_access(data_repo: DataRepository) -> None:
    """El recurso de tabla se reutiliza en los accesos siguientes."""
    table = data_repo.table

    assert data_repo.table is table
