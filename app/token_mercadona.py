"""Guarda y comprueba el token de tu sesion de Mercadona.

QUE ES UN TOKEN
---------------
Cuando entras en tienda.mercadona.es con tu usuario y contrasena, su servidor
te devuelve un codigo largo (empieza por "eyJ..."). A partir de ahi tu
navegador ya no manda nunca mas la contrasena: manda ese codigo en cada
peticion y el servidor sabe que eres tu. Es como la pulsera que te ponen al
entrar a un recinto.

DONDE SE GUARDA
---------------
En datos/token_mercadona.json, en tu ordenador y en ningun sitio mas. Esa
carpeta ya esta en .gitignore por la regla /datos/, asi que no puede subirse a
GitHub ni por accidente. En tu otro ordenador tendras que volver a pegarlo.

Guia completa para sacarlo: docs/08-completar-la-compra.md
"""

import base64
import json
import time
from dataclasses import dataclass

from app import config

ARCHIVO = config.DIR_DATOS_GENERADOS / "token_mercadona.json"


@dataclass
class EstadoToken:
    """Que sabemos del token guardado."""

    hay_token: bool
    valido: bool
    mensaje: str
    id_cliente: str | None = None
    caduca_en: str | None = None
    dias_restantes: int | None = None


def guardar(token: str) -> EstadoToken:
    """Guarda el token, quitandole la basura de alrededor si la trae."""
    token = _limpiar(token)
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO, "w", encoding="utf-8") as archivo:
        json.dump({"token": token}, archivo, indent=2)
    return estado()


def borrar() -> None:
    """Olvida el token guardado."""
    if ARCHIVO.exists():
        ARCHIVO.unlink()


def leer() -> str | None:
    """Devuelve el token guardado, o None si no hay."""
    if not ARCHIVO.exists():
        return None
    try:
        with open(ARCHIVO, "r", encoding="utf-8") as archivo:
            return json.load(archivo).get("token") or None
    except (OSError, json.JSONDecodeError):
        return None


def estado() -> EstadoToken:
    """Comprueba si hay token y si sigue sirviendo."""
    token = leer()
    if not token:
        return EstadoToken(False, False, "No has guardado ningun token todavia.")

    datos = _contenido(token)
    if datos is None:
        return EstadoToken(
            True, False,
            "El texto guardado no parece un token valido. Vuelve a copiarlo del navegador.",
        )

    id_cliente = _buscar_id_cliente(datos)
    caducidad = datos.get("exp")

    if caducidad:
        segundos = caducidad - time.time()
        if segundos <= 0:
            return EstadoToken(
                True, False,
                "El token ha caducado. Vuelve a copiarlo del navegador (son dos minutos).",
                id_cliente,
            )
        dias = int(segundos // 86400)
        fecha = time.strftime("%d/%m/%Y", time.localtime(caducidad))
        return EstadoToken(
            True, True,
            f"Token valido. Caduca el {fecha}.",
            id_cliente, fecha, dias,
        )

    return EstadoToken(True, True, "Token guardado (sin fecha de caducidad).", id_cliente)


def id_cliente() -> str | None:
    """El identificador de cliente que va dentro del token."""
    token = leer()
    if not token:
        return None
    datos = _contenido(token)
    return _buscar_id_cliente(datos) if datos else None


# ---------------------------------------------------------------------------
# LEER LO QUE LLEVA DENTRO EL TOKEN
# ---------------------------------------------------------------------------


def _contenido(token: str) -> dict | None:
    """Saca el JSON que lleva dentro un token JWT.

    Un JWT son tres trozos separados por puntos:

        cabecera . contenido . firma

    Los dos primeros son un JSON codificado en base64, o sea que se pueden
    leer sin ninguna clave: base64 NO es cifrado, solo es una forma de escribir
    datos con letras y numeros. Lo que protege el token es la FIRMA, que impide
    fabricar uno falso, pero no impide leerlo.

    Nos interesa para dos cosas: sacar tu identificador de cliente (asi no hay
    que pedirtelo aparte) y saber cuando caduca (para poder avisarte antes de
    que falle).
    """
    partes = token.split(".")
    if len(partes) < 2:
        return None
    try:
        # base64url usa "-" y "_" donde el base64 normal usa "+" y "/".
        contenido = partes[1].replace("-", "+").replace("_", "/")
        # Y le quita el relleno de "=" del final, asi que hay que reponerlo:
        # base64 trabaja en bloques de 4 caracteres.
        contenido += "=" * (-len(contenido) % 4)
        return json.loads(base64.b64decode(contenido))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _buscar_id_cliente(datos: dict) -> str | None:
    """Busca el identificador de cliente entre los campos del token.

    Se prueban varios nombres porque no sabemos cual usa Mercadona exactamente
    y es el tipo de detalle que puede cambiar. Si ninguno aparece, el modulo
    del carrito lo pedira al servidor por otra via.
    """
    for clave in ("customer_id", "customer", "user_id", "uid", "sub", "id"):
        valor = datos.get(clave)
        if valor:
            return str(valor)
    return None


def _limpiar(texto: str) -> str:
    """Quita lo que suele venir pegado al copiar del navegador.

    Segun de donde lo copies te traes "Authorization: Bearer eyJ...", o solo
    "Bearer eyJ...", o comillas alrededor. Todo eso sobra, y es mucho mejor
    quitarlo aqui que hacerte a ti pelearte con ello.
    """
    texto = texto.strip().strip('"').strip("'")
    for prefijo in ("authorization:", "Authorization:"):
        if texto.lower().startswith(prefijo.lower()):
            texto = texto[len(prefijo):].strip()
    if texto.lower().startswith("bearer "):
        texto = texto[7:].strip()
    return texto.strip().strip('"').strip("'")
