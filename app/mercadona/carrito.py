"""Mete productos en tu carrito de la tienda online de Mercadona.

ESTE ES EL UNICO ARCHIVO DEL PROYECTO QUE ESCRIBE EN MERCADONA.
Su hermano cliente.py es el unico que lee. Estan separados a proposito: leer
un catalogo publico y tocar la cuenta de alguien son dos cosas de riesgo muy
distinto, y conviene que se vea de un vistazo donde pasa cada una.

QUE HACE Y QUE NO HACE
----------------------
LLENA el carrito. NO compra nada, no hace ningun pedido y no paga.
Despues abres tienda.mercadona.es, revisas la cesta, cambias lo que quieras y
compras tu a mano.

POR QUE HACE FALTA UN TOKEN
---------------------------
Lo comprobe antes de escribir esto: el catalogo se puede leer sin
identificarse, pero el carrito no. GET /api/customers/<id>/cart/ devuelve 401
sin token, y hasta OPTIONS lo devuelve. No hay carrito anonimo. Asi que la
unica forma es usar TU sesion, y por eso hay que pegar el token.

EL TROZO QUE HAY QUE AJUSTAR
----------------------------
La forma exacta de la peticion que ANADE lineas al carrito no esta documentada
en ningun sitio publico, y no se puede averiguar sin una sesion iniciada.
Lo que si sabemos es que va contra /api/customers/<id>/cart/ y que necesita el
Bearer.

Asi que aqui va la forma mas probable, y si no funciona el error te dice
exactamente lo que respondio el servidor. Con eso y la captura de tu navegador
(la misma con la que sacas el token: F12 -> Red -> anadir un producto a mano)
se ajusta FORMATOS_PETICION y listo. Esta preparado para que sea cambiar una
lista, no reescribir el archivo.

Y pase lo que pase, la web nunca se queda colgada: si esto falla, te ensena la
lista con todos los productos enlazados para que los anadas tu.
"""

import requests

from app import config

URL_BASE = "https://tienda.mercadona.es/api"

