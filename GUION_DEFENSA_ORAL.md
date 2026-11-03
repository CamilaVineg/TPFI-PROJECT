# Guion Paso a Paso para la Defensa Oral del TPFI

Este documento es tu **guion de exposición**: te indica exactamente **qué comando ejecutar**, **qué mirar en la pantalla** y **qué decir palabra por palabra** ante los profesores durante la presentación.

---

## 0. Preparación Previa (Antes de que te llamen a exponer)

Abre **3 terminales de PowerShell** acomodadas una al lado de la otra (o dos a la izquierda y una a la derecha):

```
+-----------------------------------+-----------------------------------+
|            TERMINAL 1             |            TERMINAL 2             |
|    (Servidor TCP Multihilo)       |       (ObserverClient Push)       |
+-----------------------------------+-----------------------------------+
|                            TERMINAL 3                                 |
|             (SingletonClient - Peticiones Transaccionales)            |
+-----------------------------------------------------------------------+
```

Asegúrate de que en las 3 terminales esté activo el entorno virtual (`(.venv)` al inicio de la línea):
```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 1. Introducción Inicial (30 segundos)

> *"Buenas tardes profesores. Nuestro proyecto es una aplicación distribuida cliente-servidor desarrollada sobre TCP y conectada a AWS DynamoDB.  
> El sistema implementa cuatro patrones de diseño GoF:*
> 1. ***Singleton:*** *Para gestionar el acceso único y seguro a las tablas físicas `CorporateData` y `CorporateLog`.*
> 2. ***Proxy:*** *Para interceptar, validar datos mínimos y proteger las claves primarias antes de acceder a la base.*
> 3. ***Observer:*** *Para notificar en tiempo real a clientes suscriptos cada vez que un registro cambia.*
> 4. ***Iterator:*** *Para recorrer y paginar transparentemente DynamoDB sin truncamientos ni saturación de memoria.*
> 
> *A continuación, vamos a realizar la demostración funcional en vivo con 3 servicios concurrentes."*

---

## 2. Puesta en Marcha de Servicios (1 minuto)

### Paso 2.1: Iniciar el Servidor (Terminal 1)
Ejecuta en la **Terminal 1**:
```powershell
python -m tpfi.singletonproxyobserver -p 8080 -v
```

> **Qué decir:**  
> *"Iniciamos en la Terminal 1 el servidor multihilo en el puerto 8080.  
> Como pueden ver en los logs, los repositorios de datos y auditoría se inicializan bajo el patrón Singleton: una única instancia para todo el proceso.  
> Además, cada cliente que se conecte será atendido en un hilo independiente para no bloquear el servicio."*

---

### Paso 2.2: Conectar el Observador (Terminal 2)
Ejecuta en la **Terminal 2**:
```powershell
python -m tpfi.observerclient -s 127.0.0.1 -p 8080 -v
```

> **Qué decir:**  
> *"En la Terminal 2 conectamos el cliente Observer.  
> El observador envió su UUID de hardware solicitando la suscripción.  
> El servidor confirmó la suscripción con `status: ok` y dejó el canal TCP abierto de forma persistente.  
> Queda a la espera pasiva de cualquier cambio que ocurra en los registros."*

---

## 3. Batería de Pruebas en Vivo (Terminal 3)

> *"Ahora, desde la Terminal 3, utilizaremos el `SingletonClient` para enviar peticiones puntuales y demostrar todos los casos de uso."*

---

### Caso 1: Consulta Puntual por Clave Primaria (`get`)
Ejecuta en la **Terminal 3**:
```powershell
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_get.json" -v
```

> **Qué señalar y decir:**  
> 1. Señala la **Terminal 3**: *"Enviamos la acción `get` consultando la sede `UADER-FCyT-IS2`. El servidor nos devuelve los datos completos con `status: ok`."*  
> 2. Señala la **Terminal 1 (Servidor)**: *"Fíjense en los logs del servidor: antes de resolver la lectura, se registró obligatoriamente la pista de auditoría en la tabla `CorporateLog` con la marca de tiempo UTC y la CPU del solicitante."*

---

### Caso 2: Modificación Parcial y Notificación en Cascada (`set`)
*(¡Este es el momento estrella de la demostración!)*

Ejecuta en la **Terminal 3**:
```powershell
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_set.json" -v
```

> **Qué señalar y decir:**  
> 1. Señala la **Terminal 3**: *"Enviamos una modificación parcial (`set`) actualizando únicamente el teléfono y la web. El Proxy fusiona estos campos preservando los anteriores mediante una actualización atómica en DynamoDB."*  
> 2. Señala inmediatamente la **Terminal 2 (Observador)**:  
>    **"¡Miren la Terminal 2! Sin hacer ninguna recarga ni polling, el `ObserverClient` acaba de recibir la notificación push en cascada en tiempo real con el registro actualizado."**

---

### Caso 3: Listado Completo con Paginación de DynamoDB (`list`)
Ejecuta en la **Terminal 3**:
```powershell
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_list.json" -v
```

> **Qué decir:**  
> *"Ejecutamos la acción `list`.  
> Aquí entra en acción el **patrón Iterator**: DynamoDB tiene un límite físico estricto de 1 MB por llamada a `scan`. Si la tabla supera ese límite, la respuesta se corta.  
> Nuestro `RecordIterator` recorre la tabla página por página siguiendo `LastEvaluatedKey` de forma perezosa (`lazy evaluation`), trayendo todos los registros sin saturar la memoria RAM del servidor."*

---

### Caso 4: Control de Integridad y Validación del Proxy (`set` inválido)
Ejecuta en la **Terminal 3**:
```powershell
python -m tpfi.singletonclient -s 127.0.0.1 -p 8080 -i "samples/input_invalido.json" -v
```

> **Qué señalar y decir:**  
> *"Enviamos un requerimiento malicioso o corrupto donde el cliente intenta modificar el atributo reservado `id` (clave primaria).  
> Observen la respuesta: **el Proxy interceptó el intento y lo rechazó con `status: error`**.  
> La petición ni siquiera llegó a tocar la base de datos física, protegiendo la integridad estructural de la tabla."*

---

## 4. Cierre y Verificación Automatizada (1 minuto)

> *"Para finalizar, demostramos que el proyecto no solo funciona en vivo, sino que cumple con los estándares más rigurosos de ingeniería de software."*

Abre una cuarta pestaña o ejecuta en la **Terminal 3**:

```powershell
pytest
```

> **Qué decir:**  
> *"El proyecto cuenta con **195 pruebas automatizadas**, incluyendo:  
> - Pruebas unitarias con mocks para aislar la red y AWS.  
> - La **suite formal de pruebas de aceptación** (`test_acceptance.py`) con los 5 escenarios exigidos por la cátedra (camino feliz, parámetros malformados, falta de datos mínimos, servidor caído y rechazo de doble bind).  
> - Pruebas basadas en propiedades con **Hypothesis** (`test_hypothesis.py`) sometiendo al protocolo a fuzzing.  
> Alcanzamos una cobertura total del **95.03%**, superando ampliamente el 85% solicitado."*

Por último, ejecuta:
```powershell
ruff check . ; black --check .
```

> **Qué decir:**  
> *"El código cumple al 100% con los linters de calidad de código de la industria (Ruff, Black y tipado estricto con Mypy)."*

---

## 5. Respuestas Rápidas por si el Profesor Pregunta:

- **¿Por qué `session_id` lo crea el servidor y no el cliente?**  
  *Respuesta:* "Por seguridad y no repudio. Si el cliente lo eligiera, podría sobrescribir auditorías anteriores o falsear identidades en `CorporateLog`."
- **¿Qué pasa si se cae el observador?**  
  *Respuesta:* "El servidor detecta el socket roto, hace una poda automática (`unsubscribe`) para no dejar sockets zombis, y el cliente tiene un bucle que reintenta reconectarse cada 30 segundos."
- **¿Por qué usan delimitador `\n` en los sockets?**  
  *Respuesta:* "Porque TCP es un flujo continuo de bytes (stream). Sin encuadre por delimitador, los mensajes podrían mezclarse o llegar fragmentados. `JsonSocket` bufferiza y entrega mensajes JSON completos."
- **¿Qué pasa si falla Internet en el aula?**  
  *Respuesta:* "Tenemos preparado el script `python demo_runner.py` que emula el ciclo completo contra repositorios en memoria (offline)."

