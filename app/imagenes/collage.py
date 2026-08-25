"""Monta la imagen de cada receta con las fotos reales de sus ingredientes.

El problema: nuestro recetario es nuestro, asi que no tenemos fotos de los
platos. Buscar sesenta fotos de platos con licencia libre y pegarlas a mano
seria un trabajo aburrido y los enlaces acabarian rompiendose con el tiempo.

La solucion: la API de Mercadona SI nos da una foto de cada producto. Asi que
cogemos las fotos de los ingredientes principales de la receta y montamos un
mosaico. Siempre funciona, no depende de nadie mas y ademas encaja
visualmente con la lista de la compra, que lleva esas mismas fotos.

Las imagenes se guardan en datos/imagenes/ y se generan una sola vez.
"""

import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from app import config
from app.planificador.cesta import elegir_producto
from app.recetario import Ingrediente, Receta

# Tamaño final de la imagen, en píxeles. Es un cuadrado de 2x2 fotos.
LADO = 600
# Alto de la franja de abajo donde va el nombre de la receta.
ALTO_BANDA = 84

# Colores, en RGB.
FONDO = (243, 240, 234)
BANDA = (28, 32, 38)
TEXTO = (255, 255, 255)
BORDE = (255, 255, 255)


def ruta_de(receta: Receta) -> Path:
    """Donde vive (o vivira) la imagen de esta receta."""
    return config.DIR_IMAGENES / f"{receta.id}.png"


def obtener(
    receta: Receta,
    ingredientes: dict[str, Ingrediente],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
) -> Path | None:
    """Devuelve la ruta de la imagen, generandola si hace falta.

    Si ya existe, se devuelve tal cual: montar el collage implica descargar
    cuatro fotos de internet, y no tiene ningun sentido repetirlo cada vez que
    alguien abre la pagina.
    """
    ruta = ruta_de(receta)
    if ruta.exists():
        return ruta

    urls = _fotos_de_ingredientes(receta, ingredientes, emparejamientos, productos)
    if not urls:
        return None

    try:
        imagen = _montar(urls, receta.nombre)
    except Exception:
        # Que falle una imagen no puede tirar abajo la página entera. Sin
        # foto se ve peor, pero el menú y la lista de la compra, que es lo
        # que de verdad importa, siguen ahí.
        return None

    config.DIR_IMAGENES.mkdir(parents=True, exist_ok=True)
    imagen.save(ruta, "PNG")
    return ruta


def _fotos_de_ingredientes(
    receta: Receta,
    ingredientes: dict[str, Ingrediente],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
) -> list[str]:
    """Las urls de las fotos de los 4 ingredientes principales.

    "Principales" significa los que mas pesan en la receta, dejando fuera los
    condimentos y la despensa: una foto del bote de sal no le dice nada a
    nadie sobre que plato es este.
    """
    candidatos = []
    for item in receta.ingredientes:
        ingrediente = ingredientes.get(item.id)
        if ingrediente is None or ingrediente.despensa:
            continue
        if ingrediente.grupo == "condimento":
            continue
        candidatos.append((item.gramos, ingrediente))

    # De más gramos a menos.
    candidatos.sort(key=lambda par: -par[0])

    urls = []
    for gramos, ingrediente in candidatos:
        emparejamiento = emparejamientos.get(ingrediente.id, {})
        opciones = [
            productos[id_producto]
            for id_producto in emparejamiento.get("productos", [])
            if id_producto in productos
        ]
        producto = elegir_producto(opciones, ingrediente, gramos)
        if producto and producto.get("url_imagen"):
            urls.append(producto["url_imagen"])
        if len(urls) == 4:
            break

    return urls


def _montar(urls: list[str], titulo: str) -> Image.Image:
    """Descarga las fotos y las coloca en un mosaico 2x2 con su titulo."""
    lienzo = Image.new("RGB", (LADO, LADO + ALTO_BANDA), FONDO)

    mitad = LADO // 2
    # Las cuatro esquinas donde va cada foto.
    posiciones = [(0, 0), (mitad, 0), (0, mitad), (mitad, mitad)]

    for indice, posicion in enumerate(posiciones):
        # Si la receta tiene menos de 4 ingredientes principales, se repiten
        # las fotos que haya en vez de dejar huecos blancos.
        url = urls[indice % len(urls)]
        foto = _descargar(url)
        if foto is None:
            continue
        foto = _recortar_cuadrado(foto, mitad)
        lienzo.paste(foto, posicion)

    # Líneas blancas de separación entre las cuatro fotos, para que se vea
    # que son cuatro y no una sola imagen confusa.
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.line([(mitad, 0), (mitad, LADO)], fill=BORDE, width=4)
    dibujo.line([(0, mitad), (LADO, mitad)], fill=BORDE, width=4)

    # La banda con el nombre de la receta.
    dibujo.rectangle([(0, LADO), (LADO, LADO + ALTO_BANDA)], fill=BANDA)
    _escribir_titulo(dibujo, titulo)

    return lienzo


def _descargar(url: str) -> Image.Image | None:
    """Baja una foto de internet y la convierte en imagen manipulable."""
    try:
        respuesta = requests.get(url, timeout=config.TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
        # BytesIO hace que los bytes descargados se comporten como si fueran un
        # archivo, que es lo que Pillow espera recibir. Así nos ahorramos
        # guardar la foto en disco solo para volver a leerla.
        return Image.open(io.BytesIO(respuesta.content)).convert("RGB")
    except Exception:
        return None


def _recortar_cuadrado(imagen: Image.Image, lado: int) -> Image.Image:
    """Recorta la imagen a un cuadrado centrado y la escala al tamano pedido.

    Recortamos en vez de deformar: estirar una foto rectangular hasta hacerla
    cuadrada deja los productos con una pinta rarisima.
    """
    ancho, alto = imagen.size
    corte = min(ancho, alto)
    izquierda = (ancho - corte) // 2
    arriba = (alto - corte) // 2
    imagen = imagen.crop((izquierda, arriba, izquierda + corte, arriba + corte))
    return imagen.resize((lado, lado), Image.LANCZOS)


def _escribir_titulo(dibujo: ImageDraw.ImageDraw, titulo: str) -> None:
    """Escribe el nombre de la receta centrado en la banda de abajo."""
    fuente = _fuente(30)

    # Si el nombre no cabe, lo cortamos y le ponemos puntos suspensivos.
    texto = titulo
    while _ancho(dibujo, texto, fuente) > LADO - 48 and len(texto) > 4:
        texto = texto[:-1]
    if texto != titulo:
        texto = texto[:-1] + "…"

    ancho = _ancho(dibujo, texto, fuente)
    x = (LADO - ancho) // 2
    y = LADO + (ALTO_BANDA - 34) // 2
    dibujo.text((x, y), texto, fill=TEXTO, font=fuente)


def _fuente(tamano: int):
    """Busca una tipografia decente; si no la hay, usa la de serie de Pillow.

    Pillow no trae tipografias: usa las del sistema. Como este proyecto es
    para Windows, probamos con las de Windows, pero si no aparecen tiramos de
    la de serie, que es fea pero funciona en cualquier sitio.
    """
    for nombre in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default()


def _ancho(dibujo: ImageDraw.ImageDraw, texto: str, fuente) -> int:
    """Cuantos pixeles ocupa de ancho un texto con esa tipografia."""
    izquierda, _, derecha, _ = dibujo.textbbox((0, 0), texto, font=fuente)
    return derecha - izquierda
