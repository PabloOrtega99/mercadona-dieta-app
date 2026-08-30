"""Carga los ingredientes y las recetas desde sus archivos JSON.

Este archivo hace de puerta de entrada a nuestros datos. Nadie mas en el
proyecto abre ingredientes.json ni recetas.json directamente: todos pasan por
aqui. Asi, si algun dia cambia el formato de esos archivos, solo hay que tocar
un sitio.

Ademas valida los datos al cargarlos, para que un error tonto (un ingrediente
mal escrito en una receta) salte enseguida y con un mensaje claro, en vez de
provocar un fallo raro tres archivos mas alla.
"""

import json
from dataclasses import dataclass, field

from app import config

# Las cuatro dietas que ofrece la app.
DIETAS = ("equilibrada", "proteina", "vegetariana", "vegana")

# Nombres bonitos para enseñar en la web.
NOMBRES_DIETAS = {
    "equilibrada": "Equilibrada / mediterránea",
    "proteina": "Alta en proteína",
    "vegetariana": "Vegetariana",
    "vegana": "Vegana",
}

# Niveles de dificultad, de menos a más.
DIFICULTADES = ("facil", "media", "elaborada")

NOMBRES_DIFICULTAD = {
    "facil": "Fácil",
    "media": "Media",
    "elaborada": "Elaborada",
}

# Los grupos de alimento que tiene sentido que alguien marque como "me gusta
# más esto". Son un subconjunto de los 12 valores de "grupo" que existen en
# ingredientes.json: se dejan fuera "condimento", "otro" y "grasa" porque son
# categorías técnicas o de despensa (el aceite, la sal...), no un gusto real
# que alguien vaya a marcar en un formulario.
GRUPOS_PREFERIBLES = (
    "carne",
    "pescado",
    "huevo",
    "lacteo",
    "legumbre",
    "verdura",
    "fruta",
    "cereal",
    "fruto_seco",
)

NOMBRES_GRUPOS = {
    "carne": "Carne",
    "pescado": "Pescado y marisco",
    "huevo": "Huevo",
    "lacteo": "Lácteos",
    "legumbre": "Legumbres",
    "verdura": "Verdura",
    "fruta": "Fruta",
    "cereal": "Cereales y pasta",
    "fruto_seco": "Frutos secos",
}


# ---------------------------------------------------------------------------
# LAS "CAJAS" DE DATOS
# ---------------------------------------------------------------------------
# @dataclass es un atajo de Python que convierte una clase en una simple caja
# de datos: le escribe por nosotros el constructor y unos cuantos métodos.
#
# ¿Por qué usar esto en vez de diccionarios sueltos?
#   - Se escribe ingrediente.kcal_100g en vez de ingrediente["kcal_100g"].
#   - Si te equivocas y escribes ingrediente.kcal_1000g, el error salta al
#     momento. Con un diccionario, obtendrías un KeyError mucho más adelante,
#     o peor, un None que se propaga en silencio.
#   - El editor te autocompleta los campos.
# ---------------------------------------------------------------------------


@dataclass
class Ingrediente:
    """Un ingrediente: su información nutricional y cómo encontrarlo en Mercadona."""

    id: str
    nombre: str
    kcal_100g: float
    proteina_100g: float
    hidratos_100g: float
    grasa_100g: float
    grupo: str
    vegetariano: bool
    vegano: bool
    busqueda: list[str]
    excluir: list[str]
    despensa: bool
    gramos_por_unidad: float | None


@dataclass
class IngredienteDeReceta:
    """Cuánto lleva una receta de un ingrediente concreto."""

    id: str
    gramos: float


