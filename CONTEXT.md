# CONTEXT.md

Registro de los prompts utilizados durante el desarrollo de
`TPFI-PROJECT` con asistencia de IA, conforme lo exige la
consigna del TPFI.

## Convenciones

- Fecha en formato `AAAA-MM-DD`, obtenida del reloj del sistema.
- Se registra el objetivo del prompt, no la conversacion completa.
- Solo se documentan los prompts que generaron codigo del proyecto.
- Cuando una decision del modelo resulto incorrecta, se deja constancia en
  la seccion de la sesion correspondiente.

## Sesiones

### 2026-09-30 - Estructura inicial

**Objetivo:** diseño del esqueleto del proyecto basado en Cookiecutter.

- Crear la plantilla `cookiecutter-tpfi` con `cookiecutter.json` y un hook
  `post_gen_project.py` que genere `VERSION`, `BUILD` y los archivos de
  requirements.
- Configurar en `pyproject.toml` las herramientas exigidas por la consigna:
  `ruff`, `black`, `mypy`, `pyright`, `pytest` con cobertura minima del 85%,
  `bandit` y `pdoc`.
- Implementar los patrones Singleton (`patterns/singleton.py`) y Observer
  (`patterns/observer.py`), y la interfaz del patron Proxy
  (`patterns/proxy.py`).
- Crear los puntos de entrada `server.py`, `singleton_client.py` y
  `observer_client.py` con el parseo de argumentos de la consigna.
- Redactar `README.md` y `CHANGELOG.md`.

**Resultado:** esqueleto generado y validado con el tooling completo.

### 2026-10-03 - Repositorios Singleton y Proxy

**Objetivo:** implementar la capa de acceso a datos sobre DynamoDB y el patron
Proxy, con sus pruebas unitarias.

- Agregar `repository.py` con `DataRepository` y `AuditRepository`, ambos bajo
  `SingletonABCMeta`, respetando el requisito de la consigna de que el acceso a
  `CorporateData` y `CorporateLog` se realice mediante dos singletons separados.
- Implementar `get_cpu_info()` con `uuid.getnode()` y `platform`, para el
  registro de auditoria.
- Adoptar el esquema de auditoria que ya existe en la tabla `CorporateLog`
  (inspeccionando un registro real), en lugar de inventar un formato propio.
- Agregar `proxy.py` con `DataProxy`, que implementa `ProxyInterface` y aplica
  validaciones de datos minimos y la actualizacion parcial de registros.
- Incorporar `boto3-stubs[dynamodb]` al grupo de desarrollo para poder ejecutar
  `mypy --strict` sobre el codigo que interactua con boto3.
- Escribir `tests/test_repository.py` y `tests/test_proxy.py` con dobles de
  prueba, sin llamadas reales a AWS.
- Validar el comportamiento real contra la cuenta: verificar el Singleton, el
  `get` por clave, el `list` completo, la creacion de registros, la
  actualizacion parcial y los rechazos por requerimiento incompleto.

**Correccion relevante:** la consigna indica la region `us-west-2`, pero las
tablas de la catedra estan en `us-east-1`. El codigo inicial pasaba la region
hardcodeada a `boto3.resource`, lo que provocaba `ResourceNotFoundException`
en todas las operaciones. Se modifico `config.get_region()` para resolver la
region por el orden de precedencia de boto3 (variable de entorno, sesion de
`aws configure`, y por ultimo el valor de la plantilla) y se cambio el valor
por defecto a `us-east-1`.

**Pendiente detectado:** DynamoDB devuelve los atributos numericos como
`Decimal` (por ejemplo `idReq`), que `json.dumps` no puede serializar. Habra
que convertirlo a texto o numero al construir la respuesta JSON del servidor.

**Resultado:** 78 pruebas en verde con 89,6% de cobertura; `ruff`, `black`,
`mypy --strict` y `bandit` sin observaciones; capa de datos y proxy verificados
contra la base real.

### 2026-10-05 - Clientes (Fase 5)

