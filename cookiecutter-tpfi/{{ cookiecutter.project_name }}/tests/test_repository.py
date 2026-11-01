"""Pruebas de los repositorios Singleton sobre DynamoDB.

Se emplea un doble de la tabla de boto3 para verificar el uso de las
operaciones correctas sin efectuar llamadas reales a AWS.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from botocore.exceptions import ClientError

from {{ cookiecutter.package_name }}.config import CORPORATE_FIELDS
from {{ cookiecutter.package_name }}.patterns.singleton import SingletonABCMeta
from {{ cookiecutter.package_name }}.repository import AuditRepository, DataRepository, get_cpu_info

_UPDATE_ASSIGNMENT = re.compile(r"(#\d+) = (:\w+|if_not_exists\(#\d+, :null\))")


class FakeTable:
    """Doble de prueba que simula un ``Table`` de boto3."""

    def __init__(self) -> None:
        """Inicializa la tabla simulada sin elementos."""
        self.items: dict[str, dict[str, Any]] = {}
        self.get_calls: list[dict[str, Any]] = []
        self.put_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.scan_calls: list[dict[str, Any]] = []

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

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        """Simula ``update_item`` con una expresion ``SET`` simple.

        Args:
            **kwargs: Parametros de ``update_item``. Se interpretan
                ``UpdateExpression``, ``ExpressionAttributeNames`` y
                ``ExpressionAttributeValues``.

        Returns:
            Un diccionario con ``Attributes`` si se pidio ``ALL_NEW``.
        """
        self.update_calls.append(kwargs)
        record_id = kwargs["Key"]["id"]
        current = dict(self.items.get(record_id, {"id": record_id}))
        names: dict[str, str] = kwargs["ExpressionAttributeNames"]
        values: dict[str, Any] = kwargs["ExpressionAttributeValues"]
        for name_token, value_token in _UPDATE_ASSIGNMENT.findall(kwargs["UpdateExpression"]):
            field = names[name_token]
            if value_token.startswith(":"):
                current[field] = values[value_token]
            elif field not in current:
                current[field] = values[":null"]
        self.items[record_id] = current
        if kwargs.get("ReturnValues") == "ALL_NEW":
            return {"Attributes": dict(current)}
        return {}

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Simula ``scan`` devolviendo todos los elementos en una pagina.

        Args:
            **kwargs: Parametros de la llamada, como ``ExclusiveStartKey``.

        Returns:
            Un diccionario con la lista ``Items`` y sin ``LastEvaluatedKey``,
            porque la tabla simulada cabe entera en una sola pagina.
        """
        self.scan_calls.append(dict(kwargs))
        return {"Items": [dict(item) for item in self.items.values()]}


class PagedFakeTable:
    """Doble que simula la paginacion real de DynamoDB.

    Cada llamada a ``scan`` devuelve una pagina y, salvo en la ultima, incluye
    una ``LastEvaluatedKey`` que obliga a pedir la siguiente.
    """

    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        """Carga las paginas que devolvera la tabla.

        Args:
            pages: Contenido de cada pagina, en orden.
        """
        self.pages = pages
        self.requests: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Devuelve la pagina indicada por ``ExclusiveStartKey``.

        Args:
            **kwargs: Parametros de la llamada; ``ExclusiveStartKey`` indica
                el numero de pagina a entregar.

        Returns:
            Un diccionario con ``Items`` de la pagina y, si no es la ultima,
            con ``LastEvaluatedKey`` apuntando a la siguiente.
        """
        self.requests.append(dict(kwargs))
        index = int(kwargs.get("ExclusiveStartKey", {}).get("page", 0))
        response: dict[str, Any] = {"Items": [dict(item) for item in self.pages[index]]}
        if index + 1 < len(self.pages):
            response["LastEvaluatedKey"] = {"page": index + 1}
        return response


class FailingTable:
    """Doble que simula un rechazo de AWS al recorrer la tabla."""

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Lanza el mismo error que devuelve DynamoDB ante un fallo.

        Args:
            **kwargs: Parametros de la llamada, no utilizados.

        Raises:
            ClientError: Siempre, para verificar el manejo de errores.
        """
        raise ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "fallo simulado"}},
            "Scan",
        )


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


def test_merge_updates_only_informed_fields(data_repo: DataRepository) -> None:
    """La actualizacion atomica conserva los campos no informados."""
    data_repo.put("A", {"id": "A", "sede": "FCyT", "telefono": "111"})

    result = data_repo.merge("A", {"sede": "Central"})

    assert result["id"] == "A"
    assert result["sede"] == "Central"
    assert result["telefono"] == "111"


