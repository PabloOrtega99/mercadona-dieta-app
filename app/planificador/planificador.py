"""EL ALGORITMO: elegir que recetas cocinar sin pasarse del presupuesto.

Le das: presupuesto, semanas, dieta y numero de personas.
Te devuelve: un menu, una lista de la compra y un informe nutricional.

=============================================================================
COMO FUNCIONA, EN CORTO
=============================================================================

El problema es una variante del "problema de la mochila": tienes un limite
(el dinero) y quieres meter dentro lo mejor posible (comidas variadas y
suficientes). Ese tipo de problemas no tiene una solucion perfecta rapida:
probar todas las combinaciones de 60 recetas es imposible en la practica.

Asi que usamos un algoritmo VORAZ (greedy): en cada paso elegimos lo que
mejor pinta AHORA MISMO, sin mirar mas alla. No garantiza el resultado
optimo, pero da resultados muy buenos, es rapido y, sobre todo, se entiende.

    1. Calcular cuantas raciones hacen falta.
    2. Quedarse solo con las recetas de la dieta elegida.
    3. Repetir hasta cubrir todas las raciones:
         a. Puntuar cada receta candidata (mas abajo esta la formula).
         b. Coger la mejor y anadir una "cocinada" entera.
    4. Si sobra dinero, mejorar la variedad cambiando repeticiones.
    5. Repartir las comidas por dias.

El ingrediente secreto es el COSTE MARGINAL (ver cesta.py): lo que sube la
cesta al anadir una receta, contando que ya has comprado envases que sirven
para ella. Por eso el algoritmo tiende a juntar recetas que comparten
ingredientes, que es exactamente lo que hace cualquiera que cocine con cabeza.

Explicacion detallada, con un ejemplo numerico paso a paso, en
docs/06-el-algoritmo-del-menu.md
"""

from dataclasses import dataclass, field

from app import config
from app.planificador.cesta import Cesta
from app.recetario import Ingrediente, Receta

# Cuántos intentos de mejora hacemos en el paso 4. Es un tope de seguridad
# para que el bucle no se pueda quedar dando vueltas indefinidamente.
INTENTOS_DE_MEJORA = 60


@dataclass
class RecetaElegida:
    """Una receta del plan y cuantas veces se cocina."""

    receta: Receta
    veces: int

    @property
    def raciones_totales(self) -> int:
        return self.receta.raciones * self.veces


@dataclass
class Plan:
    """El resultado completo: menu, cesta e informe."""

    # Lo que pediste
    presupuesto: float
    semanas: int
    personas: int
    dieta: str
    con_desayunos: bool
    despensa_en_casa: bool = False

    # Lo que sale
    elegidas: list[RecetaElegida] = field(default_factory=list)
    cesta: Cesta | None = None
    menu: list[dict] = field(default_factory=list)

    # Dinero
    coste_total: float = 0.0
    coste_despensa: float = 0.0

    # Avisos
    presupuesto_insuficiente: bool = False
    ingredientes_sin_producto: list[str] = field(default_factory=list)

    # Nutrición
    kcal_dia: float = 0.0
    proteina_dia: float = 0.0
    hidratos_dia: float = 0.0
    grasa_dia: float = 0.0

    @property
    def comidas_totales(self) -> int:
        return config.COMIDAS_POR_SEMANA * self.semanas

    @property
    def dinero_sobrante(self) -> float:
        return self.presupuesto - self.coste_total

    @property
    def porcentaje_presupuesto(self) -> float:
        if self.presupuesto <= 0:
            return 0.0
        return min(100.0, self.coste_total / self.presupuesto * 100.0)