# eq=False merece una explicación, porque es un detalle sutil que da un error
# muy desconcertante si te lo dejas.
#
# Por defecto, @dataclass escribe un __eq__ que compara campo a campo, y en
# cuanto una clase define __eq__, Python deja de considerarla "hasheable", o
# sea, deja de poder usarse como CLAVE de un diccionario. Y el planificador
# hace justo eso: lleva la cuenta de las recetas elegidas en un diccionario
# {receta: veces}.
#
# Con eq=False, dos recetas se consideran iguales solo si son literalmente el
# mismo objeto en memoria. Que es exactamente lo que queremos aquí: el
# recetario se carga una vez y todos usamos esos mismos objetos.
@dataclass(eq=False)
class Receta:
    """Una receta: qué lleva, para cuántos y cómo se hace."""

    id: str
    nombre: str
    dietas: list[str]
    raciones: int
    minutos: int
    dificultad: str = "media"
    ingredientes: list[IngredienteDeReceta] = field(default_factory=list)
    pasos: list[str] = field(default_factory=list)

    def vale_para(self, dieta: str) -> bool:
        """¿Sirve esta receta para la dieta pedida?"""
        return dieta in self.dietas

    @property
    def nombre_dificultad(self) -> str:
        return NOMBRES_DIFICULTAD.get(self.dificultad, self.dificultad)

    def grupos_relevantes(self, ingredientes: dict[str, Ingrediente]) -> set[str]:
        """Los grupos de alimento que de verdad definen esta receta.

        Se usa tanto para marcar "Recomendada" en la pantalla de elegir como
        para el quinto termino de _calidad() en el planificador. Reutiliza
        EXACTAMENTE el mismo criterio que ya usa collage.py para elegir las
        fotos principales de una receta (excluir despensa y condimentos): si
        una receta lleva sal, eso no la convierte en "afín a condimentos", lo
        mismo que una foto de un bote de sal no representa el plato.
        """
        grupos = set()
        for item in self.ingredientes:
            ingrediente = ingredientes.get(item.id)
            if ingrediente is None or ingrediente.despensa or ingrediente.grupo == "condimento":
                continue
            grupos.add(ingrediente.grupo)
        return grupos

    def macros_por_racion(self, ingredientes: dict[str, Ingrediente]) -> dict:
        """Calcula kcal y macronutrientes de UNA ración.

        Suma lo que aporta cada ingrediente y divide entre las raciones.
        Los valores de la tabla son por 100 g, de ahí el "/ 100".
        """
        totales = {"kcal": 0.0, "proteina": 0.0, "hidratos": 0.0, "grasa": 0.0}

        for item in self.ingredientes:
            ingrediente = ingredientes.get(item.id)
            if ingrediente is None:
                continue
            proporcion = item.gramos / 100.0
            totales["kcal"] += ingrediente.kcal_100g * proporcion
            totales["proteina"] += ingrediente.proteina_100g * proporcion
            totales["hidratos"] += ingrediente.hidratos_100g * proporcion
            totales["grasa"] += ingrediente.grasa_100g * proporcion

        return {clave: valor / self.raciones for clave, valor in totales.items()}


# ---------------------------------------------------------------------------
# LA CARGA
# ---------------------------------------------------------------------------


class ErrorDatos(Exception):
    """Los datos de ingredientes.json o recetas.json tienen algún fallo."""


def cargar_ingredientes() -> dict[str, Ingrediente]:
    """Lee ingredientes.json y devuelve un diccionario {id: Ingrediente}.

    Devolvemos un diccionario en vez de una lista porque la operación que más
    se repite en todo el programa es "dame el ingrediente con este id". En un
    diccionario eso es inmediato; en una lista habría que recorrerla entera.
    """
    datos = _leer_json(config.ARCHIVO_INGREDIENTES)

    ingredientes: dict[str, Ingrediente] = {}
    for bruto in datos.get("ingredientes", []):
        identificador = bruto["id"]
        if identificador in ingredientes:
            raise ErrorDatos(f"El ingrediente '{identificador}' esta repetido en ingredientes.json")

        ingredientes[identificador] = Ingrediente(
            id=identificador,
            nombre=bruto["nombre"],
            kcal_100g=float(bruto["kcal_100g"]),
            proteina_100g=float(bruto["proteina_100g"]),
            hidratos_100g=float(bruto["hidratos_100g"]),
            grasa_100g=float(bruto["grasa_100g"]),
            grupo=bruto.get("grupo", "otro"),
            vegetariano=bool(bruto.get("vegetariano", False)),
            vegano=bool(bruto.get("vegano", False)),
            busqueda=list(bruto.get("busqueda", [])),
            excluir=list(bruto.get("excluir", [])),
            despensa=bool(bruto.get("despensa", False)),
            gramos_por_unidad=bruto.get("gramos_por_unidad"),
        )

    if not ingredientes:
        raise ErrorDatos("ingredientes.json no tiene ningun ingrediente")

    return ingredientes


def cargar_recetas() -> dict[str, Receta]:
    """Lee recetas.json y devuelve un diccionario {id: Receta}."""
    datos = _leer_json(config.ARCHIVO_RECETAS)

    recetas: dict[str, Receta] = {}
    for bruto in datos.get("recetas", []):
        identificador = bruto["id"]
        if identificador in recetas:
            raise ErrorDatos(f"La receta '{identificador}' esta repetida en recetas.json")

        minutos = int(bruto.get("minutos", 30))

        recetas[identificador] = Receta(
            id=identificador,
            nombre=bruto["nombre"],
            dietas=list(bruto.get("dietas", [])),
            raciones=int(bruto.get("raciones", 4)),
            minutos=minutos,
            dificultad=bruto.get("dificultad") or _dificultad_por_tiempo(minutos),
            ingredientes=[
                IngredienteDeReceta(id=item["id"], gramos=float(item["gramos"]))
                for item in bruto.get("ingredientes", [])
            ],
            pasos=list(bruto.get("pasos", [])),
        )

    if not recetas:
        raise ErrorDatos("recetas.json no tiene ninguna receta")

    return recetas


