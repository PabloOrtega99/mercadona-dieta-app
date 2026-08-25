# 08 · Completar la compra: llevar la lista al carrito de Mercadona

Archivos que explica este documento:
[`app/token_mercadona.py`](../app/token_mercadona.py) ·
[`app/mercadona/carrito.py`](../app/mercadona/carrito.py) ·
[`app/plantillas/token.html`](../app/plantillas/token.html)

---

## 1. Lo primero, para que no haya dudas

> ### El botón LLENA el carrito. NO compra nada.
>
> No hace ningún pedido, no elige hora de entrega y no paga. Después de
> pulsarlo tienes que entrar en Mercadona, revisar la cesta y comprar tú.
> Esta aplicación no tiene forma técnica de hacer un pedido.

Si algo sale mal, lo peor que puede pasar es que te encuentres productos de
más en el carrito. Se quitan desde la web de Mercadona en dos clics.

---

## 2. Por qué hace falta identificarse

Esto lo comprobé antes de escribir una línea de código, y condiciona todo lo demás:

| Petición | Sin identificarse |
|---|---|
| `GET /api/categories/` (catálogo) | ✅ Funciona |
| `GET /api/products/4241/` | ✅ Funciona |
| `GET /api/customers/<id>/cart/` | ❌ **401 No autorizado** |
| `OPTIONS /api/customers/<id>/cart/` | ❌ **401 No autorizado** |

Leer el catálogo es público. Tocar un carrito, no: **un carrito es de alguien**, y ese alguien tienes que ser tú. **No existe un carrito anónimo.**

Así que la única forma de que esto funcione es que la app use **tu sesión**. Y para eso hace falta un token.

---

## 3. Qué es un token

Cuando entras en `tienda.mercadona.es` con tu usuario y contraseña, su servidor te devuelve un código largo que empieza por `eyJ...`. A partir de ahí, tu navegador **no vuelve a mandar la contraseña nunca**: manda ese código en cada petición, y el servidor sabe que eres tú.

> Es la pulsera que te ponen al entrar a un recinto: la enseñas y pasas, sin repetir quién eres cada vez.

Ese código se llama **JWT** y tiene tres partes separadas por puntos:

```
   eyJhbGciOiJIUzI1NiJ9  .  eyJjdXN0b21lcl9pZCI6IjEyMyIsImV4cCI6MTc...  .  4pcPyMD09olPSyXnr...
   └──── cabecera ─────┘     └──────────── contenido ───────────────┘     └───── firma ─────┘
```

Las dos primeras partes son **JSON escrito en base64**, y base64 **no es cifrado**: es solo una forma de escribir datos usando letras y números. O sea que el contenido de un token **se puede leer sin ninguna clave**. Lo que protege el token es la *firma*, que impide fabricar uno falso, no que se lea.

Eso nos viene bien para dos cosas, y las dos las hace [`token_mercadona.py`](../app/token_mercadona.py):

1. **Sacar tu identificador de cliente**, así no hay que pedírtelo aparte.
2. **Saber cuándo caduca**, para avisarte antes de que falle en lugar de después.

Y también implica algo que conviene tener claro: **un token es como una contraseña temporal**. Quien lo tenga puede entrar en tu cuenta hasta que caduque. Por eso no se sube a ningún sitio.

---

## 4. Cómo conseguirlo (dos minutos)

