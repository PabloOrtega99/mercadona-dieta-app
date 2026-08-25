"""Busca fotos de platos ya cocinados en bancos de imagenes libres.

El problema: el recetario es nuestro, asi que no tenemos fotos de los platos.
Antes se resolvia montando un collage con las fotos de los productos de
Mercadona (ver collage.py, que sigue ahi como red de seguridad), pero un
mosaico de envases no da hambre.

Se usan DOS fuentes, y en este orden:

  1. OPENVERSE (api.openverse.org). Es un buscador de imagenes con licencia
     libre que agrega Flickr, museos y otros. Cubre MUY bien la cocina
     espanola: buscando "merluza al horno" salen fotos de merluza al horno.
     No hace falta clave ni registro.

  2. WIKIMEDIA COMMONS. Licencias mas libres, pero cobertura floja para
     platos: buscando "Lentejas guisadas" la primera respuesta fue un libro
     de fabulas de Esopo de 1500 y pico. Se usa para rellenar cuando
     Openverse se queda corto.

SOBRE LAS LICENCIAS
-------------------
Muchas fotos son CC BY-NC (no comercial) o BY-ND (sin obras derivadas). Este
proyecto es personal y no se distribuye, asi que ambas valen. Pero hay que
cumplir dos cosas:

  - ATRIBUIR: guardamos autor, licencia y enlace al original, y se ensenan en
    la ficha de la receta. Openverse ya nos da el texto de atribucion montado.

  - NO MODIFICAR la foto: nada de recortarla ni de escribirle el nombre encima
    como hace el collage. ND no lo permite. Se guarda tal cual y el tamano lo
    decide el CSS.
"""

import time
import urllib.parse

import requests

from app import config
from app.utiles import normalizar_texto

OPENVERSE = "https://api.openverse.org/v1/images/"
COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA = "https://es.wikipedia.org/w/api.php"

# Cuanto se le suma a la relevancia de una foto que venga de Wikipedia.
#
# No es un capricho: la foto principal de un articulo de Wikipedia sobre un
# plato la ha elegido una persona para ilustrar ESE plato. Una foto de un
# banco de imagenes solo tiene un titulo que casualmente comparte una palabra.
# La primera merece mas confianza de partida, y este numero lo dice.
BONUS_WIKIPEDIA = 2

CABECERAS = {
    "User-Agent": "mercadona-dieta-app/2.0 (proyecto personal)",
    "Accept": "application/json",
}

# Las dos fuentes son gratuitas y sin clave. Se les trata con la misma
# educacion que a la API de Mercadona: una pausa entre peticiones.
PAUSA = 0.4

# Palabras que no aportan nada al buscar.
VACIAS = {
    "de", "del", "la", "el", "los", "las", "con", "y", "a", "al", "en",
    "para", "un", "una", "sin", "su", "e", "o",
}

# Palabras que dicen el TIPO de plato pero no de que es.
#
# Sirven para dos cosas: no dejar que una consulta se quede formada SOLO por
# estas palabras, y exigir que la foto elegida coincida en algo MAS que el
# tipo de plato.
#
# Esta lista se equivoco dos veces y las dos merecen quedar escritas:
#
#   1. Al principio no existia. Al acortar los nombres se llegaba a consultas
#      como "crema de" o "ensalada de", y Openverse devolvia lo primero que
#      las contuviera: la misma foto de un bizcocho de chocolate acabo en
#      CUATRO recetas de crema, y una ensalada de nopal en CINCO ensaladas.
#
#   2. Al crearla meti aqui tambien "lasana", "paella", "tortilla"... y fue
#      pasarse al otro extremo: una foto de una lasana vale perfectamente para
#      una receta de lasana. Exigir que ademas mencionara la carne dejo 82 de
#      las 130 recetas sin ninguna foto.
#
# Aqui van SOLO las palabras que no identifican el plato.
GENERICAS = {
    "crema", "ensalada", "sopa", "guiso", "estofado", "potaje", "salteado",
    "plato", "receta", "comida", "casera", "casero",
    "completo", "completa", "verduras", "salsa",
    "relleno", "rellena",
    "gratinada", "gratinado", "horno", "plancha", "asada", "asado",
}