@dataclass
class Contexto:
    """Todo lo que hace falta para montar una cesta, en un solo objeto.

    Antes de existir esto, cada funcion interna del planificador recibia por
    separado ingredientes, emparejamientos, productos, gramos_basicos y el
    ajuste de despensa. Cinco parametros que iban SIEMPRE juntos, repetidos en
    seis firmas de funcion y en todas sus llamadas.

    Cuando varios datos viajan siempre en grupo, es senal de que en realidad
    son una sola cosa y les falta un nombre. Ponerselo (aqui, "Contexto") deja
    las funciones legibles y, sobre todo, hace que anadir un dato nuevo sea
    tocar un sitio en vez de doce.
    """

    ingredientes: dict[str, Ingrediente]
    emparejamientos: dict[str, dict]
    productos: dict[str, dict]
    gramos_basicos: dict[str, float]
    despensa_en_casa: bool

    def cesta_vacia(self) -> Cesta:
        """Una cesta nueva que ya trae metidos los basicos del desayuno."""
        cesta = Cesta(
            self.ingredientes,
            self.emparejamientos,
            self.productos,
            self.despensa_en_casa,
        )
        cesta.anadir(self.gramos_basicos)
        return cesta


def preparar_contexto(
    semanas: int,
    personas: int,
    dieta: str,
    ingredientes: dict[str, Ingrediente],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
    basicos: list[dict],
    con_desayunos: bool = True,
    despensa_en_casa: bool = False,
) -> Contexto:
    """Monta el Contexto, incluidos los gramos de desayuno del periodo.

    Los desayunos son un gasto fijo: no dependen de las recetas que elijas,
    pero si se comen parte del presupuesto. Van dentro del contexto para que
    cualquier cesta que se monte los lleve ya puestos y el algoritmo trabaje
    con el dinero que queda de verdad.
    """
    gramos_basicos = (
        _gramos_de_basicos(basicos, semanas, personas, dieta, ingredientes)
        if con_desayunos
        else {}
    )
    return Contexto(
        ingredientes=ingredientes,
        emparejamientos=emparejamientos,
        productos=productos,
        gramos_basicos=gramos_basicos,
        despensa_en_casa=despensa_en_casa,
    )


def proponer_recetas(
    presupuesto: float,
    semanas: int,
    personas: int,
    dieta: str,
    recetas: dict[str, Receta],
    contexto: Contexto,
) -> dict[Receta, int]:
    """Elige que recetas cocinar y cuantas veces. Devuelve {receta: veces}.

    Aqui vive el algoritmo entero: el bucle voraz y la escalada posterior.
    Antes esto estaba pegado a la construccion del resultado dentro de
    generar_plan(). Se separo para que la pantalla de seleccion pueda pedir
    una propuesta, dejar que el usuario la cambie, y luego construir el plan
    con lo que el haya decidido. Sin esta separacion habria que duplicar medio
    planificador.
    """
    # Cuántas raciones hacen falta: 14 comidas por semana x semanas x personas.
    raciones_objetivo = config.COMIDAS_POR_SEMANA * semanas * personas

    candidatas = [receta for receta in recetas.values() if receta.vale_para(dieta)]
    if not candidatas:
        return {}

    # --- El bucle voraz ----------------------------------------------------
    seleccion = _elegir_recetas(candidatas, raciones_objetivo, presupuesto, contexto)

    # --- Ajustar al presupuesto --------------------------------------------
    # Según de qué lado del presupuesto hayamos caído, toca una cosa o la otra.
    coste = _construir_cesta(seleccion, contexto).coste_total()

    if coste > presupuesto:
        # No cabe: intentamos apretar para que la cifra que te demos como
        # "presupuesto mínimo" sea de verdad lo mínimo, y no lo primero que
        # encontró el bucle voraz.
        seleccion = _abaratar(seleccion, candidatas, presupuesto, contexto)
    else:
        # Cabe y sobra dinero: lo gastamos en comer mejor.
        # Las calorías que deberían aportar las recetas en todo el periodo:
        # unas 750 por comida (el resto del día lo cubre el desayuno).
        kcal_objetivo = config.KCAL_OBJETIVO_COMIDA * raciones_objetivo
        seleccion = _mejorar_variedad(
            seleccion, candidatas, presupuesto, contexto, kcal_objetivo
        )

    return seleccion