def test_merge_creates_missing_record_with_blank_fields(data_repo: DataRepository) -> None:
    """Un registro nuevo queda con el tuple completo y los omitidos en ``None``."""
    result = data_repo.merge("B", {"sede": "FQyT"})

    assert result["id"] == "B"
    assert result["sede"] == "FQyT"
    assert set(result) == set(CORPORATE_FIELDS)
    assert result["telefono"] is None


def test_merge_is_a_single_atomic_operation(data_repo: DataRepository) -> None:
    """``merge`` no hace lectura previa ni reemplazo completo del registro."""
    table = data_repo._table
    assert isinstance(table, FakeTable)

    data_repo.merge("C", {"sede": "Central"})

    assert table.get_calls == []
    assert table.put_calls == []
    assert len(table.update_calls) == 1
    assert table.update_calls[0]["ReturnValues"] == "ALL_NEW"


def test_merge_rejects_fields_outside_the_tuple(data_repo: DataRepository) -> None:
    """Un campo ajeno al tuple se rechaza antes de llamar a DynamoDB."""
    with pytest.raises(ValueError, match="ajenos a CorporateData"):
        data_repo.merge("A", {"campo_inventado": "x"})


def test_list_returns_all_items(data_repo: DataRepository) -> None:
    """El listado devuelve todos los registros almacenados."""
    data_repo.put("A", {"sede": "FCyT"})
    data_repo.put("B", {"sede": "FQyT"})

    assert len(data_repo.list()) == 2


def test_list_on_empty_table(data_repo: DataRepository) -> None:
    """Una tabla vacia devuelve una lista vacia."""
    assert data_repo.list() == []


def test_scan_yields_every_item(data_repo: DataRepository) -> None:
    """El recorrido entrega cada registro de la tabla."""
    data_repo.put("A", {"sede": "FCyT"})
    data_repo.put("B", {"sede": "FQyT"})

    assert {record["id"] for record in data_repo.scan()} == {"A", "B"}


def test_scan_on_empty_table(data_repo: DataRepository) -> None:
    """Una tabla vacia no entrega ningun registro."""
    assert list(data_repo.scan()) == []


def test_scan_does_not_query_until_consumed() -> None:
    """El recorrido es perezoso: no consulta AWS hasta el primer registro."""
    repo = DataRepository()
    table = FakeTable()
    repo._table = table  # type: ignore[assignment]
    table.items["A"] = {"id": "A"}

    iterator = repo.scan()

    assert table.scan_calls == []
    assert list(iterator) == [{"id": "A"}]
    assert len(table.scan_calls) == 1


def test_scan_follows_last_evaluated_key() -> None:
    """El recorrido pide la pagina siguiente mientras AWS la indique."""
    repo = DataRepository()
    table = PagedFakeTable([[{"id": "A"}, {"id": "B"}], [{"id": "C"}]])
    repo._table = table  # type: ignore[assignment]

    records = list(repo.scan())

    assert [record["id"] for record in records] == ["A", "B", "C"]
    assert len(table.requests) == 2
    assert "ExclusiveStartKey" not in table.requests[0]
    assert table.requests[1]["ExclusiveStartKey"] == {"page": 1}


def test_scan_stops_without_last_evaluated_key() -> None:
    """Sin ``LastEvaluatedKey`` no se pide una segunda pagina."""
    repo = DataRepository()
    table = PagedFakeTable([[{"id": "A"}]])
    repo._table = table  # type: ignore[assignment]

    assert list(repo.scan()) == [{"id": "A"}]
    assert len(table.requests) == 1


def test_list_includes_every_page() -> None:
    """El listado completo incluye los registros de todas las paginas."""
    repo = DataRepository()
    table = PagedFakeTable([[{"id": "A"}], [{"id": "B"}], [{"id": "C"}]])
    repo._table = table  # type: ignore[assignment]

    assert len(repo.list()) == 3


def test_scan_propagates_aws_errors() -> None:
    """Un rechazo de AWS se propaga en lugar de devolver un listado vacio."""
    repo = DataRepository()
    repo._table = FailingTable()  # type: ignore[assignment]

    with pytest.raises(ClientError):
        list(repo.scan())


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


def test_audit_scan_paginates() -> None:
    """La pista de auditoria tambien se recorre pagina por pagina."""
    repo = AuditRepository()
    table = PagedFakeTable([[{"id": "S-1"}], [{"id": "S-2"}]])
    repo._table = table  # type: ignore[assignment]

    assert len(list(repo.scan())) == 2
    assert len(table.requests) == 2


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

    monkeypatch.setattr("{{ cookiecutter.package_name }}.repository._build_table", lambda name: FakeTable())
    assert isinstance(repo.table, FakeTable)


def test_table_is_cached_after_first_access(data_repo: DataRepository) -> None:
    """El recurso de tabla se reutiliza en los accesos siguientes."""
    table = data_repo.table

    assert data_repo.table is table
