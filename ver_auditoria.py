"""Muestra las últimas entradas de la tabla de auditoría ``CorporateLog``.

Se usa durante la defensa para verificar que cada acción realizada por los
clientes quedó registrada con su sesión, UUID de CPU y timestamp.
"""

from __future__ import annotations

import argparse

import boto3

from tpfi.config import LOG_TABLE, get_region


def parse_args() -> argparse.Namespace:
    """Interpreta los argumentos de línea de comandos.

    Returns:
        El namespace con la cantidad de entradas a mostrar.
    """
    parser = argparse.ArgumentParser(
        prog="ver_auditoria",
        description="Muestra las últimas entradas de CorporateLog.",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="Cantidad de entradas a mostrar (por defecto: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    """Imprime las últimas entradas de auditoría ordenadas por timestamp.

    Returns:
        ``0`` si la consulta se realizó correctamente.
    """
    args = parse_args()
    table = boto3.resource("dynamodb", region_name=get_region()).Table(LOG_TABLE)
    items = [item for item in table.scan().get("Items", []) if "action" in item]
    ordered = sorted(items, key=lambda item: str(item.get("timestamp", "")), reverse=True)

    print(f"{'ACCION':<18} {'CLAVE':<22} {'SESION':<38} {'CLIENTE':<18} TIMESTAMP")
    print("-" * 130)
    for item in ordered[: args.limit]:
        print(
            f"{str(item.get('action', '-')):<18} "
            f"{str(item.get('key', '-')):<22} "
            f"{str(item.get('session_id', '-')):<38} "
            f"{str(item.get('client_uuid', '-')):<18} "
            f"{item.get('timestamp', '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
