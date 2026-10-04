"""Constantes y configuracion del proyecto.

Centraliza los nombres de tablas, el puerto por defecto y la region de AWS
utilizados tanto por el servidor como por los clientes.
"""

from __future__ import annotations

import os

import boto3

AWS_REGION = "us-west-2"
CORPORATE_TABLE = "CorporateData"
LOG_TABLE = "CorporateLog"
DEFAULT_PORT = 8080
DEFAULT_HOST = "localhost"

RETRY_INTERVAL = 30

CORPORATE_FIELDS = (
    "id",
    "cp",
    "CUIT",
    "domicilio",
    "idreq",
    "idSeq",
    "localidad",
    "provincia",
    "sede",
    "seqID",
    "telefono",
    "web",
)


def get_region() -> str:
    """Devuelve la region de AWS efectiva.

    La resolucion sigue el orden de precedencia que aplica boto3: primero la
    variable de entorno ``AWS_DEFAULT_REGION``, luego la region configurada
    con ``aws configure`` y, como ultimo recurso, el valor por defecto de la
    plantilla.

    Delegar en ``boto3.Session`` es importante porque las tablas de la catedra
    pueden no estar en la region del valor por defecto, y pasar una region
    equivocada a ``boto3.resource`` produce ``ResourceNotFoundException``.

    Returns:
        El nombre de la region.
    """
    from_env = os.environ.get("AWS_DEFAULT_REGION")
    if from_env:
        return from_env

    from_session = boto3.Session().region_name
    return from_session or AWS_REGION


def positive_int(value: str) -> int:
    """Convierte ``value`` en un entero estrictamente positivo.

    Se usa como ``type`` de los argumentos numericos de argparse para que un
    valor invalido provoque un error de argumentos en lugar de propagarse a la
    capa de red.

    Args:
        value: Cadena con el valor numérico.

    Returns:
        El valor convertido a ``int``.

    Raises:
        argparse.ArgumentTypeError: Si el valor no es un entero positivo.
    """
    import argparse

    try:
        number = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"'{value}' no es un numero entero valido") from err
    if number <= 0:
        raise argparse.ArgumentTypeError(f"'{value}' debe ser mayor que cero")
    return number


def tcp_port(value: str) -> int:
    """Convierte ``value`` en un puerto TCP valido.

    Args:
        value: Cadena con el numero de puerto.

    Returns:
        El puerto convertido a ``int``.

    Raises:
        argparse.ArgumentTypeError: Si el puerto esta fuera del rango 1-65535.
    """
    import argparse

    try:
        port = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"'{value}' no es un numero de puerto valido") from err
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"'{value}' esta fuera del rango de puertos TCP")
    return port
