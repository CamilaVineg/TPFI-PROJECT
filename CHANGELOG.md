# Changelog

Todas las novedades de `TPFI-PROJECT` se registran en este
archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/) y el proyecto
adhiere a [Semantic Versioning](https://semver.org/).

Los cambios se agrupan por version. Cada version indica su fecha de liberacion
y los autores que participaron en el trabajo durante ese periodo.

## [No publicado]

### Agregado

- `tests/test_acceptance.py`: suite completa de pruebas de aceptacion automatizadas segun la seccion de Validacion y Verificacion de la consigna (camino feliz con impacto en `CorporateData` y `CorporateLog`, argumentos malformados de CLI y archivo, requerimiento sin datos minimos, clientes ante servidor caido y rechazo de doble bind).
- `tests/test_hypothesis.py`: pruebas basadas en propiedades con `hypothesis` para verificar ida y vuelta de serializacion del protocolo, decodificacion robusta ante bytes arbitrarios, campos de control de requerimiento, generacion de UUID4 y validacion de identificadores y campos del proxy.
- Soporte en `singletonclient.py` para el formato JSON indicativo de la consigna (`UUID`, `ID` y `ACTION` en mayusculas, con campos del tuple al nivel raiz para `set`), conservando compatibilidad con el formato propio.
- Operacion atomica `DataRepository.merge()` con `update_item` en DynamoDB, preservando campos previos y rellenando con `None` (NULL) los no informados al crear registros.
- Asignacion y generacion obligatoria de `session_id` por parte del servidor (`uuid.uuid4()`) para evitar suplantacion o colisiones en la clave primaria de `CorporateLog`.
- Proteccion contra desbordamiento de memoria en `protocol.JsonSocket.receive()` mediante limite maximo de mensaje (:data:`MAX_MESSAGE_SIZE`).
- Soporte para multiples conexiones simultaneas de observadores desde un mismo UUID de CPU mediante `SocketObserver` por socket.
- Manejo limpio de cancelacion manual (`KeyboardInterrupt`) en `observerclient.py` y salida con codigo `1` en `singletonclient.py` cuando el servidor responde `status=error`.

### Corregido

- `demo_runner.py`: correccion de docstrings PEP 257 e importaciones no utilizadas (`F401`, `D101-D107`).
- `tests/test_singletonproxyobserver.py`: alias de tipo `ServerFixture` para compatibilidad simultanea con `ruff format` y `black`.
- `observerclient.py`: socket bloqueante (`settimeout(None)`) tras conectar para evitar desconexiones espurias cada 10 segundos, emision simultanea por stdout y archivo, y aislamiento de reintentos exclusivamente para fallas de socket (`OSError`).
- `proxy.py`: validacion estricta contra atributos ajenos a `CORPORATE_FIELDS` y liberacion explicita del iterador en `list()`.
- `singletonproxyobserver.py`: desactivacion de `allow_reuse_address` en Windows para impedir que dos instancias escuchen en el mismo puerto, y aborto con error si falla el registro de auditoria.
- Plantilla `cookiecutter-tpfi`: sincronizacion de todos los modulos faltantes (`collection.py`, `protocol.py`, `proxy.py`, `repository.py`), tests de aceptacion e hipotesis, parametrizados con `{{ cookiecutter.package_name }}`.

### Pendiente

- Diagramas UML de actividad para proxy y de estado para observer.
- Informe escrito final del proyecto.

## [0.5.0] - 2026-10-28

### Agregado

- `patterns/iterator.py`: patron Iterator con `IteratorProtocol`,
  `AggregateProtocol` y `AggregateMixin`, y la correspondencia explicita entre
  la notacion GoF y los iteradores nativos de Python.
- `collection.py`: `CorporateDataCollection` (agregado) y `RecordIterator`
  (iterador concreto), que recorren `CorporateData` con filtros por igualdad y
  orden opcional, sin materializar la tabla.
- `repository.py`: `scan()` en `DataRepository` y `AuditRepository`, que
  recorre la tabla pagina por pagina siguiendo `LastEvaluatedKey`.
- Pruebas de paginacion multietapa, filtrado, orden, evaluacion perezosa y
  liberacion del generador de origen.

### Corregido

- `repository.py`: el listado se interrumpia en el limite de 1 MB por llamada
  a `scan` y devolvia resultados incompletos sin informar error. Ahora el
  recorrido sigue `LastEvaluatedKey` hasta agotar la tabla.

### Cambiado

- `proxy.py`: la accion `list` se resuelve con la coleccion y el iterador del
  patron; la respuesta sigue siendo una lista, porque el protocolo devuelve un
  unico mensaje JSON.
- Los tres programas se renombraron para coincidir exactamente con la nomenclatura de la consigna: `server.py` pasa a `singletonproxyobserver.py`, `singleton_client.py` a `singletonclient.py` y `observer_client.py` a `observerclient.py`. Se actualizaron los `entry points` de `pyproject.toml`, los imports y las pruebas correspondientes. Los nombres no usan guiones, por lo que son identificadores validos en Python.

### Autores

- Camila Viñeg

## [0.4.0] - 2026-10-06

### Agregado

- `server.py`: servidor de aplicaciones TCP (`ApplicationServer` y `ServerHandler`) que integra los patrones Proxy (`DataProxy`), Singleton (`DataRepository`, `AuditRepository`) y Observer (`ObservedSubject`).
- `server.py`: soporte para las 4 acciones exigidas por la consigna (`get`, `list`, `set`, `subscribe`), con registro de auditoria en `CorporateLog` y notificacion en cascada a observadores suscritos ante operaciones `set`.
- `server.py`: inyeccion de dependencias del proxy, el repositorio de auditoria y el sujeto observable, para permitir su sustitucion en las pruebas.
- `tests/test_server.py`: suite completa de pruebas unitarias e integrales para el servidor TCP, cubriendo las 4 acciones, notificaciones en cascada, auditoria y manejo de errores.

### Corregido

- `observer.py`: encuadre estandarizado con delimitador `\n` en las notificaciones enviadas por `ObservedSubject.notify`.

### Autores

- Tadeo Rochas

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

- Abrilpoggio

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

- Camila Viñeg

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

- Camila Viñeg