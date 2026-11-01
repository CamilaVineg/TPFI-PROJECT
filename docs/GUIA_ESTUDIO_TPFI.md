# Guía Completa de Estudio y Defensa: TPFI IS2

**Materia:** Ingeniería de Software II (UADER - FCyT)  
**Proyecto:** TPFI-PROJECT (Arquitectura Distribuida con Patrones GoF y AWS DynamoDB)  
**Autores del Repositorio:** Camila Vinegar, Tadeo Rochas, Abril Poggio  
**Versión:** 0.5.0  

---

## 1. Visión General del Sistema y Requerimientos

El sistema es una **aplicación cliente-servidor distribuida sobre TCP** que gestiona información corporativa de sedes institucionales en una base de datos NoSQL (**AWS DynamoDB**).

### Programas requeridos por la consigna:
| Programa | Archivo fuente | Rol y Responsabilidad |
|---|---|---|
| `SingletonProxyObserverTPFI` | `src/tpfi/singletonproxyobserver.py` | Servidor TCP multihilo. Recibe conexiones, audita cada petición, valida mediante Proxy, interactúa con la base física vía Singleton y emite notificaciones a observadores. |
| `SingletonClient` | `src/tpfi/singletonclient.py` | Cliente de operaciones transaccionales puntuales. Lee una petición JSON (`-i input.json`), consulta o actualiza la tabla y emite la respuesta (`-o output.json` o consola). |
| `ObserverClient` | `src/tpfi/observerclient.py` | Cliente suscriptor. Se conecta, envía su UUID de CPU y mantiene el socket abierto para recibir actualizaciones en tiempo real cada vez que un registro cambia. |

### Las 2 Tablas de AWS DynamoDB:
- **`CorporateData`:** Almacena los registros de sedes. Clave primaria: `id`. Atributos: `cp`, `CUIT`, `domicilio`, `idreq`, `idSeq`, `localidad`, `provincia`, `sede`, `seqID`, `telefono`, `web`.
- **`CorporateLog`:** Pista de **auditoría obligatoria**. Toda acción (`get`, `list`, `set`, `subscribe`) registra: `id` (= `session_id`), `action`, `client_uuid`, `timestamp` (ISO 8601 UTC), `key` (el ID o `*`), y `cpu_info` (nodo, SO, arquitectura, procesador y UUID de CPU vía `uuid.getnode()`).

---

## 2. Arquitectura y los 4 Patrones de Diseño (GoF)