def construir_plan(
    seleccion: dict[Receta, int],
    presupuesto: float,
    semanas: int,
    personas: int,
    dieta: str,
    contexto: Contexto,
    con_desayunos: bool = True,
) -> Plan:
    """Monta el Plan completo a partir de una seleccion de recetas ya decidida.

    No elige nada: recibe las recetas hechas y calcula la cesta, la lista de la
    compra, el menu por dias, la nutricion y los avisos.

    La seleccion puede venir de proponer_recetas() o directamente del usuario
    desde la pantalla de seleccion. A esta funcion le da igual de donde salga,
    y eso es justamente lo que la hace util.
    """
    plan = Plan(
        presupuesto=presupuesto,
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        con_desayunos=con_desayunos,
        despensa_en_casa=contexto.despensa_en_casa,
    )

    cesta = _construir_cesta(seleccion, contexto)

    plan.elegidas = sorted(
        (RecetaElegida(receta=receta, veces=veces) for receta, veces in seleccion.items()),
        key=lambda elegida: (-elegida.veces, elegida.receta.nombre),
    )
    plan.cesta = cesta
    plan.coste_total = cesta.coste_total()
    plan.presupuesto_insuficiente = plan.coste_total > presupuesto

    lineas = cesta.lineas_de_compra()
    plan.coste_despensa = sum(
        linea["coste"] for linea in lineas if linea["ingrediente"].despensa
    )
    plan.ingredientes_sin_producto = [
        linea["ingrediente"].nombre for linea in lineas if linea["sin_producto"]
    ]

    plan.menu = _repartir_menu(seleccion, semanas, personas)
    _calcular_nutricion(plan, seleccion, contexto.ingredientes, contexto.gramos_basicos)

    return plan


def generar_plan(
    presupuesto: float,
    semanas: int,
    personas: int,
    dieta: str,
    ingredientes: dict[str, Ingrediente],
    recetas: dict[str, Receta],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
    basicos: list[dict],
    con_desayunos: bool = True,
    despensa_en_casa: bool = False,
) -> Plan:
    """Propone recetas y monta el plan de una tacada.

    Es el camino de siempre: el que usa scripts/probar_plan.py y el que se
    usaba en la web antes de que existiera la pantalla de seleccion. Ahora
    no es mas que juntar las dos piezas de arriba.
    """
    contexto = preparar_contexto(
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        ingredientes=ingredientes,
        emparejamientos=emparejamientos,
        productos=productos,
        basicos=basicos,
        con_desayunos=con_desayunos,
        despensa_en_casa=despensa_en_casa,
    )
    seleccion = proponer_recetas(
        presupuesto=presupuesto,
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        recetas=recetas,
        contexto=contexto,
    )
    return construir_plan(
        seleccion=seleccion,
        presupuesto=presupuesto,
        semanas=semanas,
        personas=personas,
        dieta=dieta,
        contexto=contexto,
        con_desayunos=con_desayunos,
    )


# ---------------------------------------------------------------------------
# PASO 3: EL BUCLE VORAZ
# ---------------------------------------------------------------------------


def _elegir_recetas(
    candidatas: list[Receta],
    raciones_objetivo: int,
    presupuesto: float,
    contexto: Contexto,
) -> dict[Receta, int]:
    """Elige recetas una a una hasta cubrir todas las raciones."""

    cesta = contexto.cesta_vacia()

    seleccion: dict[Receta, int] = {}
    raciones_cubiertas = 0

    while raciones_cubiertas < raciones_objetivo:
        # ¿Nos queda dinero? Si ya nos hemos pasado, cambiamos el chip: dejamos
        # de buscar variedad y vamos a lo más barato posible, porque comer hay
        # que comer igual. El plan saldrá marcado como "presupuesto
        # insuficiente" y te diremos cuánto haría falta de verdad.
        modo_ahorro = cesta.coste_total() >= presupuesto

        mejor_receta = None
        mejor_puntuacion = None

        for receta in candidatas:
            aportes = _gramos_de_receta(receta)
            coste_marginal = cesta.coste_marginal(aportes)
            puntuacion = _puntuar(
                receta, coste_marginal, seleccion.get(receta, 0), modo_ahorro
            )
            if mejor_puntuacion is None or puntuacion < mejor_puntuacion:
                mejor_receta = receta
                mejor_puntuacion = puntuacion

        if mejor_receta is None:
            break

        # Se añade la receta COMPLETA, no media. Cocinas la cazuela entera:
        # si sale para 4 y solo necesitas 2 raciones, las otras 2 existen
        # igualmente (y las pagas igualmente).
        cesta.anadir(_gramos_de_receta(mejor_receta))
        seleccion[mejor_receta] = seleccion.get(mejor_receta, 0) + 1
        raciones_cubiertas += mejor_receta.raciones

    return seleccion


