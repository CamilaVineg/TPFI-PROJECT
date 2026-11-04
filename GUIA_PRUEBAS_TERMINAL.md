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

### Terminal 2 - ObserverClient

```powershell
observerclient -s localhost -p 8080 -o salida_observer.json -v

```

### Terminal 3 - SingletonClient

## 2. Archivos de entrada y camino feliz

### 2.1 `get` de un registro existente

```powershell
singletonclient -i samples/input_get.json -v
```

### 2.2 `set` del registro de prueba

```powershell
singletonclient -i samples/input_set.json -v
```

### 2.3 `list` de toda la tabla

```powershell
singletonclient -i samples/input_list.json -v
```

### 2.4 `subscribe`

Se prueba con la Terminal 2: al arrancar `observerclient`, el servidor registra
la suscripción y responde `{"subscribed": true}`. Al hacer el `set` del punto
2.2, el observer recibe la notificación en cascada.

Para detenerlo, `Ctrl+C`: el observer corta la escucha en menos de un segundo,
aunque el servidor siga activo. No hace falta bajar el servidor ni cerrar la
terminal.

---

## 3. Casos de Validación y Verificación de la consigna

### 3.1 Argumentos malformados en cada programa

```powershell
# Servidor: puerto no numérico. Debe salir con código 2.
singletonproxyobserver -p NO_ES_PUERTO

#levantar el servidor de nuevo
singletonproxyobserver -p 8080 -v

# Cliente: falta el archivo de entrada obligatorio. Debe salir con código 2.
singletonclient

# Observer: intervalo de reintento inválido. Debe salir con código 2.
observerclient --retry-interval 0
```
Resultado esperado: `argparse` muestra el error y el proceso termina con `exit=2`.

> **Aclaración importante:** "argumentos malformados" se refiere a cómo se
> invoca el programa desde la terminal, no al contenido del JSON. El mensaje
> `the following arguments are required: -i/--input` que muestra
> `singletonclient` es exactamente el caso esperado: falta el argumento
> obligatorio `-i` y `argparse` corta antes de leer ningún archivo.

### 3.2 Requerimiento sin datos mínimos

```powershell
# get sin ID
singletonclient -i samples/input_get_sin_id.json -v

# set sin ID ni datos
singletonclient -i samples/input_set_sin_datos.json -v

# set con ID pero sin ningún campo para modificar
singletonclient -i samples/input_set_sin_campos.json -v
```

### 3.3 Intento de modificar un campo reservado

```powershell
singletonclient -i samples/input_invalido.json -v
```

### 3.4 Cliente con el servidor caído

```powershell
singletonclient -i samples/input_get.json -v
```

### 3.5 Intento de levantar dos veces el servidor

```powershell
singletonproxyobserver -p 8080 -v
```

## 4. Verificar el impacto en las tablas

### 4.1 CorporateData

```powershell
aws dynamodb get-item `
  --table-name CorporateData `
  --region us-east-1 `
  --key '{\"id\":{\"S\":\"TPFI-DEMO-2026\"}}'
```
### 4.2 CorporateLog

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

## 5. Testeos 

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

También existe una demostración offline, sin AWS:

```powershell
python demo_runner.py
```
