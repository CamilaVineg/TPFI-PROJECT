# Guía de prueba manual por terminal

Esta guía sigue la sección **Validación y Verificación** de la consigna oficial
`docs/IS2_TPFI_FullStack Python Singleton.pdf` y prueba los tres programas:

- `singletonproxyobserver` (servidor)
- `singletonclient` (cliente de operaciones)
- `observerclient` (cliente suscripto)

Todos los comandos se ejecutan desde la raíz del proyecto:

```powershell
cd C:\Users\vineg\OneDrive\Escritorio\UADER_IS2_\TPFI\TPFI-PROJECT
.\.venv\Scripts\Activate.ps1
```

Verificar que AWS esté configurado y que las tablas existan:

```powershell
aws sts get-caller-identity
aws dynamodb describe-table --table-name CorporateData --region us-east-1 --query "Table.TableStatus"
aws dynamodb describe-table --table-name CorporateLog  --region us-east-1 --query "Table.TableStatus"
```

Ambas tablas deben responder `ACTIVE`.

> **Windows PowerShell 5.1:** escribí los argumentos separados por espacio
> (`-o salida_observer.json`). Si usás la forma con igual
> (`-o=salida_observer.json`), PowerShell 5.1 corta el argumento en el punto y
> el programa recibe `-o=salida_observer` y `.json`, por lo que `argparse`
> responde `unrecognized arguments: .json`. Si preferís el igual, entrecomillá
> todo el argumento: `"-o=salida_observer.json"`. En PowerShell 7, cmd y bash la
> forma con igual funciona sin problemas.

---

## 1. Abrir las tres terminales

### Terminal 1 - Servidor

```powershell
singletonproxyobserver -p 8080 -v
```

Resultado esperado:

```text
Iniciando singletonproxyobserver en el puerto 8080
Repositorio de datos inicializado sobre CorporateData
Repositorio de auditoria inicializado sobre CorporateLog
Servidor listo y escuchando en el puerto 8080
```

Dejar esta terminal abierta. Es el proceso que escucha y atiende a los clientes.

### Terminal 2 - ObserverClient

```powershell
observerclient -s localhost -p 8080 -o salida_observer.json -v
```

Resultado esperado:

```text
Iniciando observerclient contra localhost:8080
Conectado a localhost:8080 como <UUID_DE_TU_CPU>
```

Dejar esta terminal abierta. Cada `set` que se haga desde la Terminal 3 debe
aparecer acá y, además, quedar acumulado en `salida_observer.json`.

### Terminal 3 - SingletonClient

Todos los comandos siguientes se ejecutan en esta terminal.

---

## 2. Camino feliz de cada acción

### 2.1 `get` de un registro existente

```powershell
singletonclient -i samples/input_get.json -v
```

Resultado esperado: `status: "ok"` y el registro `UADER-FCyT-IS2` con todos sus
campos.

### 2.2 `list` de toda la tabla

```powershell
singletonclient -i samples/input_list.json -v
```

Resultado esperado: `status: "ok"` y un arreglo con todos los registros de
`CorporateData`. Este comando ejercita el patrón Iterator y la paginación de
DynamoDB.

### 2.3 `set` de un registro de prueba

El archivo `samples/input_set_demo.json` usa el formato oficial de la consigna
(`UUID`, `ID`, `ACTION` en mayúsculas y los campos del tuple en la raíz):

```powershell
singletonclient -i samples/input_set_demo.json -v
```

Resultado esperado:

- En la Terminal 3: `status: "ok"` con los datos del registro `TPFI-DEMO-2026`.
- En la Terminal 2: una notificación `type: "notification"` con esos mismos datos.

### 2.4 `get` del registro recién creado

```powershell
singletonclient -i samples/input_get_demo.json -v
```

Resultado esperado: `status: "ok"` y los datos de `TPFI-DEMO-2026`.

### 2.5 `subscribe`

Se prueba con la Terminal 2: al arrancar `observerclient`, el servidor registra
la suscripción y responde `{"subscribed": true}`. Al hacer el `set` del punto
2.3, el observer recibe la notificación en cascada.

---

## 3. Casos de Validación y Verificación de la consigna

### 3.1 Argumentos malformados en cada programa

```powershell
# Servidor: puerto no numérico. Debe salir con código 2.
singletonproxyobserver -p NO_ES_PUERTO

# Cliente: falta el archivo de entrada obligatorio. Debe salir con código 2.
singletonclient

# Observer: intervalo de reintento inválido. Debe salir con código 2.
observerclient --retry-interval 0
```

