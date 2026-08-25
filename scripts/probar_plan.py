"""Genera un plan desde la terminal, para comprobar que las cuentas salen.

    python scripts/probar_plan.py                       (usa los casos de prueba)
    python scripts/probar_plan.py 80 2 1 equilibrada    (presupuesto semanas personas dieta)

Sirve para revisar el algoritmo sin pasar por la web. Ensena la cesta con sus
subtotales, para que puedas coger la calculadora y verificar que la suma
cuadra con el total.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, datos_app  # noqa: E402
from app.planificador import planificador  # noqa: E402
from app.utiles import formato_euros  # noqa: E402

# Casos de prueba que cubren lo normal y lo que puede salir mal.
CASOS = [
    (60, 1, 1, "equilibrada", False),
    (60, 1, 1, "equilibrada", True),  # el mismo, pero con la despensa ya en casa
    (200, 4, 2, "proteina", False),
    (90, 2, 1, "vegana", False),
    (15, 4, 1, "equilibrada", False),  # presupuesto imposible a proposito
]


def probar(datos, presupuesto, semanas, personas, dieta, despensa_en_casa=False) -> None:
    print("\n" + "=" * 78)
    print(
        f"  {formato_euros(presupuesto)} | {semanas} semana(s) | "
        f"{personas} persona(s) | dieta {dieta}"
        f"{' | despensa ya en casa' if despensa_en_casa else ''}"
    )
    print("=" * 78)

    plan = planificador.generar_plan(
        presupuesto=presupuesto,
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        ingredientes=datos.ingredientes,
        recetas=datos.recetas,
        emparejamientos=datos.emparejamientos,
        productos=datos.productos,
        basicos=datos.basicos,
        con_desayunos=True,
        despensa_en_casa=despensa_en_casa,
    )

    # --- Las recetas elegidas ---
    raciones = sum(elegida.raciones_totales for elegida in plan.elegidas)
    print(f"\n  RECETAS ({len(plan.elegidas)} distintas, {raciones} raciones):")
    for elegida in plan.elegidas:
        veces = f" x{elegida.veces}" if elegida.veces > 1 else "  "
        print(f"    {elegida.receta.nombre[:44]:<44}{veces}  {elegida.raciones_totales:>3} raciones")

    # --- La lista de la compra ---
    lineas = plan.cesta.lineas_de_compra()
    print(f"\n  LISTA DE LA COMPRA ({len(lineas)} productos):")
    suma_comprobacion = 0.0
    for linea in sorted(lineas, key=lambda l: -l["coste_imputado"]):
        if linea["sin_producto"]:
            print(f"    !! {linea['ingrediente'].nombre}: sin producto asociado")
            continue
        suma_comprobacion += linea["coste_imputado"]
        if linea["ingrediente"].despensa:
            marca = " (despensa, ya la tienes)" if not linea["se_cobra"] else " (despensa)"
        else:
            marca = ""
        print(
            f"    {linea['unidades']:>2} x {linea['producto']['nombre'][:40]:<40} "
            f"{formato_euros(linea['coste']):>9}{marca}"
        )

    # --- Los numeros ---
    print(f"\n  {'TOTAL DE LA COMPRA':<38} {formato_euros(plan.coste_total):>10}")
    print(f"  {'Presupuesto':<38} {formato_euros(plan.presupuesto):>10}")
    print(f"  {'Sobra':<38} {formato_euros(plan.dinero_sobrante):>10}")
    print(f"  {'(de eso, despensa)':<38} {formato_euros(plan.coste_despensa):>10}")

    # Comprobacion aritmetica: la suma de las lineas tiene que ser el total.
    # Si esto falla es que hay un error en el calculo, no un redondeo.
    diferencia = abs(suma_comprobacion - plan.coste_total)
    estado = "OK" if diferencia < 0.01 else f"!! DESCUADRE DE {diferencia:.4f}"
    print(f"\n  Comprobacion suma de lineas = total: {estado}")

    # --- Comidas cubiertas ---
    huecos = sum(
        1 for fila in plan.menu for momento in ("comida", "cena") if fila[momento] is None
    )
    print(f"  Comidas del periodo: {plan.comidas_totales} | sin cubrir: {huecos}")

    # --- Nutricion ---
    print(
        f"  Nutricion/dia: {plan.kcal_dia:.0f} kcal "
        f"(objetivo {config.KCAL_OBJETIVO_DIA}) | "
        f"P {plan.proteina_dia:.0f} g | H {plan.hidratos_dia:.0f} g | G {plan.grasa_dia:.0f} g"
    )

    if plan.presupuesto_insuficiente:
        print(
            f"\n  AVISO: no cabe en el presupuesto. "
            f"Harian falta al menos {formato_euros(plan.coste_total)}."
        )

    # --- Comprobacion de dieta ---
    # En vegana y vegetariana, ni un solo ingrediente puede incumplir.
    if dieta in ("vegana", "vegetariana"):
        atributo = "vegano" if dieta == "vegana" else "vegetariano"
        intrusos = [
            linea["ingrediente"].nombre
            for linea in lineas
            if not getattr(linea["ingrediente"], atributo)
        ]
        if intrusos:
            print(f"\n  !! FALLO DE DIETA: la cesta lleva {', '.join(intrusos)}")
        else:
            print(f"  Comprobacion dieta {dieta}: OK, ningun ingrediente incumple.")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        datos = datos_app.cargar_todo()
    except datos_app.ErrorPreparacion as error:
        print(f"\nFALTA UN PASO PREVIO:\n{error}\n")
        return 1

    print(f"Catalogo: {datos.total_productos} productos ({datos.catalogo_actualizado})")
    print(f"Recetario: {len(datos.recetas)} recetas, {len(datos.ingredientes)} ingredientes")

    if len(sys.argv) >= 5:
        casos = [(float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], False)]
    else:
        casos = CASOS

    for caso in casos:
        probar(datos, *caso)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
