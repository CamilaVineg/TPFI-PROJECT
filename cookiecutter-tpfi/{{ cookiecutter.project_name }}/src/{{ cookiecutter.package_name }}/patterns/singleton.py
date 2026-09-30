"""Implementacion del patron Singleton.

El patron garantiza que una clase posea una unica instancia y que exista un
punto de acceso global a ella. En el TPFI se utiliza para encapsular el acceso
fisico a las tablas ``{{ cookiecutter.corporate_table }}`` y
``{{ cookiecutter.log_table }}``, de modo que todos los clientes del servidor
compartan la misma conexion y no se abran multiples recursos contra AWS.

Se ofrecen dos mecanismos complementarios:

* :class:`SingletonABCMeta`: metaclase que aplica el patron a clases que
  heredan de :class:`abc.ABC`.
* :func:`singleton`: decorador alternativo para clases simples.
"""

from __future__ import annotations

import abc
import functools
import threading
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

__all__ = ["SingletonABCMeta", "singleton"]

T = TypeVar("T")


class SingletonABCMeta(abc.ABCMeta):
    """Metaclase que restringe a una unica instancia por clase concreta.

    La instancia se construye de forma diferida la primera vez que se invoca
    la clase y se reutiliza en todas las invocaciones posteriores, incluso
    desde hilos distintos.
    """

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Devuelve la instancia unica asociada a ``cls``.

        Args:
            *args: Argumentos posicionales, ignorados si la instancia ya existe.
            **kwargs: Argumentos con nombre, ignorados si la instancia ya existe.

        Returns:
            La unica instancia de la clase.
        """
        if cls not in SingletonABCMeta._instances:
            with SingletonABCMeta._lock:
                if cls not in SingletonABCMeta._instances:
                    SingletonABCMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonABCMeta._instances[cls]

    def reset_instance(cls) -> None:
        """Elimina la instancia cacheada de ``cls``.

        Metodo de apoyo para las pruebas unitarias, que necesitan partir de un
        estado conocido entre un caso y otro.
        """
        with SingletonABCMeta._lock:
            SingletonABCMeta._instances.pop(cls, None)

    @classmethod
    def reset_all(cls) -> None:
        """Elimina todas las instancias cacheadas de la metaclase."""
        with SingletonABCMeta._lock:
            SingletonABCMeta._instances.clear()


def singleton(cls: Callable[..., T]) -> Callable[..., T]:
    """Convierte ``cls`` en una clase con una unica instancia compartida.

    Args:
        cls: Clase a decorar.

    Returns:
        Envoltorio que devuelve siempre la misma instancia de ``cls``.
    """
    instances: dict[type, T] = {}
    lock = threading.Lock()
    class_key: type[Any] = cls  # type: ignore[assignment]

    @functools.wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        if class_key not in instances:
            with lock:
                if class_key not in instances:
                    instances[class_key] = cls(*args, **kwargs)
        return instances[class_key]

    return get_instance
