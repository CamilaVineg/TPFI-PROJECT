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

**Objetivo:** diseno del esqueleto del proyecto basado en Cookiecutter.

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