1. Abre [tienda.mercadona.es](https://tienda.mercadona.es) e **inicia sesión**.
2. Pulsa **F12**. Se abre el panel de herramientas del navegador.
3. Ve a la pestaña **Red** (o *Network*).
4. Haz cualquier cosa en la web: busca un producto, entra en una categoría. Verás cómo se llena la lista de peticiones.
5. Pincha en cualquiera de esas líneas y busca, dentro de **Cabeceras de solicitud** (*Request Headers*), una que ponga:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoi...
```

6. Copia ese texto entero.
7. En la app, ve a **Conectar mi cuenta** (`http://localhost:8000/carrito/token`), pégalo y guarda.

No te preocupes por copiar de más: si te traes el `Authorization:` o el `Bearer`, o unas comillas, se quitan solos. Eso lo hace `_limpiar()`.

Al guardar, la app **prueba el token contra Mercadona de verdad**. No basta con que tenga buena pinta: podría estar revocado. Es mejor enterarse ahí que cuando vayas a hacer la compra.

### Dónde se guarda

En `datos/token_mercadona.json`, en tu ordenador. Esa carpeta ya está protegida por la regla `/datos/` del [`.gitignore`](../.gitignore), así que **no puede subirse a GitHub ni por accidente**.

Como consecuencia: en tu otro ordenador tendrás que repetir estos pasos. Es lo correcto, aunque sea un poco incómodo. Las credenciales no viajan.

### Caduca

El token dura unas **6 semanas**. Cuando caduque, el botón te lo dirá con todas las letras y vuelves a hacer los cinco pasos. La pantalla de conexión te enseña siempre cuántos días quedan.

---

## 5. Cómo funciona por dentro

Todo el código que **escribe** en Mercadona está en un solo archivo: [`app/mercadona/carrito.py`](../app/mercadona/carrito.py). Su hermano `cliente.py` es el único que **lee**.

Están separados a propósito. Leer un catálogo público y tocar la cuenta de alguien son dos cosas de riesgo muy distinto, y conviene que se vea de un vistazo dónde pasa cada una.

El proceso:

```
   1. Leer el carrito actual        ← comprueba que el token vale ANTES de escribir
   2. Juntar lo que ya hay con lo nuevo
   3. Escribir el carrito completo
```

Dos detalles de ese proceso que merece la pena entender:

**Se lee antes de escribir.** Si el token no vale, es mucho mejor descubrirlo con una petición que no cambia nada que a mitad de meter treinta productos.

**Si un producto ya estaba, se queda la cantidad MAYOR, no se suman.** Si generas el plan dos veces y pulsas el botón dos veces, no quieres acabar con el doble de pollo.

---

## 6. Si no funciona

Aquí hay que ser honesto: **la forma exacta de la petición que añade líneas al carrito no está documentada en ningún sitio público, y no se puede averiguar sin una sesión iniciada.** Lo intenté: hasta `OPTIONS` devuelve 401.

Lo que sí sabemos con certeza: que va contra `/api/customers/<id>/cart/` y que necesita la cabecera `Authorization: Bearer`.

Así que el código prueba **las cuatro formas más probables**, en orden:

```python
FORMATOS_PETICION = [
    ("PUT",  "lines",    "product_id"),
    ("PUT",  "lines",    "id"),
    ("POST", "lines",    "product_id"),
    ("PUT",  "products", "product_id"),
]
```

Si ninguna funciona, la app te enseña **la respuesta literal del servidor**. Con eso se arregla en un minuto:

1. En Mercadona, con **F12 → Red** abierto, **añade un producto al carrito a mano**.
2. Busca en la lista la petición que se manda al hacerlo (irá a `.../cart/`).
3. Mira dos cosas: el **método** (PUT, POST, PATCH...) y el **cuerpo** de la petición (*Payload*), que te dirá cómo se llaman los campos.
4. Añade esa combinación a `FORMATOS_PETICION`, arriba del todo.

Es una lista precisamente para eso: para que ajustarlo sea añadir una línea, no reescribir el archivo.

> **Consejo**: haz la captura del punto 1 **a la vez** que sacas el token. Es la misma sesión de F12 y te ahorras repetirlo.

### Pase lo que pase, el botón sirve para algo

Si no hay token, si ha caducado, si la petición falla o si no hay internet, la página de resultado **enseña igualmente la lista completa con cada producto enlazado a su página de Mercadona**, más un botón para copiarla al portapapeles.

Es un principio que merece la pena coger: **degradar, no romperse**. Una función automática que falla y te deja sin nada es peor que no tenerla. Una que falla y te deja el trabajo hecho a medias sigue siendo útil.

---

## 7. Riesgos, dichos claramente

- **Es tu cuenta real.** Los productos van a tu carrito de verdad.
- **Es una API no oficial.** Mercadona no la ha publicado para terceros y puede cambiarla cuando quiera. Si eso pasa, el botón dejará de funcionar y caerá al modo enlaces.
- **El token es sensible.** Está en `datos/`, fuera de Git. No lo pegues en ningún sitio público, y si crees que se ha filtrado, cierra sesión en Mercadona: eso lo invalida.
- **Uso personal.** Esto está pensado para que tú manejes tu propia cuenta, y las peticiones son las mismas que haría tu navegador.

---

## 8. Una mejora posible para más adelante

Al explorar la API encontré esto:

```
OPTIONS /api/auth/tokens/  →  acepta: refresh_token, username, password
```

Existe un mecanismo de **refresh token**: un código de vida más larga que sirve para pedir tokens nuevos sin volver a hacer login. Si algún día te cansas de renovar el token cada mes y medio, ese es el camino: guardar el *refresh token* y que la app se saque uno nuevo sola cuando el suyo caduque.

No está implementado a propósito. Un refresh token es una credencial más potente y de vida más larga, y para empezar es mejor la opción que se entiende entera de un vistazo. Queda apuntado por si en el futuro compensa.
