"""Implementacion del patron Iterator.

El patron permite recorrer los elementos de una coleccion sin exponer su
representacion interna ni obligar a tenerlos todos en memoria. En el TPFI se
usa para resolver dos problemas concretos del acceso a DynamoDB:

* ``scan`` devuelve como maximo 1 MB por llamada y, si quedan datos, entrega
  una ``LastEvaluatedKey`` para continuar. El recorrido completo solo puede
  hacerse pagina por pagina, y eso es exactamente un iterador.
* El listado de ``CorporateData`` admite filtros y orden sin cargar la tabla
  entera: el iterador filtra a medida que recorre.

La estructura sigue el patron GoF adaptada a los iteradores nativos de Python:

=====================  ================================================
Participante GoF       Implementacion
=====================  ================================================
``Aggregate``          :class:`AggregateMixin`
``ConcreteAggregate``  :class:`tpfi.collection.CorporateDataCollection`
``Iterator``           :class:`IteratorProtocol`
``ConcreteIterator``   :class:`tpfi.collection.RecordIterator`
=====================  ================================================

``CreateIterator()`` equivale a :meth:`AggregateMixin.create_iterator`,
``Next()`` a ``__next__``, y el fin del recorrido se senala con
``StopIteration`` en lugar de un metodo ``IsDone()``: es la forma en que Python
expresa esa condicion.
"""

from __future__ import annotations

import abc
from typing import Generic, Protocol, TypeVar, runtime_checkable

__all__ = ["AggregateMixin", "AggregateProtocol", "IteratorProtocol"]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class IteratorProtocol(Protocol[T_co]):
    """Contrato que cumple un iterador (participante ``Iterator``).

    Cualquier objeto con ``__iter__`` y ``__next__`` lo satisface, incluidas
    las funciones generadoras de Python, de modo que no hace falta envolver un
    ``yield`` para usarlo donde el patron espera un iterador.
    """

    def __iter__(self) -> IteratorProtocol[T_co]:
        """Devuelve el propio iterador.

        Returns:
            Este mismo objeto, como exige el protocolo de iteracion.
        """
        ...  # pragma: no cover

    def __next__(self) -> T_co:
        """Devuelve el elemento siguiente del recorrido.

        Returns:
            El proximo elemento de la coleccion.

        Raises:
            StopIteration: Cuando no quedan elementos por recorrer.
        """
        ...  # pragma: no cover


@runtime_checkable
class AggregateProtocol(Protocol[T_co]):
    """Contrato de una coleccion recorrible (participante ``Aggregate``)."""

    def create_iterator(self) -> IteratorProtocol[T_co]:
        """Crea un iterador nuevo sobre la coleccion.

        Returns:
            Un iterador independiente, ubicado en su posicion inicial.
        """
        ...  # pragma: no cover


class AggregateMixin(abc.ABC, Generic[T]):
    """Base de las colecciones que exponen un iterador propio.

    Implementa ``__iter__`` delegando en :meth:`create_iterator`, de modo que
    la coleccion se pueda recorrer con ``for`` sin renunciar al metodo que
    exige el patron.
    """

    @abc.abstractmethod
    def create_iterator(self) -> IteratorProtocol[T]:
        """Crea un iterador nuevo sobre la coleccion.

        Returns:
            Un iterador independiente, ubicado en su posicion inicial.
        """

    def __iter__(self) -> IteratorProtocol[T]:
        """Permite recorrer la coleccion con ``for``.

        Returns:
            Un iterador nuevo sobre la coleccion.
        """
        return self.create_iterator()
