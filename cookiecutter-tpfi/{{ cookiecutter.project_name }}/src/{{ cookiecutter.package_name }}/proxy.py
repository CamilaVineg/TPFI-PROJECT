"""Implementacion del patron Proxy para el acceso a ``CorporateData``.

El servidor de aplicaciones nunca habla con DynamoDB de forma directa: toda
operacion pasa por :class:`DataProxy`. El proxy cumple tres funciones:

1. **Interceptar** cada requerimiento antes de que llegue a la base.
2. **Validar** que el requerimiento tenga los datos minimos exigidos por la
   consigna, de modo que un cliente no pueda corromper un registro.
3. **Resolver la actualizacion parcial**, porque la accion ``set`` solo modifica
   los campos informados y conserva el resto.

Por eso se lo denomina proxy: hace de intermediario entre el cliente y el
repositorio Singleton que realiza el acceso fisico.
"""

from __future__ import annotations

import logging
from typing import Any

from {{ cookiecutter.package_name }}.collection import CorporateDataCollection
from {{ cookiecutter.package_name }}.config import CORPORATE_FIELDS
from {{ cookiecutter.package_name }}.patterns.proxy import ProxyInterface
from {{ cookiecutter.package_name }}.repository import DataRepository

__all__ = ["DataProxy", "InvalidRequestError"]

logger = logging.getLogger(__name__)

KEY_ATTRIBUTE = "id"

# Campos que el proxy no permite escribir desde un cliente: son de control.
RESERVED_FIELDS = frozenset({KEY_ATTRIBUTE})

# Unicos atributos que el cliente puede modificar: los del tuple de la consigna.
ALLOWED_FIELDS = frozenset(CORPORATE_FIELDS) - RESERVED_FIELDS


class InvalidRequestError(Exception):
    """Se lanza cuando el requerimiento no cumple los datos minimos."""


class DataProxy(ProxyInterface):
    """Proxy de datos sobre el repositorio Singleton ``CorporateData``.

    Actua como punto unico de contacto con la tabla de datos corporativos y
    aplica las reglas de negocio antes de delegar en el repositorio.
    """

    def __init__(self, repository: DataRepository | None = None) -> None:
        """Construye el proxy sobre el repositorio indicado.

        Args:
            repository: Repositorio a utilizar. Si se omite se toma la
                instancia unica de :class:`~{{ cookiecutter.package_name }}.repository.DataRepository`,
                que es el comportamiento esperado en el servidor.
        """
        self._repository = repository if repository is not None else DataRepository()
        self._collection = CorporateDataCollection(self._repository)

    @property
    def repository(self) -> DataRepository:
        """Repositorio Singleton sobre el que delega el proxy."""
        return self._repository

    @property
    def collection(self) -> CorporateDataCollection:
        """Coleccion recorrible sobre la que se resuelve el listado."""
        return self._collection

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Valida y resuelve un requerimiento de lectura por clave.

        Args:
            record_id: Clave primaria del registro solicitado.

        Returns:
            El registro solicitado o ``None`` si no existe.

        Raises:
            InvalidRequestError: Si ``record_id`` viene vacio o no es texto.
        """
        record_id = self._validate_id(record_id)
        logger.debug("Proxy: get sobre el registro %s", record_id)
        return self._repository.get(record_id)

    def list(self) -> list[dict[str, Any]]:
        """Resuelve un requerimiento de listado completo de la tabla.

        Recorre la coleccion con el iterador del patron, que resuelve la
        paginacion de DynamoDB, y materializa el resultado porque la respuesta
        del protocolo es un unico mensaje JSON.

        Returns:
            Todos los registros de la tabla.
        """
        logger.debug("Proxy: list de la tabla completa")
        iterator = self._collection.create_iterator()
        try:
            return list(iterator)
        finally:
            iterator.close()

    def set(self, record_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        """Valida y resuelve una actualizacion parcial de un registro.

        Los campos no informados en ``values`` se conservan. Si el registro no
        existe previamente se crea uno nuevo con los campos informados y los
        omitidos en blanco.

        Args:
            record_id: Clave primaria del registro a modificar.
            values: Campos a escribir.

        Returns:
            El registro resultante tras la operacion.

        Raises:
            InvalidRequestError: Si ``record_id`` es invalido, si ``values``
                no es un diccionario, si se intenta escribir un campo
                reservado o si se informa un atributo que no pertenece al
                tuple ``CorporateData``.
        """
        record_id = self._validate_id(record_id)
        if not isinstance(values, dict):
            raise InvalidRequestError("El conjunto de campos a escribir debe ser un objeto JSON")

        forbidden = RESERVED_FIELDS.intersection(values)
        if forbidden:
            raise InvalidRequestError(
                f"No se admiten los campos reservados: {', '.join(sorted(forbidden))}"
            )
        unknown = set(values) - ALLOWED_FIELDS
        if unknown:
            raise InvalidRequestError(
                f"No se admiten los campos ajenos a CorporateData: {', '.join(sorted(unknown))}"
            )
        if not values:
            raise InvalidRequestError("No se informo ningun campo para modificar")

        logger.debug("Proxy: set parcial sobre el registro %s", record_id)
        return self._repository.merge(record_id, values)

    @staticmethod
    def _validate_id(record_id: Any) -> str:
        """Comprueba que el identificador sea utilizable como clave primaria.

        Args:
            record_id: Valor recibido del cliente.

        Returns:
            El identificador validado como ``str``.

        Raises:
            InvalidRequestError: Si el identificador no es texto no vacio.
        """
        if not isinstance(record_id, str) or not record_id.strip():
            raise InvalidRequestError("El identificador del registro es obligatorio")
        return record_id
