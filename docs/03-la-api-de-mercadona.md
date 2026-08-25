# 03 · De dónde salen los precios: la API de Mercadona

Archivos que explica este documento:
[`app/mercadona/cliente.py`](../app/mercadona/cliente.py) ·
[`app/mercadona/catalogo.py`](../app/mercadona/catalogo.py) ·
[`scripts/actualizar_catalogo.py`](../scripts/actualizar_catalogo.py)

---

## 1. Scraping vs. API

Tú pediste "webscraping o lo que sea, de la mejor forma posible". Resultó que había algo mejor que el scraping. Merece la pena entender la diferencia porque se aplica a cualquier proyecto parecido.

### Qué es el *scraping*

Descargar la página web tal cual la ve tu navegador (un montón de HTML) y rebuscar el dato entre las etiquetas:

```html
<div class="product-cell">
  <h4 class="product-cell__description-name">Arroz redondo Hacendado</h4>
  <p class="product-price__unit-price">1,15 €</p>
</div>
```

Funciona, pero es frágil por una razón de fondo: **ese HTML está pensado para que lo lean personas, no programas**. El día que Mercadona rediseñe la web y `product-price__unit-price` pase a llamarse otra cosa, tu programa deja de funcionar sin avisar. Y no se enterará: seguirá ejecutándose y devolviendo listas vacías.

### Qué es una **API**

Una API (*Application Programming Interface*) es una dirección web que, en vez de devolver una página bonita, devuelve **los datos en crudo y ordenados**, pensados para que los lea un programa.

Abre esto en el navegador y lo ves tú mismo:

```
https://tienda.mercadona.es/api/categories/118/?lang=es&wh=mad1
```

Sale algo así:

```json
{
  "id": 118,
  "name": "Arroz",
  "categories": [{
    "products": [{
      "id": "5044",
      "display_name": "Arroz redondo Hacendado",
      "thumbnail": "https://prod-mercadona.imgix.net/images/....jpg",
      "price_instructions": {
        "unit_price": "1.15",
        "unit_size": 1.0,
        "size_format": "kg",
        "reference_price": "1.150",
        "reference_format": "kg"
      }
    }]
  }]
}
```

Eso es **JSON**, y es infinitamente mejor para nosotros:

| | Scraping | API |
|---|---|---|
| Los datos vienen... | mezclados con el diseño | limpios y estructurados |
| Se rompe si... | cambian el diseño (a menudo) | cambian los datos (raro) |
| Precio | hay que quitar el "€", la coma... | ya es un número |
| Peso del envase | no aparece | viene explícito |

### Ojo: es una API **no oficial**

Esta API existe porque la propia web de Mercadona la usa por detrás para pintarse. No está documentada ni pensada para terceros, así que:

- **Puede cambiar sin avisar.** Por eso todo el contacto con ella está encerrado en un solo archivo, `cliente.py`. Si un día se rompe, sabes exactamente dónde mirar.
- **Hay que usarla con educación.** Ver el punto 4.

---

## 2. Cómo está organizado el catálogo

Mercadona ordena los productos en dos niveles, como los pasillos de la tienda:

```
26 categorías              151 subcategorías              ~4.000 productos
─────────────────          ──────────────────             ────────────────
Arroz, legumbres y pasta ┬─ Arroz ─────────────────────── Arroz redondo, 1,15 €
                         ├─ Legumbres                     Arroz largo, 1,20 €
                         └─ Pasta y fideos                ...
Carne ───────────────────┬─ Aves y pollo
                         └─ ...
```

Necesitamos dos direcciones distintas:

| Para qué | Dirección |
|---|---|
| El mapa de categorías | `/api/categories/` |
| Los productos de una subcategoría | `/api/categories/118/` |

Y el proceso es: pedir el mapa (1 petición) → recorrer las 151 subcategorías (151 peticiones) → juntar todos los productos.

### El parámetro `wh`

Fíjate en el final de la dirección: `?lang=es&wh=mad1`. Lo que va detrás de `?` son **parámetros**, ajustes de la petición.

`wh` es de *warehouse*, almacén. Mercadona sirve cada zona desde un almacén distinto y el surtido puede variar. Comprobados: `mad1` (Madrid), `bcn1` (Barcelona), `vlc1` (Valencia), `svq1` (Sevilla). Se cambia en [`app/config.py`](../app/config.py).

---

## 3. El campo más importante: `price_instructions`

Aquí está todo lo que necesita el proyecto. Merece un vistazo detenido porque **de entenderlo bien depende que las cuentas salgan**:

```json
"price_instructions": {
  "unit_price":      "17.75",   ← lo que PAGAS por un envase
  "unit_size":        5.0,      ← cuánto trae el envase
  "size_format":     "l",       ← en qué unidad está ese 5.0
  "reference_price": "3.550",   ← precio por litro
  "reference_format":"L",
  "approx_size":      false     ← ¿el peso es aproximado?
}
```

Comprobé varios tipos de producto contra la API real y el patrón se cumple siempre:

| Producto | `unit_price` | `unit_size` | `size_format` | Qué significa |
|---|---|---|---|---|
| Arroz redondo | 1,15 | 1.0 | `kg` | Paquete de 1 kg |
| Aceite garrafa | 17,75 | 5.0 | `l` | Garrafa de 5 L |
| Pack 6 yogures | 1,00 | 0.75 | `kg` | 750 g en total (6 × 125 g) |
| Docena de huevos | 3,05 | 12.0 | `ud` | 12 piezas |
| Plátano | 0,39 | 0.17 | `kg` | ~170 g, `approx_size: true` |