def _puntuar(
    receta: Receta, coste_marginal: float, veces_ya_elegida: int, modo_ahorro: bool
) -> float:
    """Puntua una receta. MENOS ES MEJOR.

    La formula tiene tres factores que se multiplican:

      1. COSTE MARGINAL POR RACION. El nucleo. Lo que costaria de verdad
         anadir esta receta, repartido entre las raciones que da.

      2. PENALIZACION POR REPETICION. Cada vez que una receta ya esta en el
         menu, su puntuacion empeora. Es lo que evita que el algoritmo, que
         solo entiende de dinero, te ponga lentejas catorce veces porque son
         lo mas barato. Crece de forma exponencial: la segunda vez penaliza,
         la tercera penaliza mucho mas.

      3. AJUSTE CALORICO. Penaliza las recetas que se alejan de lo que deberia
         ser una comida (unas 750 kcal). Sin esto, el algoritmo llenaria el
         menu de ensaladas de 250 kcal porque salen baratisimas por racion,
         y te quedarias con hambre.

    En modo ahorro se apagan los factores 2 y 3: cuando no llega el dinero, lo
    unico que importa es que haya comida en la mesa.
    """
    # El +0.01 evita dividir entre cero si una receta sale gratis del todo
    # (todos sus ingredientes ya estaban comprados). Sin él, el programa
    # reventaría con un ZeroDivisionError justo cuando encuentra la mejor
    # opción posible, que sería bastante irónico.
    coste_por_racion = max(0.01, coste_marginal / max(1, receta.raciones))

    if modo_ahorro:
        return coste_por_racion

    penalizacion = (1.0 + config.PENALIZACION_REPETICION) ** veces_ya_elegida

    # Guardamos las kcal por ración en la propia receta la primera vez que se
    # calculan, porque esto se ejecuta miles de veces y el cálculo se repetiría
    # una y otra vez con el mismo resultado. Se llama "memorizar" (memoization).
    kcal = getattr(receta, "_kcal_racion_cache", None)
    if kcal is None:
        return coste_por_racion * penalizacion

    desviacion = abs(kcal - config.KCAL_OBJETIVO_COMIDA) / config.KCAL_OBJETIVO_COMIDA
    ajuste = 1.0 + config.PESO_AJUSTE_CALORICO * desviacion

    return coste_por_racion * penalizacion * ajuste


# ---------------------------------------------------------------------------
# PASO 4: MEJORAR LA VARIEDAD SI SOBRA DINERO
# ---------------------------------------------------------------------------


# Cuánto pesa cada cosa en la puntuación de calidad de un menú.
PESO_RECETA_DISTINTA = 3.0
PESO_GRUPO_ALIMENTO = 2.0
PESO_REPETICION = 1.5
PESO_CALORIAS = 15.0


