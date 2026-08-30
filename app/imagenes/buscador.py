"""Busca fotos de platos ya cocinados en bancos de imagenes libres.

El problema: el recetario es nuestro, asi que no tenemos fotos de los platos.
Antes se resolvia montando un collage con las fotos de los productos de
Mercadona (ver collage.py, que sigue ahi como red de seguridad), pero un
mosaico de envases no da hambre.

Se usan CUATRO fuentes, y en este orden:

  1. THEMEALDB (themealdb.com). Una base de datos de recetas con foto, no un
     banco de imagenes generico: cuando encuentra algo, es SIEMPRE la foto de
     ESE plato ya cocinado, nunca un articulo generico ni una casualidad de
     texto. Clave publica "1" (de desarrollo/educativa, sin registro). Su
     cobertura de cocina espanola es real pero modesta: comprobado a mano,
     "Pollo en pepitoria", "Gambas al ajillo" o "Gazpacho" encuentran su plato
     exacto, pero la mayoria de nombres de este recetario no estan en su base
     (no tienen "Lentejas estofadas con chorizo" ni "Bacalao a la vizcaina").
     Por eso nunca es la unica fuente: es la primera bala, y casi siempre hay
     que seguir con las demas.

  2. WIKIPEDIA (es.wikipedia.org). La foto principal del articulo que mejor
     encaja. Acierta mucho porque la eligio una persona para ilustrar ESE
     plato, pero solo funciona bien con consultas de dos palabras o mas.

  3. OPENVERSE (api.openverse.org). Un buscador de imagenes con licencia
     libre que agrega Flickr, museos y otros. Cubre bien la cocina espanola.
     No hace falta clave ni registro.

  4. WIKIMEDIA COMMONS. Licencias mas libres, pero cobertura floja para
     platos sueltos. Se usa para rellenar cuando las demas se quedan cortas.

SOBRE LAS LICENCIAS
-------------------
Wikipedia, Openverse y Commons dan fotos con licencia libre de verdad (a
veces CC BY-NC o BY-ND; este proyecto es personal y no se distribuye, asi
que ambas valen). Con esas tres se cumplen dos cosas:

  - ATRIBUIR: guardamos autor, licencia y enlace al original, y se ensenan en
    la ficha de la receta. Openverse ya nos da el texto de atribucion montado.

  - NO MODIFICAR la foto: nada de recortarla ni de escribirle el nombre encima
    como hace el collage. ND no lo permite. Se guarda tal cual y el tamano lo
    decide el CSS.

TheMealDB es distinto y hay que ser honestos con ello: sus fotos vienen de
blogs de recetas externos (BBC Good Food y similares) y NO llevan una
licencia libre confirmada — su propia documentacion lo dice: la clave "1" es
"para desarrollo y uso educativo", y avisa de que hay que revisar la licencia
de cada imagen antes de redistribuirla. Aqui no se redistribuye nada (la foto
solo se guarda en tu disco para que la veas tu), pero por eso en la ficha de
la receta su atribucion NO dice "CC" como las demas: dice honestamente que la
licencia no esta confirmada, con un enlace a la pagina del plato en TheMealDB.
Si algun dia esto se convirtiera en algo publico, las fotos de TheMealDB
serian las primeras que revisar.
"""

import time
import urllib.parse

import requests

from app import config
from app.utiles import normalizar_texto

OPENVERSE = "https://api.openverse.org/v1/images/"
COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA = "https://es.wikipedia.org/w/api.php"
THEMEALDB = "https://www.themealdb.com/api/json/v1/1/search.php"

# Cuanto se le suma a la relevancia de una foto que venga de Wikipedia o de
# TheMealDB frente a una de un banco de imagenes generico.
#
# No es un capricho: la foto principal de un articulo de Wikipedia, o la foto
# de una receta de TheMealDB, la ha elegido una persona para ilustrar ESE
# plato. Una foto de un banco de imagenes generico solo tiene un titulo que
# casualmente comparte una palabra. Las dos merecen mas confianza de partida
# que Openverse o Commons, y este numero lo dice; van igualadas entre si
# porque las dos son "alguien eligio esta foto para este plato exacto", pese
# a que la licencia de TheMealDB sea menos clara (ver el docstring de arriba).
BONUS_WIKIPEDIA = 2
BONUS_THEMEALDB = 2

