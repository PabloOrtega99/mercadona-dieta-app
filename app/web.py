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

import json
import sys
import threading
import webbrowser

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

from app import config, datos_app, recetario, token_mercadona
from app.imagenes import fotos
from app.mercadona import carrito
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
        grupos_preferibles=recetario.GRUPOS_PREFERIBLES,
        nombres_grupos=recetario.NOMBRES_GRUPOS,
        datos=DATOS,
        recetas_por_dieta={
            dieta: sum(1 for receta in DATOS.recetas.values() if receta.vale_para(dieta))
            for dieta in recetario.DIETAS
        },
    )


@app.route("/elegir", methods=["POST"])
def elegir():
    """Paso 2: ensena la propuesta de recetas para que la retoques.

    Esta ruta se llama a si misma. La primera vez llega desde el formulario y
    pide una propuesta al algoritmo; despues, cada vez que pulsas "Actualizar",
    vuelve aqui con TU seleccion y solo recalcula los numeros.

    Lo que distingue un caso del otro es el campo oculto "recalcular", que solo
    viaja en el segundo.
    """
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    peticion = _leer_peticion(request.form)
    contexto = _preparar_contexto(peticion)

    if request.form.get("recalcular") == "1":
        seleccion = _leer_seleccion(request.form)
    else:
        seleccion = planificador.proponer_recetas(
            presupuesto=peticion["presupuesto"],
            semanas=peticion["semanas"],
            personas=peticion["personas"],
            dieta=peticion["dieta"],
            recetas=DATOS.recetas,
            contexto=contexto,
            tiempo_max=peticion["tiempo_max"],
            preferencias=peticion["preferencias"],
        )

    return _pantalla_elegir(peticion, contexto, seleccion)


@app.route("/plan", methods=["POST"])
def generar():
    """Paso 3: monta el plan con las recetas que has elegido."""
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    peticion = _leer_peticion(request.form)
    contexto = _preparar_contexto(peticion)
    seleccion = _leer_seleccion(request.form)

    if not seleccion:
        # Sin recetas no hay plan. En vez de enseñar una página vacía y rara,
        # se vuelve al selector con el aviso puesto.
        return _pantalla_elegir(
            peticion,
            contexto,
            {},
            aviso="No has elegido ninguna receta. Marca al menos una para poder "
            "generar el plan.",
        )

    plan = planificador.construir_plan(
        seleccion=seleccion,
        presupuesto=peticion["presupuesto"],
        semanas=peticion["semanas"],
        personas=peticion["personas"],
        dieta=peticion["dieta"],
        contexto=contexto,
        con_desayunos=peticion["con_desayunos"],
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
        peticion=peticion,
        seleccion_form=_seleccion_a_formulario(seleccion),
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
        imagen=DATOS.imagenes.get(receta.id),
    )


@app.route("/receta/<id_receta>/imagen.png")
def imagen_receta(id_receta):
    """La imagen de la receta: la foto del plato, o el collage si no hay."""
    if ERROR_ARRANQUE or DATOS is None:
        abort(404)

    receta = DATOS.recetas.get(id_receta)
    if receta is None:
        abort(404)

    ruta, tipo = fotos.obtener(
        receta, DATOS.imagenes, DATOS.ingredientes, DATOS.emparejamientos, DATOS.productos
    )
    if ruta is None:
        # Sin imagen devolvemos una foto vacía en lugar de un error, para que
        # el hueco de la tarjeta se vea limpio y no con el icono roto.
        return send_file(config.RAIZ / "app" / "estaticos" / "sin-imagen.svg")

    return send_file(ruta, mimetype="image/jpeg" if tipo == "plato" else "image/png")


