# 06 · El algoritmo: cómo se decide el menú

Archivos que explica este documento:
[`app/planificador/cesta.py`](../app/planificador/cesta.py) ·
[`app/planificador/planificador.py`](../app/planificador/planificador.py)

**Este es el documento importante.** Aquí está la idea que hace que el proyecto funcione, y está explicada con números reales del catálogo de Mercadona.

---

## 1. La idea que lo cambia todo

Ya la hemos mencionado, pero ahora toca verla con números:

> ### En el supermercado no compras gramos. Compras envases enteros.

Una receta lleva 50 g de aceite. Tú no pagas 50 g de aceite: pagas **una botella**. Y esa botella te sirve también para las otras cuatro recetas de la semana que llevan aceite, sin pagar nada más.

De ahí salen **dos números distintos**, y confundirlos rompe las cuentas por completo:

| | Qué es | Para qué sirve |
|---|---|---|
| **Coste prorrateado** | gramos × precio por gramo | Comparar recetas entre sí |
| **Coste real** | envases necesarios × precio del envase | **Lo que pagas** |

El coste real **solo tiene sentido calculado sobre el plan entero**, nunca receta a receta. Y de él sale el concepto que usa el algoritmo una y otra vez:

> ### Coste marginal = lo que SUBE la cesta al añadir una receta.

---

## 2. El coste marginal, con números reales

Vamos a montar una cesta desde cero. Precios reales del catálogo (los del día en que se descargó).

### Receta 1: Espaguetis con tomate y ajo

Cesta vacía. Hay que comprarlo todo:

| Ingrediente | Necesito | Envase | Precio | Envases | Coste |
|---|---|---|---|---|---|
| Spaghetti Hacendado | 350 g | 1.000 g | 1,15 € | ⌈350/1000⌉ = **1** | 1,15 € |
| Tomate triturado | 500 g | 800 g | 1,00 € | ⌈500/800⌉ = **1** | 1,00 € |
| Cebollas | 120 g | 2.000 g | 3,60 € | **1** | 3,60 € |
| Ajo troceado | 15 g | 150 g | 0,95 € | **1** | 0,95 € |
| Aceite de oliva | 30 g | (botella) | 2,60 € | **1** | 2,60 € |
| Orégano | 3 g | 25 g | 1,00 € | **1** | 1,00 € |
| Sal fina | 4 g | 1.000 g | 0,40 € | **1** | 0,40 € |
| | | | | **TOTAL** | **10,70 €** |

Da 4 raciones → **2,68 € por ración**.

Fíjate en lo absurdo que sería el coste prorrateado aquí: 4 g de sal valen 0,0016 €. Pero tú pagas el paquete de 0,40 €. La diferencia es de 250 veces.

Ese símbolo ⌈ ⌉ es el **redondeo hacia arriba**, y es literalmente lo que hace el supermercado: si necesitas 1.100 g de arroz y el paquete es de 1 kg, te llevas dos. No existe comprar 1,1 paquetes. En el código es `math.ceil()`.

### Receta 2: Macarrones con chorizo

Ahora viene lo bueno. **La cesta ya tiene cosas dentro.**

| Ingrediente | Necesito | Ya tenía | Total | Envases antes → después | Coste extra |
|---|---|---|---|---|---|
| Macarrón Hacendado | 350 g | 0 g | 350 g | 0 → 1 | **+1,15 €** |
| Chorizo oreado | 200 g | 0 g | 200 g | 0 → 1 (360 g) | **+2,48 €** |
| Tomate triturado | 400 g | 500 g | 900 g | 1 → 2 | **+1,00 €** |
| Queso rallado | 60 g | 0 g | 60 g | 0 → 1 (400 g) | **+1,90 €** |
| Cebollas | 120 g | 120 g | 240 g | 1 → 1 | **+0,00 €** ✓ |
| Ajo troceado | 10 g | 15 g | 25 g | 1 → 1 | **+0,00 €** ✓ |
| Aceite de oliva | 20 g | 30 g | 50 g | 1 → 1 | **+0,00 €** ✓ |
| Sal fina | 4 g | 4 g | 8 g | 1 → 1 | **+0,00 €** ✓ |
| | | | | **COSTE MARGINAL** | **6,53 €** |

