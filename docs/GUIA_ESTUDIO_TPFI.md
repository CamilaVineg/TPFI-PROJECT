# Guía Maestra de Estudio y Defensa: TPFI IS2

**Materia:** Ingeniería de Software II (UADER - FCyT)  
**Proyecto:** TPFI-PROJECT (Arquitectura Distribuida con Patrones GoF y AWS DynamoDB)  
**Autores del Repositorio:** Camila Viñeg, Tadeo Rochas, Abril Poggio  
**Versión:** 0.5.0  

---

## 1. Visión General del Sistema y Requerimientos

El sistema es una **aplicación cliente-servidor distribuida sobre TCP** que gestiona información corporativa de sedes institucionales en una base de datos NoSQL (**AWS DynamoDB**).

### 1.1 Programas exigidos por la consigna oficial:
| Programa (CLI) | Archivo fuente | Rol y Responsabilidad |
|---|---|---|
| `singletonproxyobserver` | `src/tpfi/singletonproxyobserver.py` | Servidor TCP multihilo (`SingletonProxyObserverTPFI`). Recibe conexiones concurrentes, audita cada petición en `CorporateLog`, intercepta y valida mediante Proxy, ejecuta la persistencia física vía Singleton y emite notificaciones en tiempo real a observadores. |
| `singletonclient` | `src/tpfi/singletonclient.py` | Cliente transaccional puntual (`SingletonClient`). Lee una petición JSON (`-i input.json`), consulta o actualiza la tabla y emite la respuesta (`-o output.json` o consola). Soporta tanto el formato tradicional como el formato de la consigna con atributos en mayúsculas a nivel raíz. |
| `observerclient` | `src/tpfi/observerclient.py` | Cliente suscriptor reactivo (`ObserverClient`). Se conecta, envía su UUID de CPU (`subscribe`) y mantiene el socket abierto para recibir actualizaciones en tiempo real cada vez que un registro cambia. Cuenta con bucle de reconexión automática ante caídas de red. |

### 1.2 Las 2 Tablas de AWS DynamoDB:
- **`CorporateData`:** Almacena los registros de sedes institucionales.
  - **Clave primaria (Partition Key):** `id` (texto no vacío, identificador único de la sede).
  - **Campos del tuple corporativo:** `cp`, `CUIT`, `domicilio`, `idreq`, `idSeq`, `localidad`, `provincia`, `sede`, `seqID`, `telefono`, `web`.
- **`CorporateLog`:** Pista de **auditoría obligatoria** por requerimiento de seguridad.
  - **Clave primaria:** `id` (almacena el `session_id` generado autoritativamente por el servidor).
  - **Atributos registrados:** `action` (`get`, `set`, `list`, `subscribe`), `client_uuid` (identificador de CPU del solicitante), `session_id`, `timestamp` (marca de tiempo ISO 8601 UTC), `key` (el `id` de la sede afectada o `*` si aplica a toda la tabla), y `cpu_info` (telemetría del nodo, sistema operativo, arquitectura, procesador y UUID obtenido por `uuid.getnode()`).

---

## 2. Arquitectura y los 4 Patrones de Diseño (GoF) en Detalle

```
                   +----------------------------------------------+
                   |         SingletonProxyObserverTPFI           |
                   |       (Servidor TCP Multihilo - :8080)       |
                   +----------------------------------------------+
                         |                                |
         [1. Auditoría Obligatoria]              [2. Acceso a Datos]
                         v                                v
               +--------------------+           +------------------+
               |  AuditRepository   |           |    DataProxy     |  <-- PATRÓN PROXY
               |    (SINGLETON)     |           +------------------+
               +--------------------+                    |
                         |                      (Valida y delega)
                         |                               v
                         |                      +------------------+
                         |                      |  DataRepository  |  <-- PATRÓN SINGLETON
                         |                      |   (SINGLETON)    |
                         |                      +------------------+
                         |                               |
                         v                               v
              +----------------------+        +--------------------------+
              | DynamoDB CorporateLog|        | DynamoDB CorporateData   |
              +----------------------+        +--------------------------+
                                                          |
                                                (Si hubo 'set' exitoso)
                                                          v
                                                 +------------------+
                                                 | ObservedSubject  |  <-- PATRÓN OBSERVER
                                                 +------------------+
                                                          | (Notificación en cascada \n)
                                                          v
                                                [ ObserverClient ]
```

