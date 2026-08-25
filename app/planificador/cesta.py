"""La cesta de la compra: cuantos envases hay que comprar y cuanto cuestan.

=============================================================================
EL CONCEPTO CENTRAL DE TODO EL PROYECTO
=============================================================================

En el supermercado NO compras gramos, compras ENVASES ENTEROS.

Si una receta lleva 50 g de aceite, tu no pagas 50 g de aceite: pagas una
botella entera. Y si haces cuatro recetas mas que tambien llevan aceite, esa
misma botella te sirve para todas y no pagas nada mas.

De ahi salen dos numeros distintos, y confundirlos rompe las cuentas:

  COSTE PRORRATEADO  = gramos x precio_por_gramo
      Sirve para comparar recetas entre si ("esta es mas cara que aquella").
      NO es lo que pagas.

  COSTE REAL         = envases_necesarios x precio_del_envase
      Es lo que pagas de verdad. Solo tiene sentido calculado sobre el plan
      ENTERO, nunca receta a receta.

Y de ahi sale la idea que hace que el algoritmo funcione bien:

  COSTE MARGINAL = lo que SUBE el coste real al anadir una receta a la cesta.

Anadir una receta que aprovecha envases que ya ibas a comprar es casi gratis.
Por eso el planificador acaba proponiendo cestas realistas, en vez de una lista
con treinta productos a medio usar.
"""

import math

from app.recetario import Ingrediente


def gramos_por_envase(producto: dict, ingrediente: Ingrediente) -> float | None:
    """Cuanta comida trae un envase, en gramos.

    Casi siempre nos lo da Mercadona directamente. El caso especial son los
    productos que se venden por piezas (huevos, platanos): la API dice "12
    unidades" pero no cuanto pesa cada una. Ese dato lo pone nuestra tabla de
    ingredientes, en el campo gramos_por_unidad.
    """
    if producto.get("gramos_envase"):
        return float(producto["gramos_envase"])

    unidades = producto.get("unidades_envase")
    if unidades and ingrediente.gramos_por_unidad:
        return float(unidades) * float(ingrediente.gramos_por_unidad)

    # Sin este dato no podemos calcular nada con este producto.
    return None


def envases_necesarios(gramos_pedidos: float, gramos_envase: float) -> int:
    """Cuantos envases hay que comprar para cubrir esos gramos.

    math.ceil redondea SIEMPRE hacia arriba, y ese es justo el comportamiento
    del supermercado: si necesitas 1.100 g de arroz y el paquete es de 1 kg,
    te llevas dos paquetes. No existe comprar 1,1 paquetes.
    """
    if gramos_envase <= 0:
        return 0
    return math.ceil(gramos_pedidos / gramos_envase)


def coste_de(producto: dict, ingrediente: Ingrediente, gramos_pedidos: float) -> tuple[int, float]:
    """Devuelve (cuantos envases, cuanto cuesta) para cubrir esos gramos."""
    tamano = gramos_por_envase(producto, ingrediente)
    if not tamano:
        return 0, 0.0
    unidades = envases_necesarios(gramos_pedidos, tamano)
    return unidades, unidades * float(producto["precio"])


def elegir_producto(
    candidatos: list[dict], ingrediente: Ingrediente, gramos_pedidos: float
) -> dict | None:
    """De entre varios productos validos, elige el que sale mas barato AQUI.

    Esta funcion tiene mas miga de la que parece, porque:

        EL MAS BARATO POR KILO NO SIEMPRE ES EL MAS BARATO.

    Ejemplo real del catalogo de Mercadona:

        Saco de 5 kg de patatas ... 5,60 EUR  ->  1,12 EUR/kg  (el mas barato por kilo)
        Bolsa de 1 kg ............ 2,55 EUR  ->  2,55 EUR/kg

    Si tu plan necesita 800 g de patatas, comprar el saco de 5 kg te cuesta
    5,60 EUR y tiras 4,2 kg. La bolsa de 1 kg te cuesta 2,55 EUR. Gana la bolsa,
    aunque sea mas del doble de cara por kilo.

    Pero si el plan es de 4 semanas para 2 personas y necesitas 6 kg, entonces
    si gana el saco. Por eso esta decision NO se puede tomar al emparejar
    ingredientes con productos: hay que tomarla cuando ya sabemos cuanto se
    necesita, o sea, aqui.

    En caso de empate en precio, gana el que menos comida desperdicia.
    """
    mejor = None
    mejor_coste = None
    mejor_sobra = None

    for producto in candidatos:
        tamano = gramos_por_envase(producto, ingrediente)
        if not tamano:
            continue

        unidades, coste = coste_de(producto, ingrediente, gramos_pedidos)
        sobra = unidades * tamano - gramos_pedidos

        # Redondeamos a céntimos antes de comparar. Los números decimales del
        # ordenador arrastran errores minúsculos (0.1 + 0.2 no da exactamente
        # 0.3), y sin este redondeo dos precios idénticos podrían parecer
        # distintos y el desempate por desperdicio no llegaría a aplicarse.
        coste_redondeado = round(coste, 2)

        if (
            mejor is None
            or coste_redondeado < mejor_coste
            or (coste_redondeado == mejor_coste and sobra < mejor_sobra)
        ):
            mejor = producto
            mejor_coste = coste_redondeado
            mejor_sobra = sobra

    return mejor


