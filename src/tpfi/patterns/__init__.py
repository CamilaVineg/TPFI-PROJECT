"""Patrones de diseno utilizados por el TPFI.

Este paquete agrupa las implementaciones de los patrones **Singleton**,
**Proxy** y **Observer** exigidos por la consigna.

Los tres patrones se mantienen separados y desacoplados del resto de la
aplicacion para poder verificar su correcto funcionamiento de forma aislada
mediante las pruebas unitarias.
"""

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