def buscar_candidatas(nombre_receta: str, cuantas: int = 6) -> list[dict]:
    """Devuelve varias fotos candidatas para una receta, la mejor primero.

    Se prueban varias formas de escribir la busqueda porque el nombre completo
    de la receta muchas veces es demasiado especifico para un banco de fotos:
    "Berenjenas al horno con quinoa" no lo va a encontrar nadie, pero
    "berenjenas horno" si.

    Al final se ordenan por lo bien que el TITULO de la foto encaja con el
    nombre de la receta, que resulta ser una senal bastante fiable.
    """
    candidatas: list[dict] = []
    vistas: set[str] = set()
    consultas = _variantes(nombre_receta)

    # Wikipedia va primera porque acierta mucho mas, pero SOLO con consultas
    # de dos palabras o mas. Con una sola palabra se va a la botanica y a la
    # geografia: "lentejas" devuelve una lamina cientifica de Lens culinaris,
    # "berenjena" la planta y "canelones" un monumento de Uruguay. Con dos
    # palabras entiende que hablas de un plato: "canelones carne" ya devuelve
    # la foto de unos canelones.
    consultas_wikipedia = [c for c in consultas if len(_palabras_utiles(c)) >= 2]

    for buscar_en, lista in (
        (_wikipedia, consultas_wikipedia),
        (_openverse, consultas),
        (_commons, consultas),
    ):
        for consulta in lista:
            for resultado in buscar_en(consulta, cuantas):
                if resultado["url"] in vistas:
                    continue
                vistas.add(resultado["url"])
                resultado["relevancia"] = _relevancia(resultado["titulo"], nombre_receta)
                if resultado["origen"] == "Wikipedia" and resultado["relevancia"] > 0:
                    resultado["relevancia"] += BONUS_WIKIPEDIA
                candidatas.append(resultado)
            # Con unas cuantas que encajen bien ya vale: no hace falta
            # machacar las dos APIs con todas las variantes.
            if sum(1 for c in candidatas if c["relevancia"] > 0) >= cuantas:
                break
        if sum(1 for c in candidatas if c["relevancia"] > 0) >= cuantas:
            break

    # Se ORDENAN por relevancia, pero no se descarta ninguna.
    #
    # La primera version si descartaba las de relevancia cero, y fue pasarse:
    # 82 de las 130 recetas se quedaban sin ninguna candidata. Descartar es
    # una decision que no hace falta tomar aqui: quien preselecciona ya exige
    # relevancia mayor que cero, y para la pantalla de revision es mejor
    # ensenarte seis fotos regulares que ninguna, porque a veces la buena esta
    # entre ellas aunque su titulo no lo diga.
    candidatas.sort(key=lambda c: -c["relevancia"])
    return candidatas[:cuantas]


def _es_generica(palabra: str) -> bool:
    """Dice si una palabra indica el tipo de plato pero no de que es.

    Comprueba tambien el singular, para no tener que listar cada palabra dos
    veces ("gratinada" y "gratinadas", "asado" y "asados"...). Listar los
    plurales a mano es justo la clase de lista que siempre acaba con un hueco:
    se me escapo "gratinadas" y volvio a colarse como consulta ella sola.
    """
    palabra = palabra.lower()
    if palabra in GENERICAS:
        return True
    return palabra.endswith("s") and palabra[:-1] in GENERICAS


def _palabras_utiles(nombre: str) -> list[str]:
    """Las palabras de un nombre que sirven para buscar, sin tildes."""
    return [p for p in normalizar_texto(nombre).split() if p not in VACIAS]


