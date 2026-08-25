# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Idioma

**Todo el código, los comentarios, los mensajes de commit y la documentación están en castellano.** No es una preferencia estética: el proyecto es el material de aprendizaje de su autor, que tiene nociones básicas de programación. Los nombres de funciones, variables y campos JSON también van en castellano (`coste_marginal`, `gramos_envase`, `elegir_producto`).

Los comentarios explican **por qué**, no qué hace la línea. Cuando un fallo real enseña algo, se deja contado en el código o en `docs/` en vez de borrar el rastro (ver el comentario largo de `app/config.py`, o `_elegir_variados()` en `emparejador.py`).

Cualquier cambio de comportamiento debe reflejarse en el documento de `docs/` correspondiente.

## Comandos

No hay framework de tests. La verificación se hace con scripts que imprimen resultados y comprobaciones aritméticas.

```powershell
# Entorno (Windows / PowerShell). Todos los comandos asumen el venv activado
# o el uso directo de .\.venv\Scripts\python.exe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Descargar el catálogo de Mercadona (~3 min, 151 peticiones). Imprescindible
# antes de nada: sin él la app arranca pero solo muestra la página de error.
python scripts/actualizar_catalogo.py

# Buscar fotos de plato (~10 min, tres APIs externas). Opcional: sin esto
# las recetas usan el collage de productos, que siempre funciona.
python scripts/buscar_fotos.py --preseleccionar

# Arrancar la web (http://localhost:8000). También: doble clic en arrancar.bat
python -m app.web
```

Verificación, en el orden en que conviene ejecutarla tras un cambio:

```powershell
python scripts/comprobar_datos.py            # valida ingredientes.json y recetas.json
python scripts/revisar_emparejamientos.py    # tabla ingrediente -> producto elegido
python scripts/revisar_emparejamientos.py --regenerar   # recalcula y guarda
python scripts/comprobar_precios.py          # detecta emparejamientos sospechosos por €/kg
python scripts/probar_plan.py                # los 5 casos de prueba estándar
python scripts/probar_plan.py 80 2 1 equilibrada   # un caso suelto: € semanas personas dieta
```

`probar_plan.py` es lo más parecido a un test: comprueba que la suma de las líneas cuadra con el total, que no quedan comidas sin cubrir y que en las dietas vegana/vegetariana no se cuela ningún ingrediente incompatible.

Tras editar cualquier JSON de `app/datos/` con el servidor arrancado, la ruta `/recargar` relee los datos sin reiniciar.

## Arquitectura

### La pieza central: el ingrediente

El proyecto conecta dos mundos que no encajan: las recetas hablan de **gramos**, el supermercado vende **envases con precio**. El ingrediente es el traductor, y por eso casi todo el código gira alrededor de `app/datos/ingredientes.json`.

```
RECETA (gramos) → INGREDIENTE (nutrición + términos de búsqueda) → PRODUCTO (envase + precio)
                   app/recetario.py         emparejador.py            catalogo.py
```

Dos hechos comprobados contra la API real que explican decisiones que si no parecerían arbitrarias:

1. **Mercadona tiene API pública no oficial** (`tienda.mercadona.es/api/`), así que no hay scraping de HTML. Todo el contacto con ella está aislado en `app/mercadona/cliente.py`: si la API cambia, ese es el único archivo que se toca.
2. **La API no devuelve información nutricional.** Ni la de Open Food Facts sirve (sus EAN dan 404). De ahí la tabla propia de 105 ingredientes.

### El flujo completo

```
API Mercadona ──> cliente.py ──> catalogo.py (SQLite, 4.304 productos)
                                      │
                       emparejador.py │ (offline, se guarda en emparejamientos.json)
                                      ▼
recetas.json ──> recetario.py ──> planificador.py ──> web.py ──> plantillas/
                                      ▲                  │
                                 cesta.py                └──> carrito.py ──> API Mercadona
                          (la matemática de envases)          (escribe, con token)
```

`app/datos_app.py` carga todo de una vez y es la puerta de entrada para la web y los scripts. Lanza `ErrorPreparacion` con el comando exacto a ejecutar cuando falta un paso previo.

### El flujo de la web: tres pasos, sin estado en el servidor

```
GET /  →  POST /elegir  →  POST /plan  →  POST /completar-compra
```

`/elegir` se llama a sí misma al pulsar "Actualizar" (lo distingue el campo oculto `recalcular`). **Todo el estado viaja en campos ocultos del formulario**, no en sesiones: sin estado que se desincronice, dos pestañas no se pisan y el botón "atrás" funciona.

