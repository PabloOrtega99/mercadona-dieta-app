"""Decide que producto de Mercadona corresponde a cada ingrediente.

Es el puente entre los dos mundos del proyecto:

    "150 g de pechuga de pollo"   (mundo receta)
              |
              v
    "Filetes de pechuga de pollo Hacendado, bandeja 900 g, 6,45 EUR"  (mundo super)

El resultado se guarda en app/datos/emparejamientos.json, que SI se sube a
GitHub. Ese archivo guarda solo IDS de producto, nunca precios: los precios se
consultan en el momento en la base de datos, para que siempre esten al dia.

Explicacion completa en docs/05-emparejar-ingredientes-productos.md
"""

import json
import sqlite3

from app import config
from app.mercadona import catalogo
from app.recetario import Ingrediente
from app.utiles import normalizar_texto
from app.planificador.cesta import gramos_por_envase

# Cuantos productos guardamos por ingrediente.
#
# ¿Por qué más de uno? Porque el más barato por kilo no siempre es el más
# barato para la cantidad que necesitas (el saco de 5 kg de patatas frente a
# la bolsa de 1 kg). Guardando varios, la cesta puede elegir el mejor cuando
# ya sabe cuánto hace falta. Ver elegir_producto() en cesta.py.
CANDIDATOS_POR_INGREDIENTE = 4

# Cuantas veces mas caro por kilo puede ser el formato pequeno que guardamos
# como alternativa. Por encima de esto, no es un envase pequeno del mismo
# producto: es otro producto distinto. Ver _elegir_variados().
MAX_VECES_MAS_CARO = 3.0

# Categorías del supermercado que NO son comida.
#
# Este filtro salió de un error real y bastante cómico: el ingrediente "miel"
# se emparejó con "Gel de baño vainilla y miel", y "limón" con "Lejía
# perfumada con detergente limón". Las dos contienen la palabra buscada, pero
# ninguna es comida.
#
# Filtrar por categoría es mucho más robusto que ir añadiendo palabras
# prohibidas de una en una: no hay forma de anticipar todos los champús con
# nombre de fruta que existen, pero sí es fácil decir "de la sección de
# droguería no cojas nada".
CATEGORIAS_NO_ALIMENTARIAS = {
    "bebe",
    "cuidado del cabello",
    "cuidado facial y corporal",
    "fitoterapia y parafarmacia",
    "limpieza y hogar",
    "maquillaje",
    "mascotas",
}

# Palabras que descartan un producto para CUALQUIER ingrediente.
#
# Son platos ya cocinados: no nos sirven como ingrediente de una receta.
#
# Al principio bloqueamos por categoría la seccion entera de "Pizzas y platos
# preparados", y fue un error: alli dentro esta el "Tofu firme Hacendado", que
# es un ingrediente perfectamente normal, y nos quedamos sin tofu. Es un buen
# ejemplo de por que conviene revisar la tabla de emparejamientos en vez de
# fiarse: el filtro parecia razonable y se llevaba por delante cosas buenas.
EXCLUSIONES_GLOBALES = [
    "pizza",
    "croqueta",
    "empanadilla",
    "san jacobo",
    "canelon",
    "precocinad",
    "sin gluten",
    "sin lactosa",
    "infantil",
    "papilla",
    "potito",
]

# Los términos de búsqueda de esta longitud o menos tienen que coincidir con
# una palabra ENTERA del nombre del producto.
#
# El motivo: con palabras cortas, permitir que sean el principio de otra
# palabra da desastres. "ajo" es el principio de "bajo", así que el ingrediente
# ajo acababa emparejado con "Caldo de pollo bajo en sal". Y "pera" es el
# principio de "camperas", así que las peras se emparejaban con "Huevos de
# gallinas camperas".
#
# Con palabras largas el prefijo sí interesa, porque resuelve los plurales:
# queremos que "champinon" encuentre "Champiñones laminados".
LONGITUD_PALABRA_CORTA = 4