def _relevancia(titulo: str, nombre_receta: str) -> int:
    """Cuanto encaja el titulo de una foto con el nombre de una receta.

    Cuenta cuantas palabras comparten, PERO las genericas ("crema",
    "ensalada") valen la mitad que las concretas ("calabacin", "lentejas"), y
    si no coincide ninguna concreta la puntuacion es cero.

    Esa ultima regla es la que mata al bizcocho: se titulaba "Coc de crema de
    xocolata", comparte "crema" con "Crema de calabacin y queso", pero no
    comparte ni "calabacin" ni "queso". Cero.
    """
    titulo_normalizado = normalizar_texto(titulo)
    palabras = _palabras_utiles(nombre_receta)

    concretas = 0
    genericas = 0
    for palabra in palabras:
        # Se compara por prefijo para que "lenteja" encuentre "lentejas".
        raiz = palabra[:-1] if len(palabra) > 5 and palabra.endswith("s") else palabra
        if raiz in titulo_normalizado:
            if _es_generica(palabra):
                genericas += 1
            else:
                concretas += 1

    if concretas == 0:
        return 0
    return concretas * 2 + genericas


def _variantes(nombre: str) -> list[str]:
    """Formas de buscar el nombre de una receta, de la mas concreta a la mas general.

    "Crema de calabacin y queso" -> ["crema de calabacin y queso",
                                     "crema de calabacin",
                                     "crema calabacin queso",
                                     "crema calabacin",
                                     "calabacin",
                                     "queso"]

    Fijate en lo que NO esta: "crema" a secas. Nunca se genera una consulta
    formada solo por palabras genericas.
    """
    limpio = nombre.lower().strip()
    variantes = [limpio]

    # Cortar por " con " o " y " suele dejar el plato principal. Pero solo si
    # lo que queda tiene sustancia: "Pavo con cuscus y verduras" cortado por
    # " con " deja "pavo" a secas, y buscar "pavo" en un banco de fotos trae
    # pavos reales, que efectivamente son pavos pero no se comen.
    for separador in (" con ", " estilo ", " y "):
        if separador in limpio:
            trozo = limpio.split(separador)[0]
            if len(_palabras_utiles(trozo)) >= 2:
                variantes.append(trozo)

    # Despues, las palabras utiles, quitando de atras hacia delante.
    utiles = _palabras_utiles(nombre)
    for cuantas in range(len(utiles), 0, -1):
        variantes.append(" ".join(utiles[:cuantas]))

    # Y como ultimo recurso, cada palabra CONCRETA por separado. Esto salva
    # los nombres cortos: "Berenjenas gratinadas" solo genera una consulta
    # util, y si esa no da nada nos quedabamos sin foto pudiendo buscar
    # simplemente "berenjenas".
    for palabra in utiles:
        if not _es_generica(palabra):
            variantes.append(palabra)

    # La regla que si hay que respetar siempre: fuera las consultas formadas
    # SOLO por palabras genericas.
    # dict.fromkeys quita repetidos conservando el orden (set no lo conserva).
    return [
        v for v in dict.fromkeys(variantes)
        if v and any(not _es_generica(p) for p in _palabras_utiles(v))
    ]


