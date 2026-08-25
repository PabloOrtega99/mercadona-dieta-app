"""Revisa que ingredientes.json y recetas.json esten bien.

Ejecutalo SIEMPRE despues de editar a mano cualquiera de esos dos archivos:

    python scripts/comprobar_datos.py

Te dira si te has dejado una coma, si has escrito mal el id de un ingrediente
o si has marcado como vegana una receta que lleva queso.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import recetario  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("  COMPROBANDO LOS DATOS")
    print("=" * 70)

    # Primero cargar. Si el JSON está mal escrito, esto ya falla aquí y con un
    # mensaje que dice el archivo y la línea del problema.
    try:
        ingredientes = recetario.cargar_ingredientes()
        recetas = recetario.cargar_recetas()
    except recetario.ErrorDatos as error:
        print(f"\n  ERROR AL LEER LOS ARCHIVOS:\n  {error}")
        return 1

    print(f"\n  {len(ingredientes)} ingredientes")
    print(f"  {len(recetas)} recetas")

    # Cuántas recetas hay por dieta: si alguna se queda corta, los menús de esa
    # dieta saldrán repetitivos.
    print("\n  Recetas disponibles por dieta:")
    for dieta in recetario.DIETAS:
        cuantas = sum(1 for receta in recetas.values() if receta.vale_para(dieta))
        print(f"    {recetario.NOMBRES_DIETAS[dieta]:<28} {cuantas:3}")

    # Ingredientes que no usa ninguna receta: no es un error, pero es peso
    # muerto que conviene saber que está ahí.
    usados = {item.id for receta in recetas.values() for item in receta.ingredientes}
    sin_usar = sorted(set(ingredientes) - usados)
    if sin_usar:
        print(f"\n  {len(sin_usar)} ingredientes definidos que ninguna receta usa:")
        print(f"    {', '.join(sin_usar)}")

    # Ahora las comprobaciones de coherencia de verdad.
    problemas = recetario.comprobar(ingredientes, recetas)

    print()
    if problemas:
        print("=" * 70)
        print(f"  {len(problemas)} PROBLEMAS ENCONTRADOS")
        print("=" * 70)
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    print("=" * 70)
    print("  TODO CORRECTO")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
