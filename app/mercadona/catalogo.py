"""Guarda y consulta el catálogo de Mercadona en una base de datos local.

¿Por qué guardar una copia en vez de preguntar a Mercadona cada vez?

1. VELOCIDAD. Bajarse el catálogo son 151 peticiones y unos 3 minutos. Si la
   app hiciera eso cada vez que pulsas "generar menú", sería inusable.
2. EDUCACIÓN. El planificador consulta precios miles de veces al calcular un
   menú. Hacer miles de peticiones a un servidor ajeno para eso es abusivo.
3. FUNCIONA SIN INTERNET. Una vez descargado, puedes generar menús sin conexión.

El precio a pagar es que los datos son de cuando los descargaste. Por eso la
app te enseña siempre la fecha de la última actualización.

Usamos SQLite, que es una base de datos que vive en UN SOLO ARCHIVO
(datos/catalogo.sqlite) y viene incluida con Python. No hay nada que instalar
ni ningún servidor que arrancar: es abrir el archivo y trabajar.
"""

import sqlite3
from datetime import datetime

from app import config
from app.utiles import normalizar_texto

# Este texto es SQL, el lenguaje con el que se habla con las bases de datos.
# "CREATE TABLE IF NOT EXISTS" = crea la tabla, pero si ya existe no te quejes.
CREAR_TABLAS = """
CREATE TABLE IF NOT EXISTS productos (
    id                  TEXT PRIMARY KEY,   -- id de Mercadona, no se repite
    nombre              TEXT NOT NULL,
    nombre_normalizado  TEXT NOT NULL,      -- en minúsculas y sin tildes, para buscar
    categoria           TEXT,
    subcategoria        TEXT,
    precio              REAL NOT NULL,      -- lo que cuesta un envase
    precio_referencia   REAL,               -- precio por kilo / litro
    formato_referencia  TEXT,               -- "kg", "L", "ud"...
    gramos_envase       REAL,               -- cuánta comida trae el envase
    unidades_envase     REAL,               -- o cuántas piezas, si va por unidades
    peso_aproximado     INTEGER NOT NULL DEFAULT 0,  -- 0 = no, 1 = sí
    url_imagen          TEXT,
    url_web             TEXT
);

-- Un índice es como el índice alfabético de un libro: le permite a la base de
-- datos encontrar filas sin leerlas todas una por una. Con 4.000 productos y
-- miles de búsquedas al planificar un menú, se nota mucho.
CREATE INDEX IF NOT EXISTS idx_nombre ON productos(nombre_normalizado);

-- Tabla auxiliar para guardar datos sueltos, como la fecha de actualización.
CREATE TABLE IF NOT EXISTS meta (
    clave  TEXT PRIMARY KEY,
    valor  TEXT
);
"""


def abrir() -> sqlite3.Connection:
    """Abre la base de datos (creando el archivo y las tablas si no existían)."""
    # mkdir con parents=True crea también las carpetas intermedias que falten,
    # y con exist_ok=True no protesta si la carpeta ya está. Hace falta porque
    # la carpeta datos/ no viene de GitHub.
    config.DIR_DATOS_GENERADOS.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(config.BD_CATALOGO)

    # Por defecto SQLite devuelve cada fila como una tupla: fila[0], fila[1]...
    # Con sqlite3.Row podemos escribir fila["nombre"], que se entiende mucho
    # mejor y no se rompe si algún día cambia el orden de las columnas.
    conexion.row_factory = sqlite3.Row

    # executescript permite ejecutar varias instrucciones SQL de una vez.
    conexion.executescript(CREAR_TABLAS)
    return conexion


