"""Enseña con que producto de Mercadona se ha emparejado cada ingrediente.

    python scripts/revisar_emparejamientos.py              <- solo mirar
    python scripts/revisar_emparejamientos.py --regenerar  <- recalcular y guardar

REVISA ESTA TABLA DE VEZ EN CUANDO. El emparejamiento automatico funciona por
texto y acierta casi siempre, pero no siempre. Si ves algo raro (por ejemplo
que "pollo" se ha emparejado con un caldo), tienes dos formas de arreglarlo:

  a) Afinar el ingrediente en app/datos/ingredientes.json, anadiendo palabras
     a "excluir" o afinando "busqueda". Es la mejor solucion, porque arregla
     el problema de raiz.

  b) Editar app/datos/emparejamientos.json a mano, poner el id del producto
     que quieras y marcar "fijado": true para que no te lo pise la proxima
     regeneracion.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import recetario  # noqa: E402
from app.mercadona import catalogo  # noqa: E402
from app.planificador import emparejador  # noqa: E402
from app.planificador.cesta import gramos_por_envase  # noqa: E402
from app.utiles import formato_euros  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    regenerar = "--regenerar" in sys.argv

    ingredientes = recetario.cargar_ingredientes()
    conexion = catalogo.abrir()

    if catalogo.contar(conexion) == 0:
        print("La base de datos esta vacia. Ejecuta primero:")
        print("    python scripts/actualizar_catalogo.py")
        return 1

    anteriores = emparejador.cargar_emparejamientos()

    if regenerar:
        print("Regenerando emparejamientos...\n")
        emparejamientos, sin_producto = emparejador.regenerar(
            conexion, ingredientes, anteriores
        )
        emparejador.guardar_emparejamientos(emparejamientos)
    else:
        if not anteriores:
            print("Todavia no hay emparejamientos. Ejecuta:")
            print("    python scripts/revisar_emparejamientos.py --regenerar")
            return 1
        emparejamientos = anteriores
        sin_producto = [
            id_ing
            for id_ing in ingredientes
            if not emparejamientos.get(id_ing, {}).get("productos")
        ]

    # --- La tabla -----------------------------------------------------------
    print(f"{'INGREDIENTE':<26} {'PRODUCTO ELEGIDO':<44} {'ENVASE':>9} {'PRECIO':>9} {'EUR/KG':>9}")
    print("-" * 102)

    # Agrupamos por grupo de alimento para que la tabla se lea mejor: todas las
    # carnes juntas, todas las verduras juntas...
    por_grupo: dict[str, list] = {}
    for id_ingrediente, ingrediente in ingredientes.items():
        por_grupo.setdefault(ingrediente.grupo, []).append((id_ingrediente, ingrediente))

    fijados = 0
    for grupo in sorted(por_grupo):
        print(f"\n  -- {grupo.upper()} --")
        for id_ingrediente, ingrediente in sorted(por_grupo[grupo]):
            emparejamiento = emparejamientos.get(id_ingrediente, {})
            ids_producto = emparejamiento.get("productos", [])
            marca_fijado = " *" if emparejamiento.get("fijado") else "  "
            if emparejamiento.get("fijado"):
                fijados += 1

            if not ids_producto:
                print(f"{marca_fijado}{ingrediente.nombre[:24]:<24} {'!! SIN PRODUCTO':<44}")
                continue

            producto = catalogo.obtener(conexion, ids_producto[0])
            if producto is None:
                print(f"{marca_fijado}{ingrediente.nombre[:24]:<24} {'!! producto descatalogado':<44}")
                continue

            tamano = gramos_por_envase(producto, ingrediente) or 0
            precio_kg = (float(producto["precio"]) / tamano * 1000) if tamano else 0

            print(
                f"{marca_fijado}{ingrediente.nombre[:24]:<24} "
                f"{producto['nombre'][:44]:<44} "
                f"{tamano:>7.0f} g "
                f"{formato_euros(float(producto['precio'])):>9} "
                f"{precio_kg:>7.2f} €"
            )

    # --- Resumen ------------------------------------------------------------
    print("\n" + "=" * 102)
    print(f"  {len(ingredientes)} ingredientes | {fijados} fijados a mano (marcados con *)")

    if sin_producto:
        print(f"\n  {len(sin_producto)} INGREDIENTES SIN PRODUCTO:")
        for id_ingrediente in sin_producto:
            ingrediente = ingredientes[id_ingrediente]
            print(f"    - {ingrediente.nombre} (busca: {', '.join(ingrediente.busqueda)})")
        print("\n  Prueba a cambiar los terminos de 'busqueda' en ingredientes.json.")
        print("  Puedes ver como se llaman los productos de verdad en tienda.mercadona.es")

    print("=" * 102)
    conexion.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
