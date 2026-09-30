# {{ cookiecutter.project_name }}

Trabajo Practico Final Integrador de Ingenieria de Software II (UADER-FCyT).

Implementa los patrones **Proxy**, **Singleton** y **Observer** sobre una base
DynamoDB en AWS, con un servidor de aplicaciones TCP y dos clientes.

## Componentes

| Programa | Modulo | Descripcion |
| --- | --- | --- |
| `{{ cookiecutter.app_name }}` | `{{ cookiecutter.package_name }}.server` | Servidor TCP: Proxy + Singleton + Observer + auditoria. |
| `{{ cookiecutter.client_name }}` | `{{ cookiecutter.package_name }}.singleton_client` | Cliente que consulta o modifica `{{ cookiecutter.corporate_table }}`. |
| `{{ cookiecutter.observer_name }}` | `{{ cookiecutter.package_name }}.observer_client` | Cliente suscripto que recibe notificaciones de cambios. |

## Patrones

| Patron | Ubicacion | Aplicacion |
| --- | --- | --- |
| Singleton | `{{ cookiecutter.package_name }}.patterns.singleton` | Acceso fisico unico a las tablas DynamoDB. |
| Proxy | `{{ cookiecutter.package_name }}.patterns.proxy` | Intercepcion y validacion de las actualizaciones. |
| Observer | `{{ cookiecutter.package_name }}.patterns.observer` | Gestion de suscripciones y notificacion de cambios. |

## Requisitos

- Python 3.10 o superior
- AWS CLI v2 configurado (`aws configure`) en la region `{{ cookiecutter.aws_region }}`
- Tablas `{{ cookiecutter.corporate_table }}` y `{{ cookiecutter.log_table }}` ya creadas

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
{{ cookiecutter.app_name }} -p={{ cookiecutter.default_port }} -v
{{ cookiecutter.client_name }} -i=input.json -o=output.json -v
{{ cookiecutter.observer_name }} -s=localhost -p={{ cookiecutter.default_port }} -v
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
pdoc -o docs src/{{ cookiecutter.package_name }}
```

## Estructura

```
{{ cookiecutter.project_name }}/
|-- src/{{ cookiecutter.package_name }}/    Codigo fuente
|-- tests/                                 Pruebas unitarias y de aceptacion
|-- docs/                                  Documentacion generada con pdoc
|-- VERSION, BUILD                         Registro de version y build
|-- REQUIREMENTS.TXT                       Dependencias de ejecucion
|-- REQUIREMENTS-DEV.TXT                   Dependencias de desarrollo
`-- CHANGELOG.md, CONTEXT.md               Historial de cambios y prompts de IA
```

## Licencia

{{ cookiecutter.license }}. Ver [LICENSE](LICENSE).