@app.route("/fotos")
def revisar_fotos():
    """Pantalla para elegir la foto de cada receta.

    Ensena las candidatas que encontro scripts/buscar_fotos.py y te deja
    pulsar la que mejor represente el plato. La eleccion se guarda al momento.
    """
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    candidatas = _cargar_candidatas()
    if not candidatas:
        return render_template(
            "error.html",
            mensaje=(
                "Todavia no se han buscado fotos de plato.\n"
                "Ejecuta:  python scripts/buscar_fotos.py --preseleccionar"
            ),
        )

    # "sin_revisar" enseña solo las que aún no has tocado a mano. Con 130
    # recetas, poder ir tachando lo pendiente es la diferencia entre terminar
    # la revisión y abandonarla a la mitad.
    solo_pendientes = request.args.get("pendientes") == "1"

    filas = []
    for receta in sorted(DATOS.recetas.values(), key=lambda r: r.nombre):
        eleccion = DATOS.imagenes.get(receta.id)
        revisada = bool(eleccion and eleccion.get("revisada"))
        if solo_pendientes and revisada:
            continue
        filas.append(
            {
                "receta": receta,
                "candidatas": candidatas.get(receta.id, []),
                "eleccion": eleccion,
                "revisada": revisada,
            }
        )

    return render_template(
        "fotos.html",
        datos=DATOS,
        filas=filas,
        total=len(DATOS.recetas),
        revisadas=sum(1 for e in DATOS.imagenes.values() if e.get("revisada")),
        con_foto=len(DATOS.imagenes),
        solo_pendientes=solo_pendientes,
    )


@app.route("/fotos/elegir", methods=["POST"])
def elegir_foto():
    """Guarda la foto elegida para una receta."""
    if ERROR_ARRANQUE:
        abort(400)

    id_receta = request.form.get("receta", "")
    if id_receta not in DATOS.recetas:
        abort(404)

    indice = request.form.get("indice", "")
    candidatas = _cargar_candidatas().get(id_receta, [])

    elecciones = dict(DATOS.imagenes)

    if indice == "collage":
        # Quitar la foto de plato: vuelve a usarse el collage de productos.
        elecciones.pop(id_receta, None)
    else:
        try:
            elegida = dict(candidatas[int(indice)])
        except (ValueError, IndexError):
            abort(400)
        # "revisada" marca que la eligió una persona, no el preseleccionador.
        elegida["revisada"] = True
        elecciones[id_receta] = elegida

    fotos.guardar_elecciones(elecciones)
    DATOS.imagenes = elecciones

    # Al cambiar de foto hay que tirar la copia descargada de la anterior.
    # Si no, se seguiría viendo la vieja para siempre, que es un fallo de los
    # que vuelven loco a cualquiera: "he cambiado la foto y no cambia nada".
    ruta = fotos.ruta_de(DATOS.recetas[id_receta])
    if ruta.exists():
        ruta.unlink()

    destino = url_for("revisar_fotos")
    if request.form.get("pendientes") == "1":
        destino += "?pendientes=1"
    return redirect(f"{destino}#receta-{id_receta}")


# ---------------------------------------------------------------------------
# COMPLETAR LA COMPRA EN MERCADONA
# ---------------------------------------------------------------------------


@app.route("/carrito/token", methods=["GET", "POST"])
def configurar_token():
    """Pantalla para pegar el token de tu sesion de Mercadona."""
    mensaje = None
    if request.method == "POST":
        if request.form.get("accion") == "borrar":
            token_mercadona.borrar()
            mensaje = ("ok", "Token borrado.")
        else:
            pegado = request.form.get("token", "").strip()
            if not pegado:
                mensaje = ("error", "No has pegado nada.")
            else:
                token_mercadona.guardar(pegado)
                # No basta con que el token parezca bien formado: se prueba
                # contra Mercadona de verdad. Es mucho mejor decirte ahora que
                # no vale, que dejarte descubrirlo cuando vayas a comprar.
                vale, detalle = carrito.comprobar_token(token_mercadona.leer())
                mensaje = ("ok" if vale else "error", detalle)

    return render_template(
        "token.html",
        datos=DATOS,
        estado=token_mercadona.estado(),
        mensaje=mensaje,
    )


