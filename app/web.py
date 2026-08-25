"""La aplicacion web: recibe lo que pides en el navegador y devuelve la pagina.

Se arranca con:

    python -m app.web

y luego se abre http://localhost:8000 en el navegador. O mas facil: doble clic
en arrancar.bat, que hace las dos cosas.

Usamos FLASK, que es el servidor web mas sencillo de Python. La idea es
simple: se escriben funciones y se les pone encima una etiqueta @app.route
diciendo a que direccion responden.

    @app.route("/")          ->  responde a http://localhost:8000/
    @app.route("/receta/5")  ->  responde a http://localhost:8000/receta/5

Cada funcion devuelve una pagina HTML, que se construye rellenando una
plantilla de la carpeta plantillas/ con los datos que le pasamos.

Explicacion completa en docs/07-la-interfaz-web.md
"""

import sys
import threading
import webbrowser

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

from app import config, datos_app, recetario
from app.imagenes import collage
from app.planificador import planificador
from app.utiles import formato_euros

app = Flask(
    __name__,
    template_folder="plantillas",
    static_folder="estaticos",
)

# Los datos (catálogo, recetas, ingredientes) se cargan UNA vez al arrancar y
# se quedan en memoria. Cargarlos en cada visita significaría abrir la base de
# datos y releer los JSON cada vez que pulsas un botón: lento y para nada,
# porque no cambian mientras el servidor está encendido.
DATOS: datos_app.DatosApp | None = None
ERROR_ARRANQUE: str | None = None


def cargar():
    """Carga los datos, guardando el error si algo falta en vez de reventar."""
    global DATOS, ERROR_ARRANQUE
    try:
        DATOS = datos_app.cargar_todo()
        ERROR_ARRANQUE = None
    except (datos_app.ErrorPreparacion, recetario.ErrorDatos) as error:
        # Si falta el catálogo, es mejor arrancar igualmente y enseñar una
        # página que explique qué comando hay que ejecutar, en vez de que el
        # servidor no arranque y te deje con un mensaje de error en la
        # terminal que no dice nada.
        DATOS = None
        ERROR_ARRANQUE = str(error)


# ---------------------------------------------------------------------------
# FILTROS DE PLANTILLA
# ---------------------------------------------------------------------------
# Un "filtro" es una función que se puede usar dentro del HTML con la barra
# vertical:   {{ 12.5 | euros }}   ->   12,50 €
# Sirve para que las plantillas queden limpias, sin cuentas por el medio.


@app.template_filter("euros")
def filtro_euros(cantidad):
    return formato_euros(float(cantidad or 0))


@app.template_filter("gramos")
def filtro_gramos(cantidad):
    """Pasa gramos a kilos cuando la cifra se hace grande, que se lee mejor."""
    cantidad = float(cantidad or 0)
    if cantidad >= 1000:
        return f"{cantidad / 1000:.2f} kg".replace(".", ",")
    return f"{cantidad:.0f} g"


# ---------------------------------------------------------------------------
# LAS PÁGINAS
# ---------------------------------------------------------------------------


@app.route("/")
def inicio():
    """El formulario: presupuesto, semanas, dieta y personas."""
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    return render_template(
        "inicio.html",
        dietas=recetario.DIETAS,
        nombres_dietas=recetario.NOMBRES_DIETAS,
        datos=DATOS,
        recetas_por_dieta={
            dieta: sum(1 for receta in DATOS.recetas.values() if receta.vale_para(dieta))
            for dieta in recetario.DIETAS
        },
    )