Da 4 raciones → **1,63 € por ración**.

### Compara las dos cifras

```
   Receta 1 (cesta vacía)  ......  2,68 € / ración
   Receta 2 (cesta con cosas)  ..  1,63 € / ración   ← un 39 % más barata
```

**La segunda receta es más barata solo porque llega después.** La cebolla, el ajo, el aceite y la sal ya estaban comprados y le salen gratis.

Ahí está todo el proyecto. Un algoritmo que mira el coste marginal **junta recetas que comparten ingredientes de forma natural**, sin que nadie se lo haya programado explícitamente. Que es exactamente lo que hace cualquiera que cocine con cabeza: si compras un manojo de perejil, esa semana cocinas cosas con perejil.

Y el efecto contrario también importa: sin esta idea, el algoritmo produciría una lista con treinta productos a medio usar y una cuenta imposible.

---

## 3. El problema, y por qué no hay solución perfecta

Lo que tenemos entre manos es una variante del **problema de la mochila**: hay un límite (el dinero) y quieres meter dentro lo mejor posible (comidas variadas y suficientes).

Este tipo de problemas es **NP-difícil**, que en la práctica significa: no se conoce ninguna forma rápida de encontrar la mejor solución posible.

¿Cómo de malo es? Con 60 recetas y eligiendo 7, las combinaciones posibles son unos **386 millones**. Y eso es solo para una semana; con cuatro semanas y repeticiones permitidas, el número se dispara a cifras sin nombre. Probarlas todas está descartado.

Así que se usa un **algoritmo voraz** (*greedy*): en cada paso elige lo que mejor pinta **ahora mismo**, sin mirar más allá.

> Es como bajar una montaña con niebla: en cada paso vas hacia donde más baja el terreno. No te garantiza llegar al punto más bajo del valle, pero llegas abajo, y llegas rápido.

No da el óptimo. Da un resultado muy bueno, en centésimas de segundo, con un código que se puede leer y entender. Para elegir la cena, eso vale más que el óptimo matemático.

---

## 4. Los cinco pasos

```
  ┌─────────────────────────────────────────────────────────┐
  │ PASO 1  ¿Cuántas raciones hacen falta?                  │
  │         14 comidas/semana x semanas x personas          │
  └───────────────────────────┬─────────────────────────────┘
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ PASO 2  Filtrar recetas por dieta                       │
  │         + meter los desayunos (gasto fijo)              │
  └───────────────────────────┬─────────────────────────────┘
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ PASO 3  BUCLE VORAZ: coger la mejor receta, repetir     │
  │         hasta cubrir todas las raciones                 │
  └───────────────────────────┬─────────────────────────────┘
                              ▼
                     ¿cabe en el presupuesto?
                    ╱                        ╲
                  SÍ                          NO
                  ▼                            ▼
  ┌───────────────────────────┐  ┌──────────────────────────┐
  │ PASO 4a  Gastar lo que    │  │ PASO 4b  Apretar todo lo │
  │ sobra en comer mejor      │  │ que se pueda y avisar    │
  └───────────────┬───────────┘  └────────────┬─────────────┘
                  └──────────────┬────────────┘
                                 ▼
  ┌─────────────────────────────────────────────────────────┐
  │ PASO 5  Repartir las comidas por días                   │
  └─────────────────────────────────────────────────────────┘
```

---

## 5. Paso 3: el bucle voraz y su fórmula

En cada vuelta se puntúa cada receta candidata y se coge la mejor. **Menos puntuación es mejor**, porque en el fondo es un precio.

```
puntuación  =  coste marginal por ración
               ×  penalización por repetición
               ×  ajuste calórico
```

### Factor 1: coste marginal por ración

El núcleo. Lo que acabamos de ver.

### Factor 2: penalización por repetición

```python
penalizacion = (1 + 0.55) ** veces_ya_elegida
```