### 2.1 Patrón Singleton (`tpfi.patterns.singleton` y `tpfi.repository`)
- **Problema que resuelve:** En un servidor multihilo, abrir clientes de AWS (`boto3.resource`) en cada petición agota rápidamente los file descriptors, colapsa el pool de sockets y añade una sobrecarga de latencia inaceptable. Se requiere un punto de acceso único y compartido a la base física.
- **Implementación Técnica:**
  - Se define la metaclase `SingletonABCMeta` que hereda de `abc.ABCMeta`.
  - Intercepta el constructor mediante el método especial `__call__(cls, *args, **kwargs)`.
  - **Técnica Double-Checked Locking:**
    ```python
    if cls not in SingletonABCMeta._instances:
        with SingletonABCMeta._lock:
            if cls not in SingletonABCMeta._instances:
                SingletonABCMeta._instances[cls] = super().__call__(*args, **kwargs)
    return SingletonABCMeta._instances[cls]
    ```
    *¿Por qué?* La primera comprobación evita tomar el lock en lecturas frecuentes concurrentes (altísimo rendimiento). La adquisición del cerrojo (`threading.Lock`) serializa la creación, y la segunda comprobación asegura que si dos hilos llegaron al cerrojo al mismo tiempo, solo uno instancie el objeto.
- **Uso en el sistema:** Se aplica a `DataRepository` y a `AuditRepository`. Ambos son Singletons completamente independientes respetando el Principio de Responsabilidad Única.

### 2.2 Patrón Proxy (`tpfi.patterns.proxy` y `tpfi.proxy`)
- **Problema que resuelve:** El servidor jamás debe comunicarse directamente con la infraestructura de persistencia. Se requiere un intermediario de protección y validación de reglas de negocio que impida que peticiones maliciosas o malformadas impacten en DynamoDB.
- **Implementación Técnica:**
  - Interfaz abstracta `ProxyInterface` e implementación `DataProxy`.
- **Los 5 Pasos de Validación en `DataProxy.set()`:**
  1. **Validación de Identificador:** Verifica que el `id` sea una cadena de texto no vacía (`_validate_id()`).
  2. **Validación de Estructura:** Asegura que `values` sea un diccionario JSON válido.
  3. **Protección de Clave Reservada:** Si el cliente incluye `"id"` dentro del cuerpo de datos, el Proxy rechaza la operación inmediatamente (`RESERVED_FIELDS = frozenset({'id'})`).
  4. **Control Estricto de Esquema:** Comprueba que no existan atributos ajenos a `CORPORATE_FIELDS`. Si el cliente envía atributos no reconocidos, se aborta la petición.
  5. **Delegación Atómica:** Si supera todos los filtros, delega en `self._repository.merge(record_id, values)`.

### 2.3 Patrón Observer (`tpfi.patterns.observer`)
- **Problema que resuelve:** Notificar en tiempo real a clientes suscriptos cada vez que un registro corporativo se modifique (`set`), sin que el cliente tenga que hacer polling continuo (consultas periódicas) a la base de datos.
- **Implementación Técnica:**
  - El servidor mantiene una instancia de `ObservedSubject`.
  - Cada cliente suscriptor se encapsula en un `SocketObserver` que implementa `ObserverProtocol`.
  - **Soporte Concurrente:** El sujeto almacena `_observers: dict[str, list[SocketObserver]]`, permitiendo múltiples instancias de observadores desde una misma máquina (mismo CPU UUID).
  - **Snapshot Isolation (Aislamiento por Instantánea):**
    Al momento de emitir la notificación, el sujeto copia la lista de destinatarios bajo cerrojo y luego libera el cerrojo antes de realizar las llamadas a la red (`sendall`):
    ```python
    with self._lock:
        targets = [(uuid, obs) for uuid, obs_list in self._observers.items() for obs in obs_list]
    for uuid, obs in targets:
        obs.update(payload)
    ```
    *Beneficio:* Si un cliente tiene una red lenta, no frena la ejecución ni bloquea al resto de los hilos del servidor.
  - **Poda Automática (Auto-pruning):** Si el socket de un observador falló (`SocketDeliveryError`), el sujeto lo desuscribe automáticamente, liberando los recursos del sistema operativo.

