# 07 · La web: cómo se pinta todo en el navegador

Archivos que explica este documento:
[`app/web.py`](../app/web.py) ·
[`app/plantillas/`](../app/plantillas/) ·
[`app/estaticos/estilo.css`](../app/estaticos/estilo.css) ·
[`app/imagenes/collage.py`](../app/imagenes/collage.py)

---

## 1. Qué es un "servidor web" local

Cuando escribes `http://localhost:8000` en el navegador, pasa esto:

```
   TU NAVEGADOR                        FLASK (app/web.py)
        │                                     │
        │   "dame la página /"                │
        ├────────────────────────────────────>│
        │                                     │  busca qué función
        │                                     │  responde a "/"
        │                                     │  → inicio()
        │                                     │
        │                                     │  rellena la plantilla
        │                                     │  inicio.html con datos
        │                                     │
        │   HTML ya montado                   │
        │<────────────────────────────────────┤
        │                                     │
   lo dibuja
```

**`localhost` es tu propio ordenador.** El servidor se ejecuta en tu máquina y solo tú puedes verlo: no está publicado en internet, nadie de fuera puede entrar. El `8000` es el número de puerta (*puerto*) por el que escucha.

Se para con `Ctrl + C` en la terminal.

---

## 2. Las rutas

En Flask escribes funciones normales y les pones encima una etiqueta que dice a qué dirección responden:

```python
@app.route("/")
def inicio():
    return render_template("inicio.html", ...)
```

Esa etiqueta con `@` se llama **decorador**. Es la forma que tiene Python de decir "envuelve esta función con este comportamiento extra". Aquí, el comportamiento extra es "apúntate en la lista de rutas del servidor".

Las rutas de la app:

| Dirección | Qué hace |
|---|---|
| `GET /` | El formulario |
| `POST /plan` | Recibe el formulario, calcula el plan y lo enseña |
| `GET /receta/<id>` | La ficha de una receta |
| `GET /receta/<id>/imagen.png` | El collage de esa receta |
| `GET /recargar` | Vuelve a leer los JSON sin reiniciar el servidor |

### GET y POST

- **GET** = "dame esto". Los datos van en la dirección, a la vista.
- **POST** = "toma estos datos". Van en el cuerpo de la petición, sin verse.

El formulario usa POST porque envía varios campos y quedaría feo en la barra de direcciones.

### `/recargar`, que parece una tontería y no lo es

Vuelve a leer `recetas.json` e `ingredientes.json` sin reiniciar el servidor. Mientras estés añadiendo recetas, la diferencia entre *"guardo, pulso un botón, veo el resultado"* y *"guardo, cambio de ventana, Ctrl+C, flecha arriba, Enter, espero, vuelvo al navegador"* es la diferencia entre añadir veinte recetas de una sentada o cansarte a la tercera.

---

## 3. Las plantillas: HTML con huecos

Una plantilla es HTML normal con dos añadidos de **Jinja2**:

```html
{{ plan.coste_total }}          <-- aquí se pinta un valor

{% for elegida in plan.elegidas %}   <-- esto es un bucle
  <h3>{{ elegida.receta.nombre }}</h3>
{% endfor %}
```

### La herencia de plantillas

[`base.html`](../app/plantillas/base.html) tiene el esqueleto (cabecera, pie, el `<head>`) con **huecos**:

```html
<main>
  {% block contenido %}{% endblock %}
</main>
```

Y las demás páginas solo rellenan su hueco:

```html
{% extends "base.html" %}
{% block contenido %}
  ... lo propio de esta página ...
{% endblock %}
```

Así la cabecera y el pie se escriben **una sola vez**. Cambias el logo en `base.html` y cambia en las cuatro páginas. Es el mismo principio de "no copies y pegues" que en el código Python.

### Los filtros

```html
{{ 12.5 | euros }}     →  12,50 €
{{ 1500 | gramos }}    →  1,50 kg
```

Son funciones definidas en `web.py` con `@app.template_filter`. Sirven para que las plantillas se queden limpias, sin cuentas ni formateos por el medio. El HTML dice **qué** enseñar; el Python decide **cómo** se ve.

Detalle del filtro `euros`: Python formatea los números a la inglesa (`1,234.50`) y en español es al revés (`1.234,50`). El truco de las tres sustituciones, con la almohadilla como aparcamiento temporal, está comentado en [`utiles.py`](../app/utiles.py).

---

## 4. Validar lo que llega del formulario

Todo lo que llega de un formulario es **texto**, y puede ser cualquier cosa: vacío, "hola", o un número absurdo. Aunque el campo sea `type="number"`, esa validación la hace el navegador, y el navegador se puede saltar.

```python
presupuesto = _numero(request.form.get("presupuesto"), 20, 2000, 80)
```

`_numero()` convierte, pone límites y devuelve un valor por defecto si no puede. También acepta comas, porque un usuario español escribirá "80,5".

> **La regla general**: nunca te fíes de lo que llega de fuera. Aquí eres tú el único usuario y no hay riesgo real, pero es el hábito que evita la mayoría de los agujeros de seguridad del mundo real.

Lo mismo con la dieta: si llega una que no existe en nuestra lista, se usa "equilibrada" en lugar de reventar.

---

## 5. Los collages de las recetas

**El problema**: el recetario es nuestro, así que no tenemos fotos de los platos. Buscar 60 fotos con licencia libre sería un trabajo aburrido y los enlaces acabarían rompiéndose.