```
                  +----------------------------------------------+
                  |         SingletonProxyObserverTPFI           |
                  |                (Servidor TCP)                |
                  +----------------------------------------------+
                         |                              |
         [Auditoría Obligatoria]               [Acceso a Datos]
                         v                              v
               +--------------------+          +------------------+
               |  AuditRepository   |          |    DataProxy     |  <-- PATRÓN PROXY
               |    (SINGLETON)     |          +------------------+
               +--------------------+                   | (Valida y delega)
                         |                              v
                         |                     +------------------+
                         |                     |  DataRepository  |  <-- PATRÓN SINGLETON
                         |                     |   (SINGLETON)    |
                         |                     +------------------+
                         |                              |
                         v                              v
              +----------------------+     +--------------------------+
              | DynamoDB CorporateLog|     | DynamoDB CorporateData   |
              +----------------------+     +--------------------------+
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

### 1. Patrón Singleton (`tpfi.patterns.singleton` y `tpfi.repository`)
- **Propósito:** Garantizar una única instancia física y punto de acceso global a los recursos de conexión con DynamoDB. Abrir conexiones con boto3 en cada petición saturaría recursos y sockets.
- **Implementación:** Metaclase `SingletonABCMeta` (hereda de `abc.ABCMeta`). Emplea *Double-Checked Locking* con `threading.Lock` en su método `__call__` para garantizar *thread-safety* multihilo.
- **Uso en el proyecto:** Se aplica a `DataRepository` (acceso a `CorporateData`) y `AuditRepository` (acceso a `CorporateLog`). Ambos son Singletons independientes.

### 2. Patrón Proxy (`tpfi.patterns.proxy` y `tpfi.proxy`)
- **Propósito:** Actuar como intermediario entre el cliente y el repositorio físico, agregando una capa de control y validación de reglas de negocio sin acoplar la base de datos.
- **Implementación:** Interfaz abstracta `ProxyInterface` e implementación `DataProxy`.
- **Responsabilidades del Proxy:**
  1. **Validación estricta:** Verifica que el `id` sea texto no vacío y que `data` sea un diccionario.
  2. **Protección de campos reservados:** Prohíbe que el cliente intente modificar la clave primaria `id` dentro de `data`.
  3. **Actualización parcial:** Si el registro ya existe, fusiona los campos nuevos con los existentes (`{**current, **values}`) sin borrar los datos omitidos. Si no existe, lo crea.

### 3. Patrón Observer (`tpfi.patterns.observer`)
- **Propósito:** Definir una dependencia uno-a-muchos entre el servidor y los clientes interesados, de forma tal que cuando un registro cambie, todos los observadores sean notificados automáticamente.
- **Implementación:** El servidor instancia un `ObservedSubject`. Mantiene una colección de sockets de observadores activos: `_observers: dict[str, socket.socket]`.
- **Notificación en Cascada:** Cuando cualquier cliente ejecuta una acción `set` exitosa, el servidor ejecuta `self.server.subject.notify(notification)`. El sujeto itera los observadores y retransmite el payload JSON delimitado por `\n`. Si detecta un socket caído, lo desuscribe automáticamente.

### 4. Patrón Iterator (`tpfi.patterns.iterator` y `tpfi.collection`)
- **Problema que resuelve:** La operación `scan` de AWS DynamoDB tiene un límite físico de **1 MB por petición**. Si una tabla supera ese tamaño, DynamoDB trunca la respuesta y devuelve `LastEvaluatedKey`. Sin iterador, los listados quedan incompletos.
- **Estructura GoF:**
  - `Aggregate`: `AggregateMixin` (protocolo de agregación).
  - `ConcreteAggregate`: `CorporateDataCollection`.
  - `Iterator`: `IteratorProtocol`.
  - `ConcreteIterator`: `RecordIterator`.
- **Evaluación Perezosa (Lazy):** `RecordIterator` no descarga la tabla completa en memoria; solicita a AWS la siguiente página únicamente cuando se agota la anterior. Permite además aplicar filtros y ordenación en el flujo.

---

## 3. Protocolo de Comunicación y Red (TCP Stream Framing)

En TCP, la transmisión es un *stream* continuo de bytes (no orientado a datagramas). Dos mensajes pueden llegar juntos o un mensaje puede llegar fragmentado en varios bloques de red.

> **Encuadre de Mensajes (Line-delimited JSON):** Cada mensaje viaja serializado como una línea JSON terminada estrictamente con el caracter `\n`.

La clase `JsonSocket` (`src/tpfi/protocol.py`) encapsula el socket nativo y mantiene un buffer interno (`self._buffer`). Al recibir datos con `recv(4096)`, busca `\n` con `partition()` y devuelve únicamente mensajes JSON completos y válidos.

### Formato de Mensajes:

```json
// 1. Requerimiento del Cliente (Request)
{
  "type": "request",
  "action": "get" | "set" | "list" | "subscribe",
  "session_id": "uuid-v4",
  "client_uuid": "uuid-cpu",
  "id": "UADER-FCyT-IS2",
  "data": { "sede": "FCyT Central" }
}

// 2. Respuesta Exitosa del Servidor (Response OK)
{
  "type": "response",
  "status": "ok",
  "session_id": "uuid-v4",
  "data": { ... }
}

// 3. Respuesta de Error del Servidor (Response Error)
{
  "type": "response",
  "status": "error",
  "session_id": "uuid-v4",
  "error": "El registro 'NO-EXISTE' no existe"
}