**Objetivo:** implementar los dos clientes de la Fase 5 y definir el protocolo
de mensajes que compartiran con el servidor.

- Crear `protocol.py` con el encuadre de lineas JSON (`\n`) y los constructores
  de mensajes `request`/`response`/`notification`, mas el canal `JsonSocket`.
- Implementar `singleton_client.py`: lee `input.json`, agrega `session_id` y
  `client_uuid`, se conecta, envia la accion y escribe la respuesta en
  `output.json` o por stdout. Se agrego el argumento `-s/--host`.
- Implementar `observer_client.py`: se subscribe con su `client_uuid`, queda
  escuchando y mostrando cada notificacion, y reconecta cada
  `retry_interval` segundos cuando se cae el socket.
- Escribir `tests/test_protocol.py`, `tests/test_singleton_client.py` y
  `tests/test_observer_client.py` con dobles de socket, sin red real.

**Correccion relevante:** el servidor de la Fase 4 seguia siendo un esqueleto
y no existia un protocolo definido en el repositorio. Se centralizo el formato
de mensajes en `tpfi.protocol` para que el servidor lo reutilice y ambos lados
queden acoplados al mismo contrato.

**Resultado:** 110 pruebas en verde con 93,6% de cobertura; `ruff`, `black`,
`mypy --strict` y `bandit` sin observaciones.

### 2026-10-06 - Servidor TCP y Notificacion en Cascada (Fase 4)

**Objetivo:** implementar el servidor TCP multihilo de aplicaciones (`SingletonProxyObserverTPFI`), integrando los patrones Proxy, Singleton y Observer, la notificacion en cascada y el registro obligatorio de auditoria en `CorporateLog`.

- Diseñar y desarrollar `server.py` con las clases `ApplicationServer` (basada en `socketserver.ThreadingTCPServer`) y `ServerHandler` (`socketserver.BaseRequestHandler`).
- Implementar el procesamiento de las 4 acciones exigidas por la consigna (`get`, `list`, `set`, `subscribe`):
  - **Auditoria:** Cada requerimiento genera una entrada en `CorporateLog` a traves de `AuditRepository` (Singleton), incluyendo `client_uuid`, `session_id`, `action`, `key` (`id` o `*`), `timestamp` ISO e informacion de la CPU (`get_cpu_info()`).
  - **`get` y `list`:** Intermediados por `DataProxy`, responden al cliente solicitante y cierran la conexion TCP.
  - **`subscribe`:** Suscribe el socket del cliente en `ObservedSubject` (Observer), confirma la subscripcion y mantiene el socket abierto para recibir futuras notificaciones, desuscribiendo automaticamente al cliente ante desconexion.
  - **`set`:** Realiza la actualizacion parcial mediante `DataProxy.set()`, responde al cliente solicitante y emite la notificacion en cascada a todos los observadores activos mediante `ObservedSubject.notify()`.
- Ajustar `ObservedSubject.notify` en `patterns/observer.py` para asegurar el encuadre de lineas JSON terminadas en `\n` requeridas por `JsonSocket`.
- Implementar `tests/test_server.py` cubriendo el ciclo de vida del servidor, las 4 acciones, las notificaciones en cascada hacia observadores, el registro de auditoria, la reutilizacion de puertos ocupados y las excepciones no controladas.
- Validar todo el proyecto con `pytest` (124 pruebas en verde, **93.3% de cobertura**), `ruff check`, `black`, `mypy --strict` y `bandit`.

**Resultado:** Fase 4 completada e integrada satisfactoriamente con 124 pruebas en verde y el 100% de los chequeos de calidad aprobados.

### 2026-10-12 - Versionado, changelog y verificacion de integracion

**Objetivo:** consolidar el registro de versiones del proyecto, documentar los
cambios entregados y verificar el sistema completo de extremo a extremo.

- Verificar la implementacion del servidor mediante una prueba de
  integracion manual: se levanto un `ApplicationServer` real sobre un puerto
  local y se lo interrogó con el protocolo de mensajes, sin dobles de prueba.