### 2.4 Patrón Iterator (`tpfi.patterns.iterator` y `tpfi.collection`)
- **Problema que resuelve:** DynamoDB limita la operación `scan()` a **1 MB por llamada**. Si una tabla supera ese tamaño, DynamoDB trunca la respuesta y entrega un token `LastEvaluatedKey`. Sin un iterador, las consultas de listado devuelven datos incompletos.
- **Mapeo GoF a Python:**
  - `Aggregate`: `AggregateMixin` (interfaz base).
  - `ConcreteAggregate`: `CorporateDataCollection` (envuelve al repositorio físico).
  - `Iterator`: `IteratorProtocol` (protocolo con `__iter__` y `__next__`).
  - `ConcreteIterator`: `RecordIterator` (iterador concreto perezoso).
- **Evaluación Perezosa (Lazy Evaluation):** `RecordIterator` no descarga la tabla completa en RAM. Solicita la siguiente página a DynamoDB recién cuando se agota la anterior. Soporta además filtrado de atributos y ordenamiento en vuelo. Al terminar, su método `close()` garantiza el cierre del generador subyacente.

---

## 3. Protocolo de Comunicación y Red (TCP Stream Framing)

### 3.1 Naturaleza de TCP y Encuadre (Framing)
TCP es un protocolo orientado a flujo continuo de bytes (*stream*), no a paquetes discretos. Si un emisor envía dos mensajes seguidos, el receptor puede recibirlos juntos en un solo `recv()`, o un mensaje grande puede llegar fragmentado en varios bloques.

> **Solución (Line-delimited JSON):** Cada mensaje viaja serializado como una línea JSON terminada estrictamente con el delimitador `\n`.

### 3.2 La clase `JsonSocket` (`src/tpfi/protocol.py`)
Encapsula el socket nativo y administra un búfer interno (`self._buffer`). Al invocar `receive()`, lee del socket, busca el delimitador `\n` mediante `partition()` y deserializa exclusivamente un mensaje JSON completo.
- **Protección contra Denegación de Servicio (DoS por Memoria):** `JsonSocket` impone un límite estricto de **1 MiB (`MAX_MESSAGE_SIZE`)**. Si un cliente malicioso envía un stream continuo sin `\n`, el socket aborta la conexión antes de agotar la memoria del servidor.

### 3.3 Esquema de los 4 Mensajes del Protocolo:

```json
// 1. Requerimiento del Cliente (Request)
{
  "type": "request",
  "action": "get" | "set" | "list" | "subscribe",
  "session_id": "uuid-opcional",
  "client_uuid": "uuid-cpu",
  "id": "UADER-FCyT-IS2",
  "data": { "telefono": "03442 43-1442" }
}

// 2. Respuesta Exitosa del Servidor (Response OK)
{
  "type": "response",
  "status": "ok",
  "session_id": "uuid4-generado-por-servidor",
  "data": { "id": "UADER-FCyT-IS2", "sede": "FCyT Central", ... }
}

// 3. Respuesta de Error del Servidor (Response Error)
{
  "type": "response",
  "status": "error",
  "session_id": "uuid4-generado-por-servidor",
  "error": "No se admiten los campos reservados: id"
}

// 4. Notificación en Cascada para Observadores (Notification)
{
  "type": "notification",
  "action": "set",
  "session_id": "uuid4-generado-por-servidor",
  "data": { "id": "UADER-FCyT-IS2", "telefono": "03442 43-1442", ... }
}
```

### 3.4 Ciclos de Vida de Conexión:
- **Peticiones Transaccionales (`get`, `set`, `list`):** Ciclo corto. El cliente conecta, envía petición, recibe respuesta JSON y el socket se cierra.
- **Suscripción (`subscribe`):** Ciclo de vida persistente. El cliente envía `subscribe`, recibe confirmación y el socket **se mantiene abierto indefinidamente** para recibir las notificaciones push en cascada.

---

## 4. Auditoría, Concurrencia y Persistencia Atómica

### 4.1 Autoridad del `session_id` en el Servidor
En `ServerHandler.handle()`, el servidor **siempre genera un nuevo `session_id = str(uuid.uuid4())`**.
*¿Por qué?* Si se permitiera que el cliente elija el `session_id`, un atacante podría sobrescribir registros previos en `CorporateLog` o suplantar sesiones ajenas. El servidor actúa como autoridad certificante de la auditoría.

### 4.2 Actualización Atómica en DynamoDB (`DataRepository.merge`)
La consigna exige que `set` actualice únicamente los campos informados y preserve los preexistentes.
- **Riesgo:** Hacer un `get` previo en Python y luego un `put` genera una ventana de carrera (*Race Condition*): si dos clientes escriben al mismo tiempo, uno sobrescribirá los datos del otro.
- **Solución implementada:** Se delega la fusión directamente en el motor de DynamoDB utilizando una única operación atómica `update_item` con expresiones `SET #field = :val` e `if_not_exists(#field, :null)` para inicializar campos no informados.