// 4. Notificación en Cascada para Observadores (Notification)
{
  "type": "notification",
  "action": "set",
  "session_id": "uuid-v4",
  "data": { "id": "UADER-FCyT-IS2", "sede": "FCyT Central", ... }
}
```

---

## 4. Guía de Ejecución y Demostración en Vivo

### Opción A: Demostración Rápida Automatizada (Script `demo_runner.py`)
Ideal si no dispones de conexión con AWS en el momento de la exposición, o para mostrar en 10 segundos el flujo completo funcionando sin errores:
```bash
python demo_runner.py
```
**Lo que demuestra en consola ante los profesores:**
1. Levanta el servidor multihilo TCP en `127.0.0.1:8888`.
2. Conecta en segundo plano un `ObserverClient` y confirma su suscripción.
3. Ejecuta un `get` con `SingletonClient` y muestra la respuesta.
4. Ejecuta un `set` con actualización parcial y muestra cómo el `ObserverClient` **recibe inmediatamente la notificación en cascada**.
5. Ejecuta un `list` completo paginado con el patrón Iterator.
6. Verifica e imprime el contenido de la tabla de auditoría `CorporateLog`.

---

### Opción B: Demostración Manual en 3 Terminales (Conforme a la consigna)
Abre 3 ventanas de terminal (PowerShell o Bash) en la raíz del proyecto:

**Terminal 1: Iniciar el Servidor**
```bash
singletonproxyobserver -p=8080 -v
```

**Terminal 2: Iniciar el Observador**
```bash
observerclient -s=localhost -p=8080 -v
```

**Terminal 3: Ejecutar operaciones del Cliente**
```bash
# 1. Consultar registro existente
singletonclient -i=samples/input_get.json -v

# 2. Modificar registro (¡Observa la Terminal 2 recibir la notificación!)
singletonclient -i=samples/input_set.json -v

# 3. Listar todos los registros
singletonclient -i=samples/input_list.json -v
```

---

## 5. Banco de Preguntas y Respuestas para el Coloquio

**P1: ¿Por qué usaron una metaclase para el Singleton en lugar de un decorador o un método get_instance()?**  
> **R:** Porque una metaclase (`SingletonABCMeta`) intercepta el constructor nativo de la clase (`__call__`). Esto permite que el resto del sistema instancie la clase de forma idiomática con `DataRepository()` sin tener que preocuparse de si es un Singleton o no. Además, se implementó con *Double-Checked Locking* para garantizar seguridad en entornos multihilo.

**P2: ¿Por qué la validación está en el Proxy y no dentro del Repositorio?**  
> **R:** Por el Principio de Responsabilidad Única (SRP). `DataRepository` solo se encarga del acceso físico a DynamoDB. El `DataProxy` gestiona las reglas de negocio (campos obligatorios, protección de claves primarias y combinación de actualizaciones parciales). Esto permite cambiar de base de datos o usar dobles de prueba (mocks) en los tests unitarios sin tocar la lógica de negocio.

**P3: ¿Qué sucede si un cliente observador se desconecta abruptamente?**  
> **R:** En el servidor, al intentar enviar una notificación o al detectar el cierre del canal en `ServerHandler`, se lanza una excepción de socket. El servidor captura el error, llama a `unsubscribe()` y cierra el socket para evitar fugas de memoria y descriptores huérfanos. En el cliente, `ObserverClient` captura la caída y reintenta conectarse cada 30 segundos automáticamente.

**P4: ¿Por qué fue necesario incorporar el patrón Iterator en la versión 0.5.0?**  
> **R:** DynamoDB limita las lecturas de `scan` a 1 MB por llamada. Si la tabla supera ese límite, la respuesta se trunca silenciosamente y entrega una `LastEvaluatedKey`. El `RecordIterator` recorre la tabla página por página bajo demanda (lazy evaluation), garantizando que ningún registro quede sin leer sin saturar la memoria del servidor.

**P5: ¿Por qué cada mensaje en los sockets TCP termina en '\n'?**  
> **R:** Porque TCP es un protocolo de flujo continuo de bytes (stream), no un protocolo de paquetes delimitados. Para saber dónde termina un mensaje JSON y empieza el siguiente sin tener que cerrar la conexión TCP, se usa el delimitador de nueva línea `\n` (Framing). `JsonSocket` acumula un buffer y entrega el mensaje solo cuando encuentra el delimitador.

**P6: ¿Cómo se maneja la concurrencia en el servidor?**  
> **R:** La clase `ApplicationServer` hereda de `socketserver.ThreadingTCPServer` con `daemon_threads = True`. Cada cliente que se conecta es atendido en un hilo independiente (thread), permitiendo que múltiples clientes consulten mientras los observadores mantienen sockets abiertos de larga duración.