Dos cosas dignas de comentar:

**a) Los packs ya vienen sumados.** El pack de 6 yogures dice `unit_size: 0.75` (750 g), no `0.125`. Mercadona hace la multiplicación por nosotros. Un alivio.

**b) `size_format: "ud"` es el caso raro.** Con los huevos, la API nos dice "12 piezas" pero no cuánto pesa un huevo. Eso lo tiene que aportar nuestra tabla de ingredientes, con un campo `gramos_por_unidad`. Es la primera pista de por qué necesitamos esa tabla.

De ahí sale la función [`_convertir_tamano()`](../app/mercadona/cliente.py), que traduce todo eso a **gramos por envase**, que es la única medida con la que trabaja el resto del proyecto.

### El detalle de que los precios vengan como texto

Fíjate: `"unit_price": "17.75"` va **entre comillas**. Es texto, no número. No puedes sumarlo directamente: `"1.15" + "1.20"` en Python da `"1.151.20"`, que no es un precio, es un disparate.

Por eso existe la función `_a_numero()` en `cliente.py`. Es la clase de detalle que no aparece en ningún tutorial y que te hace perder media tarde si no lo ves venir.

---

## 4. Usar una API ajena con educación

Esto es tan importante como el código. Cuando usas un servicio que no es tuyo:

**Espera entre peticiones.** El ordenador podría lanzar las 151 peticiones en dos segundos. Eso se parece mucho a un ataque, y bloquearte la IP sería una respuesta razonable. Ponemos `PAUSA_ENTRE_PETICIONES = 0.4` segundos: el catálogo tarda 3 minutos y no molestamos a nadie.

**Identifícate honestamente.** La cabecera `User-Agent` dice quién hace la petición. Mucha gente se disfraza de Chrome; nosotros ponemos `mercadona-dieta-app/1.0 (proyecto personal)`. Si a alguien de Mercadona le da por mirar los registros, verá exactamente qué es y no le parecerá sospechoso.

**Pon un límite de espera.** El `timeout` de 20 segundos evita que tu programa se quede colgado para siempre si el servidor no contesta.

**Reintenta, pero con retroceso.** Si falla, esperamos 1 s, luego 2 s, luego 3 s. Insistir cada décima de segundo contra un servidor saturado solo empeora las cosas para todos.

**Descarga una vez, consulta muchas.** Ver el punto siguiente.

---

## 5. Por qué guardamos una copia local

El planificador, al montar un menú, consulta precios **miles de veces**. Sería absurdo (y abusivo) hacer miles de peticiones a Mercadona para eso.

Así que descargamos el catálogo una vez y lo guardamos en **SQLite**, una base de datos que es literalmente **un solo archivo**: `datos/catalogo.sqlite`. Viene incluida con Python, no hay nada que instalar ni ningún servidor que arrancar.

Ventajas: la app va instantánea, no abusamos de Mercadona y **funciona sin internet**.
Inconveniente: los precios son de cuando lo descargaste. Por eso la app enseña siempre la fecha de la última actualización, y basta con volver a lanzar el script para refrescarlos.

### Un par de decisiones de la base de datos que merece la pena entender

**La columna `nombre_normalizado`.** Guardamos cada nombre dos veces: como viene ("Plátano de Canarias IGP") y en minúsculas sin tildes ("platano de canarias igp"). ¿Por qué duplicar? Porque para el ordenador "plátano" y "platano" no tienen absolutamente nada que ver. Guardar la versión normalizada nos permite buscar sin preocuparnos de tildes ni mayúsculas.

**Reemplazar en vez de actualizar.** Al actualizar borramos el catálogo entero y metemos el nuevo. Parece bruto, pero tiene una ventaja: **los productos descatalogados desaparecen solos**. Si fuéramos añadiendo sin más, la base de datos se llenaría de fantasmas con precios de hace meses que el planificador seguiría metiendo en tu lista de la compra.

**Los `?` de las consultas.** En el código verás:

```python
conexion.execute("SELECT * FROM productos WHERE id = ?", (id_producto,))
```

y nunca esto otro:

```python
conexion.execute(f"SELECT * FROM productos WHERE id = {id_producto}")  # ✗ MAL
```

La segunda forma es la puerta de entrada a la **inyección SQL**, el fallo de seguridad más clásico que existe. Aquí no hay riesgo real (los datos vienen de Mercadona, no de un desconocido), pero el hábito hay que cogerlo bien desde el principio, porque el día que sí importe no te acordarás de cambiarlo.

---

## 6. Cómo se usa

```powershell
python scripts/actualizar_catalogo.py
```

Tarda unos 3 minutos y va enseñando por dónde va. Al terminar dice cuántos productos ha guardado.

**Cuándo ejecutarlo:**
- La primera vez, en cada ordenador (la base de datos no viene de GitHub).
- Cuando quieras precios frescos. Una vez por semana sobra.

El script está preparado para lo que puede salir mal: si falla una subcategoría, apunta el fallo y sigue con las otras 150; si aparece un formato de envase que no conoce, te avisa al final. **No falla en silencio**, que es la peor forma de fallar.
