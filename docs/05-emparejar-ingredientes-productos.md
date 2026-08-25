# 05 · El puente: de "150 g de pollo" a un producto con precio

Archivos que explica este documento:
[`app/planificador/emparejador.py`](../app/planificador/emparejador.py) ·
[`scripts/revisar_emparejamientos.py`](../scripts/revisar_emparejamientos.py) ·
[`scripts/comprobar_precios.py`](../scripts/comprobar_precios.py)

Este documento cuenta también **los errores que fue cometiendo** el emparejador, porque cada uno enseña algo. Es probablemente el más útil del proyecto para entender cómo se depura algo de verdad.

---

## 1. El problema

Una receta dice "150 g de pechuga de pollo". El catálogo tiene 4.304 productos. ¿Cuál es?

Suena fácil: buscar "pollo". Vamos a ver por qué no lo es.

---

## 2. Intento 1: buscar el texto. Y el desastre

La primera versión hacía lo obvio: buscar en la base de datos los productos cuyo nombre contuviera las palabras buscadas, descartar los que llevaran alguna palabra prohibida, y quedarse con el más barato por kilo.

Estos son resultados **reales** de esa primera versión:

| Ingrediente | Producto que eligió | 😬 |
|---|---|---|
| Ajo | Caldo de pollo Hacendado **bajo** en sal | "ajo" está dentro de "bajo" |
| Pera | Huevos de gallinas cam**pera**s | "pera" está dentro de "camperas" |
| Miel | **Gel de baño** vainilla y miel Deliplus | no es comida |
| Limón | **Lejía** perfumada con detergente limón | no es comida |
| Bacon | **Rosca** de lomo, bacón y queso | no es bacon |
| Chorizo | **Tortilla de patata** con chorizo | no es chorizo |
| Mantequilla | **Palomitas** sabor mantequilla | no es mantequilla |
| Dorada | **Cerveza** El Águila dorada | no es pescado |
| Espaguetis | *(nada)* | Mercadona los llama "Spaghetti" |
| Cuscús | *(nada)* | Mercadona lo llama "Cous cous" |

Diez errores distintos, pero **solo tres causas de fondo**. Encontrar las causas en vez de parchear los síntomas uno a uno es la diferencia entre arreglar algo y estar tapando agujeros para siempre.

---

## 3. Las tres causas y sus arreglos

### Causa A: buscar trozos de palabra en vez de palabras

`ajo` estaba dentro de `bajo`, y `pera` dentro de `camperas`. El buscador miraba si las letras aparecían en algún sitio, sin importar dónde.

Pero tampoco vale exigir la palabra exacta, porque entonces `champinon` no encontraría "Champiñone**s** laminados" y los plurales nos dejarían sin la mitad del catálogo.

**El arreglo** ([`_palabra_encaja()`](../app/planificador/emparejador.py)) distingue por longitud:

```python
if len(palabra_buscada) <= 4:
    return palabra_producto == palabra_buscada      # exacta
return palabra_producto.startswith(palabra_buscada)  # empieza por
```

- `ajo` (3 letras) → tiene que ser la palabra "ajo" entera. `bajo` ya no cuela.
- `pera` (4 letras) → exacta. `camperas` ya no cuela.
- `champinon` (9 letras) → basta con que empiece igual. `champiñones` sí cuela.

Simple, y se lleva por delante dos errores de golpe.

### Causa B: la sección de droguería

`miel` → gel de baño. `limón` → lejía. La app estaba buscando comida en el pasillo de la limpieza.

Podríamos ir añadiendo palabras prohibidas ("gel", "lejía", "champú", "mascarilla"...), pero es una batalla perdida: no hay forma de anticipar todos los champús con nombre de fruta que existen.

**El arreglo** es no entrar en esos pasillos. La API nos dice la categoría de cada producto, así que basta con una lista de categorías que no son comida:

