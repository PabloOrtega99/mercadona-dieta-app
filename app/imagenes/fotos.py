"""Gestiona la foto de plato de cada receta: cual es, y tenerla en local.

Separa dos cosas que conviene no mezclar:

  QUE FOTO ELEGISTE  ->  app/datos/imagenes_recetas.json   (SI va a GitHub)
  LA FOTO EN SI      ->  datos/imagenes/<receta>.jpg       (NO va a GitHub)

Es el mismo criterio que con el catalogo de Mercadona: lo que decides tu se
guarda, y lo que se puede volver a bajar con un comando, no. Asi tus
elecciones te siguen al otro ordenador y las fotos se descargan solas alli la
primera vez.

Si una receta no tiene foto elegida, se usa el collage de productos de
siempre. Nunca hay un hueco roto.
"""

import json
import time
from pathlib import Path

import requests

from app import config
from app.imagenes import collage
from app.recetario import Ingrediente, Receta

# Wikimedia (de donde vienen las fotos de Wikipedia y de Commons) pide en sus
# normas de uso que el User-Agent diga QUE es el programa y COMO contactar.
# A los que no se identifican los limita o los bloquea sin contemplaciones.
CABECERAS = {
    "User-Agent": (
        "mercadona-dieta-app/2.0 (proyecto personal de aprendizaje; "
        "https://github.com/pabloortegax9/mercadona-dieta-app)"
    )
}

# Cuantas veces se reintenta una descarga que ha fallado, y cuanto se espera.
REINTENTOS = 3
ESPERA_BASE = 1.5


def cargar_elecciones() -> dict[str, dict]:
    """Lee que foto se ha elegido para cada receta."""
    if not config.ARCHIVO_IMAGENES.exists():
        return {}
    with open(config.ARCHIVO_IMAGENES, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    return {clave: valor for clave, valor in datos.items() if not clave.startswith("_")}


def guardar_elecciones(elecciones: dict[str, dict]) -> None:
    """Escribe el archivo de elecciones, ordenado para que Git no se maree."""
    contenido = {
        "_ayuda": (
            "Que foto de plato usa cada receta. Se rellena desde la pantalla /fotos "
            "de la aplicacion, o con 'python scripts/buscar_fotos.py --preseleccionar'. "
            "Guarda la direccion de la foto y su atribucion (autor y licencia), que hay "
            "que respetar. La foto en si NO se guarda aqui: se descarga a datos/imagenes/ "
            "la primera vez que hace falta."
        )
    }
    for clave in sorted(elecciones):
        contenido[clave] = elecciones[clave]

    config.ARCHIVO_IMAGENES.parent.mkdir(parents=True, exist_ok=True)
    with open(config.ARCHIVO_IMAGENES, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def ruta_de(receta: Receta) -> Path:
    """Donde se guarda la foto descargada de esta receta."""
    return config.DIR_IMAGENES / f"plato_{receta.id}.jpg"


def obtener(
    receta: Receta,
    elecciones: dict[str, dict],
    ingredientes: dict[str, Ingrediente],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
) -> tuple[Path | None, str]:
    """Devuelve (ruta de la imagen, tipo) para enseniar en la web.

    El tipo es "plato" o "collage", y sirve para saber si hay que enseniar la
    atribucion debajo (las fotos de plato son de otra gente; los collages se
    montan con las fotos de producto de Mercadona).

    El orden de preferencia es:
      1. La foto de plato que elegiste, ya descargada.
      2. La foto de plato que elegiste, descargandola ahora.
      3. El collage de productos.
    """
    eleccion = elecciones.get(receta.id)

    if eleccion and eleccion.get("url"):
        ruta = ruta_de(receta)
        if ruta.exists():
            return ruta, "plato"
        if _descargar(eleccion["url"], ruta):
            return ruta, "plato"
        # Si la descarga falla (sin internet, foto borrada del origen), no se
        # rompe nada: se cae al collage y ya se reintentará otro día.

    return collage.obtener(receta, ingredientes, emparejamientos, productos), "collage"


def _descargar(url: str, destino: Path) -> bool:
    """Baja la foto y la guarda tal cual. Devuelve si ha salido bien.

    NO se toca la imagen: ni recortar, ni redimensionar, ni escribir encima.
    Muchas de estas fotos tienen licencia "sin obras derivadas" y modificarlas
    seria incumplirla. El tamano de presentacion lo pone el CSS.

    Reintenta si falla, y ese detalle no es un adorno: la primera version se
    rendia al primer fallo y caia al collage sin decir nada. Cuando se anadio
    Wikipedia como fuente, descargar 55 fotos de golpe hacia que Wikimedia
    respondiera 429 (demasiadas peticiones) a partir de la cuarta, y TODAS
    esas recetas se quedaban con el collage sin que nadie supiera por que.

    Un fallo pasajero tratado como definitivo es de los peores errores que
    puede tener un programa, porque no da la cara: parece que "simplemente no
    hay foto".
    """
    for intento in range(1, REINTENTOS + 1):
        try:
            respuesta = requests.get(
                url, headers=CABECERAS, timeout=config.TIMEOUT_SEGUNDOS
            )

            # 429 = demasiadas peticiones. 5xx = el servidor tiene un problema.
            # Los dos son pasajeros: se espera un poco mas y se vuelve a probar.
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                if intento < REINTENTOS:
                    time.sleep(ESPERA_BASE * intento)
                    continue
                return False

            respuesta.raise_for_status()
            if not respuesta.headers.get("Content-Type", "").startswith("image/"):
                return False

            destino.parent.mkdir(parents=True, exist_ok=True)
            # Se escribe primero en un archivo temporal y luego se renombra. Si
            # el programa se corta a medio guardar, no queda un .jpg a medias
            # que luego pareceria valido y se veria roto para siempre.
            temporal = destino.with_suffix(".parcial")
            temporal.write_bytes(respuesta.content)
            temporal.replace(destino)
            return True

        except requests.RequestException:
            if intento < REINTENTOS:
                time.sleep(ESPERA_BASE * intento)
                continue
            return False
        except OSError:
            return False

    return False


def descargar_todas(
    recetas: dict[str, Receta], elecciones: dict[str, dict], pausa: float = 0.4
) -> tuple[int, list[str]]:
    """Se baja de golpe todas las fotos elegidas que falten.

    Devuelve (cuantas bajadas, nombres de las que fallaron).

    Existe para poder hacerlo con calma y una pausa entre descargas, en vez de
    que la web las pida todas a la vez la primera vez que abres una pagina con
    treinta recetas, que es justo lo que provoca el 429.
    """
    bajadas = 0
    fallos = []

    for id_receta, eleccion in elecciones.items():
        receta = recetas.get(id_receta)
        if receta is None or not eleccion.get("url"):
            continue
        ruta = ruta_de(receta)
        if ruta.exists():
            continue

        if _descargar(eleccion["url"], ruta):
            bajadas += 1
        else:
            fallos.append(receta.nombre)
        time.sleep(pausa)

    return bajadas, fallos
