# Changelog

Todas las novedades de `TPFI-PROJECT` se registran en este
archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/) y el proyecto
adhiere a [Semantic Versioning](https://semver.org/).

## [No publicado]

### Agregado

- `protocol.py`: protocolo de mensajes compartido entre servidor y clientes,
  con encuadre de lineas JSON (`\n`), builders de requerimiento/respuesta/
  notificacion y el canal `JsonSocket`.
- `singleton_client.py`: cliente Singleton completo, que lee `input.json`, se
  conecta al servidor, envia la accion y escribe la respuesta en `output.json`
  o por salida estandar.
- `observer_client.py`: cliente Observer completo, que se subscribe, queda
  escuchando las notificaciones y reconecta cada `retry_interval` segundos si
  se cae el socket.
- Pruebas de `protocol.py`, `singleton_client.py` y `observer_client.py`.
- `repository.py`: repositorios `DataRepository` y `AuditRepository`, ambos
  bajo el patron Singleton, con acceso a `CorporateData` y `CorporateLog`.
- `repository.py`: `get_cpu_info()` releva los datos de CPU exigidos por la
  consigna, incluido el UUID de `uuid.getnode()`.
- `proxy.py`: `DataProxy` implementa `get`/`set`/`list` sobre el repositorio,
  con validacion de datos minimos y actualizacion parcial de registros.
- `repository.py`: esquema de auditoria alineado con el utilizado en la tabla
  `CorporateLog` (accion, `client_uuid`, `session_id`, timestamp ISO, `key`,
  `cpu_info` anidado).
- Se agrega `boto3-stubs` al grupo de desarrollo para validar tipos con mypy.

### Corregido

- `config.get_region()` delegaba en boto3 en lugar de usar la region
  hardcodeada. Las tablas de la catedra estan en `us-east-1` y la region
  anterior provocaba `ResourceNotFoundException` en toda operacion.
- La region por defecto de la plantilla paso de `us-west-2` a `us-east-1`.

## [0.1.0] - Build 1

### Agregado

- Esqueleto del proyecto generado con Cookiecutter a partir de `cookiecutter-tpfi/`.
- Configuracion de `ruff`, `black`, `mypy`, `pyright`, `pytest` y `bandit` en `pyproject.toml`.
- Patron **Singleton** (`patterns/singleton.py`) con metaclase y decorador.
- Patron **Observer** (`patterns/observer.py`) con gestion de estados y suscripciones.
- Interfaz del patron **Proxy** (`patterns/proxy.py`).
- Constantes de tablas, region y puerto en `config.py`.
- Puntos de entrada `server.py`, `singleton_client.py` y `observer_client.py`.
- Archivos `VERSION`, `BUILD`, `REQUIREMENTS.TXT` y `REQUIREMENTS-DEV.TXT` generados por el hook.
