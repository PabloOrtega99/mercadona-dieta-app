"""Busca fotos de plato para las recetas en bancos de imagenes libres.

    python scripts/buscar_fotos.py                  <- solo buscar candidatas
    python scripts/buscar_fotos.py --preseleccionar <- buscar y elegir la primera
    python scripts/buscar_fotos.py --solo-nuevas    <- saltarse las que ya tienen foto

Las candidatas se guardan en datos/candidatas_fotos.json para que la pantalla
/fotos de la aplicacion pueda ensenartelas al instante, sin volver a llamar a
internet cada vez que abres la pagina.

Tarda unos minutos: son dos peticiones por receta con pausa entre medias.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, recetario  # noqa: E402
from app.imagenes import buscador, fotos  # noqa: E402

CANDIDATAS_POR_RECETA = 6

# Puntuacion minima para que una foto se ponga SOLA, sin que la mires tu.
#
# Con el liston en 1 valia con que la foto compartiera UNA palabra concreta
# con la receta, y eso deja pasar cosas como "Curry Club Indian Restaurant"
# para un curry de verduras, o una foto de un arrozal para el arroz tres
# delicias. Con 3 hacen falta dos coincidencias, o una coincidencia mas el
# plus de venir de Wikipedia.
#
# Las que no llegan se quedan con el collage de productos, que siempre se ve
# bien, y las puedes cambiar en /fotos. Es preferible eso a una foto que
# confunde: en una lista de recetas, una foto equivocada llama mas la
# atencion que veinte correctas.
RELEVANCIA_MINIMA = 3


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    preseleccionar = "--preseleccionar" in sys.argv
    solo_nuevas = "--solo-nuevas" in sys.argv

    recetas = recetario.cargar_recetas()
    elecciones = fotos.cargar_elecciones()
    candidatas = _cargar_candidatas()

    pendientes = [
        receta
        for receta in recetas.values()
        if not (solo_nuevas and receta.id in candidatas and candidatas[receta.id])
    ]

    print("=" * 70)
    print("  BUSCANDO FOTOS DE PLATO")
    print(f"  {len(pendientes)} recetas por buscar de {len(recetas)}")
    print("=" * 70)

    sin_resultados = []

    # Fotos que ya estan asignadas a alguna receta. Sirve para no repetir.
    #
    # Hizo falta porque en la primera pasada 26 recetas acabaron compartiendo
    # foto con otra: las cinco ensaladas tenian la misma, las cuatro cremas
    # tambien. Aunque la foto encaje, ver el mismo plato repetido en el menu
    # deja claro que las fotos no son de verdad de esas recetas.
    usadas = {e["url"] for e in elecciones.values() if e.get("url")}

    for numero, receta in enumerate(sorted(pendientes, key=lambda r: r.nombre), start=1):
        encontradas = buscador.buscar_candidatas(receta.nombre, CANDIDATAS_POR_RECETA)
        candidatas[receta.id] = encontradas

        # Para PRESELECCIONAR solo valen las que coinciden de verdad con el
        # nombre de la receta. Las de relevancia cero se guardan igualmente
        # como candidatas (por si al revisarlas encuentras la buena), pero no
        # se ponen solas: mas vale el collage de productos que una foto que
        # no tiene nada que ver.
        buenas = [c for c in encontradas if c.get("relevancia", 0) >= RELEVANCIA_MINIMA]

        if not buenas:
            sin_resultados.append(receta.nombre)
        elif preseleccionar and not elecciones.get(receta.id, {}).get("revisada"):
            # La mejor que no este ya puesta en otra receta. Si todas estan
            # cogidas, se repite antes que quedarse sin foto.
            elegida = next((c for c in buenas if c["url"] not in usadas), buenas[0])
            elecciones[receta.id] = elegida
            usadas.add(elegida["url"])

        print(
            f"  [{numero:3}/{len(pendientes)}] {receta.nombre[:44]:<44} "
            f"{len(encontradas)} candidatas   ",
            end="\r",
            flush=True,
        )

        # Se guarda sobre la marcha, no al final. Son varios minutos de
        # peticiones: si se corta a mitad (o lo paras tú), no se pierde lo
        # que ya se había buscado.
        if numero % 10 == 0:
            _guardar_candidatas(candidatas)

    print()
    _guardar_candidatas(candidatas)
    if preseleccionar:
        fotos.guardar_elecciones(elecciones)

    # Descargar aqui, con calma y una pausa entre fotos, en vez de dejar que
    # la web las pida todas de golpe la primera vez que abras una pagina con
    # treinta recetas. Wikimedia responde 429 si le llueven las peticiones.
    if preseleccionar:
        print("\nDescargando las fotos elegidas...")
        bajadas, fallos = fotos.descargar_todas(recetas, elecciones)
        print(f"  {bajadas} fotos descargadas a datos/imagenes/")
        if fallos:
            print(f"  {len(fallos)} no se pudieron bajar (usaran el collage de momento):")
            for nombre in fallos[:8]:
                print(f"    - {nombre}")

    con_fotos = sum(1 for v in candidatas.values() if v)
    print("\n" + "=" * 70)
    print(f"  {con_fotos} recetas con candidatas, {len(elecciones)} con foto elegida.")
    if sin_resultados:
        print(f"\n  {len(sin_resultados)} sin ninguna candidata:")
        for nombre in sin_resultados[:15]:
            print(f"    - {nombre}")
        print("  Esas seguiran usando el collage de productos.")
    print("\n  Revisa y cambia las que no te gusten en:  http://localhost:8000/fotos")
    print("=" * 70)
    return 0


def _cargar_candidatas() -> dict[str, list]:
    if not config.ARCHIVO_CANDIDATAS.exists():
        return {}
    with open(config.ARCHIVO_CANDIDATAS, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _guardar_candidatas(candidatas: dict[str, list]) -> None:
    config.ARCHIVO_CANDIDATAS.parent.mkdir(parents=True, exist_ok=True)
    with open(config.ARCHIVO_CANDIDATAS, "w", encoding="utf-8") as archivo:
        json.dump(candidatas, archivo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