### 4.3 Detección de Doble Servidor en Windows (`allow_reuse_address`)
En sistemas Windows, el flag por defecto `SO_REUSEADDR` permitía que dos instancias del servidor escucharan sobre el mismo puerto TCP sin avisar el error. En `ApplicationServer` se configuró:
```python
allow_reuse_address = sys.platform != "win32"
```
garantizando que al intentar levantar dos veces el servidor, el segundo falle de forma inmediata con `OSError` (puerto ya en uso).

---

## 5. Estrategia de Pruebas Automatizadas y Calidad (195 Tests - 95.03% Cobertura)

La suite de pruebas en `tests/` cubre la totalidad de la pirámide de testing requerida por la cátedra:

1. **Pruebas Unitarias Aisladas:** Validan cada patrón y módulo sin requerir conexión real a AWS mediante dobles de prueba (test doubles) y mocks de `boto3`.
2. **Suite de Aceptación Formal (`tests/test_acceptance.py`):**
   Implementa los 5 escenarios obligatorios de la consigna evaluadora:
   - **Escenario 1 (Camino feliz):** Modificación mediante `set` con verificación del registro en `CorporateData` y de la pista de auditoría en `CorporateLog`.
   - **Escenario 2 (Argumentos malformados):** Parámetros CLI inválidos y archivos JSON con sintaxis corrupta.
   - **Escenario 3 (Requerimiento sin datos mínimos):** Bloqueo de peticiones incompletas por parte del Proxy.
   - **Escenario 4 (Clientes ante servidor caído):** Comportamiento tolerante a fallos y reintentos ante rechazo de conexión TCP.
   - **Escenario 5 (Rechazo de doble bind):** Comprobación de que no se permite iniciar dos instancias del servidor en el mismo puerto.
3. **Pruebas Basadas en Propiedades con Hypothesis (`tests/test_hypothesis.py`):**
   Genera cientos de combinaciones aleatorias de bytes y esquemas para verificar:
   - Ida y vuelta (Round-trip) en la serialización y deserialización del protocolo.
   - Resiliencia del decodificador ante secuencias arbitrarias de bytes de entrada (fuzzing).
   - Generación estricta de UUID4 y validación de tipos en Proxy.
4. **Linters y Análisis Estático:**
   - `ruff check .`: 0 observaciones.
   - `black --check .`: Formato 100% homogéneo.
   - `mypy --strict`: Tipado estático estricto verificado.
   - `bandit -r src`: 0 vulnerabilidades de seguridad detectadas.

---

## 6. Protocolo de Demostración en Vivo para la Presentación

### Modo Oficial: 3 Terminales en Vivo

Abre tres ventanas de terminal PowerShell en la raíz del proyecto:

#### Terminal 1: Servidor de Aplicaciones
```powershell
python -m tpfi.singletonproxyobserver -p 8080 -v
```
*Explicación para el tribunal:* "Iniciamos el servidor multihilo en el puerto 8080. Observen que queda listo para recibir conexiones en segundo plano."

#### Terminal 2: Observador Reactivo
```powershell
python -m tpfi.observerclient -s 127.0.0.1 -p 8080 -v
```
*Explicación para el tribunal:* "Conectamos el cliente Observer. Envía su UUID de CPU (`subscribe`), el servidor lo confirma y el socket permanece abierto escuchando eventos."

#### Terminal 3: Cliente de Transacciones
```powershell
# 1. Consulta por clave (Lectura intermediada por Proxy)
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_get.json" -v

# 2. Modificación parcial (Atención: la Terminal 2 recibe la notificación en tiempo real)
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_set.json" -v

# 3. Listado completo (Paginación transparente con el patrón Iterator)
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_list.json" -v

# 4. Intento de modificación inválida (El Proxy rechaza alterar la clave primaria)
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_invalido.json" -v
```

---

## 7. Banco Maestro de Preguntas y Respuestas para el Coloquio Oral

**P1: ¿Por qué usaron una metaclase para el Singleton en lugar de un decorador o un método estático `get_instance()`?**  
> **R:** Porque una metaclase (`SingletonABCMeta`) gobierna la instanciación a nivel de lenguaje al interceptar `__call__`. Esto permite que el resto del sistema instancie la clase de forma idiomática en Python (`DataRepository()`) sin acoplarse a un método estático o función externa. Además, admite herencia limpia desde `abc.ABC` y se sincroniza con *Double-Checked Locking*.