```python
CATEGORIAS_NO_ALIMENTARIAS = {
    "bebe", "cuidado del cabello", "cuidado facial y corporal",
    "fitoterapia y parafarmacia", "limpieza y hogar", "maquillaje", "mascotas",
}
```

Siete líneas que resuelven una familia entera de errores, presentes y futuros.

### Causa C: los platos preparados

`bacon` → rosca de lomo. `chorizo` → tortilla de patata. `mantequilla` → palomitas. Todos contienen la palabra, ninguno es el ingrediente.

**El arreglo** aprovecha algo que hace Mercadona sin saberlo: **nombra sus productos empezando por lo que son**.

- "**Bacón** Hacendado cintas" → empieza por bacón: es bacón.
- "**Rosca** de lomo, bacón y queso" → empieza por rosca: es una rosca.

Así que exigimos que **el nombre del producto empiece por la primera palabra buscada**. Una regla de una línea que se lleva por delante casi todos los platos preparados.

Pero es una regla estricta y a veces se pasa de frenada: "**Media** calabaza cacahuete" empieza por "media" y es calabaza perfectamente válida. Por eso hay **dos vueltas**:

1. **Estricta**: el nombre tiene que empezar por lo buscado.
2. **Relajada**: si la estricta no encuentra nada, basta con que las palabras aparezcan en algún sitio.

Lo mejor que se puede, y si no se puede, lo que haya.

### Y el que no era un fallo del código: Spaghetti

`espaguetis` no encontraba nada porque **Mercadona los llama "Spaghetti"**. Igual con el cuscús ("Cous cous") y la carne picada ("Preparado de carne picada vacuno").

Aquí no había nada que arreglar en el programa: el dato estaba mal. La lección es que **hay que escribir los términos de búsqueda mirando el catálogo real**, no como llamas tú a las cosas.

---

## 4. Cómo queda el proceso

```
   ingrediente "pechuga_pollo"
   busqueda: ["filete pechuga pollo", "pechuga pollo"]
            │
            ▼
   ┌────────────────────────────────────────────┐
   │ SQL: dame productos que contengan          │  ← criba rápida y ancha
   │ "filete" Y "pechuga" Y "pollo"             │
   └──────────────────┬─────────────────────────┘
                      ▼
   ┌────────────────────────────────────────────┐
   │ Fuera lo que no es comida (por categoría)  │
   │ Fuera lo que lleva palabra prohibida       │  ← reglas con matices
   │ Fuera lo que no encaja palabra a palabra   │
   │ Fuera lo que no sabemos cuánto trae        │
   └──────────────────┬─────────────────────────┘
                      ▼
   ┌────────────────────────────────────────────┐
   │ Ordenar por precio por gramo               │
   │ Guardar los 3 mejores + un formato pequeño │
   └────────────────────────────────────────────┘
```

Fíjate en el reparto del trabajo: **SQL hace la criba gruesa y Python aplica las reglas finas**. Es el patrón habitual, porque cada herramienta hace lo que se le da bien. SQL es rapidísimo descartando miles de filas; Python es mucho más cómodo para reglas con excepciones.

---

## 5. Por qué se guardan cuatro productos y no uno

Porque **el más barato por kilo no siempre es el más barato**.

| Producto | Precio | Por kilo |
|---|---|---|
| Saco de patatas 5 kg | 5,60 € | **1,12 €/kg** ← el más barato por kilo |
| Bolsa de patatas 1 kg | 2,55 € | 2,55 €/kg |

Si tu plan necesita 800 g, el saco te cuesta 5,60 € y tiras 4,2 kg. La bolsa te cuesta 2,55 €. **Gana la bolsa**, aunque sea más del doble de cara por kilo.

Pero si el plan es de 4 semanas para 2 personas y necesitas 6 kg, entonces sí gana el saco.

O sea: **la decisión no se puede tomar aquí**, porque aquí todavía no sabemos cuánta cantidad hará falta. Por eso el emparejador guarda **varias opciones** y quien elige es [`elegir_producto()`](../app/planificador/cesta.py), ya con la cantidad en la mano.

