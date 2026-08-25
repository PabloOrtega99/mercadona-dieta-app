"""Habla con la API de Mercadona.

Este es el ÚNICO archivo del proyecto que se conecta a internet con Mercadona.
Eso es a propósito: la API no es oficial y puede cambiar sin avisar. Si un día
deja de funcionar, ya sabes dónde mirar: aquí y en ningún otro sitio.

Lo que hace: pedir los datos crudos a Mercadona y devolverlos ya limpios, en
el formato que le conviene al resto de nuestro programa. Al resto del proyecto
no le importa cómo llama Mercadona a sus campos.

Explicación completa de la API en docs/03-la-api-de-mercadona.md
"""

import time

import requests

from app import config

# La dirección base de la API. Todo lo demás se cuelga de aquí.
URL_BASE = "https://tienda.mercadona.es/api"

# Las cabeceras son información extra que acompaña a cada petición.
# El "User-Agent" dice quién eres. Se considera buena educación identificarse
# de forma honesta cuando usas una API que no es tuya, en vez de disfrazarte
# de navegador Chrome.
CABECERAS = {
    "User-Agent": "mercadona-dieta-app/1.0 (proyecto personal)",
    "Accept": "application/json",
}


class ErrorMercadona(Exception):
    """Nuestro propio tipo de error.

    Definir una excepción propia permite que quien use este archivo pueda
    escribir "except ErrorMercadona" y capturar solo los problemas al hablar
    con Mercadona, sin tragarse por accidente otros errores del programa.
    """


def _pedir(ruta: str) -> dict:
    """Hace una petición GET a la API y devuelve la respuesta ya convertida.

    El guion bajo del principio (_pedir) es una convención de Python que
    significa "esto es de uso interno de este archivo, no lo llames desde
    fuera". Python no lo impide, pero es una señal para quien lea el código.

    Reintenta si falla, porque los errores de red suelen ser pasajeros.
    """
    url = f"{URL_BASE}/{ruta}"
    # Los parámetros de la dirección: idioma y almacén.
    # requests los convierte en "?lang=es&wh=mad1" por nosotros.
    parametros = {"lang": "es", "wh": config.ALMACEN}

    ultimo_error = None
    for intento in range(1, config.REINTENTOS + 1):
        try:
            respuesta = requests.get(
                url,
                params=parametros,
                headers=CABECERAS,
                timeout=config.TIMEOUT_SEGUNDOS,
            )
            # raise_for_status() lanza un error si el servidor respondió con un
            # código de fallo (404 = no existe, 500 = se ha roto el servidor...).
            respuesta.raise_for_status()
            # .json() convierte el texto que llega (que es JSON) en
            # diccionarios y listas de Python, que es con lo que sabemos operar.
            return respuesta.json()

        except requests.RequestException as error:
            ultimo_error = error
            if intento < config.REINTENTOS:
                # Espera creciente: 1 s, luego 2 s, luego 3 s. Si el servidor
                # está saturado, insistir cada décima de segundo solo empeora
                # las cosas. Esto se llama "retroceso" (backoff).
                time.sleep(intento)

    raise ErrorMercadona(
        f"No se pudo obtener {url} despues de {config.REINTENTOS} intentos: {ultimo_error}"
    )


def obtener_arbol_categorias() -> list[dict]:
    """Devuelve las categorías del supermercado y sus subcategorías.

    Mercadona organiza los productos en dos niveles, igual que los pasillos
    de la tienda física:

        Aceite, especias y salsas   <- categoria (nivel 1), 26 en total
          |- Aceite, vinagre y sal  <- subcategoria (nivel 2), 151 en total
          |- Especias
          |- ...

    Los productos cuelgan de las subcategorías, así que necesitamos esta lista
    para saber a qué 151 puertas hay que llamar.

    Devuelve algo así:
        [{"id": 12, "nombre": "Aceite, especias y salsas",
          "subcategorias": [{"id": 112, "nombre": "Aceite, vinagre y sal"}, ...]}]
    """
    datos = _pedir("categories/")

    categorias = []
    for categoria in datos.get("results", []):
        subcategorias = [
            {"id": sub["id"], "nombre": sub["name"]}
            for sub in categoria.get("categories", [])
        ]
        categorias.append(
            {
                "id": categoria["id"],
                "nombre": categoria["name"],
                "subcategorias": subcategorias,
            }
        )
    return categorias


def obtener_productos_de_subcategoria(
    id_subcategoria: int, nombre_categoria: str = "", nombre_subcategoria: str = ""
) -> list[dict]:
    """Devuelve todos los productos de una subcategoría, ya limpios.

    Los nombres de categoría se pasan como argumento y no se sacan de la
    respuesta porque nos los sabemos ya del árbol, y así nos ahorramos
    rebuscarlos en un JSON anidado.
    """
    datos = _pedir(f"categories/{id_subcategoria}/")

    productos = []
    # Ojo al detalle: dentro de una subcategoría, Mercadona mete OTRO nivel de
    # agrupación ("categories") que en la web no se ve como tal. Los productos
    # están ahí dentro, así que hay que bajar un nivel más.
    for grupo in datos.get("categories", []):
        for producto_bruto in grupo.get("products", []):
            producto = _limpiar_producto(
                producto_bruto, nombre_categoria, nombre_subcategoria
            )
            if producto is not None:
                productos.append(producto)

    return productos


