"""Carga TODOS los datos que necesita la aplicacion, de una vez.

Existe para que la web, los scripts de prueba y cualquier otra cosa que
hagamos manana no tengan que repetir la misma secuencia de cinco pasos
("abre la base de datos, carga los ingredientes, carga las recetas, carga los
emparejamientos, precalcula las calorias"). Se llama a cargar_todo() y ya.

Es tambien donde se detectan y se explican los errores de "todavia no has
preparado esto": si falta el catalogo o los emparejamientos, aqui salta un
mensaje que dice exactamente que comando hay que ejecutar.
"""

from dataclasses import dataclass

from app import recetario
from app.imagenes import fotos
from app.mercadona import catalogo
from app.planificador import emparejador, planificador
from app.recetario import Ingrediente, Receta


class ErrorPreparacion(Exception):
    """Falta algun paso previo. El mensaje dice cual y como arreglarlo."""


@dataclass
class DatosApp:
    """Todo lo que la aplicacion necesita tener a mano."""

    ingredientes: dict[str, Ingrediente]
    recetas: dict[str, Receta]
    emparejamientos: dict[str, dict]
    productos: dict[str, dict]
    basicos: list[dict]
    # Que foto de plato usa cada receta. Se puede cambiar mientras la app está
    # arrancada desde la pantalla /fotos, por eso no es de solo lectura.
    imagenes: dict[str, dict]
    total_productos: int
    catalogo_actualizado: str | None


def cargar_todo() -> DatosApp:
    """Carga y prepara todo. Lanza ErrorPreparacion si falta algun paso."""

    ingredientes = recetario.cargar_ingredientes()
    recetas = recetario.cargar_recetas()
    basicos = recetario.cargar_basicos()

    conexion = catalogo.abrir()
    try:
        total = catalogo.contar(conexion)
        if total == 0:
            raise ErrorPreparacion(
                "El catalogo de Mercadona esta vacio.\n"
                "Ejecuta:  python scripts/actualizar_catalogo.py"
            )

        emparejamientos = emparejador.cargar_emparejamientos()
        if not emparejamientos:
            raise ErrorPreparacion(
                "Todavia no se han emparejado los ingredientes con los productos.\n"
                "Ejecuta:  python scripts/revisar_emparejamientos.py --regenerar"
            )

        productos = emparejador.cargar_productos_usados(conexion, emparejamientos)
        actualizado = catalogo.fecha_actualizacion(conexion)
    finally:
        conexion.close()

    # Las calorías y el coste por ración se calculan una vez aquí y quedan
    # guardados. El planificador consulta las calorías miles de veces por menú,
    # y el coste lo necesita la pantalla de selección para todas las recetas a
    # la vez.
    planificador.precalcular_calorias(recetas, ingredientes)
    planificador.precalcular_costes(recetas, ingredientes, emparejamientos, productos)

    return DatosApp(
        ingredientes=ingredientes,
        recetas=recetas,
        emparejamientos=emparejamientos,
        productos=productos,
        basicos=basicos,
        imagenes=fotos.cargar_elecciones(),
        total_productos=total,
        catalogo_actualizado=actualizado,
    )