Y por eso se guardan los 3 más baratos **más el formato pequeño**: si guardáramos solo los baratos, serían los cuatro formatos gigantes y no habría nada que elegir.

---

## 6. El error que solo se vio en una foto

Añadir el "formato más pequeño" trajo un error nuevo, y es el más interesante de todos porque **ningún filtro de texto podía detectarlo**.

Al mirar el collage de la receta de albóndigas, donde tenía que haber cebollas había esto:

> 🫙 **Cebolla** — bote de cebolla molida, sección de especias

El nombre encajaba perfectamente ("Cebolla"), no era droguería, no era plato preparado, empezaba por la palabra buscada. Todos los filtros lo daban por bueno. Y como el bote es el envase más pequeño, para los 120 g que pedía la receta salía más barato que una bolsa de 2 kg.

**La señal que sí lo delata es el precio por kilo:**

| | Precio por kilo |
|---|---|
| Cebollas frescas | 1,80 €/kg |
| Cebolla molida (especia) | ~25 €/kg |

Un formato pequeño legítimo (la botella de aceite de 1 L frente a la garrafa de 5 L) cuesta algo más por kilo, pero no mucho más. Un producto que en realidad **es otra cosa** cuesta un disparate por kilo.

**El arreglo** ([`_elegir_variados()`](../app/planificador/emparejador.py)): el formato pequeño solo se guarda si no cuesta más de **3 veces** lo que el más barato.

Y de paso salió una herramienta nueva, porque descubrir esto mirando una foto es pura suerte:

```powershell
python scripts/comprobar_precios.py
```

Compara cada ingrediente con la **mediana** de su grupo de alimento (la carne con la carne, la verdura con la verdura) y saca los que se salen. Con 105 ingredientes no puedes revisarlos todos a mano cada semana, pero sí puedes revisar los 3 que se salen.

> Detalle: usa la **mediana** y no la media. La media se deja arrastrar por un solo valor disparatado, que es justo lo que estamos buscando. Si el error contaminase la referencia, se escondería a sí mismo.

Ahora mismo marca 3 casos, y los 3 son correctos: soja texturizada, café molido y placas de lasaña son caros de verdad.

---

## 7. Revisar y corregir a mano

```powershell
python scripts/revisar_emparejamientos.py              # solo mirar
python scripts/revisar_emparejamientos.py --regenerar  # recalcular y guardar
python scripts/comprobar_precios.py                    # buscar rarezas
```

La tabla sale agrupada por tipo de alimento y con el precio por kilo:

```
  -- VERDURA --
  Cebolla         Cebollas                       2000 g   3,60 €   1.80 €
  Tomate          Tomate pera                     140 g   0,25 €   1.79 €
  Zanahoria       Zanahorias                     1000 g   1,20 €   1.20 €
```

Si algo está mal, hay dos formas de arreglarlo:

**a) Afinar el ingrediente** (mejor). En `ingredientes.json`, añade palabras a `excluir` o afina `busqueda`. Arregla el problema de raíz y sigue funcionando cuando cambie el catálogo.

**b) Fijarlo a mano** (para casos concretos). En `emparejamientos.json`, pon el id del producto que quieras y marca `"fijado": true`:

```json
"pechuga_pollo": {
  "fijado": true,
  "productos": ["12345"],
  "_nombres": ["El que yo quiero"]
}
```

El `"fijado": true` es importante: sin él, la próxima regeneración te pisaría la corrección. Y si eso pasara cada semana, acabarías no corrigiendo nada. Las herramientas que borran tu trabajo dejan de usarse.

> **Nota**: `emparejamientos.json` guarda solo **ids de producto**, nunca precios. Los precios se consultan en el momento en la base de datos, así que siempre están al día. El campo `_nombres` es solo para que puedas leer el archivo; el programa lo ignora.

---

## 8. Estado actual

**Los 105 ingredientes tienen producto asignado.** Ninguno se queda sin emparejar.