En `planificador.py`, `generar_plan()` es la unión de dos funciones que también se usan por separado: **`proponer_recetas()`** (el algoritmo) y **`construir_plan()`** (montar el resultado a partir de una selección ya decidida, venga del algoritmo o del usuario). Esa separación es lo que hace posible la pantalla de selección.

### `cesta.py`: envases, no gramos

Es el módulo que hay que entender antes de tocar el algoritmo. La idea:

- Se compran **envases enteros** (`math.ceil(gramos / gramos_envase)`), así que el coste real solo tiene sentido calculado sobre el plan **entero**, nunca receta a receta.
- De ahí sale `Cesta.coste_marginal(aportes)`: lo que sube la cesta al añadir algo, contando lo que ya está comprado. **Acepta gramos negativos**, y eso se usa para evaluar intercambios de recetas sin reconstruir la cesta.
- `elegir_producto(candidatos, ingrediente, gramos)` decide qué formato comprar **en función de la cantidad**: el saco de 5 kg de patatas es el más barato por kilo pero no para 800 g. Por eso el emparejador guarda varios candidatos y no uno.

**Invariante que no se puede romper**: la suma de `coste_imputado` de todas las líneas de `lineas_de_compra()` debe ser exactamente `coste_total()`. Hubo un descuento silencioso a los productos de despensa que rompía esto (la lista sumaba 90,88 € y el total decía 79,54 €); se sustituyó por la casilla `despensa_en_casa`, que el usuario controla. Si vuelves a introducir un ajuste de precio, tiene que aparecer en la línea.

### `planificador.py`: voraz + escalada

Es un problema tipo mochila, sin solución óptima rápida. El algoritmo tiene dos fases y según de qué lado del presupuesto caiga la primera, la segunda va en un sentido u otro:

1. **Voraz** (`_elegir_recetas`): puntúa cada receta con `coste_marginal_por_ración × penalización_por_repetición × ajuste_calórico` y coge la mejor, hasta cubrir las raciones. Siempre añade recetas **enteras** (se cocina la cazuela entera).
2. **Escalada**, en una de dos direcciones:
   - `_mejorar_variedad()` si sobra dinero: intercambia recetas mientras suba `_calidad()` (recetas distintas + grupos de alimentos − repeticiones − distancia al objetivo calórico) y siga cabiendo.
   - `_abaratar()` si no cabe: intercambia buscando bajar el precio, para que la cifra de "presupuesto mínimo" que se le da al usuario sea real y no la primera que encontró el voraz.

`Contexto` es un dataclass que agrupa los cinco datos que viajaban juntos por seis firmas de función. Si añades un dato que necesiten las funciones internas, va ahí.

La nutrición es **informe, no restricción**: mezclar presupuesto máximo + objetivo calórico exacto + variedad haría el problema irresoluble muchas veces. Las calorías entran en `_calidad()` como preferencia fuerte (peso 15).

Dos optimizaciones que hay que respetar si tocas la escalada: se evalúa primero la calidad (cuenta trivial) y solo se calcula el precio de los cambios que mejoran; y el precio se calcula con `coste_marginal()` en vez de reconstruir la cesta. Un plan tarda <0,1 s.

### `emparejador.py`: texto → producto

Dos vueltas sobre los términos de `busqueda` de cada ingrediente:

- **Estricta**: el nombre del producto debe **empezar** por la primera palabra buscada. Mercadona nombra sus productos empezando por lo que son, así que esto separa "Bacón Hacendado cintas" de "Rosca de lomo, bacón y queso".
- **Relajada**: solo si la estricta no da nada.

`_palabra_encaja()` exige coincidencia exacta para palabras de ≤4 letras y prefijo para las largas. Sin esa distinción, `ajo` encontraba "caldo **bajo** en sal" y `pera` encontraba "gallinas cam**pera**s"; con coincidencia exacta siempre, `champinon` no encontraría "champiñones".

Los términos de `busqueda` deben escribirse **con el vocabulario de Mercadona**, no el propio: sus espaguetis son "Spaghetti", su cuscús "Cous cous", su carne picada "Preparado de carne picada vacuno".

`_elegir_variados()` guarda los 3 más baratos por gramo **más un formato pequeño**, pero solo si no cuesta más de 3× lo que el más barato. Ese tope evita que un bote de especia sustituya a la verdura fresca (la cebolla molida sale a ~25 €/kg frente a 1,80 €/kg de la fresca).