def _wikipedia(consulta: str, cuantas: int) -> list[dict]:
    """Coge la foto principal del articulo de Wikipedia que mejor encaje.

    Es la fuente mas fiable de las tres, y por un motivo que merece la pena
    entender: en un banco de imagenes buscas fotos cuyo TITULO contenga unas
    palabras, y el titulo lo puso quien subio la foto, a veces mal y a veces
    en broma. En Wikipedia buscas un ARTICULO y coges la foto que alguien
    eligio para ilustrarlo. Es informacion curada, no una coincidencia de
    texto.

    Solo devuelve una foto por consulta (la del articulo que mejor encaja),
    asi que las otras dos fuentes siguen haciendo falta para tener variedad.
    """
    parametros = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrlimit": 2,
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": 800,
    }
    try:
        respuesta = requests.get(
            WIKIPEDIA, params=parametros, headers=CABECERAS, timeout=config.TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return []
    finally:
        time.sleep(PAUSA)

    paginas = (datos.get("query") or {}).get("pages") or {}
    resultados = []
    for pagina in paginas.values():
        miniatura = (pagina.get("thumbnail") or {}).get("source")
        if not miniatura:
            continue
        titulo = pagina.get("title", "")
        resultados.append(
            {
                "url": miniatura,
                "titulo": titulo,
                # Las fotos de Wikipedia vienen de Wikimedia Commons y son
                # todas de licencia libre. El autor concreto habria que
                # pedirlo en otra peticion; se atribuye al articulo, que es
                # de donde la hemos sacado.
                "autor": "colaboradores de Wikipedia",
                "licencia": "CC / dominio publico",
                "licencia_url": "https://commons.wikimedia.org/wiki/Commons:Licensing",
                "enlace": f"https://es.wikipedia.org/wiki/{urllib.parse.quote(titulo)}",
                "atribucion": f"Foto del articulo '{titulo}' de Wikipedia en espanol",
                "origen": "Wikipedia",
                "consulta": consulta,
            }
        )
    return resultados


def _openverse(consulta: str, cuantas: int) -> list[dict]:
    """Busca en Openverse."""
    parametros = {
        "q": consulta,
        "license_type": "all-cc",
        "page_size": cuantas,
        # Solo fotografias: sin esto salen ilustraciones y dibujos.
        "category": "photograph",
    }
    try:
        respuesta = requests.get(
            OPENVERSE, params=parametros, headers=CABECERAS, timeout=config.TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return []
    finally:
        time.sleep(PAUSA)

    resultados = []
    for item in datos.get("results", []):
        # La miniatura de Openverse es una version ya reducida servida por
        # ellos. Se usa tanto para ensenar candidatas como para guardar la
        # elegida: pesa poco y, al no redimensionarla nosotros, respetamos las
        # licencias "sin obras derivadas".
        miniatura = item.get("thumbnail")
        if not miniatura:
            continue
        resultados.append(
            {
                "url": miniatura,
                "titulo": item.get("title") or consulta,
                "autor": item.get("creator") or "desconocido",
                "licencia": (item.get("license") or "cc").upper(),
                "licencia_url": item.get("license_url") or "",
                "enlace": item.get("foreign_landing_url") or "",
                "atribucion": item.get("attribution") or "",
                "origen": "Openverse",
                "consulta": consulta,
            }
        )
    return resultados


def _commons(consulta: str, cuantas: int) -> list[dict]:
    """Busca en Wikimedia Commons."""
    parametros = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrnamespace": 6,  # 6 = espacio de nombres de archivos
        "gsrlimit": cuantas,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 800,
    }
    try:
        respuesta = requests.get(
            COMMONS, params=parametros, headers=CABECERAS, timeout=config.TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return []
    finally:
        time.sleep(PAUSA)

    paginas = (datos.get("query") or {}).get("pages") or {}
    resultados = []
    for pagina in paginas.values():
        info = (pagina.get("imageinfo") or [{}])[0]
        miniatura = info.get("thumburl")
        if not miniatura:
            continue
        # Commons guarda cosas que no son fotos: djvu y pdf son libros
        # escaneados, svg son dibujos. Fuera.
        titulo = pagina.get("title", "")
        if any(titulo.lower().endswith(ext) for ext in (".djvu", ".svg", ".pdf", ".tif")):
            continue

        extra = info.get("extmetadata") or {}
        autor = _limpiar_html((extra.get("Artist") or {}).get("value", "desconocido"))
        licencia = (extra.get("LicenseShortName") or {}).get("value", "CC")

        resultados.append(
            {
                "url": miniatura,
                "titulo": titulo.replace("File:", ""),
                "autor": autor,
                "licencia": licencia,
                "licencia_url": (extra.get("LicenseUrl") or {}).get("value", ""),
                "enlace": info.get("descriptionurl", ""),
                "atribucion": f"{titulo.replace('File:', '')} por {autor} ({licencia})",
                "origen": "Wikimedia Commons",
                "consulta": consulta,
            }
        )
    return resultados


def _limpiar_html(texto: str) -> str:
    """Quita las etiquetas HTML del nombre del autor.

    Commons devuelve el autor como un trozo de HTML, tipo
    '<a href="...">Fulano</a>', porque esta pensado para pintarse en su web.
    A nosotros solo nos interesa el nombre.
    """
    resultado = []
    dentro = False
    for caracter in texto:
        if caracter == "<":
            dentro = True
        elif caracter == ">":
            dentro = False
        elif not dentro:
            resultado.append(caracter)
    return urllib.parse.unquote("".join(resultado)).strip() or "desconocido"
