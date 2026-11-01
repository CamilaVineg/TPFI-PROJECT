"""{{ cookiecutter.project_name }}.

Trabajo Practico Final Integrador de Ingenieria de Software II (UADER-FCyT).

Implementa los patrones Proxy, Singleton y Observer sobre DynamoDB en AWS,
con un servidor de aplicaciones TCP y dos clientes.
"""

from __future__ import annotations

import pathlib

__version__ = "{{ cookiecutter.version }}"

_PACKAGE_DIR = pathlib.Path(__file__).resolve().parent
_PACKAGE_BUILD_FILE = _PACKAGE_DIR / "BUILD"
_PROJECT_BUILD_FILE = _PACKAGE_DIR.parents[1] / "BUILD"


def get_build() -> str:
    """Devuelve el numero de build registrado en el archivo ``BUILD``.

    Se busca primero dentro del paquete, donde lo instala el wheel mediante
    ``force-include``, y luego en la raiz del proyecto para el caso de una
    ejecucion desde el arbol de trabajo.

    Returns:
        El contenido de ``BUILD`` sin espacios, o ``"0"`` si no existe.
    """
    for candidate in (_PACKAGE_BUILD_FILE, _PROJECT_BUILD_FILE):
        try:
            return candidate.read_text(encoding="utf-8").strip() or "0"
        except OSError:
            continue
    return "0"


__build__ = get_build()

__all__ = ["__build__", "__version__", "get_build"]
