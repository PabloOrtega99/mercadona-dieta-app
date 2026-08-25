"""Busca emparejamientos sospechosos comparando precios por kilo.

    python scripts/comprobar_precios.py

Por que existe: el emparejamiento automatico funciona por texto, y el texto
enga�a. En las pruebas nos paso que la "cebolla" acabara emparejada con un bote
de CEBOLLA MOLIDA. El nombre encajaba perfectamente, asi que ningun filtro de
palabras lo detectaba. Solo se vio porque salio la foto del bote en el collage
de una receta, y eso es pura suerte.

La senal que si delata esos casos es el PRECIO POR KILO. Un ingrediente
emparejado con el producto equivocado casi siempre esta desproporcionadamente
caro (la cebolla molida cuesta 20 veces mas por kilo que la cebolla) o
sospechosamente barato.

Este script compara cada ingrediente con lo tipico de su grupo de alimento y
saca los que se salen. No decide nada: te da una lista corta para que la mires
tu, que es justo lo que hace falta cuando no puedes revisar 105 filas a mano.
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import recetario  # noqa: E402
from app.mercadona import catalogo  # noqa: E402
from app.planificador import emparejador  # noqa: E402
from app.planificador.cesta import gramos_por_envase  # noqa: E402

# Cuantas veces por encima o por debajo de la mediana de su grupo tiene que
# estar un ingrediente para que lo marquemos como sospechoso.
VECES_CARO = 4.0
VECES_BARATO = 6.0

# Precio por kilo por encima del cual algo huele mal, sea del grupo que sea.
# Las especias estan legitimamente por encima, por eso se saltan el aviso.
TECHO_ABSOLUTO = 25.0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ingredientes = recetario.cargar_ingredientes()
    emparejamientos = emparejador.cargar_emparejamientos()
    if not emparejamientos:
        print("No hay emparejamientos. Ejecuta primero:")
        print("    python scripts/revisar_emparejamientos.py --regenerar")
        return 1

    conexion = catalogo.abrir()

    # Precio por kilo del producto elegido para cada ingrediente.
    precios: dict[str, float] = {}
    for id_ingrediente, ingrediente in ingredientes.items():
        ids = emparejamientos.get(id_ingrediente, {}).get("productos", [])
        if not ids:
            continue
        producto = catalogo.obtener(conexion, ids[0])
        if producto is None:
            continue
        tamano = gramos_por_envase(producto, ingrediente)
        if not tamano:
            continue
        precios[id_ingrediente] = float(producto["precio"]) / tamano * 1000

    # La mediana de cada grupo. Usamos mediana y no media porque la media se
    # deja arrastrar por un solo valor disparatado, que es exactamente lo que
    # estamos buscando: si el error contaminase la referencia, se escondería
    # a sí mismo.
    por_grupo: dict[str, list[float]] = {}
    for id_ingrediente, precio in precios.items():
        por_grupo.setdefault(ingredientes[id_ingrediente].grupo, []).append(precio)
    medianas = {
        grupo: statistics.median(valores)
        for grupo, valores in por_grupo.items()
        if len(valores) >= 3
    }

    print("=" * 78)
    print("  REVISION DE PRECIOS POR KILO")
    print("=" * 78)
    print("\n  Precio tipico (mediana) de cada grupo:")
    for grupo in sorted(medianas):
        print(f"    {grupo:<14} {medianas[grupo]:>7.2f} EUR/kg   ({len(por_grupo[grupo])} ingredientes)")

    sospechosos = []
    for id_ingrediente, precio in precios.items():
        ingrediente = ingredientes[id_ingrediente]
        # Las especias son caras por kilo por naturaleza: se compran a gramos.
        if ingrediente.grupo == "condimento":
            continue

        mediana = medianas.get(ingrediente.grupo)
        motivo = None
        if mediana and precio > mediana * VECES_CARO:
            motivo = f"{precio / mediana:.0f}x mas caro que su grupo"
        elif mediana and precio < mediana / VECES_BARATO:
            motivo = f"{mediana / precio:.0f}x mas barato que su grupo"
        elif precio > TECHO_ABSOLUTO and ingrediente.grupo not in ("pescado", "fruto_seco"):
            motivo = f"pasa de {TECHO_ABSOLUTO:.0f} EUR/kg"

        if motivo:
            ids = emparejamientos[id_ingrediente]["productos"]
            producto = catalogo.obtener(conexion, ids[0])
            sospechosos.append((precio, ingrediente, producto["nombre"], motivo))

    print()
    if sospechosos:
        print("=" * 78)
        print(f"  {len(sospechosos)} EMPAREJAMIENTOS PARA REVISAR")
        print("=" * 78)
        for precio, ingrediente, nombre, motivo in sorted(sospechosos, reverse=True):
            print(f"\n  {ingrediente.nombre}  ({ingrediente.grupo})")
            print(f"    -> {nombre}")
            print(f"       {precio:.2f} EUR/kg  --  {motivo}")
        print("\n  Si alguno esta mal, anade palabras a 'excluir' en ingredientes.json")
        print("  y vuelve a ejecutar revisar_emparejamientos.py --regenerar")
    else:
        print("=" * 78)
        print("  Ningun emparejamiento se sale de lo normal.")
        print("=" * 78)

    conexion.close()
    # Devolvemos 0 aunque haya sospechosos: son avisos para mirar, no errores.
    return 0


if __name__ == "__main__":
    sys.exit(main())
