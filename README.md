# TPFI-PROJECT

Trabajo Practico Final Integrador de Ingenieria de Software II (UADER-FCyT).

Implementa los patrones **Proxy**, **Singleton** y **Observer** sobre una base
DynamoDB en AWS, con un servidor de aplicaciones TCP y dos clientes.

## Componentes

| Programa | Modulo | Descripcion |
| --- | --- | --- |
| `singletonproxyobserver` | `tpfi.server` | Servidor TCP: Proxy + Singleton + Observer + auditoria. |
| `singletonclient` | `tpfi.singleton_client` | Cliente que consulta o modifica `CorporateData`. |
| `observerclient` | `tpfi.observer_client` | Cliente suscripto que recibe notificaciones de cambios. |

## Patrones

| Patron | Ubicacion | Aplicacion |
| --- | --- | --- |
| Singleton | `tpfi.patterns.singleton` | Acceso fisico unico a las tablas DynamoDB. |
| Proxy | `tpfi.patterns.proxy` | Intercepcion y validacion de las actualizaciones. |
| Observer | `tpfi.patterns.observer` | Gestion de suscripciones y notificacion de cambios. |

## Requisitos

- Python 3.10 o superior
- AWS CLI v2 configurado (`aws configure`) en la region `us-west-2`
- Tablas `CorporateData` y `CorporateLog` ya creadas

## Instalacion

Este proyecto fue generado con Cookiecutter a partir de la plantilla
`cookiecutter-tpfi/`.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Uso

```bash
singletonproxyobserver -p=8080 -v
singletonclient -i=input.json -o=output.json -v
observerclient -s=localhost -p=8080 -v
```

## Calidad

```bash
ruff check .
black --check .
mypy
pyright
pytest
bandit -r src
```

## Documentacion

```bash
pdoc -o docs src/tpfi
```

## Estructura

```
TPFI-PROJECT/
|-- src/tpfi/    Codigo fuente
|-- tests/                                 Pruebas unitarias y de aceptacion
|-- docs/                                  Documentacion generada con pdoc
|-- VERSION, BUILD                         Registro de version y build
|-- REQUIREMENTS.TXT                       Dependencias de ejecucion
|-- REQUIREMENTS-DEV.TXT                   Dependencias de desarrollo
`-- CHANGELOG.md, CONTEXT.md               Historial de cambios y prompts de IA
```

## Licencia

MIT. Ver [LICENSE](LICENSE).