`emparejamientos.json` guarda **solo ids de producto, nunca precios** — se consultan en el momento. El campo `"fijado": true` protege las correcciones manuales de la siguiente regeneración.

### `carrito.py`: el único archivo que ESCRIBE en Mercadona

`cliente.py` lee (catálogo público, sin autenticación). `carrito.py` escribe (requiere `Authorization: Bearer`, guardado en `datos/token_mercadona.json`, fuera de Git). Están separados a propósito: leer un catálogo y tocar la cuenta de alguien son riesgos distintos.

**La forma exacta de la petición que añade líneas al carrito no se puede averiguar sin sesión iniciada** (hasta `OPTIONS` devuelve 401). El código prueba las combinaciones de `FORMATOS_PETICION` y, si ninguna funciona, muestra la respuesta literal del servidor. Ajustarlo es añadir una línea a esa lista. Ver `docs/08-completar-la-compra.md`.

**El botón nunca se queda sin hacer nada**: sin token, con token caducado o si falla la petición, cae a una página con todos los productos enlazados y un botón de copiar. Degradar, no romperse.

### `buscador.py`: fotos de plato

Tres fuentes en orden: **Wikipedia (es)** → **Openverse** → **Wikimedia Commons**. Wikipedia acierta mucho más (la foto de un artículo la eligió una persona para ilustrar ese plato) pero **solo con consultas de dos palabras o más**: con una sola se va a la botánica y a la geografía.

Dos reglas que costaron tres intentos y están explicadas en `docs/09-las-fotos-de-los-platos.md`:

- **Nunca una consulta formada solo por palabras genéricas.** "crema de" o "ensalada" a secas devuelven cualquier cosa (la misma foto de un bizcocho acabó en cuatro recetas de crema).
- **`GENERICAS` contiene solo palabras que NO identifican el plato.** Meter ahí "lasaña" o "paella" fue un error que dejó 82 de 130 recetas sin foto.

Se **ordena** por relevancia pero no se descarta nada; quien exige `RELEVANCIA_MINIMA` es la preselección, no la búsqueda.

## Detalles que muerden

- **`@dataclass(eq=False)` en `Receta`** es obligatorio: el planificador la usa como clave de diccionario, y el `__eq__` que genera dataclass por defecto la haría no hasheable.
- **`.gitignore` usa `/datos/` con barra inicial.** Sin ella, Git ignoraba también `app/datos/`, que sí debe subirse (recetas e ingredientes escritos a mano). `datos/` en la raíz es generado y no se sube.
- **Filtrado por dieta en dos sitios.** Las recetas se filtran en `generar_plan`, pero los básicos de desayuno son un camino independiente: `_gramos_de_basicos()` aplica el campo `alternativas` del JSON **y además** una comprobación final contra `vegano`/`vegetariano`. Un plan vegano llevaba leche por saltarse esto.
- **Pillow debe ser ≥12** para tener wheels de Python 3.14; las versiones anteriores intentan compilar y fallan por falta de zlib.
- **Encoding**: los scripts hacen `sys.stdout.reconfigure(encoding="utf-8")` porque en Windows, al redirigir la salida, Python usa una codificación que revienta con tildes.
- **Educación con las APIs**: `PAUSA_ENTRE_PETICIONES = 0.4` en Mercadona, `PAUSA = 0.4` en los bancos de imágenes, y `User-Agent` que se identifica honestamente en las cuatro. No quitar.
- **El único JavaScript del proyecto** (`selector.js`) calcula las comidas cubiertas pero **no el precio**, a propósito: el precio depende del coste marginal y solo lo sabe el servidor. Un total aproximado en el navegador no cuadraría con el de la página siguiente.
- **Al filtrar en el selector, las tarjetas se esconden con `display:none`, no se borran del DOM.** Un input escondido se sigue enviando; uno borrado, no. Borrarlas vaciaría media selección al filtrar.
- **`revisada: true` en `imagenes_recetas.json`** protege las fotos que eligió una persona de la siguiente pasada del preseleccionador. Misma idea que `"fijado": true` en los emparejamientos.
- **Al cambiar la foto de una receta hay que borrar `datos/imagenes/plato_<id>.jpg`.** Si no, se sigue viendo la vieja y parece que el cambio no funciona.

## Ajustes

Todo lo configurable está en `app/config.py`, comentado: almacén de Mercadona (`ALMACEN`, por defecto `mad1`), objetivos calóricos, `PENALIZACION_REPETICION`, y las rutas. Los pesos de `_calidad()` están en la cabecera de `planificador.py`.