class Cesta:
    """Acumula gramos de cada ingrediente y sabe lo que costaria comprarlos.

    Se usa asi:

        cesta = Cesta(ingredientes, emparejamientos, productos)
        cesta.anadir({"arroz": 320, "pollo": 500})
        print(cesta.coste_total())

    Y lo importante para el algoritmo:

        cesta.coste_marginal({"arroz": 320})   # ¿cuanto SUBIRIA si anado esto?

    que responde sin modificar nada.
    """

    def __init__(
        self,
        ingredientes: dict[str, Ingrediente],
        emparejamientos: dict[str, dict],
        productos: dict[str, dict],
        despensa_en_casa: bool = False,
    ):
        self.ingredientes = ingredientes
        self.emparejamientos = emparejamientos
        self.productos = productos  # {id_producto: datos del producto}

        # Si el usuario ha dicho que ya tiene aceite, sal y especias en casa,
        # esos productos siguen apareciendo en la lista (por si acaso) pero no
        # se le cobran. Lo elige él en el formulario.
        self.despensa_en_casa = despensa_en_casa

        # Cuántos gramos de cada ingrediente lleva el plan hasta ahora.
        self.gramos: dict[str, float] = {}

    def copia(self) -> "Cesta":
        """Devuelve una cesta igual pero independiente.

        Sirve para probar alternativas ("¿y si en vez de esta receta pongo
        aquella?") sin estropear la cesta buena.

        Ojo con un fallo clásico de principiante: si aquí escribiéramos
        "nueva.gramos = self.gramos", las dos cestas compartirían el MISMO
        diccionario y tocar una cambiaría la otra. Por eso hacemos dict(...),
        que crea uno nuevo con los mismos valores.
        """
        nueva = Cesta(
            self.ingredientes,
            self.emparejamientos,
            self.productos,
            self.despensa_en_casa,
        )
        nueva.gramos = dict(self.gramos)
        return nueva

    def anadir(self, aportes: dict[str, float]) -> None:
        """Suma gramos a la cesta."""
        for id_ingrediente, gramos in aportes.items():
            self.gramos[id_ingrediente] = self.gramos.get(id_ingrediente, 0.0) + gramos

    def candidatos_de(self, id_ingrediente: str) -> list[dict]:
        """Los productos de Mercadona que sirven para este ingrediente."""
        emparejamiento = self.emparejamientos.get(id_ingrediente)
        if not emparejamiento:
            return []
        return [
            self.productos[id_producto]
            for id_producto in emparejamiento.get("productos", [])
            if id_producto in self.productos
        ]

    def coste_de_ingrediente(self, id_ingrediente: str, gramos: float) -> float:
        """Cuanto cuesta comprar esos gramos de ese ingrediente.

        Devuelve lo que SE LE COBRA al presupuesto. Es el precio real de los
        envases, salvo que sea un producto de despensa y el usuario haya dicho
        que ya lo tiene en casa: entonces son 0 euros, porque no lo compra.

        Cualquiera que sea el caso, la suma de las lineas de la lista de la
        compra cuadra siempre con el total. Ver la nota larga en config.py.
        """
        if gramos <= 0:
            return 0.0

        ingrediente = self.ingredientes.get(id_ingrediente)
        if ingrediente is None:
            return 0.0

        if ingrediente.despensa and self.despensa_en_casa:
            return 0.0

        candidatos = self.candidatos_de(id_ingrediente)
        producto = elegir_producto(candidatos, ingrediente, gramos)
        if producto is None:
            # No hemos encontrado ningún producto para este ingrediente. Se
            # cuenta como 0 € y el planificador lo avisará aparte. Devolver 0
            # es preferible a reventar: mejor un plan con un aviso que ningún
            # plan.
            return 0.0

        _, coste = coste_de(producto, ingrediente, gramos)
        return coste

    def coste_total(self) -> float:
        """Lo que costaria la cesta entera, imputado al presupuesto."""
        return sum(
            self.coste_de_ingrediente(id_ingrediente, gramos)
            for id_ingrediente, gramos in self.gramos.items()
        )

    def coste_marginal(self, aportes: dict[str, float]) -> float:
        """Cuanto CAMBIARIA el coste si anadieramos esos gramos. No modifica nada.

        Este es el metodo mas importante de la clase y el que usa el algoritmo
        una y otra vez.

        Los gramos pueden ser NEGATIVOS, y eso es util de verdad: sirve para
        preguntar "¿y si quito esta receta y pongo esta otra?" sin tener que
        recalcular la cesta entera. El resultado sale negativo si la cesta
        acaba costando menos.

        El truco de eficiencia: solo recalculamos los ingredientes que cambian.
        Si la cesta tiene 40 ingredientes y la receta que estamos probando usa
        8, solo tocamos esos 8. Como el planificador llama a esto miles de
        veces, la diferencia entre hacerlo bien y recalcularlo todo es la
        diferencia entre que la web responda al instante o tarde medio minuto.
        """
        diferencia = 0.0
        for id_ingrediente, gramos_extra in aportes.items():
            actuales = self.gramos.get(id_ingrediente, 0.0)
            antes = self.coste_de_ingrediente(id_ingrediente, actuales)
            # max(0, ...) protege de que un redondeo deje gramos negativos, que
            # no significan nada y darían costes absurdos.
            despues = self.coste_de_ingrediente(
                id_ingrediente, max(0.0, actuales + gramos_extra)
            )
            diferencia += despues - antes
        return diferencia

    def lineas_de_compra(self) -> list[dict]:
        """La lista de la compra: que productos comprar, cuantos y a que precio.

        Devuelve una linea por ingrediente, con el producto elegido y las
        unidades. Es lo que se enseña en pantalla y lo que te llevas al super.
        """
        lineas = []

        for id_ingrediente, gramos in sorted(self.gramos.items()):
            if gramos <= 0:
                continue

            ingrediente = self.ingredientes.get(id_ingrediente)
            if ingrediente is None:
                continue

            candidatos = self.candidatos_de(id_ingrediente)
            producto = elegir_producto(candidatos, ingrediente, gramos)

            if producto is None:
                # Ingrediente sin producto asociado: lo sacamos igualmente en
                # la lista, marcado, para que sepas que tienes que buscarlo tú.
                lineas.append(
                    {
                        "ingrediente": ingrediente,
                        "producto": None,
                        "gramos_necesarios": gramos,
                        "unidades": 0,
                        "coste": 0.0,
                        "coste_imputado": 0.0,
                        "se_cobra": False,
                        "sobra_gramos": 0.0,
                        "sin_producto": True,
                    }
                )
                continue

            unidades, coste = coste_de(producto, ingrediente, gramos)
            tamano = gramos_por_envase(producto, ingrediente) or 0.0

            # ¿Se le cobra o no? Solo hay un caso en que no: producto de
            # despensa y el usuario ha dicho que ya lo tiene.
            se_cobra = not (ingrediente.despensa and self.despensa_en_casa)

            lineas.append(
                {
                    "ingrediente": ingrediente,
                    "producto": producto,
                    "gramos_necesarios": gramos,
                    "unidades": unidades,
                    # Lo que cuesta el producto en la tienda.
                    "coste": coste,
                    # Lo que se le carga al presupuesto: lo mismo, o 0 si ya lo
                    # tienes en casa. La suma de esta columna ES el total.
                    "coste_imputado": coste if se_cobra else 0.0,
                    "se_cobra": se_cobra,
                    # Cuánto sobra. Útil para detectar desperdicio.
                    "sobra_gramos": max(0.0, unidades * tamano - gramos),
                    "sin_producto": False,
                }
            )

        return lineas
