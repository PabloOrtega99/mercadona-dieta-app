"""Ajustes del proyecto, todos en un único sitio.

¿Por qué un archivo solo para esto? Porque son los valores que vas a querer
cambiar de vez en cuando (tu supermercado, tus calorías objetivo...) y así no
tienes que ir buscándolos escondidos por el medio del código.

Regla general que conviene coger: los "números mágicos" sueltos por el código
son una fuente clásica de errores. Si el 14 (comidas por semana) aparece en
cuatro archivos distintos y un día quieres cambiarlo, seguro que te dejas uno.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------
# __file__ es la ruta de ESTE archivo (app/config.py).
# .resolve() la convierte en ruta absoluta y .parent sube un nivel de carpeta.
# Como este archivo está en "app/", subir dos veces nos deja en la raíz del
# proyecto. Hacerlo así (y no escribir "D:\Proyectos Claude\...") es lo que
# permite que el proyecto funcione igual en tu otro ordenador.
RAIZ = Path(__file__).resolve().parent.parent

# Datos que se GENERAN (no se suben a GitHub, están en .gitignore).
DIR_DATOS_GENERADOS = RAIZ / "datos"
BD_CATALOGO = DIR_DATOS_GENERADOS / "catalogo.sqlite"
DIR_IMAGENES = DIR_DATOS_GENERADOS / "imagenes"

# Datos que ESCRIBIMOS NOSOTROS a mano (estos sí se suben a GitHub).
DIR_DATOS = RAIZ / "app" / "datos"
ARCHIVO_INGREDIENTES = DIR_DATOS / "ingredientes.json"
ARCHIVO_RECETAS = DIR_DATOS / "recetas.json"
ARCHIVO_EMPAREJAMIENTOS = DIR_DATOS / "emparejamientos.json"
ARCHIVO_BASICOS = DIR_DATOS / "basicos_desayuno.json"
ARCHIVO_IMAGENES = DIR_DATOS / "imagenes_recetas.json"

# Las fotos candidatas que devuelven los bancos de imagenes. Esto SÍ es
# regenerable (basta con volver a buscar), así que vive con lo generado.
ARCHIVO_CANDIDATAS = DIR_DATOS_GENERADOS / "candidatas_fotos.json"


# ---------------------------------------------------------------------------
# MERCADONA
# ---------------------------------------------------------------------------
# Mercadona no tiene un catálogo único: cada zona se sirve desde un almacén
# distinto, y el surtido puede variar un poco. El código del almacén va en la
# dirección de cada petición (el "wh=" de wh=mad1, de warehouse).
#
# Códigos que he comprobado que funcionan: mad1 (Madrid), bcn1 (Barcelona),
# vlc1 (Valencia), svq1 (Sevilla).
ALMACEN = "mad1"

# Segundos de espera entre una petición y la siguiente al servidor de Mercadona.
#
# Esto NO es un detalle menor. Estamos usando una API que Mercadona no ha
# publicado oficialmente para terceros. Lanzar 151 peticiones tan rápido como
# el ordenador pueda es un comportamiento agresivo, se parece a un ataque y te
# pueden bloquear la IP con razón. Con 0,4 s el catálogo entero tarda unos
# 3 minutos, que para algo que haces una vez por semana está perfecto.
PAUSA_ENTRE_PETICIONES = 0.4

# Cuántos segundos esperamos como máximo a que el servidor conteste antes de
# darlo por perdido. Sin esto, si Mercadona se cuelga, tu programa se queda
# esperando para siempre.
TIMEOUT_SEGUNDOS = 20

# Cuántas veces reintentamos una petición que ha fallado. Los fallos de red
# suelen ser pasajeros: reintentar tres veces resuelve casi todos.
REINTENTOS = 3


# ---------------------------------------------------------------------------
# PLANIFICACIÓN
# ---------------------------------------------------------------------------
# Planificamos comida y cena: 2 comidas al día x 7 días = 14 por semana.
# El desayuno se cubre aparte, con la lista de básicos (basicos_desayuno.json).
COMIDAS_POR_DIA = 2
DIAS_POR_SEMANA = 7
COMIDAS_POR_SEMANA = COMIDAS_POR_DIA * DIAS_POR_SEMANA  # 14

# Objetivo calórico orientativo de un adulto medio, para el informe nutricional.
# No se usa como límite, solo para decirte si el menú se queda corto o pasado.
KCAL_OBJETIVO_DIA = 2000

# Cuántas calorías debería tener una comida o una cena.
#
# El desayuno se lleva más o menos la cuarta parte del día, así que lo que
# queda se reparte entre comida y cena: 2000 x 0,75 / 2 = 750.
#
# Esto lo usa el planificador para no llenarte el menú de ensaladas de 250 kcal
# solo porque salen baratas. Una comida tiene que alimentar.
KCAL_OBJETIVO_COMIDA = KCAL_OBJETIVO_DIA * 0.75 / COMIDAS_POR_DIA

# Cuánto pesa el ajuste calórico frente al precio a la hora de elegir recetas.
# A 0 el planificador solo mira el dinero; subiéndolo se preocupa más de que
# las comidas tengan un tamaño razonable.
PESO_AJUSTE_CALORICO = 0.6

# Cuánto penalizamos repetir una receta que ya está en el menú.
# Es el mando de la "variedad": súbelo y el menú será más variado pero más caro;
# bájalo y saldrá más barato pero comerás lentejas cuatro veces por semana.
# Se explica a fondo en docs/06-el-algoritmo-del-menu.md.
PENALIZACION_REPETICION = 0.55

# --- Sobre los ingredientes de despensa (aceite, sal, especias...) ---
#
# Estos duran meses, así que no es realista cargarlos enteros al presupuesto de
# una semana. Pero tampoco se pueden regalar: si no los tienes, los pagas.
#
# La primera versión de esto aplicaba un descuento del 25 % a los productos de
# despensa. Fue un error, y se vio en cuanto salió la primera página: la lista
# de la compra sumaba 90,88 € y el total ponía 79,54 €. Dos números distintos
# para la misma cosa, sin explicación posible. Cualquiera que mira una lista de
# la compra suma mentalmente y comprueba, y ahí perdías la confianza en todas
# las demás cifras de la página.
#
# La solución no fue matemática sino de diseño: PREGUNTARLE AL USUARIO. En el
# formulario hay una casilla de "ya tengo la despensa básica en casa". Si la
# marcas, esos productos aparecen en una lista aparte y no cuentan; si no, se
# cobran enteros. En los dos casos, la suma de la lista cuadra con el total.
#
# La lección general: cuando dos números que deberían ser el mismo no cuadran,
# el arreglo casi nunca es afinar la fórmula. Es replantear qué se enseña.
