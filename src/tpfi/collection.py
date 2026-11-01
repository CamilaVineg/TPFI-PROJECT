"""Coleccion de registros corporativos recorrible con el patron Iterator.

Este modulo aporta el participante ``ConcreteAggregate``
(:class:`CorporateDataCollection`) y el ``ConcreteIterator``
(:class:`RecordIterator`) del patron descrito en :mod:`tpfi.patterns.iterator`.

La coleccion no almacena los registros: sabe como pedirlos al repositorio
Singleton y como recorrerlos. El iterador es quien resuelve los dos detalles
que hacen util al patron en este proyecto:

1. **Paginacion transparente.** DynamoDB entrega hasta 1 MB por llamada a
   ``scan``; el iterador sigue pidiendo paginas mientras el consumidor las
   necesite, sin que el servidor ni el proxy se enteren de que existen.
2. **Filtrado perezoso.** Los filtros se aplican registro por registro, de
   modo que descartar un elemento no cuesta memoria ni lecturas extra.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable, Mapping
from collections.abc import Iterator as IteratorABC
from typing import Any

from tpfi.patterns.iterator import AggregateMixin, IteratorProtocol
from tpfi.repository import DataRepository

__all__ = ["CorporateDataCollection", "RecordIterator"]


class RecordIterator:
    """Iterador perezoso sobre los registros de ``CorporateData``.

    Recorre la fuente de a un registro, aplicando los filtros en el camino.
    El orden solo se aplica si se indica ``sort_by``, porque ordenar exige
    conocer todos los elementos antes de entregar el primero: en ese caso el
    iterador deja de ser perezoso y materializa la fuente.

    Attributes:
        returned: Cantidad de registros entregados hasta el momento.
        current: Ultimo registro entregado, o ``None`` si aun no entrego
            ninguno.
    """

    def __init__(
        self,
        source: Iterable[dict[str, Any]],
        *,
        filters: Mapping[str, Any] | None = None,
        sort_by: str | None = None,
    ) -> None:
        """Prepara el recorrido sobre ``source``.

        Args:
            source: Iterable de registros. En produccion es el generador de
                :meth:`tpfi.repository.DataRepository.scan`, que resuelve la
                paginacion de DynamoDB.
            filters: Campos que debe cumplir un registro para ser entregado.
                La comparacion es por igualdad y se exigen todos a la vez. Un
                registro que no tiene el campo no coincide.
            sort_by: Campo por el que ordenar. Si se omite, se respeta el
                orden en que la fuente entrega los registros.
        """
        self._source = source
        self._filters = dict(filters or {})
        self._sort_by = sort_by
        self._stream: IteratorABC[dict[str, Any]] | None = None
        self._returned = 0
        self._current: dict[str, Any] | None = None

    def __iter__(self) -> IteratorProtocol[dict[str, Any]]:
        """Devuelve el propio iterador.

        Returns:
            Este mismo objeto, como exige el protocolo de iteracion.
        """
        return self

    def __next__(self) -> dict[str, Any]:
        """Devuelve el proximo registro que cumple los filtros.

        Returns:
            El registro siguiente.

        Raises:
            StopIteration: Cuando no quedan registros por recorrer.
        """
        stream = self._stream
        if stream is None:
            stream = iter(self._ordered())
            self._stream = stream
        record = next(stream)
        self._returned += 1
        self._current = record
        return record

    @property
    def returned(self) -> int:
        """Cantidad de registros entregados hasta el momento."""
        return self._returned

    @property
    def current(self) -> dict[str, Any] | None:
        """Ultimo registro entregado, o ``None`` si aun no entrego ninguno."""
        return self._current

    @property
    def filters(self) -> Mapping[str, Any]:
        """Filtros aplicados al recorrido."""
        return dict(self._filters)

    @property
    def sort_by(self) -> str | None:
        """Campo de ordenacion, o ``None`` si se respeta el de la fuente."""
        return self._sort_by

    def close(self) -> None:
        """Libera el generador de la fuente, si esta abierto.

        Cerrar el iterador devuelve la conexion y evita seguir paginando una
        tabla que ya no se va a recorrer. Se cierra tanto el flujo de filtrado
        como la fuente, porque una expresion generadora no cierra por si sola
        el iterable del que se alimenta.
        """
        stream = self._stream
        if isinstance(stream, Generator):
            stream.close()
        if isinstance(self._source, Generator):
            self._source.close()

    def _ordered(self) -> IteratorABC[dict[str, Any]]:
        """Genera los registros filtrados, ordenados si se pidio.

        Returns:
            Un iterador sobre los registros que cumplen los filtros.
        """
        filtered = (record for record in self._source if self._matches(record))
        if self._sort_by is None:
            return filtered
        field = self._sort_by
        return iter(sorted(filtered, key=lambda record: str(record.get(field, ""))))

    def _matches(self, record: dict[str, Any]) -> bool:
        """Indica si ``record`` cumple todos los filtros del iterador.

        Args:
            record: Registro candidato.

        Returns:
            ``True`` si el registro tiene cada campo filtrado con el valor
            esperado.
        """
        return all(
            field in record and record[field] == value for field, value in self._filters.items()
        )


class CorporateDataCollection(AggregateMixin[dict[str, Any]]):
    """Coleccion de los registros de ``CorporateData``.

    Envuelve el repositorio Singleton y expone un iterador que resuelve la
    paginacion de DynamoDB. Es el participante ``ConcreteAggregate`` del
    patron: no guarda los registros, solo sabe como recorrerlos.
    """

    def __init__(self, repository: DataRepository | None = None) -> None:
        """Construye la coleccion sobre el repositorio indicado.

        Args:
            repository: Repositorio a recorrer. Si se omite se toma la
                instancia unica de :class:`~tpfi.repository.DataRepository`,
                que es el comportamiento esperado en el servidor.
        """
        self._repository = repository if repository is not None else DataRepository()

    @property
    def repository(self) -> DataRepository:
        """Repositorio Singleton del que se obtienen los registros."""
        return self._repository

    def create_iterator(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        sort_by: str | None = None,
    ) -> RecordIterator:
        """Crea un iterador nuevo sobre la tabla.

        Args:
            filters: Campos que debe cumplir un registro para ser entregado.
            sort_by: Campo por el que ordenar, o ``None`` para respetar el
                orden de la tabla.

        Returns:
            Un iterador independiente sobre la coleccion, que pide cada pagina
            de DynamoDB recien cuando la anterior se agota.
        """
        return RecordIterator(self._repository.scan(), filters=filters, sort_by=sort_by)
