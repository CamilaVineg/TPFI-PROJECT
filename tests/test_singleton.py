"""Pruebas del patron Singleton."""

from __future__ import annotations

import abc
import threading

import pytest

from tpfi.patterns.singleton import SingletonABCMeta, singleton


class DemoMetaClass(metaclass=SingletonABCMeta):
    """Clase de apoyo que aplica Singleton mediante metaclase."""

    def __init__(self, value: int = 0) -> None:
        """Guarda ``value`` para poder comparar identidades.

        Args:
            value: Valor marcador de la instancia.
        """
        self.value = value


class DemoABC(metaclass=SingletonABCMeta):
    """Clase abstracta de apoyo que aplica Singleton mediante metaclase."""

    @abc.abstractmethod
    def run(self) -> str:
        """Ejecuta la operacion de ejemplo."""


class ConcreteDemo(DemoABC):
    """Implementacion concreta de :class:`DemoABC`."""

    def run(self) -> str:
        """Devuelve una cadena constante.

        Returns:
            La cadena ``"ok"``.
        """
        return "ok"


class DemoDecorated:
    """Clase de apoyo a la que se le aplica el decorador ``singleton``."""

    def __init__(self) -> None:
        """Inicializa un contador de constructions."""
        self.created = True


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    """Limpia las instancias cacheadas antes y despues de cada prueba."""
    SingletonABCMeta.reset_all()
    yield
    SingletonABCMeta.reset_all()


def test_metaclass_returns_same_instance() -> None:
    """Dos invocaciones de la clase producen la misma instancia."""
    first = DemoMetaClass(1)
    second = DemoMetaClass(2)

    assert first is second


def test_metaclass_ignores_later_arguments() -> None:
    """Los argumentos posteriores a la primera construccion se ignoran."""
    first = DemoMetaClass(1)
    second = DemoMetaClass(99)

    assert first.value == 1
    assert second.value == 1


def test_metaclass_shares_instance_across_threads() -> None:
    """Hilos distintos reciben la misma instancia."""
    results: list[DemoMetaClass] = []

    def worker() -> None:
        results.append(DemoMetaClass(1))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 5
    assert all(instance is results[0] for instance in results)


def test_metaclass_allows_instantiation_of_abstract_class() -> None:
    """``ConcreteDemo`` es instanciable y devuelve la unica instancia."""
    first = ConcreteDemo()
    second = ConcreteDemo()

    assert first is second
    assert first.run() == "ok"


def test_reset_instance_forces_new_object() -> None:
    """``reset_instance`` descarta la instancia cacheada."""
    first = DemoMetaClass(1)
    DemoMetaClass.reset_instance()
    second = DemoMetaClass(2)

    assert first is not second


def test_reset_instance_of_unknown_class_is_noop() -> None:
    """Resetear una clase sin instancia cacheada no lanza excepcion."""

    class Unused(metaclass=SingletonABCMeta):
        """Clase nunca instanciada."""

    Unused.reset_instance()


def test_decorator_returns_same_instance() -> None:
    """El decorador ``singleton`` tambien unifica las instancias."""
    wrapped = singleton(DemoDecorated)

    first = wrapped()
    second = wrapped()

    assert first is second


def test_decorator_is_thread_safe() -> None:
    """El decorador construye una unica instancia bajo concurrencia."""
    wrapped = singleton(DemoDecorated)
    results: list[DemoDecorated] = []

    def worker() -> None:
        results.append(wrapped())

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(instance is results[0] for instance in results)


def test_decorator_preserves_metadata() -> None:
    """El decorador conserva el nombre de la clase original."""
    wrapped = singleton(DemoDecorated)

    assert wrapped.__name__ == "DemoDecorated"
