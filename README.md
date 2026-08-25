# Menús y lista de la compra de Mercadona

Aplicación web de uso personal. Le dices **cuánto quieres gastar**, **para cuántas semanas**, **qué dieta** y **para cuánta gente**, y te devuelve:

- Un **menú** de comidas y cenas con recetas concretas.
- La **lista de la compra de Mercadona**, con productos y precios reales, agrupada por sección del supermercado.
- Un **informe nutricional** del plan.

Los precios se descargan de la API pública de `tienda.mercadona.es`, así que se mantienen al día ejecutando un solo comando.

```
   80 €  ·  2 semanas  ·  1 persona  ·  equilibrada
                        ↓
   7 recetas · 28 comidas · 36 productos · 79,22 €
```

---

## Empezar en un ordenador nuevo

Los cinco comandos, en orden. Explicación detallada en [`docs/02-python-entorno-virtual.md`](docs/02-python-entorno-virtual.md).

```powershell
# 1. Descargar el proyecto
git clone https://github.com/TU-USUARIO/mercadona-dieta-app.git
cd mercadona-dieta-app

# 2. Crear el entorno de Python (una vez por ordenador)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar las librerías
pip install -r requirements.txt

# 4. Descargar el catálogo de Mercadona (~3 minutos)
python scripts/actualizar_catalogo.py

# 5. Arrancar
python -m app.web
```

Y se abre solo `http://localhost:8000`.

Los pasos 1-4 son solo la primera vez. Después, **doble clic en `arrancar.bat`**.

> Si el paso 2 da un error rojo de "ejecución de scripts está deshabilitada", ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

## El día a día

| Quiero... | Comando |
|---|---|
| Abrir la app | Doble clic en `arrancar.bat` |
| Actualizar los precios | `python scripts/actualizar_catalogo.py` |
| Comprobar que los datos están bien | `python scripts/comprobar_datos.py` |
| Ver con qué producto se empareja cada ingrediente | `python scripts/revisar_emparejamientos.py` |
| Rehacer los emparejamientos | `python scripts/revisar_emparejamientos.py --regenerar` |
| Buscar emparejamientos sospechosos | `python scripts/comprobar_precios.py` |
| Probar el algoritmo sin la web | `python scripts/probar_plan.py` |

**Trabajando desde dos ordenadores:** `git pull` al empezar, `git push` al terminar. La guía completa está en [`docs/01-git-y-github.md`](docs/01-git-y-github.md).

---

## Cambiar cosas sin tocar código

Tres archivos de texto que puedes editar con el Bloc de notas:

| Archivo | Qué contiene |
|---|---|
| [`app/datos/recetas.json`](app/datos/recetas.json) | Las 60 recetas |
| [`app/datos/ingredientes.json`](app/datos/ingredientes.json) | Los 105 ingredientes y sus datos nutricionales |
| [`app/datos/basicos_desayuno.json`](app/datos/basicos_desayuno.json) | Lo que se consume de desayuno |

Después de editar cualquiera de ellos:

```powershell
python scripts/comprobar_datos.py
```

Te avisa si te has dejado una coma, si has escrito mal el id de un ingrediente, o si has marcado como vegana una receta que lleva queso.

Los ajustes del algoritmo (calorías objetivo, cuánto penalizar la repetición, tu almacén de Mercadona) están todos en [`app/config.py`](app/config.py), comentados uno a uno.

---

## Documentación

Está pensada para leerse en orden, y explica **por qué** se ha hecho cada cosa, no solo qué hace.

| # | Documento | De qué va |
|---|---|---|
| 00 | [Visión general](docs/00-vision-general.md) | Qué construimos y cómo encajan las piezas |
| 01 | [Git y GitHub](docs/01-git-y-github.md) | Desde cero, y cómo trabajar desde varios ordenadores |
| 02 | [Python y el entorno virtual](docs/02-python-entorno-virtual.md) | Preparar el ordenador |
| 03 | [La API de Mercadona](docs/03-la-api-de-mercadona.md) | De dónde salen los precios |
| 04 | [Nutrición y recetas](docs/04-nutricion-y-recetas.md) | Los datos que puedes editar tú |
| 05 | [Emparejar ingredientes y productos](docs/05-emparejar-ingredientes-productos.md) | El puente entre receta y supermercado |
| 06 | [**El algoritmo del menú**](docs/06-el-algoritmo-del-menu.md) | **El más interesante**, con ejemplo numérico |
| 07 | [La interfaz web](docs/07-la-interfaz-web.md) | Flask, plantillas y CSS |

---

## Cómo está organizado

```
mercadona-dieta-app/
├── arrancar.bat                 doble clic para abrir la app
├── app/
│   ├── config.py                todos los ajustes, en un sitio
│   ├── web.py                   el servidor y las páginas
│   ├── recetario.py             carga y valida recetas e ingredientes
│   ├── datos_app.py             carga todo de una vez
│   ├── utiles.py                funciones pequeñas compartidas
│   ├── mercadona/
│   │   ├── cliente.py           ← ÚNICO sitio que habla con Mercadona
│   │   └── catalogo.py          guarda el catálogo en SQLite
│   ├── planificador/
│   │   ├── emparejador.py       ingrediente → producto real
│   │   ├── cesta.py             cuántos envases y cuánto cuestan
│   │   └── planificador.py      ← EL ALGORITMO
│   ├── imagenes/collage.py      la foto de cada receta
│   ├── datos/                   los JSON que puedes editar
│   ├── plantillas/              el HTML
│   └── estaticos/               el CSS
├── scripts/                     herramientas de línea de comandos
├── docs/                        la documentación
└── datos/                       generado, no se sube a GitHub
```

Cada archivo tiene **un solo trabajo**. Si Mercadona cambia su API, solo se toca `cliente.py`. Si quieres cambiar cómo se eligen las recetas, solo `planificador.py`.

---

## Cómo funciona, en tres ideas

**1. Precios reales, no scraping.** Mercadona tiene una API pública no oficial que devuelve los datos ya limpios. 4.304 productos con precio, envase y foto. No hay que rebuscar entre etiquetas HTML.

**2. Se compran envases, no gramos.** Si una receta lleva 50 g de aceite, pagas la botella entera. Y esa botella vale para las demás recetas. Todo el cálculo se basa en eso, y es lo que hace que el algoritmo junte recetas que comparten ingredientes: salen más baratas.

**3. La nutrición la ponemos nosotros.** La API de Mercadona no da ni una caloría (comprobado). Así que hay una tabla propia de 105 ingredientes con sus valores por 100 g, y las recetas se definen en términos de esos ingredientes.

---

## Límites, dichos claramente

- **La API de Mercadona no es oficial.** Puede cambiar sin avisar. Todo el acceso está aislado en `app/mercadona/cliente.py`, así que si cambia solo hay que tocar ese archivo. Las peticiones van espaciadas 0,4 s y con un `User-Agent` que se identifica honestamente.
- **Los valores nutricionales son orientativos.** Salen de tablas de composición de alimentos por ingrediente, no del producto concreto. Sirven para hacerse una idea; no es una herramienta médica.
- **Los precios son los del día en que descargaste el catálogo.** La app siempre enseña esa fecha.
- **El plan asume que compras todo de cero**, salvo que marques la casilla de "ya tengo la despensa en casa".
- **Proyecto personal.** No está pensado para distribuirse ni para publicarse en internet.