@app.route("/completar-compra", methods=["POST"])
def completar_compra():
    """Mete la lista de la compra en tu carrito de Mercadona.

    Llena el carrito. NO compra nada: despues tienes que entrar en Mercadona,
    revisar la cesta y pagar tu.
    """
    if ERROR_ARRANQUE:
        return render_template("error.html", mensaje=ERROR_ARRANQUE)

    # Las líneas viajan desde la página del plan en campos ocultos. Se podría
    # recalcular el plan aquí, pero entonces el carrito podría no coincidir
    # exactamente con la lista que estás viendo, y eso sería inaceptable.
    lineas = []
    for clave, valor in request.form.items():
        if not clave.startswith("producto_"):
            continue
        lineas.append(
            {
                "id": clave[len("producto_"):],
                "unidades": int(_numero(valor, 1, 99, 1)),
                "nombre": request.form.get(f"nombre_{clave[len('producto_'):]}", ""),
            }
        )

    estado = token_mercadona.estado()
    resultado = None
    error = None

    if not lineas:
        error = "La lista de la compra llego vacia."
    elif not estado.valido:
        error = estado.mensaje
    else:
        try:
            resultado = carrito.anadir(token_mercadona.leer(), estado.id_cliente, lineas)
        except carrito.ErrorCarrito as fallo:
            error = str(fallo)

    return render_template(
        "compra.html",
        datos=DATOS,
        lineas=lineas,
        resultado=resultado,
        error=error,
        estado=estado,
        total=sum(
            float(DATOS.productos[l["id"]]["precio"]) * l["unidades"]
            for l in lineas
            if l["id"] in DATOS.productos
        ),
    )


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
# EL FLUJO DE TRES PASOS
# ---------------------------------------------------------------------------
#
# La app tiene tres pantallas encadenadas:
#
#     /  ──>  /elegir  ──>  /plan
#
# y hay que arrastrar información de una a otra: lo que pediste en el
# formulario, y luego las recetas que has marcado.
#
# Se hace con CAMPOS OCULTOS del formulario (<input type="hidden">), no con
# sesiones ni cookies. Es la solución más sencilla que funciona bien:
#
#   - El servidor no guarda nada entre peticiones, así que no hay estado que
#     se quede desincronizado ni que caduque.
#   - Puedes abrir dos pestañas con dos planes distintos y no se pisan.
#   - El botón "atrás" del navegador se comporta como esperas.
#
# El precio a pagar es que la información viaja en cada envío. Con cuatro
# números y unas pocas recetas marcadas es irrelevante.


def _leer_peticion(form) -> dict:
    """Lee y valida los datos del formulario del paso 1.

    Todo lo que llega de un formulario es TEXTO y puede ser cualquier cosa:
    vacio, "hola" o un numero absurdo. Aqui se convierte y se acota una sola
    vez, para que a partir de este punto el resto del programa pueda fiarse.
    """
    dieta = form.get("dieta", "equilibrada")
    if dieta not in recetario.DIETAS:
        dieta = "equilibrada"

    # 0 = sin límite. Las franjas (25/40/60) son las mismas que ya usaba el
    # filtro visual de /elegir, para no inventar una escala nueva.
    tiempo_max = int(_numero(form.get("tiempo_max"), 0, 240, 0))

    # Varios checkboxes con el mismo name="preferencias". getlist() los trae
    # todos de una vez; el "& GRUPOS_PREFERIBLES" descarta cualquier valor que
    # no sea uno de los grupos válidos, por si alguien manipula el formulario.
    preferencias = frozenset(form.getlist("preferencias")) & frozenset(
        recetario.GRUPOS_PREFERIBLES
    )

    return {
        "presupuesto": _numero(form.get("presupuesto"), 20, 2000, 80),
        "semanas": int(_numero(form.get("semanas"), 1, 4, 1)),
        "personas": int(_numero(form.get("personas"), 1, 8, 1)),
        "dieta": dieta,
        # Una casilla marcada llega como "on"; sin marcar, no llega nada.
        "con_desayunos": form.get("desayunos") == "on",
        "despensa_en_casa": form.get("despensa") == "on",
        "tiempo_max": tiempo_max,
        "preferencias": preferencias,
    }


def _preparar_contexto(peticion: dict):
    """Monta el Contexto del planificador a partir de la peticion."""
    return planificador.preparar_contexto(
        semanas=peticion["semanas"],
        personas=peticion["personas"],
        dieta=peticion["dieta"],
        ingredientes=DATOS.ingredientes,
        emparejamientos=DATOS.emparejamientos,
        productos=DATOS.productos,
        basicos=DATOS.basicos,
        con_desayunos=peticion["con_desayunos"],
        despensa_en_casa=peticion["despensa_en_casa"],
    )


