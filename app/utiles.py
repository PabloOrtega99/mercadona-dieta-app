"""Funciones pequeñas que se usan desde varios sitios del proyecto.

Cuando una función la necesitan dos archivos distintos, ponerla en un tercero
evita el peor error de principiante: copiarla y pegarla. Si está copiada en dos
sitios y arreglas un fallo en uno, el otro se queda roto para siempre.
"""

import unicodedata


def normalizar_texto(texto: str) -> str:
    """Deja un texto en minúsculas y sin tildes, para poder compararlo.

        normalizar_texto("Plátano de Canarias IGP")  ->  "platano de canarias igp"

    ¿Por qué hace falta? Porque para el ordenador "plátano" y "platano" son dos
    palabras completamente distintas. Si en nuestra tabla de ingredientes
    escribimos "platano" sin tilde y buscamos en el catálogo de Mercadona, que
    lo escribe con tilde, no encontraríamos nada.

    Cómo funciona por dentro: unicodedata.normalize con "NFD" separa cada letra
    acentuada en dos piezas ("á" pasa a ser "a" + el acento como signo aparte).
    Después nos quedamos solo con las piezas que no son marcas de acento
    (categoría "Mn", de Mark-nonspacing).
    """
    if not texto:
        return ""
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(
        caracter
        for caracter in descompuesto
        if unicodedata.category(caracter) != "Mn"
    )
    return sin_tildes.lower().strip()


def formato_euros(cantidad: float) -> str:
    """Formatea un número como precio en español: 1234.5 -> '1.234,50 EUR'.

    En español el separador de miles es el punto y el de decimales la coma,
    justo al revés que en inglés, que es como lo hace Python por defecto.
    El truco de las tres sustituciones intercambia los dos símbolos usando
    la almohadilla como aparcamiento temporal.
    """
    texto = f"{cantidad:,.2f}"          # 1,234.50  (formato inglés)
    texto = texto.replace(",", "#")     # 1#234.50
    texto = texto.replace(".", ",")     # 1#234,50
    texto = texto.replace("#", ".")     # 1.234,50
    return f"{texto} €"