CABECERAS_BASE = {
    "User-Agent": "mercadona-dieta-app/2.0 (proyecto personal)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Las formas de mandar las lineas que vamos a probar, en orden. En cuanto una
# funcione, se usa esa. Tener varias no es indecision: es que el coste de
# probar es cero y el de equivocarse es que no funcione nada.
#
# Cada entrada dice: (metodo HTTP, como se llama la lista, como se llama el id).
FORMATOS_PETICION = [
    ("PUT", "lines", "product_id"),
    ("PUT", "lines", "id"),
    ("POST", "lines", "product_id"),
    ("PUT", "products", "product_id"),
]


class ErrorCarrito(Exception):
    """Algo ha ido mal al hablar con el carrito. El mensaje explica el que."""


def anadir(token: str, id_cliente: str | None, lineas: list[dict]) -> dict:
    """Anade productos al carrito. Devuelve un resumen de lo que ha pasado.

    lineas: [{"id": "4241", "unidades": 2, "nombre": "..."}]

    Devuelve {"anadidos": n, "formato": "...", "carrito": {...}}
    """
    if not lineas:
        raise ErrorCarrito("No hay productos que anadir.")

    sesion = requests.Session()
    sesion.headers.update(CABECERAS_BASE)
    sesion.headers["Authorization"] = f"Bearer {token}"

    if not id_cliente:
        id_cliente = _averiguar_id_cliente(sesion)

    # Primero se lee el carrito. Sirve para dos cosas: comprobar que el token
    # vale ANTES de intentar escribir nada, y saber qué hay ya dentro para no
    # duplicarlo.
    carrito = _leer(sesion, id_cliente)

    cantidades = {str(linea["id"]): int(linea["unidades"]) for linea in lineas}
    for existente in carrito.get("lines", []) or []:
        id_producto = str(existente.get("product_id") or existente.get("id") or "")
        if id_producto in cantidades:
            # Ya estaba en el carrito: nos quedamos con la cantidad mayor en
            # vez de sumar. Si generas el plan dos veces y pulsas el botón dos
            # veces, no quieres acabar con el doble de pollo.
            cantidades[id_producto] = max(cantidades[id_producto], int(existente.get("quantity", 0)))

    ultimo_error = None
    for metodo, campo_lista, campo_id in FORMATOS_PETICION:
        cuerpo = {
            campo_lista: [
                {campo_id: id_producto, "quantity": unidades}
                for id_producto, unidades in cantidades.items()
            ]
        }
        try:
            respuesta = sesion.request(
                metodo,
                f"{URL_BASE}/customers/{id_cliente}/cart/",
                json=cuerpo,
                timeout=config.TIMEOUT_SEGUNDOS,
            )
        except requests.RequestException as error:
            ultimo_error = f"No se pudo conectar con Mercadona: {error}"
            continue

        if respuesta.status_code in (200, 201, 202, 204):
            return {
                "anadidos": len(cantidades),
                "formato": f"{metodo} {campo_lista}/{campo_id}",
                "carrito": _json_o_vacio(respuesta),
            }

        if respuesta.status_code == 401:
            raise ErrorCarrito(
                "Mercadona ha rechazado el token (401). Lo mas probable es que haya "
                "caducado: vuelve a copiarlo del navegador."
            )

        ultimo_error = (
            f"{metodo} respondio {respuesta.status_code}: {respuesta.text[:300]}"
        )

    raise ErrorCarrito(
        "Ninguna de las formas conocidas de anadir al carrito ha funcionado.\n\n"
        f"Ultima respuesta del servidor:\n{ultimo_error}\n\n"
        "Esto significa que Mercadona espera la peticion de otra manera. Mira "
        "docs/08-completar-la-compra.md, apartado 'Si no funciona': se arregla "
        "anadiendo una linea a FORMATOS_PETICION en app/mercadona/carrito.py."
    )


def comprobar_token(token: str) -> tuple[bool, str]:
    """Prueba el token contra Mercadona de verdad. Devuelve (vale, mensaje).

    Comprobar la fecha de caducidad que lleva dentro el token no basta: puede
    haber sido revocado, o ser de otra cosa. La unica forma de saber si sirve
    es usarlo.
    """
    sesion = requests.Session()
    sesion.headers.update(CABECERAS_BASE)
    sesion.headers["Authorization"] = f"Bearer {token}"

    try:
        id_cliente = _averiguar_id_cliente(sesion)
        _leer(sesion, id_cliente)
        return True, "El token funciona: Mercadona te ha reconocido."
    except ErrorCarrito as error:
        return False, str(error)


# ---------------------------------------------------------------------------
# LO DE DENTRO
# ---------------------------------------------------------------------------


def _averiguar_id_cliente(sesion: requests.Session) -> str:
    """Pregunta a Mercadona quien eres, si no lo sacamos del token."""
    from app import token_mercadona

    guardado = token_mercadona.id_cliente()
    if guardado:
        return guardado

    try:
        respuesta = sesion.get(f"{URL_BASE}/customers/", timeout=config.TIMEOUT_SEGUNDOS)
        if respuesta.status_code == 401:
            raise ErrorCarrito(
                "Mercadona ha rechazado el token (401). Puede que haya caducado o "
                "que se haya copiado mal. Vuelve a sacarlo del navegador."
            )
        datos = _json_o_vacio(respuesta)
        for clave in ("id", "customer_id", "uuid"):
            if datos.get(clave):
                return str(datos[clave])
    except requests.RequestException as error:
        raise ErrorCarrito(f"No se pudo conectar con Mercadona: {error}") from error

    raise ErrorCarrito(
        "No he podido averiguar tu identificador de cliente a partir del token. "
        "Mira docs/08-completar-la-compra.md."
    )


def _leer(sesion: requests.Session, id_cliente: str) -> dict:
    """Lee el carrito actual."""
    try:
        respuesta = sesion.get(
            f"{URL_BASE}/customers/{id_cliente}/cart/", timeout=config.TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as error:
        raise ErrorCarrito(f"No se pudo conectar con Mercadona: {error}") from error

    if respuesta.status_code == 401:
        raise ErrorCarrito(
            "Mercadona ha rechazado el token (401). Lo mas probable es que haya "
            "caducado: vuelve a copiarlo del navegador."
        )
    if respuesta.status_code == 404:
        # Carrito vacío o todavía sin crear: no es un error.
        return {}
    if respuesta.status_code >= 400:
        raise ErrorCarrito(
            f"Mercadona respondio {respuesta.status_code} al leer el carrito: "
            f"{respuesta.text[:300]}"
        )

    return _json_o_vacio(respuesta)


def _json_o_vacio(respuesta: requests.Response) -> dict:
    """Convierte la respuesta a diccionario sin reventar si no es JSON."""
    try:
        datos = respuesta.json()
        return datos if isinstance(datos, dict) else {}
    except ValueError:
        return {}
