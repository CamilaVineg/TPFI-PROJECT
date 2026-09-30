"""Pruebas del patron Observer."""

from __future__ import annotations

import json
import socket

import pytest

from tpfi.patterns.observer import (
    ObservedSubject,
    SocketDeliveryError,
    SocketObserver,
    SubjectState,
    close_socket,
)


class FakeSocket:
    """Doble de prueba que simula un socket TCP."""

    def __init__(self, fail: bool = False) -> None:
        """Crea el doble de prueba.

        Args:
            fail: Si es ``True``, ``sendall`` simula un error de conexion.
        """
        self.sent: list[bytes] = []
        self.fail = fail
        self.closed = False

    def sendall(self, data: bytes) -> None:
        """Registra los datos enviados o falla segun la configuracion.

        Args:
            data: Bytes a enviar.

        Raises:
            OSError: Si el doble fue configurado para fallar.
        """
        if self.fail:
            raise OSError("conexion perdida")
        self.sent.append(data)

    def shutdown(self, how: int) -> None:
        """Simula el cierre ordenado del socket.

        Args:
            how: Direccion de cierre, ignorada.
        """
        self.closed = True

    def close(self) -> None:
        """Marca el socket como cerrado."""
        self.closed = True


@pytest.fixture
def sock() -> FakeSocket:
    """Devuelve un doble de socket que funciona correctamente."""
    return FakeSocket()


def test_initial_state_is_idle() -> None:
    """Un sujeto recien creado esta en ``IDLE`` y sin observadores."""
    subject = ObservedSubject()

    assert subject.state is SubjectState.IDLE
    assert subject.subscriber_count == 0


def test_subscribe_changes_state_to_subscribed(sock: FakeSocket) -> None:
    """Registrar un observador lleva al sujeto a ``SUBSCRIBED``."""
    subject = ObservedSubject()

    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    assert subject.state is SubjectState.SUBSCRIBED
    assert subject.subscriber_count == 1


def test_subscribe_twice_raises_error(sock: FakeSocket) -> None:
    """No se admite la subscripcion duplicada de un mismo UUID."""
    subject = ObservedSubject()
    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ya se encuentra subscripto"):
        subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]


def test_notify_delivers_json_to_observers(sock: FakeSocket) -> None:
    """La notificacion llega serializada como JSON a cada observador."""
    subject = ObservedSubject()
    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    subject.notify({"id": "UADER-FCyT-IS2", "sede": "FCyT"})

    assert json.loads(sock.sent[0].decode("utf-8")) == {
        "id": "UADER-FCyT-IS2",
        "sede": "FCyT",
    }


def test_notify_delivers_to_all_observers() -> None:
    """Cada observador registrado recibe su propia copia del mensaje."""
    first = FakeSocket()
    second = FakeSocket()
    subject = ObservedSubject()
    subject.subscribe("cpu-1", first)  # type: ignore[arg-type]
    subject.subscribe("cpu-2", second)  # type: ignore[arg-type]

    subject.notify({"id": "x"})

    assert len(first.sent) == 1
    assert len(second.sent) == 1


def test_notify_drops_failing_observer() -> None:
    """Un observador que falla se elimina del registro."""
    failing = FakeSocket(fail=True)
    working = FakeSocket()
    subject = ObservedSubject()
    subject.subscribe("cpu-1", failing)  # type: ignore[arg-type]
    subject.subscribe("cpu-2", working)  # type: ignore[arg-type]

    subject.notify({"id": "x"})

    assert subject.subscriber_count == 1
    assert len(working.sent) == 1


def test_notify_without_observers_is_noop() -> None:
    """Notificar sin observadores registrados no lanza excepcion."""
    subject = ObservedSubject()

    subject.notify({"id": "x"})

    assert subject.subscriber_count == 0


def test_unsubscribe_removes_observer(sock: FakeSocket) -> None:
    """Desuscribir cierra el socket y descuenta el observador."""
    subject = ObservedSubject()
    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    subject.unsubscribe("cpu-1")

    assert subject.subscriber_count == 0
    assert sock.closed is True


def test_unsubscribe_unknown_uuid_is_noop() -> None:
    """Desuscribir un UUID inexistente no altera el estado."""
    subject = ObservedSubject()

    subject.unsubscribe("cpu-inexistente")

    assert subject.state is SubjectState.IDLE


def test_unsubscribe_last_observer_moves_to_disconnected(sock: FakeSocket) -> None:
    """Perder el ultimo observador deja al sujeto en ``DISCONNECTED``."""
    subject = ObservedSubject()
    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    subject.unsubscribe("cpu-1")

    assert subject.state is SubjectState.DISCONNECTED


def test_shutdown_closes_every_socket() -> None:
    """``shutdown`` cierra todos los sockets y vacia el registro."""
    first = FakeSocket()
    second = FakeSocket()
    subject = ObservedSubject()
    subject.subscribe("cpu-1", first)  # type: ignore[arg-type]
    subject.subscribe("cpu-2", second)  # type: ignore[arg-type]

    subject.shutdown()

    assert subject.subscriber_count == 0
    assert first.closed is True
    assert second.closed is True
    assert subject.state is SubjectState.DISCONNECTED


def test_socket_observer_sends_payload(sock: FakeSocket) -> None:
    """``SocketObserver`` cumple el contrato de entrega del patron."""
    observer = SocketObserver(sock)  # type: ignore[arg-type]

    observer.update({"id": "UADER-FCyT-IS2"})

    assert json.loads(sock.sent[0].decode("utf-8")) == {"id": "UADER-FCyT-IS2"}


def test_socket_observer_raises_on_failure() -> None:
    """Un fallo de socket se traduce a ``SocketDeliveryError``."""
    observer = SocketObserver(FakeSocket(fail=True))  # type: ignore[arg-type]

    with pytest.raises(SocketDeliveryError, match="No se pudo entregar"):
        observer.update({"id": "x"})


def test_close_socket_tolerates_closed_socket() -> None:
    """``close_socket`` no falla si el socket ya estaba cerrado."""
    sock = FakeSocket()

    def raise_on_shutdown(how: int) -> None:
        """Simula un socket ya desconectado.

        Args:
            how: Direccion de cierre, ignorada.

        Raises:
            OSError: Siempre, para emular un socket caido.
        """
        raise OSError("socket ya cerrado")

    sock.shutdown = raise_on_shutdown  # type: ignore[method-assign]

    close_socket(sock)  # type: ignore[arg-type]

    assert sock.closed is True


def test_real_socket_type_is_accepted(sock: FakeSocket) -> None:
    """El sujeto opera con objetos que cumplen el protocolo de socket."""
    assert hasattr(socket, "socket")
    subject = ObservedSubject()
    subject.subscribe("cpu-1", sock)  # type: ignore[arg-type]

    assert subject.subscriber_count == 1
