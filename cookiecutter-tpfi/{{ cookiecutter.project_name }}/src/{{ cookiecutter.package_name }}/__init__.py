"""{{ cookiecutter.project_name }}.

Trabajo Practico Final Integrador de Ingenieria de Software II (UADER-FCyT).

Implementa los patrones Proxy, Singleton y Observer sobre DynamoDB en AWS,
con un servidor de aplicaciones TCP y dos clientes.
"""

from __future__ import annotations

import pathlib

__version__ = "{{ cookiecutter.version }}"

_BUILD_FILE = pathlib.Path(__file__).resolve().parents[2] / "BUILD"


def get_build() -> str:
    """Devuelve el numero de build registrado en el archivo ``BUILD``.

    Returns:
        El contenido de ``BUILD`` sin espacios, o ``"0"`` si no existe.
    """
    try:
        return _BUILD_FILE.read_text(encoding="utf-8").strip() or "0"
    except OSError:
        return "0"


__build__ = get_build()

__all__ = ["__build__", "__version__", "get_build"]
