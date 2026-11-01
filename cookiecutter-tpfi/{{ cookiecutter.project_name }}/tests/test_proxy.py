"""Pruebas del patron Proxy sobre la tabla CorporateData.

Se usa un repositorio simulado para no depender de AWS ni alterar los datos
reales de la cuenta.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from {{ cookiecutter.package_name }}.collection import CorporateDataCollection
from {{ cookiecutter.package_name }}.config import CORPORATE_FIELDS
from {{ cookiecutter.package_name }}.proxy import DataProxy, InvalidRequestError


class FakeRepository:
    """Doble de prueba que simula el repositorio Singleton de datos."""

    def __init__(self, initial: dict[str, dict[str, Any]] | None = None) -> None:
        """Carga el contenido inicial de la tabla simulada.

        Args:
            initial: Registros con los que se inicializa la tabla.
        """
        self.table_name = "CorporateData"
        self.items: dict[str, dict[str, Any]] = dict(initial or {})
        self.get_calls: list[str] = []
        self.put_calls: list[str] = []
        self.merge_calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Simula la lectura por clave primaria.

        Args:
            record_id: Clave primaria buscada.

        Returns:
            Una copia del registro o ``None``.
        """
        self.get_calls.append(record_id)
        found = self.items.get(record_id)
        return dict(found) if found is not None else None

    def scan(self) -> Iterator[dict[str, Any]]:
        """Simula el recorrido paginado de la tabla.

        Yields:
            Copias de todos los registros, en una unica pagina.
        """
        yield from (dict(item) for item in self.items.values())

    def put(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Simula la escritura de un registro completo.

        Args:
            record_id: Clave primaria del registro.
            values: Atributos a escribir.

        Returns:
            El registro almacenado.
        """
        self.put_calls.append(record_id)
        item = {"id": record_id, **values}
        self.items[record_id] = item
        return item

    def merge(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Simula la actualizacion atomica de un registro.

        Args:
            record_id: Clave primaria del registro.
            values: Campos informados por el cliente.

        Returns:
            El registro resultante de la actualizacion.
        """
        self.merge_calls.append((record_id, dict(values)))
        current = self.items.get(record_id)
        if current is None:
            merged = dict.fromkeys(CORPORATE_FIELDS)
            merged.update(values)
            merged["id"] = record_id
        else:
            merged = {**current, **values}
        self.items[record_id] = merged
        return dict(merged)


@pytest.fixture
def repository() -> FakeRepository:
    """Repositorio simulado con un registro preexistente."""
    return FakeRepository(
        {
            "UADER-FCyT-IS2": {
                "id": "UADER-FCyT-IS2",
                "sede": "FCyT",
                "localidad": "Concepcion del Uruguay",
            }
        }
    )


@pytest.fixture
def proxy(repository: FakeRepository) -> DataProxy:
    """Proxy conectado al repositorio simulado."""
    return DataProxy(repository)  # type: ignore[arg-type]


def test_proxy_delegates_to_repository(proxy: DataProxy, repository: FakeRepository) -> None:
    """El proxy usa el repositorio inyectado, no el Singleton real."""
    assert proxy.repository is repository


def test_proxy_builds_its_own_repository() -> None:
    """Sin repositorio inyectado, el proxy toma la instancia Singleton."""
    proxy = DataProxy()

    assert proxy.repository is not None


def test_get_returns_existing_record(proxy: DataProxy) -> None:
    """Un registro existente se devuelve tal cual estaba."""
    result = proxy.get("UADER-FCyT-IS2")

    assert result is not None
    assert result["sede"] == "FCyT"


def test_get_returns_none_when_missing(proxy: DataProxy) -> None:
    """Un registro inexistente devuelve ``None``."""
    assert proxy.get("NO-EXISTE") is None


def test_get_requires_id(proxy: DataProxy) -> None:
    """Un identificador vacio se rechaza antes de llegar a la base."""
    with pytest.raises(InvalidRequestError, match="obligatorio"):
        proxy.get("")


def test_get_rejects_non_string_id(proxy: DataProxy) -> None:
    """Un identificador numerico se rechaza."""
    with pytest.raises(InvalidRequestError, match="obligatorio"):
        proxy.get(42)  # type: ignore[arg-type]


def test_set_creates_missing_record(proxy: DataProxy) -> None:
    """Un registro inexistente se crea con el tuple completo en blanco."""
    result = proxy.set("NUEVO-1", {"sede": "FCyT"})

    assert result is not None
    assert result["id"] == "NUEVO-1"
    assert result["sede"] == "FCyT"
    assert set(result) == set(CORPORATE_FIELDS)
    assert result["telefono"] is None


def test_set_delegates_to_atomic_merge(proxy: DataProxy, repository: FakeRepository) -> None:
    """El proxy resuelve el set con una unica operacion atomica."""
    proxy.set("UADER-FCyT-IS2", {"telefono": "03442 43-1442"})

    assert repository.merge_calls == [
        ("UADER-FCyT-IS2", {"telefono": "03442 43-1442"}),
    ]
    assert repository.get_calls == []
    assert repository.put_calls == []


def test_set_preserves_unspecified_fields(proxy: DataProxy, repository: FakeRepository) -> None:
    """La actualizacion es parcial: los campos no informados se conservan."""
    proxy.set("UADER-FCyT-IS2", {"telefono": "03442 43-1442"})

    stored = repository.items["UADER-FCyT-IS2"]
    assert stored["sede"] == "FCyT"
    assert stored["telefono"] == "03442 43-1442"


def test_set_overwrites_specified_fields(proxy: DataProxy) -> None:
    """Los campos informados reemplazan a los anteriores."""
    result = proxy.set("UADER-FCyT-IS2", {"sede": "Sede Nueva"})

    assert result is not None
    assert result["sede"] == "Sede Nueva"


def test_set_never_writes_reserved_id(proxy: DataProxy, repository: FakeRepository) -> None:
    """El proxy impide que un cliente escriba la clave primaria."""
    proxy.set("UADER-FCyT-IS2", {"sede": "FCyT"})

    assert repository.items["UADER-FCyT-IS2"]["id"] == "UADER-FCyT-IS2"


def test_set_rejects_reserved_field(proxy: DataProxy) -> None:
    """Intentar escribir el campo reservado ``id`` es un error."""
    with pytest.raises(InvalidRequestError, match="reservados"):
        proxy.set("UADER-FCyT-IS2", {"id": "OTRO"})


def test_set_rejects_unknown_field(proxy: DataProxy) -> None:
    """Un atributo ajeno al tuple ``CorporateData`` se rechaza."""
    with pytest.raises(InvalidRequestError, match="ajenos a CorporateData"):
        proxy.set("UADER-FCyT-IS2", {"campo_inventado": "x"})


def test_set_rejects_empty_values(proxy: DataProxy) -> None:
    """Un requerimiento sin campos a modificar se rechaza."""
    with pytest.raises(InvalidRequestError, match="ningun campo"):
        proxy.set("UADER-FCyT-IS2", {})


def test_set_rejects_non_dict_values(proxy: DataProxy) -> None:
    """Las acciones set deben enviar un objeto JSON."""
    with pytest.raises(InvalidRequestError, match="objeto JSON"):
        proxy.set("UADER-FCyT-IS2", ["sede"])  # type: ignore[arg-type]


def test_set_requires_id(proxy: DataProxy) -> None:
    """Un set sin identificador se rechaza."""
    with pytest.raises(InvalidRequestError, match="obligatorio"):
        proxy.set("", {"sede": "FCyT"})


def test_list_returns_all_records(proxy: DataProxy) -> None:
    """El listado devuelve todos los registros de la tabla."""
    proxy.set("SEGUNDO", {"sede": "FQyT"})

    result = proxy.list()

    assert len(result) == 2
    assert {item["id"] for item in result} == {"UADER-FCyT-IS2", "SEGUNDO"}


def test_list_returns_empty_when_table_is_empty(repository: FakeRepository) -> None:
    """Una tabla sin registros devuelve una lista vacia."""
    empty = FakeRepository()
    proxy = DataProxy(empty)  # type: ignore[arg-type]

    assert proxy.list() == []


def test_proxy_covers_proxy_interface(proxy: DataProxy) -> None:
    """El proxy implementa el contrato completo del patron."""
    from {{ cookiecutter.package_name }}.patterns.proxy import ProxyInterface

    assert isinstance(proxy, ProxyInterface)


def test_list_uses_the_collection_iterator(proxy: DataProxy, repository: FakeRepository) -> None:
    """El listado se resuelve con la coleccion del patron Iterator."""
    assert isinstance(proxy.collection, CorporateDataCollection)
    assert proxy.collection.repository is repository


def test_list_returns_a_materialized_list(proxy: DataProxy) -> None:
    """El protocolo necesita una lista, no un iterador, para serializar."""
    assert isinstance(proxy.list(), list)


def test_list_can_be_filtered_through_the_collection(proxy: DataProxy) -> None:
    """La coleccion expone el recorrido filtrado que resuelve el iterador."""
    proxy.set("OTRO", {"sede": "FQyT"})

    filtered = list(proxy.collection.create_iterator(filters={"sede": "FQyT"}))

    assert [record["id"] for record in filtered] == ["OTRO"]