def cargar_emparejamientos() -> dict[str, dict]:
    """Lee emparejamientos.json. Devuelve {} si todavia no existe."""
    if not config.ARCHIVO_EMPAREJAMIENTOS.exists():
        return {}
    with open(config.ARCHIVO_EMPAREJAMIENTOS, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    # La clave "_ayuda" es documentación para quien abra el archivo, no un
    # ingrediente. La quitamos al cargar.
    return {clave: valor for clave, valor in datos.items() if not clave.startswith("_")}


def guardar_emparejamientos(emparejamientos: dict[str, dict]) -> None:
    """Escribe emparejamientos.json, ordenado y legible."""
    contenido = {
        "_ayuda": (
            "Que producto de Mercadona se compra para cada ingrediente. Lo genera "
            "'python scripts/revisar_emparejamientos.py --regenerar'. Si algun "
            "emparejamiento no te gusta, cambia la lista 'productos' (son ids de "
            "Mercadona, los ves en la url del producto en tienda.mercadona.es) y pon "
            "\"fijado\": true para que no te lo pise la proxima regeneracion. "
            "El campo '_nombres' es solo para que puedas leerlo; no se usa para nada."
        )
    }
    # sorted() para que el archivo salga siempre en el mismo orden. Si no, cada
    # regeneración cambiaría el orden de las líneas y Git te enseñaría cientos
    # de cambios falsos que no lo son.
    for clave in sorted(emparejamientos):
        contenido[clave] = emparejamientos[clave]

    config.ARCHIVO_EMPAREJAMIENTOS.parent.mkdir(parents=True, exist_ok=True)
    with open(config.ARCHIVO_EMPAREJAMIENTOS, "w", encoding="utf-8") as archivo:
        # ensure_ascii=False para que las tildes se guarden como tildes y no
        # como códigos ilegibles tipo á.
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def _palabra_encaja(palabra_buscada: str, palabra_producto: str) -> bool:
    """¿La palabra del producto se corresponde con la que buscamos?

    Con palabras largas basta con que empiece igual, y asi "champinon"
    encuentra "champinones". Con palabras cortas exigimos que sea la misma
    palabra exacta, porque si no "ajo" encontraria "bajo".
    """
    if len(palabra_buscada) <= LONGITUD_PALABRA_CORTA:
        return palabra_producto == palabra_buscada
    return palabra_producto.startswith(palabra_buscada)


def _producto_encaja(nombre_normalizado: str, palabras: list[str], estricto: bool) -> bool:
    """¿Este producto se corresponde con el termino de busqueda?

    Hay dos niveles de exigencia:

      ESTRICTO: ademas de contener todas las palabras, el nombre del producto
      tiene que EMPEZAR por la primera de ellas. Es lo que separa
      "Bacon Hacendado cintas" (empieza por bacon: es bacon) de
      "Rosca de lomo, bacon y queso" (empieza por rosca: es una rosca).
      Es una regla simple y funciona sorprendentemente bien, porque
      Mercadona nombra sus productos empezando por lo que son.

      RELAJADO: basta con que todas las palabras aparezcan en algun sitio.
      Se usa solo si el estricto no encuentra nada, para no quedarnos sin
      producto en casos como "Media calabaza cacahuete", que empieza por
      "media" pero es calabaza igualmente.
    """
    palabras_producto = nombre_normalizado.split()
    if not palabras_producto:
        return False

    if estricto and not _palabra_encaja(palabras[0], palabras_producto[0]):
        return False

    return all(
        any(_palabra_encaja(buscada, palabra) for palabra in palabras_producto)
        for buscada in palabras
    )


def buscar_candidatos(
    conexion: sqlite3.Connection, ingrediente: Ingrediente
) -> list[dict]:
    """Busca en el catalogo los mejores productos para un ingrediente.

    El proceso:

      1. BUSCAR. Se prueban los terminos de 'busqueda' EN ORDEN, del mas
         concreto al mas general, y nos quedamos con el primero que da
         resultados validos. Asi "filete pechuga pollo" tiene prioridad sobre
         el generico "pollo", que traeria de todo.

      2. FILTRAR. Fuera lo que no es comida (por categoria), lo que lleva una
         palabra prohibida, y lo que no encaja de verdad con lo buscado.

      3. ORDENAR. Por precio por gramo, de mas barato a mas caro.

    Y todo eso dos veces: primero exigiendo que el nombre del producto EMPIECE
    por lo buscado, y solo si asi no sale nada, con el criterio relajado.
    """
    prohibidas = [normalizar_texto(p) for p in ingrediente.excluir]
    prohibidas += [normalizar_texto(p) for p in EXCLUSIONES_GLOBALES]

    # Primero la vuelta estricta con todos los términos; si ninguno da nada,
    # la vuelta relajada. Este orden importa: más vale el término genérico
    # bien encajado que el término concreto mal encajado.
    for estricto in (True, False):
        for termino in ingrediente.busqueda:
            validos = _filtrar(conexion, ingrediente, termino, prohibidas, estricto)
            if validos:
                return _elegir_variados(validos)

    return []


def _elegir_variados(validos: list[dict]) -> list[dict]:
    """Se queda con unos pocos productos, procurando que haya formatos distintos.

    Si nos quedaramos con los cuatro mas baratos por kilo a secas, en muchos
    ingredientes saldrian los cuatro en formato gigante, porque el envase
    grande casi siempre sale mejor de precio por kilo.

    Y eso da resultados absurdos: el aceite mas barato por litro es la garrafa
    de 5 litros a 19 euros. Para un plan de una semana necesitas 200 gramos, y
    plantarte una garrafa de 19 euros en una compra de 60 se lleva por delante
    un tercio del presupuesto para tirar el 96 % del aceite.

    Asi que guardamos los tres mas baratos por kilo Y ADEMAS el envase mas
    pequeno que hayamos encontrado. Con esas cuatro opciones, elegir_producto()
    (en cesta.py) ya puede escoger bien cuando sepa cuanta cantidad hace falta:
    la botella pequena para una semana, la garrafa para un mes en familia.
    """
    por_precio = sorted(validos, key=lambda p: p["precio_por_gramo"])
    elegidos = por_precio[: CANDIDATOS_POR_INGREDIENTE - 1]

    mas_pequeno = min(validos, key=lambda p: p.get("gramos_envase") or float("inf"))

    # El filtro del precio de aqui abajo no estaba, y el fallo se vio en la
    # foto de una receta: donde tenia que haber cebollas aparecia un bote de
    # cebolla molida. Al pedir "el envase mas pequeno" se colaba el bote de
    # especia, que efectivamente es el mas pequeno y para 120 gramos salia mas
    # barato que una bolsa de dos kilos... pero no es el mismo alimento.
    #
    # La senal que los distingue es el precio por kilo. Un formato pequeno
    # legitimo (la botella de aceite de 1 litro frente a la garrafa de 5)
    # cuesta algo mas por kilo, pero no mucho mas. Un producto que en realidad
    # es otra cosa cuesta un disparate por kilo: la cebolla molida sale a mas
    # de 20 euros el kilo, frente a 1,80 la fresca.
    barato = por_precio[0]["precio_por_gramo"]
    encaja_el_precio = mas_pequeno["precio_por_gramo"] <= barato * MAX_VECES_MAS_CARO

    if encaja_el_precio and all(p["id"] != mas_pequeno["id"] for p in elegidos):
        elegidos.append(mas_pequeno)

    return elegidos


def _filtrar(
    conexion: sqlite3.Connection,
    ingrediente: Ingrediente,
    termino: str,
    prohibidas: list[str],
    estricto: bool,
) -> list[dict]:
    """Aplica todos los filtros a los resultados de un termino de busqueda."""
    palabras = [p for p in normalizar_texto(termino).split() if p]
    if not palabras:
        return []

    # La base de datos hace una criba rápida y ancha (contiene estas letras);
    # aquí afinamos con las reglas de verdad. Repartir el trabajo así es lo
    # habitual: SQL es rapidísimo filtrando mucho, y Python es más cómodo para
    # las reglas con matices.
    encontrados = catalogo.buscar(conexion, termino, limite=120)

    validos = []
    for producto in encontrados:
        nombre = producto["nombre_normalizado"]

        if normalizar_texto(producto["categoria"] or "") in CATEGORIAS_NO_ALIMENTARIAS:
            continue

        if any(palabra and palabra in nombre for palabra in prohibidas):
            continue

        if not _producto_encaja(nombre, palabras, estricto):
            continue

        # ¿Sabemos cuánta comida trae el envase? Si no, es inservible: no
        # podríamos calcular cuántos comprar.
        tamano = gramos_por_envase(producto, ingrediente)
        if not tamano or tamano <= 0:
            continue

        producto = dict(producto)
        producto["precio_por_gramo"] = float(producto["precio"]) / tamano
        validos.append(producto)

    return validos


def regenerar(
    conexion: sqlite3.Connection,
    ingredientes: dict[str, Ingrediente],
    anteriores: dict[str, dict] | None = None,
) -> tuple[dict[str, dict], list[str]]:
    """Rehace los emparejamientos, respetando los que hayas fijado a mano.

    Devuelve (emparejamientos, ingredientes_sin_producto).

    Lo de respetar los fijados no es un capricho: el emparejamiento automatico
    por texto acierta bastante, pero no siempre. Cuando corriges uno a mano,
    esa correccion tiene que sobrevivir a la siguiente actualizacion del
    catalogo. Si no, perderias tu trabajo cada semana y acabarias no
    corrigiendo nada.
    """
    anteriores = anteriores or {}
    resultado: dict[str, dict] = {}
    sin_producto: list[str] = []

    for id_ingrediente, ingrediente in ingredientes.items():
        anterior = anteriores.get(id_ingrediente, {})

        # Si lo has fijado tú, no se toca.
        if anterior.get("fijado"):
            resultado[id_ingrediente] = anterior
            continue

        candidatos = buscar_candidatos(conexion, ingrediente)

        if not candidatos:
            sin_producto.append(id_ingrediente)
            resultado[id_ingrediente] = {"fijado": False, "productos": [], "_nombres": []}
            continue

        resultado[id_ingrediente] = {
            "fijado": False,
            "productos": [p["id"] for p in candidatos],
            "_nombres": [p["nombre"] for p in candidatos],
        }

    return resultado, sin_producto


def cargar_productos_usados(
    conexion: sqlite3.Connection, emparejamientos: dict[str, dict]
) -> dict[str, dict]:
    """Trae de la base de datos los productos que aparecen en los emparejamientos.

    Los cargamos todos de golpe al arrancar y los dejamos en memoria en un
    diccionario. El planificador consulta precios miles de veces al montar un
    menu; si cada consulta fuera a la base de datos, la web iria lenta sin
    ninguna necesidad.
    """
    ids = {
        id_producto
        for emparejamiento in emparejamientos.values()
        for id_producto in emparejamiento.get("productos", [])
    }

    productos: dict[str, dict] = {}
    for id_producto in ids:
        producto = catalogo.obtener(conexion, id_producto)
        if producto is not None:
            productos[id_producto] = producto

    return productos