def _calidad(
    seleccion: dict[Receta, int],
    ingredientes: dict[str, Ingrediente],
    kcal_objetivo: float,
) -> float:
    """Puntua lo bueno que es un menu, al margen de lo que cueste. MAS ES MEJOR.

    Hace falta una medida asi porque "barato" no es lo mismo que "bueno". El
    paso 3 solo sabe de dinero, y con 60 euros para una semana te monta un
    menu de 27 euros a base de pasta. Tecnicamente correcto y horrible.

    Lo que valoramos:

      + RECETAS DISTINTAS. Comer catorce veces lo mismo es lo peor que puede
        pasar, asi que es lo que mas puntua.

      + VARIEDAD DE GRUPOS DE ALIMENTOS. Un menu que toca carne, pescado,
        legumbre, verdura y lacteo es mejor que uno que solo toca cereales,
        aunque los dos tengan cuatro recetas distintas.

      - REPETICIONES. Cada vez de mas que se repite una receta, resta.

      - DISTANCIA AL OBJETIVO CALORICO. Este apareció probando: el plan vegano
        salia por 46 euros de un presupuesto de 90 y se quedaba en 1.473 kcal
        al dia. Todas las recetas eran distintas y variadas, asi que la calidad
        ya no podia subir mas y el algoritmo se plantaba ahi, con el dinero sin
        gastar y tu con hambre. Contando las calorias, prefiere platos que
        alimentan mientras el presupuesto lo permita.
    """
    grupos = set()
    kcal_totales = 0.0

    for receta, veces in seleccion.items():
        for item in receta.ingredientes:
            ingrediente = ingredientes.get(item.id)
            # Los condimentos no cuentan: que una receta lleve sal no la hace
            # más variada.
            if ingrediente is not None and ingrediente.grupo not in ("condimento", "otro"):
                grupos.add(ingrediente.grupo)

        kcal_racion = getattr(receta, "_kcal_racion_cache", 0.0) or 0.0
        kcal_totales += kcal_racion * receta.raciones * veces

    repeticiones = sum(veces - 1 for veces in seleccion.values())

    # Se penaliza tanto quedarse corto como pasarse. Sin penalizar el exceso,
    # con presupuesto de sobra el algoritmo se iría a los platos más calóricos
    # que encontrara, que tampoco es la idea.
    desviacion = abs(kcal_totales - kcal_objetivo) / max(1.0, kcal_objetivo)

    return (
        len(seleccion) * PESO_RECETA_DISTINTA
        + len(grupos) * PESO_GRUPO_ALIMENTO
        - repeticiones * PESO_REPETICION
        - desviacion * PESO_CALORIAS
    )


def _mejorar_variedad(
    seleccion: dict[Receta, int],
    candidatas: list[Receta],
    presupuesto: float,
    contexto: Contexto,
    kcal_objetivo: float,
) -> dict[Receta, int]:
    """Aprovecha el dinero que sobra para mejorar el menu.

    Prueba cambios de una receta por otra:

        quitar una cocinada de X + poner una cocinada de Y
        ¿mejora la calidad Y sigue cabiendo en el presupuesto? -> aceptado

    Esto se llama ESCALADA (hill climbing): partes de una solucion que ya
    funciona y le vas dando pasos pequenos cuesta arriba mientras mejore.

    Dos detalles que hacen que sea rapido:

      1. Primero se comprueba la calidad, que es una cuenta trivial, y solo
         se calcula el precio de los cambios que de verdad mejoran. La mayoria
         se descartan sin tocar ningun precio.

      2. El precio no se recalcula entero: se usa coste_marginal() con gramos
         negativos para la receta que sale y positivos para la que entra. Solo
         se tocan los ingredientes afectados, no los cincuenta de la cesta.
    """
    cesta = _construir_cesta(seleccion, contexto)
    coste_actual = cesta.coste_total()
    calidad_actual = _calidad(seleccion, contexto.ingredientes, kcal_objetivo)

    for _ in range(INTENTOS_DE_MEJORA):
        # Todos los cambios posibles, ordenados por cuánto prometen mejorar.
        # Así probamos primero los que más valen la pena.
        propuestas = []
        for sale in list(seleccion):
            for entra in candidatas:
                if entra is sale:
                    continue
                # La que entra tiene que dar al menos tantas raciones como la
                # que sale; si no, nos quedaríamos con comidas sin cubrir.
                if entra.raciones < sale.raciones:
                    continue

                propuesta = _aplicar_cambio(seleccion, sale, entra)
                ganancia = (
                    _calidad(propuesta, contexto.ingredientes, kcal_objetivo) - calidad_actual
                )
                if ganancia > 0:
                    propuestas.append((ganancia, sale, entra, propuesta))

        propuestas.sort(key=lambda p: -p[0])

        aplicado = False
        for _ganancia, sale, entra, propuesta in propuestas:
            # Cuánto cambia el precio: quitar una cocinada de la que sale
            # (gramos en negativo) y poner una de la que entra.
            diferencia = dict(_gramos_de_receta(entra))
            for id_ingrediente, gramos in _gramos_de_receta(sale).items():
                diferencia[id_ingrediente] = diferencia.get(id_ingrediente, 0.0) - gramos

            nuevo_coste = coste_actual + cesta.coste_marginal(diferencia)
            if nuevo_coste > presupuesto:
                continue

            # Aceptado: aplicamos el cambio de verdad.
            seleccion = propuesta
            cesta.anadir(diferencia)
            coste_actual = cesta.coste_total()
            calidad_actual = _calidad(seleccion, contexto.ingredientes, kcal_objetivo)
            aplicado = True
            break

        if not aplicado:
            # Ningún cambio mejora y cabe. Ya no vamos a llegar más arriba.
            break

    return seleccion