Cada vez que una receta ya está en el menú, su puntuación empeora. Y crece de forma **exponencial**: la segunda vez penaliza un 55 %, la tercera un 140 %, la cuarta un 272 %.

¿Por qué hace falta? Porque el algoritmo **solo entiende de dinero**. Sin este factor, encontraría que las lentejas son lo más barato y te pondría lentejas catorce veces. Sería una respuesta correcta a la pregunta que le hicimos, y una respuesta inútil.

Es el mando de la variedad, y está en [`config.py`](../app/config.py) por si quieres tocarlo: súbelo y comerás más variado y más caro; bájalo y al revés.

### Factor 3: ajuste calórico

Penaliza las recetas que se alejan de lo que debería ser una comida (unas 750 kcal; el resto del día lo cubre el desayuno).

Sin esto, el algoritmo llena el menú de ensaladas de 250 kcal porque salen baratísimas por ración. Cumpliría el presupuesto y te quedarías con hambre. **Una comida tiene que alimentar**: eso es parte de la definición del problema, aunque no lo hayas dicho.

### El modo ahorro

Si en algún momento ya nos hemos pasado del presupuesto, se apagan los factores 2 y 3 y solo queda el precio. Cuando no llega el dinero, lo único que importa es que haya comida en la mesa. Y el plan sale marcado como "presupuesto insuficiente".

### Se añaden recetas ENTERAS

Nunca media. Cocinas la cazuela entera: si sale para 4 raciones y solo necesitas 2, las otras 2 existen igualmente. Y las pagas igualmente.

---

## 6. Paso 4a: gastar bien el dinero que sobra

Aquí hay una historia que merece la pena contar, porque es un error de diseño de los que no dan ningún error.

**La primera versión** hacía el paso 3 y ya está. Resultado para 60 € y una semana:

```
   Espaguetis con tomate y ajo
   Macarrones con chorizo
   Pasta con champiñones a la crema
   Revuelto de champiñones
   ────────────────────────────────
   TOTAL: 27,43 €   de un presupuesto de 60 €
```

Técnicamente perfecto: cubría las 14 comidas y no se pasaba ni un céntimo. Y era un resultado **horrible**. Pasta tres veces, y la mitad del dinero sin usar.

El fallo era de planteamiento: el algoritmo estaba resolviendo *"el menú más barato"* cuando lo que le habíamos pedido era *"el mejor menú que quepa en 60 €"*. No son la misma pregunta.

### La solución: una medida de "bueno" separada del precio

Hay que poder decir que un menú es mejor que otro **sin hablar de dinero**. Eso es [`_calidad()`](../app/planificador/planificador.py):

```
calidad  =  recetas distintas          × 3
          + grupos de alimentos         × 2
          − repeticiones                × 1,5
          − distancia al objetivo kcal  × 15
```

Y luego una **escalada** (*hill climbing*): partiendo de la solución que ya funciona, se van probando cambios pequeños:

```
   quitar una cocinada de X  +  poner una cocinada de Y
   ¿mejora la calidad Y sigue cabiendo en el presupuesto?  →  aceptado
```

Se repite hasta que ningún cambio mejore.

**El resultado con el mismo presupuesto:**

```
   Lentejas estofadas con chorizo      (legumbre)
   Merluza rebozada con ensalada       (pescado)
   Pasta con champiñones a la crema    (cereal)
   Pollo en salsa de almendras         (carne)
   ────────────────────────────────────────────
   TOTAL: 55,88 €   de 60 €
   2.195 kcal/día · 128 g de proteína
```

De 27 € a 56 €, de pasta-pasta-pasta a legumbre-pescado-carne-cereal, y de 1.798 a 2.195 kcal. Mismo presupuesto, mismo recetario.

### El término de las calorías, que llegó después

El primer `_calidad()` solo contaba variedad. Y con la dieta vegana pasaba esto:

```
   7 recetas, todas distintas, 4 grupos de alimentos
   55 € de un presupuesto de 90 €
   1.473 kcal/día     ← poco
```

La calidad **ya no podía subir más**: todas las recetas eran distintas y no quedaban grupos de alimentos que añadir. El algoritmo se plantaba ahí, con 35 € sin gastar y tú con hambre.

