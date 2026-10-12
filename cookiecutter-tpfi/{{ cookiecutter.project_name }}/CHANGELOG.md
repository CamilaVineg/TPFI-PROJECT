# Changelog

Todas las novedades de `{{ cookiecutter.project_name }}` se registran en este
archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/) y el proyecto
adhiere a [Semantic Versioning](https://semver.org/).

Los cambios se agrupan por version. Cada version indica su fecha de liberacion
y los autores que participaron en el trabajo durante ese periodo.

## [No publicado]

### Pendiente

- Pruebas de aceptacion de los casos exigidos por la consigna: argumentos
  malformados, requerimiento sin datos minimos, manejo de clientes con el
  servidor caido y reintento de levantar el servidor dos veces.
- Pruebas de los patrones con `hypothesis`.
- Diagramas UML de actividad (proxy) y de estado (observer).

## [0.4.0] - 2026-10-06

### Agregado

- `server.py`: servidor de aplicaciones TCP (`ApplicationServer` y `ServerHandler`) que integra los patrones Proxy (`DataProxy`), Singleton (`DataRepository`, `AuditRepository`) y Observer (`ObservedSubject`).
- `server.py`: soporte para las 4 acciones exigidas por la consigna (`get`, `list`, `set`, `subscribe`), con registro de auditoria en `CorporateLog` y notificacion en cascada a observadores suscritos ante operaciones `set`.
- `server.py`: inyeccion de dependencias del proxy, el repositorio de auditoria y el sujeto observable, para permitir su sustitucion en las pruebas.
- `tests/test_server.py`: suite completa de pruebas unitarias e integrales para el servidor TCP, cubriendo las 4 acciones, notificaciones en cascada, auditoria y manejo de errores.

### Corregido

- `observer.py`: encuadre estandarizado con delimitador `\n` en las notificaciones enviadas por `ObservedSubject.notify`.

### Autores

- <autor>

## [0.3.0] - 2026-10-05

### Agregado

- `protocol.py`: protocolo de mensajes compartido entre servidor y clientes,
  con encuadre de lineas JSON (`\n`), constructors de requerimiento, respuesta y
  notificacion, y el canal `JsonSocket`.
- `singleton_client.py`: cliente Singleton completo, que lee `input.json`, se
  conecta al servidor, envia la accion y escribe la respuesta en `output.json`
  o por salida estandar.
- `observer_client.py`: cliente Observer completo, que se subscribe, queda
  escuchando las notificaciones y reconecta cada `retry_interval` segundos si
  se cae el socket.
- Pruebas de `protocol.py`, `singleton_client.py` y `observer_client.py`.

### Corregido

- Permisos del workflow de GitHub Pages: el job de documentacion declara
  `contents: write`, `pages: write` e `id-token: write`, que antes faltaban y
  provocaban el error 403 al publicar.

### Autores

- <autor>

## [0.2.0] - 2026-10-03

### Agregado

- `repository.py`: repositorios `DataRepository` y `AuditRepository`, ambos
  bajo el patron Singleton, con acceso a `CorporateData` y `CorporateLog`.
- `repository.py`: `get_cpu_info()` releva los datos de CPU exigidos por la
  consigna, incluido el UUID de `uuid.getnode()`.
- `proxy.py`: `DataProxy` implementa `get`/`set`/`list` sobre el repositorio,
  con validacion de datos minimos y actualizacion parcial de registros.
- `repository.py`: esquema de auditoria alineado con el utilizado en la tabla
  `CorporateLog` (accion, `client_uuid`, `session_id`, timestamp ISO, `key`,
  `cpu_info` anidado).
- `boto3-stubs` incorporado al grupo de desarrollo para validar tipos con mypy.

### Corregido

- `config.get_region()` usaba la region hardcodeada en lugar de delegar en
  boto3. Las tablas de la catedra estan en `us-east-1` y la region anterior
  provocaba `ResourceNotFoundException` en toda operacion.
- La region por defecto de la plantilla paso de `us-west-2` a `us-east-1`.

### Autores

- {{ cookiecutter.author }}

## [0.1.0] - 2026-09-30

### Agregado

- Esqueleto del proyecto generado con Cookiecutter a partir de la plantilla
  `cookiecutter-tpfi/`.
- Configuracion de `ruff`, `black`, `mypy`, `pyright`, `pytest` y `bandit` en
  `pyproject.toml`, con cobertura minima del 85%.
- Patron Singleton (`patterns/singleton.py`) con metaclase y decorador.
- Patron Observer (`patterns/observer.py`) con gestion de estados y
  suscripciones.
- Interfaz del patron Proxy (`patterns/proxy.py`).
- Constantes de tablas, region y puerto en `config.py`.
- Workflow de CI/CD con publicacion de documentacion en GitHub Pages.
- Archivos `VERSION`, `BUILD`, `REQUIREMENTS.TXT` y `REQUIREMENTS-DEV.TXT`
  generados por el hook de Cookiecutter.

### Autores

- {{ cookiecutter.author }}