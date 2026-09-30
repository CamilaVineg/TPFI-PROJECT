# CONTEXT.md

Registro de los prompts utilizados durante el desarrollo de
`{{ cookiecutter.project_name }}` con asistencia de IA, conforme lo exige la
consigna del TPFI.

## Convenciones

- Fecha en formato `AAAA-MM-DD`.
- Se registra el objetivo del prompt, no la conversacion completa.
- Solo se documentan los prompts que generaron codigo del proyecto.

## Sesiones

### {{ "2026-09-30" }} - Estructura inicial

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