- Comprobar contra la base real las 5 acciones: `get` de un registro existente,
  `get` de un identificador inexistente, `list` completo, accion invalida y
  `set` sin identificador.
- Verificar la notificacion en cascada: un `observerclient` subscripto recibio
  la confirmacion de suscripcion y la notificacion del `set`.
- Confirmar la auditoria leyendo las entradas mas recientes de `CorporateLog`:
  las 4 acciones quedaron registradas con `client_uuid`, `timestamp` y `key`.
- Reescribir `CHANGELOG.md` agrupando los cambios por version (0.1.0, 0.2.0,
  0.3.0 y 0.4.0) con las fechas reales del historial de git y la seccion de
  autores correspondiente a cada version.
- Actualizar en conjunto los archivos que llevan el versionado manual:
  `VERSION`, `BUILD`, `version` en `pyproject.toml` y `__version__` en
  `src/tpfi/__init__.py`. Se determino unificar la version en un unico lugar
  a futuro, porque hoy esta replicada en cuatro archivos y ya se habia
  desincronizado.

**Correccion relevante:** el `CHANGELOG.md` presente conflicto de merge porque
el servidor y el registro de versiones se modificaron sobre la misma seccion
`[No publicado]`. Se resolvio conservando la descripcion del servidor escrita
por el autor correspondiente y moviendo las tareas aun pendientes a una
subseccion `### Pendiente`, de modo que no se perdiera ninguna de las dos
versiones del registro.

**Resultado:** 124 pruebas en verde con 93,3% de cobertura; `ruff`, `black`,
`mypy --strict` y `bandit` sin observaciones; sistema verificado de extremo a
extremo contra la base de datos.

### 2026-10-28 - Patron Iterator y paginacion de DynamoDB

**Objetivo:** incorporar el patron Iterator para corregir el listado
incompleto de DynamoDB y ofrecer un recorrido filtrado y ordenado de
`CorporateData`.

- Evaluar donde el patron aporta un beneficio real y no solo estructura: se
  descarto aplicarlo en `ObservedSubject.notify` (ya itera sobre una copia) y
  en `DataProxy` (no es una coleccion).
- Detectar que `DataRepository.list()` y `AuditRepository.list()` ignoraban
  `LastEvaluatedKey`, por lo que `scan` devolvia como maximo 1 MB sin avisar.
- Implementar `patterns/iterator.py` con `IteratorProtocol`,
  `AggregateProtocol` y `AggregateMixin`, dejando explicita la equivalencia
  con la notacion GoF.
- Implementar `collection.py` con `CorporateDataCollection` (agregado) y
  `RecordIterator` (iterador concreto), con filtros por igualdad, orden
  opcional y cierre del generador de origen.
- Agregar `scan()` a ambos repositorios y conservar `list()` como
  materializacion del recorrido, para no cambiar el contrato del protocolo.
- Resolver la accion `list` del proxy a traves de la coleccion.

**Correccion relevante:** la primera version de `RecordIterator.close()` solo
cerraba la expresion generadora del filtro, que no cierra por si sola el
iterable del que se alimenta. La prueba de liberacion de la fuente lo detecto y
se corrigio cerrando tambien el origen.

**Resultado:** 163 pruebas en verde con 94,9% de cobertura; `ruff`, `black`,
`mypy --strict` y `bandit` sin observaciones.


### 2026-11-01 - Alineacion con consigna oficial y cierre de defectos P1/P2/P3

**Objetivo:** contrastar la base de codigo contra la consigna oficial del TPFI
(documento de 9 paginas de la catedra), corregir desalineaciones de
especificacion y robustecer la suite de pruebas.

- Corregir fallos de formato y linter en `demo_runner.py` e incompatibilidad de
  formato entre `black` y `ruff format` en `tests/test_singletonproxyobserver.py`.