def _dificultad_por_tiempo(minutos: int) -> str:
    """Deduce la dificultad a partir del tiempo, si la receta no la trae puesta.

    Es solo un valor por defecto razonable para no obligar a rellenar el campo
    en las recetas antiguas. El tiempo NO es lo mismo que la dificultad: un
    guiso de 55 minutos que consiste en echarlo todo a la olla y esperar es
    facil, aunque tarde. Por eso conviene poner "dificultad" a mano cuando el
    tiempo enganie, y por eso el campo del JSON manda sobre esta funcion.
    """
    if minutos < 25:
        return "facil"
    if minutos <= 50:
        return "media"
    return "elaborada"


def cargar_basicos() -> list[dict]:
    """Lee basicos_desayuno.json.

    Devuelve una lista de {"ingrediente": id, "gramos_persona_semana": n}.
    Si el archivo no esta, devuelve una lista vacia: los desayunos son
    opcionales y su ausencia no debe tirar abajo la aplicacion.
    """
    if not config.ARCHIVO_BASICOS.exists():
        return []
    datos = _leer_json(config.ARCHIVO_BASICOS)
    return list(datos.get("basicos", []))


def _leer_json(ruta) -> dict:
    """Abre un archivo JSON y lo convierte en diccionarios de Python."""
    if not ruta.exists():
        raise ErrorDatos(f"No encuentro el archivo {ruta}")
    # encoding="utf-8" es obligatorio: sin él, en Windows Python usaría una
    # codificación antigua y las tildes y eñes saldrían como símbolos raros.
    with open(ruta, "r", encoding="utf-8") as archivo:
        try:
            return json.load(archivo)
        except json.JSONDecodeError as error:
            # Este mensaje es oro cuando editas el JSON a mano y te dejas una
            # coma. Te dice el archivo Y la línea exacta.
            raise ErrorDatos(f"El archivo {ruta.name} tiene un error de formato: {error}") from error


# ---------------------------------------------------------------------------
# LAS COMPROBACIONES
# ---------------------------------------------------------------------------


def comprobar(ingredientes: dict[str, Ingrediente], recetas: dict[str, Receta]) -> list[str]:
    """Busca incoherencias en los datos y devuelve la lista de problemas.

    Devuelve una lista de textos en vez de lanzar un error al primer fallo,
    para poder enseñártelos TODOS de una vez. Si lanzara un error, arreglarías
    uno, volverías a ejecutar, aparecería el siguiente... y así veinte veces.

    Lo que comprueba:
      1. Que los ingredientes de cada receta existan de verdad.
      2. Que las etiquetas de dieta sean válidas.
      3. Que una receta etiquetada como vegana no lleve nada de origen animal
         (el error más fácil de cometer, y el más grave).
      4. Que toda receta vegana esté también etiquetada como vegetariana.
      5. Que cada dieta tenga suficientes recetas para montar un menú variado.
    """
    problemas: list[str] = []

    for receta in recetas.values():
        # 1. ¿Existen los ingredientes?
        for item in receta.ingredientes:
            if item.id not in ingredientes:
                problemas.append(
                    f"[{receta.id}] usa el ingrediente '{item.id}', que no existe en ingredientes.json"
                )
        if not receta.ingredientes:
            problemas.append(f"[{receta.id}] no tiene ingredientes")

        # 2. ¿Son válidas las etiquetas de dieta?
        for dieta in receta.dietas:
            if dieta not in DIETAS:
                problemas.append(
                    f"[{receta.id}] tiene la dieta '{dieta}', que no existe. Validas: {', '.join(DIETAS)}"
                )
        if receta.dificultad not in DIFICULTADES:
            problemas.append(
                f"[{receta.id}] tiene dificultad '{receta.dificultad}', que no existe. "
                f"Validas: {', '.join(DIFICULTADES)}"
            )

        if "equilibrada" not in receta.dietas:
            problemas.append(
                f"[{receta.id}] no incluye 'equilibrada'. La dieta equilibrada no restringe nada, "
                "asi que todas las recetas deberian llevarla."
            )

        # 3 y 4. Coherencia vegetariana / vegana.
        for etiqueta, atributo in (("vegana", "vegano"), ("vegetariana", "vegetariano")):
            if etiqueta not in receta.dietas:
                continue
            for item in receta.ingredientes:
                ingrediente = ingredientes.get(item.id)
                if ingrediente is not None and not getattr(ingrediente, atributo):
                    problemas.append(
                        f"[{receta.id}] esta marcada como {etiqueta} pero lleva "
                        f"'{ingrediente.nombre}', que no lo es"
                    )

        if "vegana" in receta.dietas and "vegetariana" not in receta.dietas:
            problemas.append(
                f"[{receta.id}] es vegana pero no esta marcada como vegetariana (toda receta vegana lo es)"
            )

    # 5. ¿Hay recetas suficientes por dieta?
    for dieta in DIETAS:
        cuantas = sum(1 for receta in recetas.values() if receta.vale_para(dieta))
        if cuantas < 8:
            problemas.append(
                f"La dieta '{dieta}' solo tiene {cuantas} recetas. Con menos de 8 los menus "
                "salen muy repetitivos."
            )

    return problemas