def _abaratar(
    seleccion: dict[Receta, int],
    candidatas: list[Receta],
    presupuesto: float,
    contexto: Contexto,
) -> dict[Receta, int]:
    """Cuando el plan no cabe en el presupuesto, aprieta todo lo que puede.

    Es la misma escalada que _mejorar_variedad pero cuesta abajo: aqui el
    unico criterio es que baje el precio.

    Por que merece la pena hacerlo: cuando el presupuesto no llega, el numero
    mas util que te podemos dar es cuanto haria falta DE VERDAD. Si nos
    quedamos con lo primero que encontro el bucle voraz, ese numero seria mas
    alto de lo necesario y te estariamos mintiendo. Se para en cuanto entra en
    presupuesto: apretar mas alla de eso no aporta nada.
    """
    cesta = _construir_cesta(seleccion, contexto)
    coste_actual = cesta.coste_total()

    for _ in range(INTENTOS_DE_MEJORA):
        if coste_actual <= presupuesto:
            break

        mejor = None
        mejor_ahorro = 0.0

        for sale in list(seleccion):
            for entra in candidatas:
                if entra is sale or entra.raciones < sale.raciones:
                    continue

                # Se prueban DOS tipos de cambio, y esto es importante:
                #   1  = cambiar una sola cocinada
                #   todas = cambiar TODAS las cocinadas de esa receta de golpe
                #
                # Sin el segundo, el algoritmo se queda atrapado. Paso de
                # verdad: con un presupuesto imposible se planto en catorce
                # cocinadas de la misma ensalada de surimi, que salia por
                # 92 euros. Cambiar UNA sola no bajaba el precio (los envases
                # seguian haciendo falta para las otras trece) y ademas obligaba
                # a comprar los de la receta nueva, asi que ningun cambio
                # mejoraba y se quedaba ahi. Es el clasico maximo local: para
                # salir hay que dar un paso grande, no muchos pequenos.
                for cuantas in {1, seleccion[sale]}:
                    diferencia = _diferencia_de_cambio(sale, entra, cuantas)
                    ahorro = -cesta.coste_marginal(diferencia)
                    if ahorro > mejor_ahorro:
                        mejor = (sale, entra, cuantas, diferencia)
                        mejor_ahorro = ahorro

        # Un céntimo de mejora no compensa seguir dando vueltas.
        if mejor is None or mejor_ahorro < 0.01:
            break

        sale, entra, cuantas, diferencia = mejor
        seleccion = _aplicar_cambio(seleccion, sale, entra, cuantas)
        cesta.anadir(diferencia)
        coste_actual = cesta.coste_total()

    return seleccion


def _diferencia_de_cambio(sale: Receta, entra: Receta, cuantas: int) -> dict[str, float]:
    """Los gramos que cambian al sustituir N cocinadas de una receta por otra.

    Los de la que sale van en negativo y los de la que entra en positivo, que
    es justo lo que espera Cesta.coste_marginal().
    """
    diferencia: dict[str, float] = {}
    for id_ingrediente, gramos in _gramos_de_receta(entra).items():
        diferencia[id_ingrediente] = diferencia.get(id_ingrediente, 0.0) + gramos * cuantas
    for id_ingrediente, gramos in _gramos_de_receta(sale).items():
        diferencia[id_ingrediente] = diferencia.get(id_ingrediente, 0.0) - gramos * cuantas
    return diferencia


def _aplicar_cambio(
    seleccion: dict[Receta, int], sale: Receta, entra: Receta, cuantas: int = 1
) -> dict[Receta, int]:
    """Devuelve una seleccion nueva con N cocinadas de 'sale' cambiadas por 'entra'."""
    propuesta = dict(seleccion)
    propuesta[sale] -= cuantas
    if propuesta[sale] <= 0:
        del propuesta[sale]
    propuesta[entra] = propuesta.get(entra, 0) + cuantas
    return propuesta