def _limpiar_producto(bruto: dict, categoria: str, subcategoria: str) -> dict | None:
    """Convierte un producto tal como lo manda Mercadona al formato nuestro.

    Esta función es la "aduana" del proyecto: aquí es donde los nombres raros
    de Mercadona (display_name, unit_size, price_instructions...) se traducen a
    nombres nuestros en castellano. A partir de aquí, el resto del programa ya
    no sabe ni le importa cómo llama Mercadona a las cosas.

    Devuelve None si el producto no nos sirve (por ejemplo, sin precio).
    """
    # price_instructions es el diccionario donde Mercadona mete todo lo
    # relacionado con el precio y el tamaño del envase.
    precios = bruto.get("price_instructions") or {}

    precio = _a_numero(precios.get("unit_price"))
    if precio is None or precio <= 0:
        # Sin precio no nos sirve de nada: no podríamos sumarlo a la cesta.
        return None

    # unit_size = cuánto trae el envase.
    # size_format = en qué unidad está expresado ese número ("kg", "l" o "ud").
    #
    # Comprobado contra la API real: Mercadona es muy consistente aquí.
    #   Arroz 1 kg          -> unit_size=1.0    size_format="kg"
    #   Aceite garrafa 5 L  -> unit_size=5.0    size_format="l"
    #   Pack 6 yogures      -> unit_size=0.75   size_format="kg"  (6 x 125 g)
    #   Docena de huevos    -> unit_size=12.0   size_format="ud"
    tamano = _a_numero(precios.get("unit_size")) or 0.0
    formato = (precios.get("size_format") or "").lower()
    precio_referencia = _a_numero(precios.get("reference_price"))

    gramos_envase, unidades_envase = _convertir_tamano(tamano, formato)

    # --- Rescate para los congelados ------------------------------------
    # Descubrimos esto revisando los avisos del script de actualización: 36 de
    # los 4.304 productos (pescado y marisco congelado) venían con unit_size
    # vacío y se quedaban sin tamaño, o sea, inservibles para la cesta.
    #
    # Pero el dato está ahí, solo que hay que deducirlo. Si sabemos lo que
    # cuesta el paquete (5,50 €) y lo que cuesta el kilo (9,167 €/kg),
    # entonces el paquete pesa 5,50 / 9,167 = 0,6 kg.
    #
    # Es una división de andar por casa que recupera productos que si no
    # perderíamos (la merluza congelada, sin ir más lejos, que usan varias
    # de nuestras recetas).
    if gramos_envase is None and unidades_envase is None:
        formato_ref = (precios.get("reference_format") or "").lower()
        if formato_ref in ("kg", "l") and precio_referencia and precio_referencia > 0:
            gramos_envase = (precio / precio_referencia) * 1000.0

    return {
        # El id viene como texto ("4241"). Lo dejamos como texto: no vamos a
        # hacer cuentas con él, y así no perdemos ceros por delante si algún
        # día los hubiera.
        "id": str(bruto["id"]),
        "nombre": bruto.get("display_name", "").strip(),
        "categoria": categoria,
        "subcategoria": subcategoria,
        # Lo que pagas al pasar por caja por UN envase.
        "precio": precio,
        # El precio por kilo / litro / docena. Es el número que sirve para
        # comparar si algo es caro o barato de verdad, más allá del envase.
        "precio_referencia": precio_referencia,
        "formato_referencia": precios.get("reference_format") or "",
        # Cuánta comida trae el envase, en gramos (o mililitros, que para
        # nuestras cuentas tratamos igual). None si se vende por unidades.
        "gramos_envase": gramos_envase,
        # Cuántas unidades trae el envase (huevos, piezas...). None si va a peso.
        "unidades_envase": unidades_envase,
        # True en fruta, verdura y carne al corte: el peso del envase es
        # aproximado, así que el precio final varía un poco. Lo guardamos para
        # poder avisarte en la lista de la compra.
        "peso_aproximado": bool(precios.get("approx_size")),
        "url_imagen": bruto.get("thumbnail") or "",
        "url_web": bruto.get("share_url") or "",
    }


def _convertir_tamano(tamano: float, formato: str) -> tuple[float | None, float | None]:
    """Traduce el tamaño del envase a gramos, o a unidades si va por piezas.

    Devuelve una pareja (gramos, unidades). Solo uno de los dos tiene valor;
    el otro es None.

    Sobre mezclar mililitros y gramos: para el aceite, la leche o el caldo,
    1 ml no pesa exactamente 1 g, pero se le parece lo suficiente. Aquí no
    estamos haciendo química: nos vale para saber cuántas botellas comprar.
    """
    if tamano <= 0:
        return None, None

    if formato in ("kg", "l"):
        # Kilos o litros -> a gramos (o mililitros).
        return tamano * 1000.0, None
    if formato in ("g", "ml"):
        # Ya viene en gramos o mililitros.
        return tamano, None
    if formato in ("ud", "uds", "u"):
        # Se vende por piezas: huevos, panecillos...
        # Cuántos gramos pesa cada pieza es algo que Mercadona no dice, así que
        # eso lo aporta nuestra tabla de ingredientes (campo gramos_por_unidad).
        return None, tamano

    # Formato que no conocemos. Devolvemos None en los dos y el script de
    # actualización nos avisará por pantalla de que ha aparecido algo nuevo.
    return None, None


def _a_numero(valor) -> float | None:
    """Convierte a número los precios, que Mercadona manda como texto.

    Mercadona devuelve los precios entre comillas: "17.75", no 17.75. Es una
    práctica habitual para que no se pierdan decimales por el camino, pero a
    nosotros nos toca convertirlos antes de poder sumar.
    """
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None