def reemplazar_productos(conexion: sqlite3.Connection, productos: list[dict]) -> int:
    """Borra el catálogo entero y lo sustituye por uno nuevo.

    Reemplazar en lugar de ir actualizando producto a producto tiene una
    ventaja importante: los productos que Mercadona ha dejado de vender
    desaparecen solos. Si fuéramos añadiendo sin más, la base de datos se
    llenaría de fantasmas con precios de hace meses.

    Todo esto ocurre dentro de una TRANSACCIÓN: o se hace entero o no se hace
    nada. Si el programa se corta a mitad, no te quedas sin catálogo.
    """
    with conexion:  # el "with" abre la transacción y la confirma al terminar
        conexion.execute("DELETE FROM productos")
        conexion.executemany(
            """
            INSERT INTO productos (
                id, nombre, nombre_normalizado, categoria, subcategoria,
                precio, precio_referencia, formato_referencia,
                gramos_envase, unidades_envase, peso_aproximado,
                url_imagen, url_web
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            # Los "?" de arriba son huecos que SQLite rellena con estos valores.
            # NUNCA se debe construir una consulta pegando texto (con f-strings):
            # es la puerta de entrada a los ataques de "inyección SQL".
            # Aquí no hay riesgo real porque los datos vienen de Mercadona, pero
            # conviene coger el hábito bien desde el principio.
            [
                (
                    p["id"],
                    p["nombre"],
                    normalizar_texto(p["nombre"]),
                    p["categoria"],
                    p["subcategoria"],
                    p["precio"],
                    p["precio_referencia"],
                    p["formato_referencia"],
                    p["gramos_envase"],
                    p["unidades_envase"],
                    1 if p["peso_aproximado"] else 0,
                    p["url_imagen"],
                    p["url_web"],
                )
                for p in productos
            ],
        )
        conexion.execute(
            "INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)",
            ("actualizado_en", datetime.now().isoformat(timespec="seconds")),
        )
        conexion.execute(
            "INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)",
            ("almacen", config.ALMACEN),
        )
    return len(productos)


def contar(conexion: sqlite3.Connection) -> int:
    """Cuántos productos hay guardados."""
    fila = conexion.execute("SELECT COUNT(*) AS n FROM productos").fetchone()
    return fila["n"]


def fecha_actualizacion(conexion: sqlite3.Connection) -> str | None:
    """Cuándo se descargó el catálogo por última vez, o None si nunca."""
    fila = conexion.execute(
        "SELECT valor FROM meta WHERE clave = 'actualizado_en'"
    ).fetchone()
    return fila["valor"] if fila else None


def obtener(conexion: sqlite3.Connection, id_producto: str) -> dict | None:
    """Devuelve un producto por su id, o None si no está."""
    fila = conexion.execute(
        "SELECT * FROM productos WHERE id = ?", (id_producto,)
    ).fetchone()
    return dict(fila) if fila else None


def buscar(conexion: sqlite3.Connection, texto: str, limite: int = 50) -> list[dict]:
    """Busca productos cuyo nombre contenga TODAS las palabras del texto.

    Ejemplo: buscar("pechuga pollo") encuentra tanto "Filetes de pechuga de
    pollo" como "Pechuga de pollo entera", porque las dos contienen ambas
    palabras, aunque no seguidas ni en ese orden.

    La consulta se construye encadenando un LIKE por palabra:
        WHERE nombre_normalizado LIKE '%pechuga%'
          AND nombre_normalizado LIKE '%pollo%'
    """
    palabras = [p for p in normalizar_texto(texto).split() if p]
    if not palabras:
        return []

    condiciones = " AND ".join(["nombre_normalizado LIKE ?"] * len(palabras))
    valores = [f"%{palabra}%" for palabra in palabras]

    filas = conexion.execute(
        f"""
        SELECT * FROM productos
        WHERE {condiciones}
        ORDER BY precio_referencia IS NULL, precio_referencia ASC
        LIMIT ?
        """,
        # Nota sobre el ORDER BY de arriba: "precio_referencia IS NULL" vale 0
        # cuando hay precio y 1 cuando no lo hay. Al ordenar por ese valor
        # primero, los productos sin precio por kilo se van al final en vez de
        # colarse los primeros, que es lo que hace SQLite con los NULL.
        (*valores, limite),
    ).fetchall()

    return [dict(fila) for fila in filas]


def todos(conexion: sqlite3.Connection) -> list[dict]:
    """Devuelve el catálogo entero. Útil para revisiones y estadísticas."""
    filas = conexion.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    return [dict(fila) for fila in filas]