# ---------------------------------------------------------------------------
# PASO 5: REPARTIR LAS COMIDAS POR DIAS
# ---------------------------------------------------------------------------

DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def _repartir_menu(seleccion: dict[Receta, int], semanas: int, personas: int) -> list[dict]:
    """Coloca las recetas en el calendario de comidas y cenas.

    Una cocinada de 4 raciones da de comer a 2 personas dos veces, o a 4
    personas una vez. De ahi sale cuantas COMIDAS aporta cada cocinada.

    El reparto se hace "a la ronda" (round-robin): en vez de poner las tres
    veces que sale el arroz seguidas, se van alternando las recetas. Asi no te
    comes lo mismo lunes, martes y miercoles.
    """
    # Cuántas comidas aporta cada receta.
    aportes: list[tuple[Receta, int]] = []
    for receta, veces in seleccion.items():
        comidas = (receta.raciones * veces) // max(1, personas)
        if comidas > 0:
            aportes.append((receta, comidas))

    # Reparto a la ronda: una comida de cada receta, luego otra vuelta, etc.
    cola: list[Receta] = []
    pendientes = {receta: comidas for receta, comidas in aportes}
    while any(pendientes.values()):
        for receta in list(pendientes):
            if pendientes[receta] > 0:
                cola.append(receta)
                pendientes[receta] -= 1

    menu = []
    posicion = 0
    for semana in range(semanas):
        for indice_dia, dia in enumerate(DIAS):
            fila = {"semana": semana + 1, "dia": dia, "numero_dia": indice_dia + 1}
            for momento in ("comida", "cena"):
                # Si el reparto no da para todas las casillas (puede pasar si
                # se agotó el presupuesto), la casilla se queda vacía en vez de
                # inventarse una receta.
                fila[momento] = cola[posicion] if posicion < len(cola) else None
                posicion += 1
            menu.append(fila)

    return menu


# ---------------------------------------------------------------------------
# NUTRICIÓN
# ---------------------------------------------------------------------------


def _calcular_nutricion(
    plan: Plan,
    seleccion: dict[Receta, int],
    ingredientes: dict[str, Ingrediente],
    gramos_basicos: dict[str, float],
) -> None:
    """Calcula las medias diarias de kcal y macronutrientes del plan."""
    totales = {"kcal": 0.0, "proteina": 0.0, "hidratos": 0.0, "grasa": 0.0}

    # Lo que aportan las recetas.
    for receta, veces in seleccion.items():
        por_racion = receta.macros_por_racion(ingredientes)
        for clave in totales:
            totales[clave] += por_racion[clave] * receta.raciones * veces

    # Lo que aportan los desayunos.
    for id_ingrediente, gramos in gramos_basicos.items():
        ingrediente = ingredientes.get(id_ingrediente)
        if ingrediente is None:
            continue
        proporcion = gramos / 100.0
        totales["kcal"] += ingrediente.kcal_100g * proporcion
        totales["proteina"] += ingrediente.proteina_100g * proporcion
        totales["hidratos"] += ingrediente.hidratos_100g * proporcion
        totales["grasa"] += ingrediente.grasa_100g * proporcion

    # Repartimos entre los días-persona que cubre el plan.
    dias_persona = max(1, config.DIAS_POR_SEMANA * plan.semanas * plan.personas)
    plan.kcal_dia = totales["kcal"] / dias_persona
    plan.proteina_dia = totales["proteina"] / dias_persona
    plan.hidratos_dia = totales["hidratos"] / dias_persona
    plan.grasa_dia = totales["grasa"] / dias_persona


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------


def _gramos_de_receta(receta: Receta) -> dict[str, float]:
    """Los gramos que necesita una cocinada de la receta, como diccionario."""
    aportes: dict[str, float] = {}
    for item in receta.ingredientes:
        aportes[item.id] = aportes.get(item.id, 0.0) + item.gramos
    return aportes