**La solución**: la API de Mercadona **sí** nos da una foto de cada producto. Así que cogemos las fotos de los ingredientes principales y montamos un mosaico 2×2.

```
   ┌─────────────┬─────────────┐
   │ carne       │ tomate      │
   │ picada      │ triturado   │
   ├─────────────┼─────────────┤
   │ arroz       │ cebollas    │
   │             │             │
   ├─────────────┴─────────────┤
   │  Albóndigas en salsa      │
   └───────────────────────────┘
```

Nunca se rompe, no depende de nadie, y encaja visualmente con la lista de la compra, que lleva esas mismas fotos.

"Ingredientes principales" son los que **más pesan** en la receta, dejando fuera condimentos y despensa: una foto de un bote de sal no le dice nada a nadie sobre qué plato es.

### Tres detalles del código

**Se cachean.** Montar un collage implica descargar cuatro fotos de internet. Se hace **una vez** y se guarda en `datos/imagenes/`. En las pruebas: 0,36 s la primera vez, 0,012 s las siguientes.

**Se recorta, no se estira.** Estirar una foto rectangular hasta hacerla cuadrada deja los productos con una pinta rarísima. Se recorta un cuadrado centrado.

**Si falla, no pasa nada.** Un `except` amplio devuelve una imagen de reserva. Que no haya internet para descargar una foto no puede tirar abajo el menú y la lista de la compra, que es lo que de verdad importa.

> Fue **mirando uno de estos collages** como se descubrió el error de la cebolla molida. Ver los datos, literalmente, encuentra cosas que ninguna comprobación automática estaba buscando. Está contado en el [documento 05](05-emparejar-ingredientes-productos.md).

---

## 6. El CSS

Escrito a mano, sin Bootstrap ni Tailwind. Para una app de cuatro páginas esas herramientas añaden más complejidad de la que quitan, y Tailwind además necesitaría instalar Node y montar un proceso de compilación.

Cuatro cosas de [`estilo.css`](../app/estaticos/estilo.css) que merece la pena conocer porque se usan en todas partes:

### Variables

```css
:root { --verde: #00843d; }
.boton { background: var(--verde); }
```

Cambias el verde en un sitio y cambia en toda la app.

### `box-sizing: border-box`

```css
*, *::before, *::after { box-sizing: border-box; }
```

Hace que el `padding` y el borde se cuenten **dentro** del ancho que le das a un elemento. Sin esto, poner `width: 100%` y `padding: 20px` da un elemento más ancho que su contenedor. Es la causa de la mitad de los desajustes de maquetación de los principiantes, y se arregla con esta línea al principio de todo.

### Rejillas que se adaptan solas

```css
grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
```

"Mete tantas columnas de al menos 215 px como quepan". Las tarjetas de receta se reordenan solas al cambiar el tamaño de la ventana, sin escribir ni una regla para el móvil.

### Tarjetas seleccionables sin JavaScript

Las tarjetas de dieta son un `<input type="radio">` invisible dentro de un `<label>`. Pulsar la tarjeta marca el radio, y el CSS colorea la tarjeta con el selector `:checked`:

```css
.dieta input:checked + .dieta-cuerpo {
  border-color: var(--verde);
  background: var(--verde-claro);
}
```

Cero JavaScript, y funciona con el teclado y con lectores de pantalla.

> Detalle importante: el radio se esconde con `opacity: 0`, **no** con `display: none`. Con `display: none` dejaría de existir para el navegador y no podrías seleccionarlo con el teclado.

---

## 7. Imprimir la lista de la compra

Al final la lista hay que llevársela al supermercado. El botón llama a `window.print()`, que abre el diálogo de imprimir del navegador (desde ahí se puede guardar como PDF, que es lo más cómodo para el móvil).

Y hay un bloque de CSS solo para el papel:

```css
@media print {
  .cabecera, .pie, .boton-secundario,
  .rejilla-recetas, .nutricion { display: none !important; }

  .seccion-compra, .linea-compra { break-inside: avoid; }
}
```

En papel sobra todo menos la lista: fuera menú de navegación, fuera botones, fuera fotos de recetas. Y `break-inside: avoid` evita que una sección se parta entre dos hojas.

---

## 8. La página de error

Si falta el catálogo, la app **arranca igualmente** y enseña una página que dice exactamente qué comando ejecutar:

```
Falta preparar algo antes de empezar

  El catalogo de Mercadona esta vacio.
  Ejecuta:  python scripts/actualizar_catalogo.py
```

Es la diferencia entre un error útil y uno inútil. Lo fácil habría sido dejar que el servidor no arrancase y soltase un `FileNotFoundError` en la terminal. Habría sido igual de "correcto" y no te habría ayudado en nada.

---

## 9. Cómo se comprobó que funciona

Además de abrirlo y mirarlo, se pasó un script de prueba que pide cada página y verifica el resultado. Lo que comprueba:

- Que cada página responde y contiene lo que tiene que contener.
- **Que la suma de la lista de la compra cuadra exactamente con el total.**
- Que se generan los collages y que la caché funciona.
- Que se avisa cuando el presupuesto no llega.
- Que la app no revienta con datos basura en el formulario.
- Que una receta inexistente devuelve un 404.

La segunda comprobación fue la que encontró un fallo de verdad: la lista sumaba **90,88 €** y el total decía **79,54 €**. El porqué y cómo se arregló está contado en el comentario largo de [`config.py`](../app/config.py). Resumen: el arreglo no fue matemático sino de diseño, y consistió en dejar de aplicar un descuento silencioso y preguntarle al usuario si ya tiene la despensa en casa.
