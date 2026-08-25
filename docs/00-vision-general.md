# 00 · Visión general: qué estamos construyendo y cómo encaja todo

Este es el documento que conviene leer primero. No tiene código: explica **la idea** y **por qué el proyecto está partido en las piezas que verás**.

---

## 1. El problema que resolvemos

Quieres poder decir:

> "Tengo **80 €** y quiero comer bien durante **2 semanas** con una dieta **alta en proteína**."

y que un programa te conteste con:

1. Un **menú** de recetas concretas para esas dos semanas.
2. Una **lista de la compra de Mercadona** con productos reales, precios reales y el total.

Y que si mañana Mercadona sube el precio del pollo, la app se entere sola.

---

## 2. La dificultad de fondo (esto es lo importante)

A primera vista parece que basta con "leer los precios de Mercadona". Pero hay un hueco entre dos mundos que no encajan:

| El mundo de las recetas | El mundo del supermercado |
|---|---|
| "150 g de pechuga de pollo" | "Bandeja de filetes de pechuga de pollo, 900 g, 6,45 €" |
| Habla de **gramos de comida** | Habla de **envases con precio** |
| Necesita saber calorías y proteínas | No te dice ni una caloría |

Ese hueco es el proyecto entero. Y se cruza con una pieza que se lleva todo el protagonismo: **el ingrediente**.

```
   RECETA                 INGREDIENTE                  PRODUCTO
"Pollo al horno"    →   "pechuga_pollo"        →   "Filetes pechuga
 necesita 150 g          165 kcal/100 g              Hacendado, 900 g"
                         31 g proteína/100 g          6,45 €
                         no es vegetariano
```

El ingrediente es el traductor. Por un lado sabe **de nutrición** (para que la dieta signifique algo). Por otro sabe **con qué producto de Mercadona se compra** (para que el precio sea real). Todo el proyecto gira alrededor de esa tabla de ingredientes.

---

## 3. Los tres hallazgos que decidieron el diseño

Antes de programar nada, probé la web de Mercadona a ver qué se podía sacar. Tres cosas cambiaron el plan:

**a) No hace falta *scraping*.** El *scraping* consiste en descargar la página web y "leer" el HTML buscando los precios entre las etiquetas. Es frágil: si Mercadona cambia el diseño de la web, tu programa deja de funcionar. Resulta que Mercadona tiene una **API** (te lo explico en [`03-la-api-de-mercadona.md`](03-la-api-de-mercadona.md)): una dirección que devuelve los datos ya ordenados y limpios. Mucho mejor.

**b) Mercadona NO da información nutricional.** Ni calorías, ni proteínas, ni grasas. Solo alérgenos e ingredientes en texto. También probé Open Food Facts (una base de datos libre de productos) con los códigos de barras de Mercadona: no los tiene.
→ **Consecuencia:** la tabla nutricional la mantenemos nosotros, ingrediente a ingrediente. Es la decisión más importante de todo el proyecto.

**c) Compras envases enteros, no gramos.** Si una receta lleva 50 g de aceite, no pagas 50 g: pagas una botella. Este detalle, que parece una tontería, es en realidad el corazón del algoritmo. Lo verás en [`06-el-algoritmo-del-menu.md`](06-el-algoritmo-del-menu.md).

---

## 4. Las piezas y qué hace cada una

Piensa en el proyecto como una cadena de montaje. Cada pieza recibe algo, lo transforma y se lo pasa a la siguiente.

```
  ┌─────────────────────────────────────────────────────────┐
  │  INTERNET: la API de Mercadona                          │
  └────────────────────────┬────────────────────────────────┘
                           │  (una vez cada varios días)
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  1. cliente.py + catalogo.py                            │
  │     Se bajan los ~4.000 productos con precio e imagen   │
  │     y los guardan en una base de datos local.           │
  └────────────────────────┬────────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  2. emparejador.py                                      │
  │     Decide QUÉ producto de Mercadona corresponde a      │
  │     cada ingrediente. "pechuga_pollo" → producto 12345  │
  └────────────────────────┬────────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  3. cesta.py                                            │
  │     Dada una lista de gramos, calcula cuántos ENVASES   │
  │     hay que comprar y cuánto cuestan de verdad.         │
  └────────────────────────┬────────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  4. planificador.py   ← EL CEREBRO                      │
  │     Elige qué recetas cocinar para cubrir las comidas    │
  │     sin pasarse del presupuesto.                        │
  └────────────────────────┬────────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  5. web.py + plantillas/                                │
  │     Enseña el resultado en el navegador.                │
  └─────────────────────────────────────────────────────────┘
```

Y aparte, los **datos** que alimentan la máquina y que puedes editar tú a mano:

- `app/datos/ingredientes.json` — la tabla nutricional.
- `app/datos/recetas.json` — el recetario.
- `app/datos/emparejamientos.json` — qué producto se compra para cada ingrediente.

---

## 5. ¿Por qué está partido en tantos archivos?

Porque cada archivo tiene **un solo trabajo**. Esto se llama *separación de responsabilidades* y es la costumbre más útil que puedes coger:

- Si Mercadona cambia su API, **solo** se toca `cliente.py`.
- Si quieres cambiar cómo se eligen las recetas, **solo** se toca `planificador.py`.
- Si quieres que la web se vea distinta, **solo** se toca el CSS.

Cuando todo está en un único archivo gigante, cualquier cambio da miedo porque no sabes qué más vas a romper.

---

## 6. Las decisiones técnicas, en corto

| Decisión | Por qué |
|---|---|
| **Python** | Ya lo tenías instalado y es el lenguaje más legible para empezar |
| **Flask** | El servidor web más sencillo de Python. Otras opciones (FastAPI) son más potentes pero traen conceptos que ahora solo estorban |
| **HTML y CSS a mano, sin React** | React necesitaría instalar Node.js y un proceso de compilación. Para lo que hace esta app, es complicarse a cambio de nada |
| **SQLite** | Una base de datos que es *un solo archivo*. No hay que instalar ni arrancar nada |
| **JSON para recetas e ingredientes** | Es texto plano: lo puedes abrir con el Bloc de notas y editarlo tú sin saber programar |

---

## 7. Por dónde seguir

1. [`01-git-y-github.md`](01-git-y-github.md) — cómo guardar el proyecto y trabajar desde varios ordenadores.
2. [`02-python-entorno-virtual.md`](02-python-entorno-virtual.md) — preparar Python.
3. [`03-la-api-de-mercadona.md`](03-la-api-de-mercadona.md) — de dónde salen los precios.
4. [`04-nutricion-y-recetas.md`](04-nutricion-y-recetas.md) — los datos que puedes editar tú.
5. [`05-emparejar-ingredientes-productos.md`](05-emparejar-ingredientes-productos.md) — el puente entre recetas y súper.
6. [`06-el-algoritmo-del-menu.md`](06-el-algoritmo-del-menu.md) — **el más interesante**: cómo se decide el menú.
7. [`07-la-interfaz-web.md`](07-la-interfaz-web.md) — cómo se pinta todo en el navegador.