@app.route("/plan", methods=["POST"])
def generar():
    """Recibe el formulario, calcula el plan y lo ensena."""
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    # request.form son los datos que ha enviado el formulario. Vienen SIEMPRE
    # como texto (aunque el campo sea numérico) y pueden venir vacíos o con
    # cualquier cosa, porque el usuario puede escribir lo que quiera.
    # Por eso todo pasa por _numero(), que valida y pone límites.
    presupuesto = _numero(request.form.get("presupuesto"), 20, 2000, 80)
    semanas = int(_numero(request.form.get("semanas"), 1, 4, 1))
    personas = int(_numero(request.form.get("personas"), 1, 8, 1))

    dieta = request.form.get("dieta", "equilibrada")
    if dieta not in recetario.DIETAS:
        dieta = "equilibrada"

    # Una casilla marcada llega como "on"; si está sin marcar, no llega nada.
    con_desayunos = request.form.get("desayunos") == "on"
    despensa_en_casa = request.form.get("despensa") == "on"

    plan = planificador.generar_plan(
        presupuesto=presupuesto,
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        ingredientes=DATOS.ingredientes,
        recetas=DATOS.recetas,
        emparejamientos=DATOS.emparejamientos,
        productos=DATOS.productos,
        basicos=DATOS.basicos,
        con_desayunos=con_desayunos,
        despensa_en_casa=despensa_en_casa,
    )

    lineas = plan.cesta.lineas_de_compra()

    return render_template(
        "plan.html",
        plan=plan,
        datos=DATOS,
        nombres_dietas=recetario.NOMBRES_DIETAS,
        compra=_agrupar_compra(lineas),
        total_productos=sum(linea["unidades"] for linea in lineas),
        semaforo=_semaforo_nutricional(plan),
    )


@app.route("/receta/<id_receta>")
def ficha_receta(id_receta):
    """La ficha de una receta: ingredientes, pasos, coste y macros."""
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    receta = DATOS.recetas.get(id_receta)
    if receta is None:
        # abort(404) devuelve la página de "no encontrado" del navegador.
        abort(404)

    # Cuánto cuesta cocinar esta receta ella sola, a precios de hoy.
    from app.planificador.cesta import Cesta

    cesta = Cesta(DATOS.ingredientes, DATOS.emparejamientos, DATOS.productos)
    for item in receta.ingredientes:
        cesta.anadir({item.id: item.gramos})

    return render_template(
        "receta.html",
        receta=receta,
        ingredientes=DATOS.ingredientes,
        macros=receta.macros_por_racion(DATOS.ingredientes),
        lineas=cesta.lineas_de_compra(),
        coste=cesta.coste_total(),
        nombres_dietas=recetario.NOMBRES_DIETAS,
    )


@app.route("/receta/<id_receta>/imagen.png")
def imagen_receta(id_receta):
    """La imagen de la receta: el collage con las fotos de los ingredientes."""
    if ERROR_ARRANQUE or DATOS is None:
        abort(404)

    receta = DATOS.recetas.get(id_receta)
    if receta is None:
        abort(404)

    ruta = collage.obtener(
        receta, DATOS.ingredientes, DATOS.emparejamientos, DATOS.productos
    )
    if ruta is None:
        # Sin imagen devolvemos una foto vacía en lugar de un error, para que
        # el hueco de la tarjeta se vea limpio y no con el icono roto.
        return send_file(config.RAIZ / "app" / "estaticos" / "sin-imagen.svg")

    return send_file(ruta, mimetype="image/png")


@app.route("/recargar")
def recargar():
    """Vuelve a leer los datos sin tener que reiniciar el servidor.

    Muy util mientras editas recetas.json o ingredientes.json: guardas el
    archivo, pulsas aqui y ya estan los cambios. Sin esto habria que parar el
    servidor y volver a arrancarlo cada vez.
    """
    cargar()
    return redirect(url_for("inicio"))


# ---------------------------------------------------------------------------
# AYUDAS
# ---------------------------------------------------------------------------


def _numero(texto, minimo, maximo, por_defecto):
    """Convierte a numero lo que venga del formulario, con limites.

    Todo lo que llega de un formulario es texto y puede ser cualquier cosa:
    vacio, "hola", o un numero absurdo como 999999999. Esta funcion se encarga
    de que a partir de aqui siempre trabajemos con un numero razonable.
    """
    try:
        # El usuario español escribirá "80,5" con coma. Python quiere punto.
        valor = float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return por_defecto
    return max(minimo, min(maximo, valor))


