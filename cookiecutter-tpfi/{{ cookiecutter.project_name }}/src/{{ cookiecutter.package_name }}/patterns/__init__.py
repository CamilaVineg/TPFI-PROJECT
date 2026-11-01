"""Patrones de diseno utilizados por el TPFI.

Este paquete agrupa las implementaciones de los patrones **Singleton**,
**Proxy** y **Observer** exigidos por la consigna, y del **Iterator**, que se
usa para paginar y filtrar el recorrido de DynamoDB.

Cada patron se mantiene separado y desacoplado del resto de la aplicacion para
poder verificar su correcto funcionamiento de forma aislada mediante las
pruebas unitarias.
"""

from tpfi.patterns.iterator import AggregateMixin, AggregateProtocol, IteratorProtocol
from tpfi.patterns.observer import (
    ObservedSubject,
    ObserverProtocol,
    SocketDeliveryError,
    SocketObserver,
    SubjectState,
    close_socket,
)
from tpfi.patterns.proxy import ProxyInterface
from tpfi.patterns.singleton import SingletonABCMeta, singleton

__all__ = [
    "AggregateMixin",
    "AggregateProtocol",
    "IteratorProtocol",
    "ObservedSubject",
    "ObserverProtocol",
    "ProxyInterface",
    "SingletonABCMeta",
    "SocketDeliveryError",
    "SocketObserver",
    "SubjectState",
    "close_socket",
    "singleton",
]