**P2: ¿Por qué la validación reside en el Proxy y no dentro del Repositorio?**  
> **R:** Por el Principio de Responsabilidad Única (SRP). `DataRepository` solo se encarga del acceso físico a DynamoDB. `DataProxy` aplica las reglas de negocio (campos obligatorios, protección de claves reservadas y rechazo de campos ajenos). Esto desacopla la persistencia: podríamos migrar de DynamoDB a PostgreSQL o utilizar dobles de prueba en memoria sin modificar las validaciones.

**P3: ¿Qué sucede si dos clientes envían un `set` sobre el mismo registro al mismo tiempo?**  
> **R:** Si hiciéramos una lectura previa en Python y luego una escritura, se produciría una condición de carrera (*race condition*). En nuestro diseño, `DataRepository.merge()` delega la operación en DynamoDB mediante una llamada atómica a `update_item` con expresiones de actualización. DynamoDB serializa las modificaciones atómicamente a nivel de registro.

**P4: ¿Por qué el `session_id` lo crea el servidor y no el cliente?**  
> **R:** Por seguridad, integridad y no repudio. Si el cliente generara el identificador de sesión, podría inventar identificadores repetidos para sobrescribir entradas de auditoría previas en `CorporateLog` o fingir la sesión de otro usuario. El servidor genera un `uuid.uuid4()` autoritativo en cada petición.

**P5: ¿Por qué fue indispensable el patrón Iterator en la versión 0.5.0?**  
> **R:** DynamoDB limita las lecturas de `scan` a 1 MB por llamada. Si la tabla supera ese límite, la respuesta se trunca y devuelve `LastEvaluatedKey`. El iterador (`RecordIterator`) resuelve la paginación transparente multietapa de forma perezosa (lazy evaluation): solicita páginas sucesivas a AWS recién cuando el consumidor agota la actual, evitando cargar la tabla completa en RAM.

**P6: ¿Cómo se maneja la desconexión abrupta de un cliente observador?**  
> **R:** En el servidor, al intentar enviar una notificación por el socket o detectar el cierre en el bucle de escucha, se captura la excepción de socket (`SocketDeliveryError` / `OSError`). El sujeto invoca automáticamente `unsubscribe()` y libera el descriptor (poda automática). En el cliente, `ObserverClient` captura el error y activa un bucle de reconexión periódica.

**P7: ¿Cómo se protege el servidor contra ataques de denegación de servicio por memoria en los sockets?**  
> **R:** En el protocolo (`JsonSocket`), se impone un límite máximo de tamaño de mensaje de 1 MiB (`MAX_MESSAGE_SIZE`). Si un emisor envía un flujo continuo de bytes sin el delimitador `\n`, el socket interrumpe la lectura y aborta la conexión antes de consumir la memoria del servidor.

**P8: ¿Cómo garantizaron que el protocolo resistiera datos corruptos o entradas imprevistas?**  
> **R:** Implementamos pruebas basadas en propiedades con `hypothesis` (`tests/test_hypothesis.py`). Hypothesis somete al protocolo a miles de iteraciones con bytes arbitrarios (fuzzing), verificando que el decodificador maneje cualquier excepción de manera controlada y sin caídas críticas del sistema.

**P9: ¿Por qué el patrón Observer utiliza Snapshot Isolation al momento de notificar?**  
> **R:** Porque transmitir datos por sockets TCP hacia múltiples clientes es una operación lenta sujeta a latencias de red. Si mantuviéramos el cerrojo `_lock` adquirido durante las llamadas a `sendall`, un observador con conexión lenta bloquearía a todos los hilos del servidor. Al copiar la lista de observadores bajo lock y liberarlo de inmediato, la difusión se ejecuta sin frenar el servidor.

**P10: ¿Qué hicieron para garantizar que dos servidores no puedan levantarse sobre el mismo puerto en Windows?**  
> **R:** Desactivamos el atributo `allow_reuse_address` para plataformas Windows (`sys.platform == 'win32'`). En Windows, el flag por defecto `SO_REUSEADDR` permitía reutilizar puertos en uso. Con este ajuste, el sistema operativo rechaza el bind con un error `OSError`, cumpliendo con el escenario exigido de la consigna.
