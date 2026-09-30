# Changelog

Todas las novedades de `{{ cookiecutter.project_name }}` se registran en este
archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/) y el proyecto
adhiere a [Semantic Versioning](https://semver.org/).

## [No publicado]

## [{{ cookiecutter.version }}] - Build {{ cookiecutter.build_number }}

### Agregado

- Esqueleto del proyecto generado con Cookiecutter a partir de `cookiecutter-tpfi/`.
- Configuracion de `ruff`, `black`, `mypy`, `pyright`, `pytest` y `bandit` en `pyproject.toml`.
- Patron **Singleton** (`patterns/singleton.py`) con metaclase y decorador.
- Patron **Observer** (`patterns/observer.py`) con gestion de estados y suscripciones.
- Interfaz del patron **Proxy** (`patterns/proxy.py`).
- Constantes de tablas, region y puerto en `config.py`.
- Puntos de entrada `server.py`, `singleton_client.py` y `observer_client.py`.
- Archivos `VERSION`, `BUILD`, `REQUIREMENTS.TXT` y `REQUIREMENTS-DEV.TXT` generados por el hook.