# Cuanto suma que el titulo de la foto mencione el ingrediente que mas pesa
# en la receta (ver el parametro ingrediente_principal en buscar_candidatas).
# Nacio de un fallo real: "Pollo al horno con patatas" acabo con una foto de
# patatas fritas SIN POLLO, porque su titulo coincidia en "patatas" y eso ya
# le daba puntuacion positiva. Este extra hace que, a igualdad de lo demas,
# gane la foto que si muestra el ingrediente que define el plato.
EXTRA_INGREDIENTE_PRINCIPAL = 3

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


def buscar_candidatas(
    nombre_receta: str, cuantas: int = 6, ingrediente_principal: str | None = None
) -> list[dict]:
    """Devuelve varias fotos candidatas para una receta, la mejor primero.

    Se prueban varias formas de escribir la busqueda porque el nombre completo
    de la receta muchas veces es demasiado especifico para un banco de fotos:
    "Berenjenas al horno con quinoa" no lo va a encontrar nadie, pero
    "berenjenas horno" si.

    Al final se ordenan por lo bien que el TITULO de la foto encaja con el
    nombre de la receta, que resulta ser una senal bastante fiable.

    `ingrediente_principal` (opcional) es el nombre del ingrediente que mas
    pesa en la receta, p.ej. "Pechuga de pollo". Si se pasa, una foto cuyo
    titulo tambien lo mencione recibe un empujon extra en la relevancia. Sirve
    para corregir un fallo real: "Pollo al horno con patatas" tenia una foto
    de una sarten de patatas SIN NI RASTRO DE POLLO, porque su titulo
    coincidia en "patatas" (una palabra concreta del nombre) y eso ya bastaba
    para pasar el filtro. Ver _relevancia().
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
        (_themealdb, consultas),
        (_wikipedia, consultas_wikipedia),
        (_openverse, consultas),
        (_commons, consultas),
    ):
        for consulta in lista:
            for resultado in buscar_en(consulta, cuantas):
                if resultado["url"] in vistas:
                    continue
                vistas.add(resultado["url"])
                resultado["relevancia"] = _relevancia(
                    resultado["titulo"], nombre_receta, ingrediente_principal
                )
                if resultado["origen"] == "Wikipedia" and resultado["relevancia"] > 0:
                    resultado["relevancia"] += BONUS_WIKIPEDIA
                elif resultado["origen"] == "TheMealDB" and resultado["relevancia"] > 0:
                    resultado["relevancia"] += BONUS_THEMEALDB
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


# A partir de que longitud una palabra se compara por PREFIJO en vez de exigir
# que sea exactamente igual. Mismo umbral, mismo motivo y mismo numero que
# app/planificador/emparejador.py, que aprendio esta leccion primero.
#
# Se descubrio aqui un fallo gemelo al de alli, y de la peor manera: mirando
# las fotos elegidas, la receta "Espaguetis con tomate y ajo" tenia puesta
# una foto de "Alfajores" (un dulce). La razon: la version de _relevancia()
# de antes comparaba "¿esta 'ajo' en alguna parte del titulo?" como texto
# corrido, sin mirar donde empiezan y acaban las palabras, y "ajo" SI esta
# ahi dentro de "alfaJOres" (a-l-f-a-J-O-r-e-s), pura casualidad de letras.
# Con TheMealDB, cuya base son sobre todo titulos en ingles, este tipo de
# coincidencia accidental se volvio mucho mas frecuente que con las otras
# fuentes.
LONGITUD_PALABRA_CORTA = 4


def _coincide(palabra: str, palabra_titulo: str) -> bool:
    """¿Cuenta esta palabra del titulo como una coincidencia de esta palabra?

    Palabras cortas (4 letras o menos) tienen que ser EXACTAMENTE la misma:
    sin esto, "ajo" encaja dentro de "alfaJOres" o "sal" dentro de "salteado".
    Palabras largas valen por prefijo, para pillar plurales y derivados:
    "champinon" encuentra "champiñones".
    """
    if len(palabra) <= LONGITUD_PALABRA_CORTA:
        return palabra_titulo == palabra
    return palabra_titulo.startswith(palabra) or palabra.startswith(palabra_titulo)


def _relevancia(titulo: str, nombre_receta: str, ingrediente_principal: str | None = None) -> int:
    """Cuanto encaja el titulo de una foto con el nombre de una receta.

    Cuenta cuantas PALABRAS COMPLETAS comparten (no trozos de palabra), PERO
    las genericas ("crema", "ensalada") valen la mitad que las concretas
    ("calabacin", "lentejas"), y si no coincide ninguna concreta la
    puntuacion es cero.

    Esa ultima regla es la que mata al bizcocho: se titulaba "Coc de crema de
    xocolata", comparte "crema" con "Crema de calabacin y queso", pero no
    comparte ni "calabacin" ni "queso". Cero.

    Si se conoce el ingrediente que mas pesa en la receta, mencionarlo suma
    un extra (EXTRA_INGREDIENTE_PRINCIPAL). No es un requisito, solo un
    empujon: exigirlo a rajatabla dejaria sin foto recetas cuya mejor
    candidata legitima no llegue a nombrar el ingrediente por su nombre
    exacto. Pero el empujon es justo lo que hacia falta para que, entre varias
    fotos con la misma puntuacion por palabras generales, gane la que de
    verdad muestra el ingrediente principal y no una guarnicion cualquiera.
    """
    palabras_titulo = normalizar_texto(titulo).split()
    palabras = _palabras_utiles(nombre_receta)

    concretas = 0
    genericas = 0
    for palabra in palabras:
        # Se quita la "s" final para que "lenteja" encuentre "lentejas" sin
        # necesitar tambien el plural exacto.
        raiz = palabra[:-1] if len(palabra) > 5 and palabra.endswith("s") else palabra
        if any(_coincide(raiz, pt) for pt in palabras_titulo):
            if _es_generica(palabra):
                genericas += 1
            else:
                concretas += 1

    if concretas == 0:
        return 0

    puntuacion = concretas * 2 + genericas

    if ingrediente_principal:
        palabras_ingrediente = _palabras_utiles(ingrediente_principal)
        if any(_coincide(p, pt) for p in palabras_ingrediente for pt in palabras_titulo):
            puntuacion += EXTRA_INGREDIENTE_PRINCIPAL

    return puntuacion


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


def _themealdb(consulta: str, cuantas: int) -> list[dict]:
    """Busca en TheMealDB, una base de datos de recetas con foto.

    A diferencia de las otras tres fuentes, aqui no se busca "una foto que
    tenga estas palabras en el titulo": se busca una RECETA que se llame asi,
    y la foto que devuelve es la de esa receta exacta. Por eso, cuando
    encuentra algo, suele ser un acierto muy limpio.

    El "search.php?s=" de su API hace una coincidencia de texto contra el
    nombre del plato (en ingles casi siempre, aunque muchos platos espanoles
    conservan su nombre: "Paella", "Gazpacho", "Pollo en pepitoria"). Por eso
    NO conviene ser la unica fuente: para un nombre como "Lentejas estofadas
    con chorizo" no va a encontrar nada, y ahi entran las demas.
    """
    parametros = {"s": consulta}
    try:
        respuesta = requests.get(
            THEMEALDB, params=parametros, headers=CABECERAS, timeout=config.TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return []
    finally:
        time.sleep(PAUSA)

    resultados = []
    for plato in (datos.get("meals") or [])[:cuantas]:
        miniatura = plato.get("strMealThumb")
        if not miniatura:
            continue
        nombre = plato.get("strMeal") or consulta
        resultados.append(
            {
                "url": miniatura,
                "titulo": nombre,
                "autor": "TheMealDB",
                # Deliberadamente NO dice "CC": ver la nota de licencias en la
                # cabecera del archivo. Es la unica fuente de las cuatro cuya
                # licencia no esta confirmada.
                "licencia": "sin licencia libre confirmada",
                "licencia_url": "https://www.themealdb.com/terms_of_use.php",
                "enlace": f"https://www.themealdb.com/meal/{plato.get('idMeal', '')}",
                "atribucion": f"Foto de la receta '{nombre}' via TheMealDB (themealdb.com)",
                "origen": "TheMealDB",
                "consulta": consulta,
            }
        )
    return resultados


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