def _leer_seleccion(form) -> dict:
    """Lee que recetas has marcado y cuantas veces cocinas cada una.

    En el formulario, cada receta manda dos campos:
        incluir_<id>  ->  la casilla; solo llega si esta marcada
        veces_<id>    ->  cuantas veces la cocinas

    Devuelve {Receta: veces}, que es justo lo que espera construir_plan().
    """
    seleccion = {}
    for clave in form:
        if not clave.startswith("incluir_"):
            continue
        id_receta = clave[len("incluir_"):]
        receta = DATOS.recetas.get(id_receta)
        if receta is None:
            continue  # id inventado o receta borrada del JSON: se ignora
        veces = int(_numero(form.get(f"veces_{id_receta}"), 1, 20, 1))
        seleccion[receta] = veces
    return seleccion


def _seleccion_a_formulario(seleccion: dict) -> list[dict]:
    """Convierte la seleccion en algo que la plantilla pueda pintar como ocultos."""
    return [
        {"id": receta.id, "veces": veces}
        for receta, veces in sorted(seleccion.items(), key=lambda p: p[0].nombre)
    ]


def _pantalla_elegir(peticion: dict, contexto, seleccion: dict, aviso: str | None = None):
    """Pinta la pantalla de seleccion de recetas."""
    tiempo_max = peticion["tiempo_max"]
    candidatas = [
        receta
        for receta in DATOS.recetas.values()
        if receta.vale_para(peticion["dieta"])
        and (tiempo_max <= 0 or receta.minutos <= tiempo_max)
    ]
    candidatas.sort(key=lambda r: r.nombre)

    # Si el aviso no venía ya puesto (p. ej. "no has elegido ninguna receta"),
    # avisamos cuando el tiempo máximo deja casi sin recetas para elegir. Es
    # el mismo umbral (8) que usa recetario.comprobar() para decir que una
    # dieta se queda corta de recetas. No se bloquea nada, solo se informa:
    # mismo criterio que con el presupuesto insuficiente.
    if aviso is None and tiempo_max > 0 and len(candidatas) < 8:
        aviso = (
            f"Con ese tiempo máximo casi no hay recetas de esta dieta "
            f"({len(candidatas)}). Prueba a ampliarlo para tener más donde elegir."
        )

    # Qué recetas son afines a tus preferencias, para la insignia "Recomendada".
    # Se calcula sobre TODAS las candidatas, no solo las elegidas: es
    # informativo, ayuda a decidir qué marcar, no un resumen de lo ya marcado.
    preferencias = peticion["preferencias"]
    recomendadas = (
        {r.id for r in candidatas if r.grupos_relevantes(DATOS.ingredientes) & preferencias}
        if preferencias
        else set()
    )

    # El coste real de lo que llevas marcado. Se calcula AQUÍ, en el servidor,
    # porque depende del coste marginal (qué envases comparten las recetas
    # entre sí) y eso el navegador no lo puede saber. Ver el comentario de
    # estaticos/selector.js.
    coste = planificador.cesta_de(seleccion, contexto).coste_total()

    raciones = sum(receta.raciones * veces for receta, veces in seleccion.items())
    comidas_cubiertas = raciones // max(1, peticion["personas"])
    comidas_necesarias = config.COMIDAS_POR_SEMANA * peticion["semanas"]

    return render_template(
        "elegir.html",
        datos=DATOS,
        peticion=peticion,
        candidatas=candidatas,
        seleccion={receta.id: veces for receta, veces in seleccion.items()},
        recomendadas=recomendadas,
        nombres_dietas=recetario.NOMBRES_DIETAS,
        nombres_dificultad=recetario.NOMBRES_DIFICULTAD,
        dificultades=recetario.DIFICULTADES,
        coste=coste,
        comidas_cubiertas=comidas_cubiertas,
        comidas_necesarias=comidas_necesarias,
        aviso=aviso,
    )


# ---------------------------------------------------------------------------
# AYUDAS
# ---------------------------------------------------------------------------


def _cargar_candidatas() -> dict[str, list]:
    """Lee las fotos candidatas que dejo el script de busqueda.

    Se lee del disco en cada visita a /fotos, y no se guarda en memoria como
    el resto de datos, a proposito: es una pantalla que se usa un rato y luego
    no se vuelve a abrir en semanas. No merece la pena tener varios megas de
    candidatas ocupando memoria todo el rato para eso.
    """
    if not config.ARCHIVO_CANDIDATAS.exists():
        return {}
    try:
        with open(config.ARCHIVO_CANDIDATAS, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return {}


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