Para ver el código de salida en PowerShell:

```powershell
Write-Host "exit=$LASTEXITCODE"
```

Resultado esperado: `argparse` muestra el error y el proceso termina con `exit=2`.

### 3.2 Requerimiento sin datos mínimos

```powershell
# get sin ID
singletonclient -i samples/input_get_sin_id.json -v

# set sin ID ni datos
singletonclient -i samples/input_set_sin_datos.json -v

# set con ID pero sin ningún campo para modificar
singletonclient -i samples/input_set_sin_campos.json -v
```

Resultados esperados:

- `El identificador del registro es obligatorio para get`
- `El identificador del registro es obligatorio para set`
- `No se informo ningun campo para modificar`

En los tres casos el cliente termina con `exit=1` y `status: "error"`.

### 3.3 Intento de modificar un campo reservado

```powershell
singletonclient -i samples/input_invalido.json -v
```

Resultado esperado:

```text
status: "error"
error: "No se admiten los campos reservados: id"
```

El Proxy rechaza el requerimiento antes de tocar DynamoDB.

### 3.4 Cliente con el servidor caído

Detener el servidor de la Terminal 1 con `Ctrl+C` y ejecutar:

```powershell
singletonclient -i samples/input_get.json -v
```

Resultado esperado: error de conexión y `exit=1`.

Para probar el reintento del observer, con el servidor detenido:

```powershell
observerclient -s localhost -p 8080 -r 2 -v
```

Resultado esperado: intenta conectarse, falla y reintenta cada 2 segundos. Se
detiene con `Ctrl+C`.

### 3.5 Intento de levantar dos veces el servidor

Con el servidor de la Terminal 1 todavía en ejecución, abrir otra terminal y
ejecutar:

```powershell
singletonproxyobserver -p 8080 -v
```

Resultado esperado en Windows:

```text
No se pudo iniciar el servidor en el puerto 8080: [WinError 10048] ...
```

Código de salida: `1`.

---

## 4. Verificar el impacto en las tablas

### 4.1 CorporateData

```powershell
aws dynamodb get-item `
  --table-name CorporateData `
  --region us-east-1 `
  --key '{\"id\":{\"S\":\"TPFI-DEMO-2026\"}}'
```

Debe devolver el registro creado por `samples/input_set_demo.json`.

### 4.2 CorporateLog

El proyecto incluye un verificador de auditoría:

```powershell
python ver_auditoria.py --limit 10
```

Muestra las últimas entradas de `CorporateLog` con acción, clave, sesión, UUID
del cliente y timestamp. Deben aparecer, como mínimo, las acciones
`subscribe`, `get`, `list` y `set` de las pruebas anteriores.

También se puede consultar directamente con AWS CLI:

```powershell
aws dynamodb scan --table-name CorporateLog --region us-east-1 --limit 5
```

---

## 5. Pruebas automatizadas

```powershell
# Suite completa (incluye cobertura)
pytest

# Solo los casos de aceptación de la consigna (sin el umbral global de cobertura)
pytest -m acceptance -v --no-cov

# Control de calidad
ruff check .
black --check .
mypy
bandit -r src
```

Resultado esperado: `196 passed` y cobertura superior al 85 %.

También existe una demostración offline, sin AWS:

```powershell
python demo_runner.py
```

---

## 6. Mapa entre la consigna y las pruebas

| Caso de Validación y Verificación | Dónde se prueba |
| --- | --- |
| Camino feliz de cada acción + CorporateLog | Puntos 2.1 a 2.5 y `pytest -m acceptance` |
| Argumentos malformados en cada programa | Punto 3.1 |
| Requerimiento sin datos mínimos | Punto 3.2 |
| Cliente con servidor caído | Punto 3.4 |
| Levantar dos veces el servidor | Punto 3.5 |
| Impacto en CorporateData y CorporateLog | Punto 4 y `ver_auditoria.py` |

---

## 7. Limpieza del registro de prueba

Si se quiere borrar el registro `TPFI-DEMO-2026` después de la demostración:

```powershell
aws dynamodb delete-item `
  --table-name CorporateData `
  --region us-east-1 `
  --key '{\"id\":{\"S\":\"TPFI-DEMO-2026\"}}'
```

Las entradas de `CorporateLog` no se borran: son la pista de auditoría de la
demostración.
