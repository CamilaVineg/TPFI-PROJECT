"""Interfaz del patron Proxy.

Define el contrato que debe cumplir el proxy de acceso a la tabla
``CorporateData``. La implementacion concreta vive en
``tpfi.proxy``.
"""

from __future__ import annotations

import abc
from typing import Any

__all__ = ["ProxyInterface"]


class ProxyInterface(abc.ABC):
    """Contrato de las operaciones expuestas por el proxy de datos.

    El servidor de aplicaciones no accede nunca a DynamoDB de forma directa:
    todas las operaciones pasan por esta interfaz, lo que permite interceptar
    y validar cada requerimiento antes de tocar la base.
    """

    @abc.abstractmethod
    def get(self, record_id: str) -> dict[str, Any] | None:
        """Obtiene un registro de la tabla.

        Args:
            record_id: Clave primaria del registro buscado.

        Returns:
            El registro solicitado o ``None`` si no existe.
        """

    @abc.abstractmethod
    def set(self, record_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        """Crea o actualiza parcialmente un registro.

        Los campos no informados en ``values`` se conservan; si el registro no
        existe se crea con los campos informados y el resto en blanco.

        Args:
            record_id: Clave primaria del registro.
            values: Campos a escribir.

        Returns:
            El registro resultante o ``None`` si la operacion fallo.
        """

    @abc.abstractmethod
    def list(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros de la tabla.

        Returns:
            La lista completa de registros.
        """
