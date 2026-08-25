# 09 · Las fotos de los platos

Archivos que explica este documento:
[`app/imagenes/buscador.py`](../app/imagenes/buscador.py) ·
[`app/imagenes/fotos.py`](../app/imagenes/fotos.py) ·
[`scripts/buscar_fotos.py`](../scripts/buscar_fotos.py)

Este documento cuenta **tres intentos fallidos seguidos** antes de dar con algo que funcionara. Es probablemente el mejor ejemplo del proyecto de cómo se ajusta algo que depende de datos que no controlas.

---

## 1. El problema

El recetario es nuestro, así que no tenemos fotos de los platos. Al principio se resolvió con un **collage de las fotos de los productos** de Mercadona (documento [07](07-la-interfaz-web.md)). Funciona, nunca se rompe... y no da nada de hambre.

Lo que queremos son fotos de platos de verdad. Y tienen que ser **gratis y con licencia que permita usarlas**.

---

## 2. De dónde salen

Probé dos fuentes:

| | Cobertura de cocina española | Licencias |
|---|---|---|
| **Wikimedia Commons** | Floja. "Lentejas guisadas" devolvió un libro de fábulas de Esopo de 1500 y pico | Muy libres |
| **Openverse** | **Buena.** Agrega Flickr y otros. "merluza al horno" devuelve merluza al horno | Variadas, incluidas NC y ND |

Ninguna necesita clave ni registro. Se usa **Openverse como principal y Commons de refuerzo**.

### Las licencias, y qué obligan

Muchas fotos son `CC BY-NC` (no comercial) o `CC BY-ND` (sin obras derivadas). Este proyecto es personal y no se distribuye, así que ambas valen. Pero hay que cumplir dos cosas, y las dos están en el código:

- **Atribuir**: se guarda autor, licencia y enlace al original, y se enseñan debajo de la foto en la ficha de la receta. Openverse ya da el texto montado.
- **No modificar la foto**: nada de recortarla ni de escribirle el nombre encima como hace el collage. `ND` no lo permite. Se guarda tal cual y el tamaño lo pone el CSS.

---

## 3. Dónde vive cada cosa

| Qué | Archivo | ¿A GitHub? |
|---|---|---|
| Qué foto elegiste (url, autor, licencia) | `app/datos/imagenes_recetas.json` | **Sí** |
| Las candidatas que devolvieron los buscadores | `datos/candidatas_fotos.json` | No |
| El .jpg descargado | `datos/imagenes/plato_<receta>.jpg` | No |

Es el mismo criterio de siempre: **lo que decides tú se guarda; lo que se puede volver a bajar con un comando, no**. Así tus elecciones te siguen al otro ordenador y las fotos se descargan solas allí la primera vez. Son unos 10 MB.

---

## 4. Los tres intentos

Aquí está lo interesante.

### Intento 1: buscar el nombre de la receta. Desastre

La primera versión buscaba el nombre completo y, si no encontraba, iba acortando hasta quedarse con las dos primeras palabras.

Resultado con 130 recetas: 119 con foto. Parecía un éxito hasta que las miré todas juntas en una hoja de contacto:

| Receta | Foto que eligió |
|---|---|
| Arroz tres delicias | un **arrozal** |
| Arroz de verduras al horno | un **caballo** |
| Bolañesa de soja | un **icono de altavoz** |
| Pavo con cuscús | un **pavo real** |
| Cocido de garbanzos | un **escenario de teatro** |
| Ensalada de pollo y aguacate | una **señora sentada a la mesa** |

Y lo peor, que solo se ve mirándolas juntas: **26 recetas compartían foto con otra**. La misma foto de un bizcocho de chocolate estaba puesta en **cuatro** recetas de crema. Una ensalada de nopal, en **cinco** ensaladas.

**La causa**: acortar a dos palabras produce, en español, consultas como `"crema de"` o `"ensalada de"`. Y a esas consultas el buscador devuelve lo primero que las contenga.

### Intento 2: filtrar por relevancia. Pasarse de frenada

Tres cambios:

1. **Nunca generar una consulta que sea solo palabras genéricas** (una lista con "crema", "ensalada", "sopa"...).
2. **Puntuar las candidatas** comparando el título de la foto con el nombre de la receta, y **descartar** las que no coincidieran en ninguna palabra concreta.
3. **No repetir foto** entre recetas.