def _gramos_de_basicos(
    basicos: list[dict],
    semanas: int,
    personas: int,
    dieta: str,
    ingredientes: dict[str, Ingrediente],
) -> dict[str, float]:
    """Los gramos de desayuno para todo el periodo, respetando la dieta.

    Esto surgio de un fallo de verdad que salio en las pruebas: el primer plan
    vegano que generamos llevaba leche entera y yogur en la lista de la compra.
    Las recetas si estaban bien filtradas, pero los desayunos se anadian a
    ciegas, sin mirar la dieta.

    Ahora hay dos redes de seguridad, y las dos hacen falta:

      1. El campo "alternativas" de basicos_desayuno.json, que dice con que
         sustituir cada cosa en cada dieta (leche -> bebida de soja) o que se
         quite directamente (yogur en vegana).

      2. Una comprobacion final: si aun asi se cuela un ingrediente que no
         cumple la dieta, se descarta. Es la que garantiza que en una dieta
         vegana NUNCA aparezca nada de origen animal, aunque el archivo de
         datos tenga un error.
    """
    aportes: dict[str, float] = {}

    for basico in basicos:
        id_ingrediente = basico["ingrediente"]

        # 1. ¿Hay que sustituirlo o quitarlo en esta dieta?
        alternativas = basico.get("alternativas") or {}
        if dieta in alternativas:
            id_ingrediente = alternativas[dieta]
            if id_ingrediente is None:
                continue  # en esta dieta este básico no se pone

        ingrediente = ingredientes.get(id_ingrediente)
        if ingrediente is None:
            continue

        # 2. La red de seguridad.
        if dieta == "vegana" and not ingrediente.vegano:
            continue
        if dieta == "vegetariana" and not ingrediente.vegetariano:
            continue

        gramos = float(basico["gramos_persona_semana"]) * semanas * personas
        aportes[id_ingrediente] = aportes.get(id_ingrediente, 0.0) + gramos

    return aportes


def cesta_de(seleccion: dict[Receta, int], contexto: Contexto) -> Cesta:
    """Monta la cesta de una seleccion de recetas. Version publica.

    La usa la pantalla de seleccion para saber cuanto cuesta lo que llevas
    marcado sin tener que construir el plan entero. El guion bajo de
    _construir_cesta significa "de uso interno", asi que se le pone esta puerta
    en vez de que la web tenga que entrar por detras.
    """
    return _construir_cesta(seleccion, contexto)


def _construir_cesta(seleccion: dict[Receta, int], contexto: Contexto) -> Cesta:
    """Monta una cesta desde cero a partir de una seleccion de recetas."""
    cesta = contexto.cesta_vacia()
    for receta, veces in seleccion.items():
        aportes = _gramos_de_receta(receta)
        cesta.anadir({clave: valor * veces for clave, valor in aportes.items()})
    return cesta


def precalcular_calorias(recetas: dict[str, Receta], ingredientes: dict[str, Ingrediente]) -> None:
    """Calcula y guarda las kcal por racion de cada receta.

    Se llama UNA vez al arrancar la aplicacion. El planificador consulta este
    dato miles de veces al montar un menu; calcularlo cada vez seria repetir
    exactamente la misma cuenta una y otra vez para nada.
    """
    for receta in recetas.values():
        receta._kcal_racion_cache = receta.macros_por_racion(ingredientes)["kcal"]


def precalcular_costes(
    recetas: dict[str, Receta],
    ingredientes: dict[str, Ingrediente],
    emparejamientos: dict[str, dict],
    productos: dict[str, dict],
) -> None:
    """Calcula lo que cuesta cada receta COCINADA ELLA SOLA, por racion.

    Es el precio que se ensena en la pantalla de seleccion, para poder comparar
    recetas de un vistazo.

    OJO, y esto hay que tenerlo claro para no confundirse mas adelante: NO es
    lo que va a costar dentro del plan. Dentro del plan casi siempre sale mas
    barata, porque comparte envases con las demas (el aceite, la cebolla, el
    arroz...). Eso es el coste marginal, y solo se puede calcular sabiendo que
    otras recetas la acompanian. Ver cesta.py.

    Por eso en la pantalla se etiqueta explicitamente como "por si sola".
    """
    for receta in recetas.values():
        cesta = Cesta(ingredientes, emparejamientos, productos)
        cesta.anadir(_gramos_de_receta(receta))
        receta._coste_racion_cache = cesta.coste_total() / max(1, receta.raciones)
