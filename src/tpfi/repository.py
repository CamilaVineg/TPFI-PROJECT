"""Repositorios Singleton para el acceso fisico a las tablas DynamoDB.

La consigna exige que el acceso a ``CorporateData`` y ``CorporateLog`` se
realice mediante sendas funciones bajo sendos patrones Singleton. Este modulo
implementa esas dos clases.

Ambas clases usan :class:`~tpfi.patterns.singleton.SingletonABCMeta`, de modo
que el servidor de aplicaciones comparte una unica instancia por tabla a lo
largo de toda su ejecucion, evitando abrir multiples recursos contra AWS.
"""

from __future__ import annotations

import logging
import platform
import uuid
from collections.abc import Iterator
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from tpfi.config import CORPORATE_FIELDS, CORPORATE_TABLE, LOG_TABLE, get_region
from tpfi.patterns.singleton import SingletonABCMeta

__all__ = ["AuditRepository", "DataRepository", "get_cpu_info"]

logger = logging.getLogger(__name__)

KEY_ATTRIBUTE = "id"


def get_cpu_info() -> dict[str, str]:
    """Releva la informacion de la CPU desde la que se ejecuta el proceso.

    Incluye el identificador unico del procesador obtenido con
    :meth:`uuid.getnode`, tal como indica la consigna.

    Returns:
        Un diccionario con los datos de plataforma y el UUID de la CPU.
    """
    node = uuid.getnode()
    return {
        "cpu_uuid": str(node),
        "node": platform.node(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "release": platform.release(),
        "version": platform.version(),
    }


def _build_table(table_name: str) -> Any:
    """Construye el recurso de tabla de DynamoDB para ``table_name``.

    Se centraliza aqui la creacion del recurso para que ambos repositorios
    compartan la misma logica de conexion.

    Args:
        table_name: Nombre de la tabla a la que acceder.

    Returns:
        El recurso ``Table`` de boto3.

    Raises:
        BotoCoreError: Si falla la construccion del recurso.
        ClientError: Si AWS rechaza la operacion.
    """
    resource = boto3.resource("dynamodb", region_name=get_region())
    return resource.Table(table_name)


def _paginate(table: Any, table_name: str) -> Iterator[dict[str, Any]]:
    r"""Recorre ``table`` por paginas hasta agotarla.

    DynamoDB entrega como maximo 1 MB de datos por llamada a ``scan``. Si
    quedan elementos devuelve una ``LastEvaluatedKey`` que debe reenviarse como
    ``ExclusiveStartKey`` para obtener la pagina siguiente. Omitir ese paso
    produce un listado incompleto sin informar ningun error, que es justamente
    el defecto que corrige el recorrido por iterador.

    Args:
        table: Recurso ``Table`` de boto3.
        table_name: Nombre de la tabla, usado en los mensajes de error.

    Yields:
        Cada registro de la tabla, de a uno y en el orden que entrega AWS.

    Raises:
        BotoCoreError: Si falla la comunicacion con AWS.
        ClientError: Si AWS rechaza la operacion.
    """
    request: dict[str, Any] = {}
    try:
        while True:
            response = table.scan(**request)
            items: list[dict[str, Any]] = response.get("Items", [])
            yield from items
            last_key: dict[str, Any] | None = response.get("LastEvaluatedKey")
            if not last_key:
                return
            request["ExclusiveStartKey"] = last_key
    except (BotoCoreError, ClientError) as err:
        logger.error("Error recorriendo la tabla %s: %s", table_name, err)
        raise


class DataRepository(metaclass=SingletonABCMeta):
    """Acceso Singleton a la tabla ``CorporateData``.

    Concentra las operaciones de lectura y escritura sobre los datos
    corporativos. No implementa validaciones de negocio: esa responsabilidad
    corresponde al patron Proxy, que se apoya en esta capa fisica.
    """

    def __init__(self, table_name: str = CORPORATE_TABLE) -> None:
        """Abre el recurso de la tabla, una unica vez por proceso.

        Args:
            table_name: Nombre de la tabla de datos corporativos.
        """
        self._table_name = table_name
        self._table: Any | None = None
        logger.debug("Repositorio de datos inicializado sobre %s", table_name)

    @property
    def table_name(self) -> str:
        """Nombre de la tabla sobre la que opera el repositorio."""
        return self._table_name

    @property
    def table(self) -> Any:
        """Devuelve el recurso de tabla, creandolo de forma diferida.

        Returns:
            El recurso ``Table`` de boto3.
        """
        if self._table is None:
            self._table = _build_table(self._table_name)
        return self._table

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Lee un registro por su clave primaria.

        Args:
            record_id: Valor del atributo ``id`` buscado.

        Returns:
            El registro encontrado o ``None`` si no existe.

        Raises:
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        try:
            response = self.table.get_item(Key={KEY_ATTRIBUTE: record_id})
        except (BotoCoreError, ClientError) as err:
            logger.error("Error leyendo el registro %s: %s", record_id, err)
            raise
        item = response.get("Item")
        if item is None:
            logger.info("El registro %s no existe", record_id)
            return None
        return dict(item)

    def scan(self) -> Iterator[dict[str, Any]]:
        """Recorre la tabla completa resolviendo la paginacion.

        Cada pagina se pide recien cuando el consumidor agota la anterior, de
        modo que el recorrido no carga la tabla entera en memoria ni pierde
        registros cuando supera el limite de 1 MB por llamada.

        Returns:
            Un iterador perezoso sobre todos los registros de la tabla.
        """
        return _paginate(self.table, self._table_name)

    def list(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros de la tabla.

        Materializa :meth:`scan`, porque el protocolo responde con un unico
        mensaje JSON. Para recorridos que no necesiten la lista completa
        conviene usar el iterador directamente.

        Returns:
            La lista completa de registros.

        Raises:
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        return list(self.scan())

    def put(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Escribe un registro completo, reemplazando el contenido previo.

        Args:
            record_id: Clave primaria del registro.
            values: Atributos a escribir. La clave se agrega automaticamente.

        Returns:
            Los atributos efectivamente almacenados.

        Raises:
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        item = {KEY_ATTRIBUTE: record_id, **values}
        try:
            self.table.put_item(Item=item)
        except (BotoCoreError, ClientError) as err:
            logger.error("Error escribiendo el registro %s: %s", record_id, err)
            raise
        logger.info("Registro %s escrito en %s", record_id, self._table_name)
        return item

    def merge(self, record_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """Actualiza un registro de forma atomica dentro de DynamoDB.

        La consigna exige que ``set`` modifique solo los campos informados y
        conserve el resto. Resolverlo con una lectura seguida de una escritura
        deja una ventana de carrera: dos clientes concurrentes pueden pisarse
        los cambios. Esta operacion delega la resolucion en DynamoDB mediante
        una unica llamada a ``update_item``.

        Para los campos informados se usa ``SET``; para los omitidos se usa
        ``if_not_exists`` con ``None``, de modo que un registro nuevo queda
        con el tuple completo y uno existente conserva su valor previo.

        Args:
            record_id: Clave primaria del registro a actualizar.
            values: Campos informados por el cliente.

        Returns:
            El registro resultante tras la actualizacion atomica.

        Raises:
            ValueError: Si ``values`` contiene atributos ajenos al tuple.
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        unknown = set(values) - set(CORPORATE_FIELDS)
        if unknown:
            raise ValueError(f"Campos ajenos a CorporateData: {', '.join(sorted(unknown))}")

        fields = [field for field in CORPORATE_FIELDS if field != KEY_ATTRIBUTE]
        names: dict[str, str] = {}
        expressions: list[str] = []
        attribute_values: dict[str, Any] = {}
        uses_null_placeholder = False
        for index, field in enumerate(fields):
            name_placeholder = f"#{index}"
            names[name_placeholder] = field
            if field in values:
                value_placeholder = f":v{index}"
                expressions.append(f"{name_placeholder} = {value_placeholder}")
                attribute_values[value_placeholder] = values[field]
            else:
                expressions.append(f"{name_placeholder} = if_not_exists({name_placeholder}, :null)")
                uses_null_placeholder = True
        # DynamoDB rechaza los valores de expresion que no se usan. Si el
        # cliente informo todos los campos no hay ninguno "en blanco" y el
        # marcador :null no debe enviarse.
        if uses_null_placeholder:
            attribute_values[":null"] = None

        try:
            response = self.table.update_item(
                Key={KEY_ATTRIBUTE: record_id},
                UpdateExpression="SET " + ", ".join(expressions),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=attribute_values,
                ReturnValues="ALL_NEW",
            )
        except (BotoCoreError, ClientError) as err:
            logger.error("Error actualizando el registro %s: %s", record_id, err)
            raise
        item: dict[str, Any] = dict(response.get("Attributes", {}))
        logger.info("Registro %s actualizado en %s", record_id, self._table_name)
        return item


class AuditRepository(metaclass=SingletonABCMeta):
    """Acceso Singleton a la tabla ``CorporateLog``.

    Genera la pista auditable de cada accion realizada sobre el servidor:
    accion solicitada, UUID del cliente, sesion, marca de tiempo y la CPU desde
    la que se ejecuto el requerimiento.
    """

    def __init__(self, table_name: str = LOG_TABLE) -> None:
        """Abre el recurso de la tabla de auditoria, una unica vez.

        Args:
            table_name: Nombre de la tabla de auditoria.
        """
        self._table_name = table_name
        self._table: Any | None = None
        logger.debug("Repositorio de auditoria inicializado sobre %s", table_name)

    @property
    def table_name(self) -> str:
        """Nombre de la tabla de auditoria."""
        return self._table_name

    @property
    def table(self) -> Any:
        """Devuelve el recurso de tabla, creandolo de forma diferida.

        Returns:
            El recurso ``Table`` de boto3.
        """
        if self._table is None:
            self._table = _build_table(self._table_name)
        return self._table

    def record(
        self,
        action: str,
        client_uuid: str,
        session_id: str,
        timestamp: str,
        key: str = "*",
    ) -> dict[str, Any]:
        """Escribe una entrada de auditoria.

        El identificador de la entrada es el propio ``session_id``, siguiendo el
        esquema utilizado en la tabla.

        Args:
            action: Accion solicitada por el cliente.
            client_uuid: UUID de la CPU que origina el requerimiento.
            session_id: Identificador unico de la sesion.
            timestamp: Marca de tiempo en formato ISO 8601.
            key: Identificador del registro afectado o ``"*"`` si no aplica.

        Returns:
            La entrada de auditoria almacenada.

        Raises:
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        entry: dict[str, Any] = {
            KEY_ATTRIBUTE: session_id,
            "action": action,
            "client_uuid": client_uuid,
            "session_id": session_id,
            "timestamp": timestamp,
            "key": key,
            "cpu_info": get_cpu_info(),
        }
        try:
            self.table.put_item(Item=entry)
        except (BotoCoreError, ClientError) as err:
            logger.error("Error registrando la auditoria de %s: %s", action, err)
            raise
        logger.info("Auditoria registrada: accion=%s uuid=%s", action, client_uuid)
        return entry

    def scan(self) -> Iterator[dict[str, Any]]:
        """Recorre la pista de auditoria resolviendo la paginacion.

        Returns:
            Un iterador perezoso sobre todas las entradas registradas.
        """
        return _paginate(self.table, self._table_name)

    def list(self) -> list[dict[str, Any]]:
        """Devuelve todas las entradas de auditoria.

        Materializa :meth:`scan`, porque se usa para inspeccionar la pista
        completa desde las pruebas y el diagnostico.

        Returns:
            La lista completa de entradas de la pista.

        Raises:
            BotoCoreError: Si falla la comunicacion con AWS.
            ClientError: Si AWS rechaza la operacion.
        """
        return list(self.scan())
