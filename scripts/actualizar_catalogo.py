"""Descarga el catálogo completo de Mercadona y lo guarda en la base de datos.

Este es EL script que mantiene la app al día. Ejecútalo cuando quieras precios
frescos (una vez a la semana está bien):

    python scripts/actualizar_catalogo.py

Tarda unos 3 minutos: son 151 peticiones con una pausa entre medias para no
machacar el servidor de Mercadona.
"""

import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Este bloque hace falta porque el script vive en scripts/ pero necesita
# importar código de app/. Sin esto, Python busca "app" solo en la carpeta
# scripts/, no lo encuentra, y falla con "ModuleNotFoundError: No module
# named 'app'".
#
# Lo que hacemos es añadir la carpeta raíz del proyecto a la lista de sitios
# donde Python busca módulos. parents[1] es "subir un nivel desde scripts/".
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402  (el import va aquí a propósito, tras el sys.path)
from app.mercadona import catalogo, cliente  # noqa: E402


def main() -> int:
    """Descarga todo el catálogo. Devuelve 0 si fue bien, 1 si falló.

    Devolver un número es la forma estándar de que un programa le diga al
    sistema si terminó bien (0) o mal (cualquier otro número).
    """
    # En Windows, cuando la salida del programa se redirige a un archivo,
    # Python usa una codificación antigua que no sabe escribir tildes ni
    # símbolos, y el programa revienta al hacer un simple print. Esto lo evita.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("  ACTUALIZANDO EL CATALOGO DE MERCADONA")
    print(f"  Almacen: {config.ALMACEN}   (se cambia en app/config.py)")
    print("=" * 70)

    # --- Paso 1: pedir el mapa de categorías -------------------------------
    print("\n[1/3] Pidiendo la lista de categorias...")
    try:
        categorias = cliente.obtener_arbol_categorias()
    except cliente.ErrorMercadona as error:
        print(f"\n  ERROR: {error}")
        print("  Comprueba que tienes internet y que tienda.mercadona.es funciona.")
        return 1

    # Aplanamos el árbol de dos niveles en una lista simple de subcategorías,
    # arrastrando el nombre de la categoría padre para no perderlo.
    subcategorias = [
        (sub["id"], categoria["nombre"], sub["nombre"])
        for categoria in categorias
        for sub in categoria["subcategorias"]
    ]
    print(f"      {len(categorias)} categorias, {len(subcategorias)} subcategorias.")

    # --- Paso 2: recorrer las subcategorías --------------------------------
    segundos = len(subcategorias) * config.PAUSA_ENTRE_PETICIONES
    print(f"\n[2/3] Descargando productos (unos {segundos / 60:.0f}-{segundos / 60 + 2:.0f} minutos)...")

    productos: list[dict] = []
    fallos: list[str] = []
    sin_tamano: list[str] = []

    # enumerate(..., start=1) nos da el número de vuelta empezando en 1, para
    # poder enseñar "37/151" por pantalla.
    for numero, (id_sub, nombre_cat, nombre_sub) in enumerate(subcategorias, start=1):
        try:
            encontrados = cliente.obtener_productos_de_subcategoria(
                id_sub, nombre_cat, nombre_sub
            )
            productos.extend(encontrados)

            # Si algún producto no trae ni gramos ni unidades, es que su envase
            # viene en un formato que nuestro cliente no sabe interpretar.
            # Lo apuntamos para avisar al final en vez de fallar en silencio.
            # Estos productos se guardan igual, pero el planificador no podrá
            # usarlos porque no sabe cuánta comida traen.
            for producto in encontrados:
                if producto["gramos_envase"] is None and producto["unidades_envase"] is None:
                    sin_tamano.append(f"{producto['nombre']} ({nombre_sub})")

            # end="" evita el salto de línea y "\r" devuelve el cursor al
            # principio, así la línea se reescribe encima de sí misma en vez de
            # llenar la pantalla con 151 líneas.
            print(
                f"      [{numero:3}/{len(subcategorias)}] {nombre_sub[:42]:<42} "
                f"{len(encontrados):3} productos   ",
                end="\r",
                flush=True,
            )

        except cliente.ErrorMercadona as error:
            # Que falle una subcategoría no debe tirar abajo las otras 150.
            # Lo apuntamos y seguimos.
            fallos.append(f"{nombre_cat} > {nombre_sub}: {error}")

        time.sleep(config.PAUSA_ENTRE_PETICIONES)

    print()  # cerrar la línea que se estaba reescribiendo

    if not productos:
        print("\n  ERROR: no se ha descargado ningun producto. Nada que guardar.")
        return 1

    # --- Paso 3: guardar ----------------------------------------------------
    # Un mismo producto puede estar en varias subcategorías (el aceite de oliva
    # aparece en "Aceite" y en "Aceite, vinagre y sal"). Como el id es la clave
    # primaria de la tabla, intentar insertarlo dos veces daría error. Un
    # diccionario indexado por id se queda automáticamente con uno solo.
    unicos = {producto["id"]: producto for producto in productos}
    duplicados = len(productos) - len(unicos)

    print(f"\n[3/3] Guardando en {config.BD_CATALOGO}...")
    conexion = catalogo.abrir()
    try:
        guardados = catalogo.reemplazar_productos(conexion, list(unicos.values()))
    finally:
        # El "finally" se ejecuta pase lo que pase, también si hay un error.
        # Así la base de datos siempre queda cerrada limpiamente.
        conexion.close()

    # --- Resumen ------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"  LISTO: {guardados} productos guardados.")
    if duplicados:
        print(f"  ({duplicados} apariciones repetidas en varias categorias, unificadas)")
    if fallos:
        print(f"\n  {len(fallos)} subcategorias fallaron:")
        for fallo in fallos[:10]:
            print(f"    - {fallo}")
    if sin_tamano:
        print(f"\n  AVISO: {len(sin_tamano)} productos sin tamano de envase interpretable.")
        print("  Se guardan, pero el planificador no podra usarlos. Ejemplos:")
        for nombre in sin_tamano[:5]:
            print(f"    - {nombre}")
        print("  Si son muchos, revisa _convertir_tamano() en app/mercadona/cliente.py")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    # Esta condición significa "solo si me estás ejecutando directamente".
    # Si alguien importara este archivo desde otro, main() no se lanzaría solo.
    # sys.exit(...) le pasa al sistema el 0 o el 1 que devuelve main().
    sys.exit(main())
