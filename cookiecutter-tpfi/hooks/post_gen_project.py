"""Hooks de Cookiecutter ejecutados tras generar el proyecto.

Se generan los archivos derivados de las variables del formulario para evitar
que el usuario los edite a mano y se desincronicen con la plantilla.

El script se renderiza como plantilla Jinja, por lo que las variables de
``cookiecutter`` ya estan disponibles al ejecutarse.
"""

from __future__ import annotations

import pathlib

PROJECT_DIR = pathlib.Path.cwd()

VERSION = "{{ cookiecutter.version }}"
BUILD = "{{ cookiecutter.build_number }}"

RUNTIME_DEPS = ["boto3>=1.34.0"]

DEV_DEPS = [
    "ruff>=0.6.0",
    "black>=24.8.0",
    "mypy>=1.11.0",
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "hypothesis>=6.113.0",
    "bandit>=1.7.9",
    "pdoc>=14.6.0",
]


def write_list(filename: str, title: str, deps: list[str]) -> None:
    """Escribe un archivo de requirements con cabecera y dependencias.

    Args:
        filename: Nombre del archivo a generar.
        title: Comentario que encabeza el archivo.
        deps: Dependencias a listar.
    """
    lines = ["# Generado por cookiecutter-tpfi", f"# {title}", ""]
    lines.extend(deps)
    lines.append("")
    (PROJECT_DIR / filename).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Genera VERSION, BUILD y los archivos de dependencias."""
    (PROJECT_DIR / "VERSION").write_text(f"{VERSION}\n", encoding="utf-8")
    (PROJECT_DIR / "BUILD").write_text(f"{BUILD}\n", encoding="utf-8")

    write_list("REQUIREMENTS.TXT", "Dependencias de ejecucion", RUNTIME_DEPS)
    write_list(
        "REQUIREMENTS-DEV.TXT",
        "Herramientas de desarrollo, linting, testing y documentacion",
        DEV_DEPS,
    )


if __name__ == "__main__":
    main()