Por eso se añadió el término de las calorías, con peso 15, el más alto de la fórmula. Ahora prefiere platos que alimenten mientras el presupuesto lo permita, y ese mismo caso sube a **1.630 kcal**.

### Dos trucos para que esto vaya rápido

La escalada prueba muchísimas combinaciones. Sin cuidado, la web tardaría medio minuto en responder.

1. **Primero lo barato de calcular.** La calidad es una cuenta trivial; el precio no. Así que solo se calcula el precio de los cambios que de verdad mejoran la calidad. La mayoría se descartan sin tocar un solo precio.

2. **No recalcular la cesta entera.** Para saber cuánto cambia el precio se usa `coste_marginal()` con gramos **negativos** para la receta que sale y positivos para la que entra. Solo se tocan los ingredientes afectados (unos 15), no los 50 de la cesta.

Resultado: **menos de 0,1 segundos** por plan.

---

## 7. Paso 4b: cuando el presupuesto no llega

Si el plan no cabe, la app **no falla y no miente**: te dice cuánto haría falta de verdad.

Para que esa cifra sea útil, antes se hace la escalada al revés (`_abaratar()`): probar cambios que **bajen** el precio, hasta entrar en presupuesto o hasta que no se pueda más.

Se nota. En una prueba de 200 € para 4 semanas y 2 personas con dieta alta en proteína:

```
   Tras el paso 3 .......  219,87 €   (no cabía)
   Tras _abaratar() .....  198,49 €   (cabe)
```

Sin ese paso, la app habría dicho "necesitas 220 €" cuando en realidad con 200 € se podía. Te habría hecho gastar 20 € de más por pereza del algoritmo.

Y cuando de verdad no llega, lo dice claro. Con 15 € para 4 semanas:

> **No cabe en el presupuesto.** Este es el plan más ajustado que he encontrado y cuesta **59,33 €**.

---

## 8. Paso 5: repartir por días

Una cocinada de 4 raciones da de comer a 2 personas dos veces, o a 4 personas una vez. De ahí sale cuántas **comidas** aporta cada cocinada.

El reparto se hace **a la ronda** (*round-robin*): en vez de poner las tres veces que sale el arroz seguidas, se van alternando las recetas. Así no comes lo mismo lunes, martes y miércoles.

---

## 9. La nutrición: informe, no restricción

El plan calcula kcal y macros y te los **enseña con un semáforo**. Lo que **no** hace es usarlos como límite obligatorio. Es una decisión deliberada:

Si exigiéramos a la vez *"máximo 60 €"* + *"exactamente 2.000 kcal/día"* + *"variedad"* + *"solo recetas veganas"*, muchas combinaciones **no tendrían solución**, y la app te devolvería un error en lugar de un menú.

> Es más útil un menú bueno con un informe honesto que un error perfectamente riguroso.

Por eso las calorías entran en la fórmula de calidad como una **preferencia fuerte** (peso 15) y no como una condición que haya que cumplir sí o sí.

---

## 10. Qué tocar si quieres cambiar el comportamiento

Todo en [`app/config.py`](../app/config.py) y en la parte de arriba de [`planificador.py`](../app/planificador/planificador.py):

| Ajuste | Qué hace |
|---|---|
| `PENALIZACION_REPETICION` | Súbelo: más variedad, más caro. Bájalo: al revés |
| `KCAL_OBJETIVO_DIA` | Tu objetivo calórico |
| `PESO_AJUSTE_CALORICO` | Cuánto importa el tamaño de las comidas frente al precio |
| `PESO_CALORIAS` | Lo mismo, pero en la fase de mejora |
| `PESO_RECETA_DISTINTA` | Cuánto vale que haya recetas distintas |
| `INTENTOS_DE_MEJORA` | Más intentos: mejores resultados, algo más lento |

Cámbialos y ejecuta `python scripts/probar_plan.py` para ver el efecto al momento. Es la forma más rápida de coger intuición sobre cómo se comporta un algoritmo: mover una perilla y mirar qué pasa.