- Solucionar desconexion espuria recurrente en `observerclient.py` asegurando
  que el socket quede bloqueante tras el handshake inicial (`settimeout(None)`).
- Soportar el formato de entrada de requerimientos de la consigna (`UUID`, `ID`,
  `ACTION` en mayusculas y campos a nivel raiz) en `singletonclient.py`.
- Permitir multiples suscripciones de observadores desde un mismo UUID de CPU
  gestionando los sockets concurrentes de manera independiente en `ObservedSubject`.
- Asegurar que `ApplicationServer` no permita `SO_REUSEADDR` en plataformas Windows
  para garantizar la deteccion del fallo al intentar levantar dos servidores.
- Implementar actualizacion atomica con `update_item` (`DataRepository.merge()`),
  dejando en `None` (NULL) los campos no informados en registros nuevos y
  rechazando atributos ajenos al tuple `CorporateData`.
- Asignar la creacion del identificador de sesion (`session_id`) al servidor
  mediante `uuid.uuid4()`, y abortar la operacion si falla la auditoria en `CorporateLog`.
- Agregar proteccion contra consumo abusivo de memoria en `protocol.py` (limite
  de mensaje de 1 MiB).
- Desarrollar la suite de pruebas de aceptacion `tests/test_acceptance.py`
  cubriendo los 5 escenarios obligatorios de la consigna con el marker `@pytest.mark.acceptance`.
- Desarrollar pruebas unitarias basadas en hipotesis con `hypothesis` en
  `tests/test_hypothesis.py`.
- Sincronizar todos los cambios, modulos y suites de prueba dentro de la
  plantilla `cookiecutter-tpfi`.

**Correccion relevante:** al intentar levantar dos servidores en Windows, el
sistema operativo permitia reutilizar el puerto por default con `SO_REUSEADDR`.
Se desactivo el flag para `sys.platform == 'win32'`. Ademas, `observerclient`
trataba las excepciones de mensaje invalido como caidas de red y reintentaba
en bucle; se corrigio para limitar los reintentos a errores `OSError` de socket
y atender `KeyboardInterrupt` limpiamente conforme a la consigna.

**Resultado:** 195 pruebas en verde con 95,03% de cobertura; `ruff`, `black`,
`mypy --strict` y `bandit` sin observaciones; plantilla Cookiecutter sincronizada
y verificada.


### 2026-11-01 - Entorno de pruebas en vivo, protocolo de integracion y guia de estudio

**Objetivo:** preparar el banco de datos de prueba, el entorno de ejecucion en vivo, la documentacion tecnica y el plan de demostracion para la defensa oral del sistema distribuido.

- Crear el juego de datos de prueba en `samples/` (`input_get.json`, `input_set.json`, `input_list.json`, `input_invalido.json`) para ensayar repetiblemente cada accion del protocolo y la validacion de integridad del Proxy.
- Desarrollar `demo_runner.py` con repositorios en memoria (`MemoryDataRepository`, `MemoryAuditRepository`) y dobles defensivos para emular el ciclo completo distribuido (servidor multihilo, observador y cliente de transacciones con auditoria) de forma autonoma y offline.
- Elaborar `COMANDOS_DEFENSA.txt` con el protocolo formal de ejecucion en 3 terminales, detallando roles, flujos de red, argumentos y pruebas de regresion y linters para la proyeccion en el examen oral.
- Redactar `docs/GUIA_ESTUDIO_TPFI.md` y `docs/GUIA_ESTUDIO_TPFI.html` con la especificacion exhaustiva de la arquitectura, patrones GoF, esquema de DynamoDB, protocolo de sockets y banco de preguntas de examen oral, junto con el script de compilacion `generate_pdf.py` para generar `docs/GUIA_ESTUDIO_TPFI.pdf`.
- Configurar la persistencia de entorno y resolucion de modulos en Windows para ejecucion transparente en terminales PowerShell.

**Resultado:** protocolo de defensa en vivo, guia de estudio y muestras de prueba 100% operativos y sincronizados con la suite de aceptacion.
