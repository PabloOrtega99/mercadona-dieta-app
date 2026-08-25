# 04 · Los datos que puedes editar tú: ingredientes y recetas

Archivos que explica este documento:
[`app/datos/ingredientes.json`](../app/datos/ingredientes.json) ·
[`app/datos/recetas.json`](../app/datos/recetas.json) ·
[`app/datos/basicos_desayuno.json`](../app/datos/basicos_desayuno.json) ·
[`app/recetario.py`](../app/recetario.py)

**Esta es la parte del proyecto que puedes cambiar sin saber programar.** Son archivos de texto: los abres, editas y guardas.

---

## 1. Por qué existe esta tabla nutricional

Ya lo vimos en el [documento 03](03-la-api-de-mercadona.md): **Mercadona no publica ni una caloría**. Lo comprobé producto a producto. Todo lo que da es alérgenos e ingredientes en texto libre.

También probé **Open Food Facts**, una base de datos libre de productos alimentarios, usando los códigos de barras (EAN) que sí devuelve la API de Mercadona. Resultado: 404, no los tiene. Mercadona usa códigos internos que no están registrados ahí.

Así que si queremos que "dieta alta en proteína" signifique algo, los datos los ponemos nosotros. Y aquí viene la decisión importante:

> **La tabla es de INGREDIENTES, no de productos.**

Es decir, guardamos "la pechuga de pollo tiene 31 g de proteína por 100 g", no "el paquete de filetes de pechuga Hacendado tiene...". ¿Por qué?

| Por ingrediente | Por producto |
|---|---|
| ~105 filas | ~4.000 filas |
| Los valores no cambian nunca | Habría que revisarlos en cada actualización |
| Si Mercadona descataloga un producto, da igual | Se queda un hueco |
| La pechuga de pollo es pechuga de pollo | Cada marca, un dato distinto |

Un ingrediente es un concepto estable. Un producto es una referencia de supermercado que puede desaparecer mañana.

---

## 2. Un ingrediente por dentro

```json
{
  "id": "pechuga_pollo",
  "nombre": "Pechuga de pollo",
  "kcal_100g": 165, "proteina_100g": 31.0,
  "hidratos_100g": 0.0, "grasa_100g": 3.6,
  "grupo": "carne",
  "vegetariano": false, "vegano": false,
  "busqueda": ["filete pechuga pollo", "pechuga pollo"],
  "excluir": ["caldo", "croqueta", "empanad", "nugget", "fiambre"],
  "despensa": false,
  "gramos_por_unidad": null
}
```

Los campos por bloques:

**Identidad.** `id` es el nombre corto que usan las recetas. **No lo cambies nunca** una vez creado: romperías todas las recetas que lo mencionan. Si te equivocaste al escribirlo, cambia el `nombre` (que es lo que se ve) y deja el `id` como está.

**Nutrición.** Valores por 100 g de producto **crudo**, salvo que el nombre diga lo contrario (`lentejas_cocidas` son cocidas). Salen de tablas de composición de alimentos, tipo BEDCA.

**Dieta.** `vegetariano` y `vegano` no solo describen: se usan para **comprobar** que las recetas están bien etiquetadas. Si marcas una receta como vegana y lleva un ingrediente con `"vegano": false`, el script de comprobación te avisa. Es una red de seguridad contra el peor error que puede cometer esta app.

**Búsqueda.** `busqueda` y `excluir` son cómo se encuentra el producto en Mercadona. Tienen su propio documento: [`05-emparejar-ingredientes-productos.md`](05-emparejar-ingredientes-productos.md).

**Los dos campos raros:**

- **`despensa`**. Marca el aceite, la sal, las especias, el vinagre. Cosas que compras una vez y te duran meses. En el formulario de la app hay una casilla para decir si ya las tienes en casa.

- **`gramos_por_unidad`**. Solo para lo que Mercadona vende **por piezas**: huevos, plátanos, manzanas. La API dice "12 unidades" pero no cuánto pesa cada una, así que ese dato lo ponemos aquí (un huevo, 60 g). Sin esto no podríamos calcular nada de una receta que lleva "2 huevos".

---

## 3. Una receta por dentro

```json
{
  "id": "lentejas_verduras",
  "nombre": "Lentejas con verduras",
  "dietas": ["equilibrada", "vegetariana", "vegana"],
  "raciones": 4,
  "minutos": 55,
  "ingredientes": [
    {"id": "lentejas", "gramos": 350},
    {"id": "zanahoria", "gramos": 200}
  ],
  "pasos": ["Sofríe cebolla, ajo, zanahoria...", "..."]
}
```

Tres cosas que conviene tener claras:

**Los gramos son del TOTAL de la receta, no de una ración.** 350 g de lentejas para las 4 raciones, no para cada una.

**`raciones` casi siempre es 4**, y eso no es casualidad. Cocinas la cazuela entera: no existe hacer "media receta de lentejas". El algoritmo lo respeta y siempre añade recetas completas.

