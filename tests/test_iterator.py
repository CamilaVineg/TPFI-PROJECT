"""Pruebas del patron Iterator y de la coleccion de registros corporativos.

Se verifica la estructura del patron (agregado, iterador y protocolos), el
filtrado y el orden, y que el recorrido sea perezoso: la fuente no se consume
hasta que el consumidor pide el primer registro.
"""

from __future__ import annotations

from collections.abc import Iterator as IteratorABC
from typing import Any

import pytest

from tpfi.collection import CorporateDataCollection, RecordIterator
from tpfi.patterns.iterator import AggregateProtocol, IteratorProtocol

RECORDS: list[dict[str, Any]] = [
    {"id": "A", "sede": "FCyT", "localidad": "Concepcion del Uruguay"},
    {"id": "B", "sede": "FQyT", "localidad": "Villaguay"},
    {"id": "C", "sede": "FCyT", "localidad": "Gualeguaychu"},
]


class FakeRepository:
    """Doble del repositorio que registra cuantas veces se lo recorrio."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        """Carga los registros que devolvera el recorrido.

        Args:
            records: Registros de la tabla simulada.
        """
        self.table_name = "CorporateData"
        self.records = list(records if records is not None else RECORDS)
        self.scans = 0

    def scan(self) -> IteratorABC[dict[str, Any]]:
        """Simula el recorrido paginado de la tabla.

        Yields:
            Copias de los registros cargados.
        """
        self.scans += 1
        yield from (dict(record) for record in self.records)


@pytest.fixture
def repository() -> FakeRepository:
    """Repositorio simulado con los registros de ejemplo."""
    return FakeRepository()


@pytest.fixture
def collection(repository: FakeRepository) -> CorporateDataCollection:
    """Coleccion apoyada en el repositorio simulado."""
    return CorporateDataCollection(repository)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# El iterador concreto
# ---------------------------------------------------------------------------


def test_iterator_yields_every_record() -> None:
    """El recorrido entrega todos los registros de la fuente."""
    iterator = RecordIterator(RECORDS)

    assert [record["id"] for record in iterator] == ["A", "B", "C"]


def test_iterator_is_its_own_iterator() -> None:
    """``iter`` sobre el iterador devuelve el mismo objeto."""
    iterator = RecordIterator(RECORDS)

    assert iter(iterator) is iterator


def test_iterator_raises_stop_iteration_when_exhausted() -> None:
    """Agotada la fuente, el iterador senala el fin con ``StopIteration``."""
    iterator = RecordIterator(RECORDS)
    list(iterator)

    with pytest.raises(StopIteration):
        next(iterator)


def test_iterator_consumes_the_source_only_on_demand() -> None:
    """La fuente no se consume hasta que se pide el primer registro."""
    pulled: list[str] = []

    def source() -> IteratorABC[dict[str, Any]]:
        for record in RECORDS:
            pulled.append(record["id"])
            yield record

    iterator = RecordIterator(source())
    assert pulled == []

    next(iterator)

    assert pulled == ["A"]


def test_iterator_counts_returned_records() -> None:
    """``returned`` informa cuantos registros se entregaron."""
    iterator = RecordIterator(RECORDS)

    assert iterator.returned == 0
    next(iterator)
    next(iterator)

    assert iterator.returned == 2


def test_iterator_tracks_the_current_record() -> None:
    """``current`` devuelve el ultimo registro entregado."""
    iterator = RecordIterator(RECORDS)

    assert iterator.current is None
    next(iterator)

    assert iterator.current == {"id": "A", "sede": "FCyT", "localidad": "Concepcion del Uruguay"}


def test_iterator_keeps_empty_source_empty() -> None:
    """Una fuente vacia no entrega ningun registro."""
    assert list(RecordIterator([])) == []


def test_iterator_exposes_its_criteria() -> None:
    """Los filtros y el orden aplicados se pueden consultar."""
    iterator = RecordIterator(RECORDS, filters={"sede": "FCyT"}, sort_by="id")

    assert iterator.filters == {"sede": "FCyT"}
    assert iterator.sort_by == "id"


def test_iterator_without_criteria_respects_source_order() -> None:
    """Sin orden explicito se respeta el orden en que llegan los registros."""
    assert [record["id"] for record in RecordIterator(RECORDS)] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Filtrado
# ---------------------------------------------------------------------------


def test_filter_returns_only_matching_records() -> None:
    """El filtro descarta los registros que no cumplen la igualdad."""
    iterator = RecordIterator(RECORDS, filters={"sede": "FCyT"})

    assert [record["id"] for record in iterator] == ["A", "C"]


def test_filter_requires_every_field() -> None:
    """Con varios filtros se exigen todos a la vez."""
    iterator = RecordIterator(RECORDS, filters={"sede": "FCyT", "localidad": "Gualeguaychu"})

    assert [record["id"] for record in iterator] == ["C"]


def test_filter_without_matches_yields_nothing() -> None:
    """Si ningun registro coincide, el recorrido queda vacio."""
    assert list(RecordIterator(RECORDS, filters={"sede": "SIN-SEDE"})) == []


def test_filter_skips_records_missing_the_field() -> None:
    """Un registro que no tiene el campo filtrado no coincide."""
    assert list(RecordIterator(RECORDS, filters={"telefono": None})) == []


# ---------------------------------------------------------------------------
# Orden
# ---------------------------------------------------------------------------


def test_sort_orders_the_records() -> None:
    """El orden solicitado se aplica antes de entregar el primer registro."""
    unsorted = [RECORDS[2], RECORDS[0], RECORDS[1]]

    assert [record["id"] for record in RecordIterator(unsorted, sort_by="id")] == ["A", "B", "C"]


def test_sort_tolerates_records_without_the_field() -> None:
    """Un registro sin el campo de orden no interrumpe el recorrido."""
    records = [{"id": "A"}, {"id": "B", "telefono": "03442"}]

    assert [record["id"] for record in RecordIterator(records, sort_by="telefono")] == ["A", "B"]


def test_sort_combines_with_filter() -> None:
    """Filtrar y ordenar se aplican sobre el mismo recorrido."""
    iterator = RecordIterator(RECORDS, filters={"sede": "FCyT"}, sort_by="localidad")

    assert [record["localidad"] for record in iterator] == [
        "Concepcion del Uruguay",
        "Gualeguaychu",
    ]


# ---------------------------------------------------------------------------
# Liberacion de la fuente
# ---------------------------------------------------------------------------


def test_close_releases_the_source_generator() -> None:
    """Cerrar el iterador cierra el generador que lo alimenta."""
    closed = False

    def source() -> IteratorABC[dict[str, Any]]:
        nonlocal closed
        try:
            yield from RECORDS
        finally:
            closed = True

    iterator = RecordIterator(source())
    next(iterator)
    iterator.close()

    assert closed is True


def test_close_is_safe_before_starting() -> None:
    """Cerrar un iterador que nunca se uso no produce errores."""
    iterator = RecordIterator(RECORDS)

    iterator.close()

    assert iterator.returned == 0


# ---------------------------------------------------------------------------
# La coleccion (agregado)
# ---------------------------------------------------------------------------


def test_collection_creates_an_iterator_over_the_repository(
    collection: CorporateDataCollection, repository: FakeRepository
) -> None:
    """El iterador se alimenta del recorrido del repositorio."""
    iterator = collection.create_iterator()

    assert [record["id"] for record in iterator] == ["A", "B", "C"]
    assert repository.scans == 1


def test_collection_is_iterable_directly(collection: CorporateDataCollection) -> None:
    """La coleccion se puede recorrer con ``for`` sin pedir el iterador."""
    assert [record["id"] for record in collection] == ["A", "B", "C"]


def test_collection_does_not_query_until_consumed(
    collection: CorporateDataCollection, repository: FakeRepository
) -> None:
    """Crear el iterador no dispara la consulta a la tabla."""
    iterator = collection.create_iterator()

    assert repository.scans == 0
    next(iterator)

    assert repository.scans == 1


def test_collection_supports_filters(collection: CorporateDataCollection) -> None:
    """El agregado delega los filtros en el iterador concreto."""
    iterator = collection.create_iterator(filters={"sede": "FCyT"})

    assert [record["id"] for record in iterator] == ["A", "C"]


def test_collection_supports_order(collection: CorporateDataCollection) -> None:
    """El agregado delega el orden en el iterador concreto."""
    iterator = collection.create_iterator(sort_by="id")

    assert [record["id"] for record in iterator] == ["A", "B", "C"]


def test_collection_returns_independent_iterators(
    collection: CorporateDataCollection,
) -> None:
    """Cada iterador recorre la coleccion desde el principio."""
    first = collection.create_iterator()
    second = collection.create_iterator()
    next(first)

    assert [record["id"] for record in second] == ["A", "B", "C"]


def test_collection_exposes_its_repository(
    collection: CorporateDataCollection, repository: FakeRepository
) -> None:
    """La coleccion no reemplaza al repositorio: lo envuelve."""
    assert collection.repository is repository


def test_empty_collection_yields_nothing() -> None:
    """Una coleccion sin registros no entrega elementos."""
    empty = CorporateDataCollection(FakeRepository([]))  # type: ignore[arg-type]

    assert list(empty) == []


# ---------------------------------------------------------------------------
# Contratos del patron
# ---------------------------------------------------------------------------


def test_iterator_satisfies_the_iterator_protocol() -> None:
    """El iterador concreto cumple el contrato del participante ``Iterator``."""
    assert isinstance(RecordIterator(RECORDS), IteratorProtocol)


def test_collection_satisfies_the_aggregate_protocol() -> None:
    """La coleccion cumple el contrato del participante ``Aggregate``."""
    collection = CorporateDataCollection(FakeRepository())  # type: ignore[arg-type]

    assert isinstance(collection, AggregateProtocol)