def _agrupar_compra(lineas):
    """Ordena la lista de la compra por seccion del supermercado.

    Esto no es un adorno: es lo que hace que la lista sirva de verdad. Si vas
    al super con los productos en orden aleatorio, acabas dando cuatro vueltas
    a la tienda. Agrupados por pasillo, haces un solo recorrido.

    La despensa (aceite, sal, especias) va en un grupo aparte al final, porque
    son cosas que probablemente ya tengas en casa.
    """
    grupos: dict[str, list] = {}
    despensa: list = []

    for linea in lineas:
        if linea["sin_producto"]:
            grupos.setdefault("Sin producto encontrado", []).append(linea)
        elif linea["ingrediente"].despensa:
            despensa.append(linea)
        else:
            seccion = linea["producto"]["categoria"] or "Otros"
            grupos.setdefault(seccion, []).append(linea)

    # Dentro de cada sección, lo más caro primero.
    for lineas_seccion in grupos.values():
        lineas_seccion.sort(key=lambda linea: -linea["coste"])
    despensa.sort(key=lambda linea: -linea["coste"])

    # El total de cada sección suma "coste_imputado", que es lo que se le carga
    # de verdad al presupuesto. Así la suma de todas las secciones cuadra
    # siempre con el total de abajo, mires donde mires.
    resultado = [
        {
            "seccion": seccion,
            "lineas": grupos[seccion],
            "total": sum(linea["coste_imputado"] for linea in grupos[seccion]),
            "es_despensa": False,
        }
        for seccion in sorted(grupos)
    ]

    if despensa:
        resultado.append(
            {
                "seccion": "Despensa (dura varios meses)",
                "lineas": despensa,
                "total": sum(linea["coste_imputado"] for linea in despensa),
                "precio_tienda": sum(linea["coste"] for linea in despensa),
                "es_despensa": True,
            }
        )

    return resultado


def _semaforo_nutricional(plan):
    """Traduce las cifras nutricionales a un semaforo de colores.

    Se ensena como informacion, NO como una restriccion. Mezclar "presupuesto
    maximo" con "objetivo calorico exacto" y "variedad" hace que muchas veces
    el problema no tenga solucion, y la app te devolveria un error en vez de un
    menu. Es mas util un menu bueno con un informe honesto.
    """
    objetivo = config.KCAL_OBJETIVO_DIA
    desviacion = (plan.kcal_dia - objetivo) / objetivo

    if abs(desviacion) <= 0.12:
        estado, mensaje = "bien", "El menú se ajusta bien a un consumo normal."
    elif desviacion < -0.12:
        estado, mensaje = (
            "bajo",
            "El menú se queda algo corto de calorías. Sube el presupuesto o "
            "añade recetas más contundentes al recetario.",
        )
    else:
        estado, mensaje = (
            "alto",
            "El menú va sobrado de calorías para un consumo medio.",
        )

    # Proteína: la referencia habitual es 0,8-1 g por kilo de peso al día.
    # Para un adulto de unos 70 kg salen unos 55-70 g.
    proteina_ok = plan.proteina_dia >= 55

    return {
        "estado": estado,
        "mensaje": mensaje,
        "porcentaje_kcal": min(150, plan.kcal_dia / objetivo * 100),
        "proteina_ok": proteina_ok,
    }


# ---------------------------------------------------------------------------
# ARRANQUE
# ---------------------------------------------------------------------------


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cargar()

    print("=" * 62)
    print("  APP DE MENUS Y LISTA DE LA COMPRA DE MERCADONA")
    if ERROR_ARRANQUE:
        print("\n  AVISO: falta un paso previo.")
        print(f"  {ERROR_ARRANQUE}")
    else:
        print(f"  {DATOS.total_productos} productos | {len(DATOS.recetas)} recetas")
        print(f"  Catalogo actualizado: {DATOS.catalogo_actualizado}")
    print("\n  Abre en el navegador:  http://localhost:8000")
    print("  Para parar el servidor: Ctrl + C")
    print("=" * 62)

    # Abrir el navegador solo, un segundo después de arrancar. Se hace en un
    # hilo aparte con un temporizador porque app.run() se queda bloqueado
    # atendiendo peticiones para siempre: cualquier cosa que pusiéramos
    # después de esa línea no llegaría a ejecutarse nunca.
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8000")).start()

    # debug=False porque el modo depuración de Flask permite ejecutar código
    # desde el navegador. En local y para uso personal el riesgo es mínimo,
    # pero es una costumbre que conviene no coger.
    app.run(host="127.0.0.1", port=8000, debug=False)


if __name__ == "__main__":
    main()