**En `dietas` hay que poner `equilibrada` siempre.** La dieta equilibrada no restringe nada, así que toda receta vale para ella. Y toda receta vegana tiene que llevar también `vegetariana`, porque lo es. El script de comprobación te avisa si se te olvida cualquiera de las dos.

---

## 4. Los básicos del desayuno

La app planifica **comida y cena**: 14 comidas por semana. El desayuno no se planifica como receta porque en la práctica desayunas casi siempre lo mismo. Pero **sí cuesta dinero**, y si no lo contáramos el presupuesto no cuadraría con la realidad.

Por eso [`basicos_desayuno.json`](../app/datos/basicos_desayuno.json) tiene una lista fija con lo que consume una persona en una semana:

```json
{ "ingrediente": "leche", "gramos_persona_semana": 1750,
  "alternativas": { "vegana": "bebida_soja" }, "nota": "250 ml al dia" }
```

### El campo `alternativas` y por qué está ahí

Esto salió de un error de verdad. El primer plan vegano que generamos llevaba **leche entera y yogur** en la lista de la compra.

Las recetas estaban bien filtradas: el planificador solo cogía recetas veganas. Pero los desayunos se añadían aparte, a ciegas, sin mirar la dieta. Un fallo clásico: hay dos caminos por los que entra comida al plan, se protege uno y se olvida el otro.

El arreglo tiene **dos capas**, y las dos hacen falta:

1. **`alternativas`** dice con qué sustituir cada cosa en cada dieta. La leche pasa a bebida de soja; el yogur, con `null`, directamente se quita.
2. **Una comprobación final en el código** que descarta cualquier ingrediente que no cumpla la dieta, aunque el archivo de datos esté mal.

La segunda capa parece redundante y no lo es: la primera depende de que el JSON esté bien escrito, que es exactamente lo que no se puede dar por hecho. Cuando algo es importante de verdad, se comprueba dos veces por caminos distintos.

---

## 5. Añadir tus propias recetas

Este es el uso normal del proyecto. Cuatro pasos:

**1. Comprueba que tienes los ingredientes.** Abre `ingredientes.json` y busca los que necesitas. Si falta alguno, copia un bloque parecido y cámbialo:

```json
{ "id": "pimiento_amarillo", "nombre": "Pimiento amarillo",
  "kcal_100g": 27, "proteina_100g": 1.0, "hidratos_100g": 6.3, "grasa_100g": 0.2,
  "grupo": "verdura", "vegetariano": true, "vegano": true,
  "busqueda": ["pimiento amarillo"], "excluir": ["asado", "conserva"],
  "despensa": false, "gramos_por_unidad": null }
```

**2. Añade la receta** en `recetas.json`, copiando otra y cambiándola. Ojo con dos cosas: la coma entre bloques (todos llevan coma detrás **menos el último**) y las comillas.

**3. Comprueba que no has roto nada:**

```powershell
python scripts/comprobar_datos.py
```

Te dirá si te falta una coma, si escribiste mal el id de un ingrediente, o si marcaste como vegana una receta que lleva queso. **Ejecuta esto siempre después de editar.**

**4. Empareja el ingrediente nuevo con su producto:**

```powershell
python scripts/revisar_emparejamientos.py --regenerar
```

Y con la app abierta, pulsa **Recargar datos** en el pie de página: los cambios aparecen sin reiniciar nada.

---

## 6. Cómo se leen estos archivos desde el código

Todo pasa por [`app/recetario.py`](../app/recetario.py). Nadie más abre esos JSON. Dos ideas que merece la pena entender de ahí:

### Los `@dataclass`

En vez de manejar los datos como diccionarios sueltos, el código los convierte en objetos:

```python
@dataclass
class Ingrediente:
    id: str
    nombre: str
    kcal_100g: float
    ...
```

Así se escribe `ingrediente.kcal_100g` en lugar de `ingrediente["kcal_100g"]`. La ventaja no es que sea más bonito: es que **si te equivocas y escribes `ingrediente.kcal_1000g`, el error salta ahí mismo**. Con un diccionario obtendrías un fallo mucho más adelante, o peor, un `None` que se propaga en silencio y acaba dando un precio mal calculado sin que nadie se entere.

### Validar todo de golpe, no de uno en uno

La función `comprobar()` devuelve una **lista** de problemas en vez de fallar en el primero. Es a propósito: si te has equivocado en veinte sitios, quieres verlos todos y arreglarlos de una tacada, no ejecutar el script veinte veces.

Lo que comprueba:

1. Que los ingredientes de cada receta existan de verdad.
2. Que las etiquetas de dieta sean válidas y que esté `equilibrada`.
3. **Que ninguna receta vegana lleve nada de origen animal.**
4. Que toda receta vegana esté también marcada como vegetariana.
5. Que cada dieta tenga al menos 8 recetas (con menos, los menús salen repetitivos).

Estado actual: **105 ingredientes y 60 recetas** — 60 para equilibrada, 23 altas en proteína, 28 vegetarianas y 16 veganas.