Resultado: de 130 recetas, **48 con foto y 82 sin ninguna**. Inservible.

**Dos errores a la vez**, y merece la pena separarlos:

- **Metí nombres de plato en la lista de genéricas**: "lasaña", "paella", "tortilla", "curry". Pero una foto de una lasaña *sí* vale para una receta de lasaña. Exigir que además mencionara la carne dejaba fuera todas las buenas.
- **Descartaba en vez de ordenar.** Descartar es una decisión irreversible, y aquí no hacía ninguna falta tomarla en ese punto.

### Intento 3: ordenar, no descartar

- La lista de genéricas se quedó **solo con las palabras que no identifican el plato**: "crema", "ensalada", "sopa", "guiso", "casera", "verduras", "horno"...
- Las candidatas se **ordenan** por relevancia y **no se descarta ninguna**. Quien exige relevancia mayor que cero es la **preselección**, no la búsqueda. Así, si la automática falla, en la pantalla de revisión sigues teniendo seis fotos entre las que elegir.
- Y se añadió un último recurso que faltaba: si con dos palabras no sale nada, **probar cada palabra concreta sola**. "Berenjenas gratinadas" generaba una única consulta útil; si esa fallaba, nos quedábamos sin foto pudiendo buscar simplemente "berenjenas".

---

## 5. Las dos reglas que quedaron

### Nunca una consulta formada solo por palabras genéricas

```
"Crema de calabacin y queso"  ->  crema de calabacin y queso
                                  crema de calabacin
                                  crema calabacin queso
                                  crema calabacin
                                  calabacin
                                  queso
```

Fíjate en lo que **no** está: `"crema"`. Ni `"crema de"`.

### La relevancia exige coincidir en algo concreto

```python
if concretas == 0:
    return 0
return concretas * 2 + genericas
```

Las palabras concretas valen el doble que las genéricas, y **si no coincide ninguna concreta, la puntuación es cero**.

Esa es la regla que mata al bizcocho: se titulaba "Coc de crema de xocolata", comparte "crema" con "Crema de calabacín y queso", pero no comparte ni "calabacín" ni "queso". Cero.

---

## 6. El truco para revisar 130 fotos

Este merece un apartado propio porque es aplicable a muchas cosas.

Revisar 130 fotos abriéndolas una a una es inviable. La solución fue montar **hojas de contacto**: una sola imagen con 20 fotos en rejilla, cada una con su número y el nombre de su receta debajo.

Con eso, revisar las 130 son **siete imágenes**, no 130. Y aparecen cosas que de una en una no se ven: fue mirando una hoja completa como salió que cinco ensaladas distintas compartían la misma foto. Ese fallo era invisible receta a receta.

> La idea general: cuando tengas que juzgar muchos datos parecidos, **júntalos en una sola vista**. Los patrones y las repeticiones saltan solos, y los que no saltan es que no importan.

---

## 7. Cómo se usa

```powershell
python scripts/buscar_fotos.py --preseleccionar   # buscar y elegir la mejor
python scripts/buscar_fotos.py --solo-nuevas      # solo las recetas nuevas
```

Y para revisar y cambiar lo que no te guste: **`http://localhost:8000/fotos`**.

Cada receta con sus seis candidatas; pulsas la buena y se guarda al momento. Hay un filtro de "solo las que no he revisado" para poder ir tachando pendientes, y una opción de **"ninguna me convence"** que vuelve a poner el collage de productos.

Dos detalles del código que evitan errores desconcertantes:

- Al cambiar de foto se **borra la copia descargada** de la anterior. Sin eso seguirías viendo la vieja para siempre, y "he cambiado la foto y no cambia nada" es de los fallos que más desesperan.
- El campo `revisada: true` marca las que has elegido tú. Volver a ejecutar el preseleccionador **no las toca**. Es la misma idea que el `"fijado": true` de los emparejamientos (documento [05](05-emparejar-ingredientes-productos.md)): una herramienta que te borra el trabajo deja de usarse.

---

## 8. Si una receta se queda sin foto

No pasa nada: se usa el collage de productos de siempre. Nunca hay un hueco roto, y esa es la parte importante del diseño.

Si quieres arreglarlo, tienes dos vías:

- Cambiar el **nombre de la receta** en `recetas.json` por uno más común. "Crema de calabacín y queso" encuentra menos que "Crema de calabacín".
- Elegir a mano en `/fotos` entre las candidatas, aunque su título no coincidiera.
