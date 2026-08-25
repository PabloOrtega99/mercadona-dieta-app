# 01 · Git y GitHub desde cero

Tu objetivo: **poder trabajar en este proyecto desde cualquier ordenador**. Empiezas algo en el portátil, lo continúas en el sobremesa, y nunca pierdes nada.

Eso lo resuelven dos cosas distintas que la gente suele confundir:

- **Git** es un programa que se instala en tu ordenador. Lleva el **historial** de tu proyecto: guarda fotos de cómo estaba tu carpeta en cada momento.
- **GitHub** es una página web donde subes ese historial para tenerlo en internet. Es "la nube" de Git.

> Analogía: **Git** es la máquina de fotos. **GitHub** es el álbum compartido en internet donde subes las fotos para verlas desde otro sitio.

---

## 1. El vocabulario mínimo

Solo necesitas estas seis palabras. En serio, con estas seis se hace el 95 % del trabajo.

| Palabra | Qué es | Con la analogía |
|---|---|---|
| **Repositorio** (*repo*) | Tu carpeta del proyecto, con su historial | El álbum entero |
| **Commit** | Una foto guardada del estado del proyecto, con un mensaje que dice qué cambiaste | Una foto con su pie de foto |
| **`add`** | Marcar qué archivos entran en la próxima foto | Elegir a quién enfocas |
| **`push`** | Subir tus commits a GitHub | Subir las fotos al álbum de internet |
| **`pull`** | Bajarte de GitHub lo que hiciste desde otro ordenador | Descargarte las fotos que subiste desde el otro móvil |
| **`origin`** | El apodo de "mi repositorio en GitHub" | La dirección del álbum |

Hay una séptima, **rama** (*branch*), que sirve para trabajar en varias versiones a la vez. Como aquí trabajas tú solo, **usaremos una sola rama**, que se llama `main`. Puedes olvidarte de ese concepto por ahora.

---

## 2. Instalación y configuración (solo la primera vez en cada ordenador)

Git ya está instalado en este ordenador. Se hizo con:

```powershell
winget install --id Git.Git -e
```

Después hay que decirle **quién eres**. Git firma cada commit con un nombre y un correo, para que en el historial se vea quién hizo cada cambio:

```powershell
git config --global user.name "Pablo"
git config --global user.email "pabloortegax9@gmail.com"
```

`--global` significa "para todos mis proyectos de este ordenador", no solo para este.

> **Importante:** después de instalar Git tienes que **cerrar y abrir la terminal**. Windows solo se entera de que hay un programa nuevo cuando abres una ventana nueva. Si escribes `git --version` y te dice que no reconoce el comando, es casi siempre esto.

---

## 3. Crear el repositorio en GitHub

Esta parte se hace en el navegador, y **la haces tú**:

1. Entra en [github.com](https://github.com) y crea una cuenta si no la tienes (usa `pabloortegax9@gmail.com`).
2. Arriba a la derecha, botón **`+`** → **New repository**.
3. Rellena:
   - **Repository name**: `mercadona-dieta-app`
   - **Description**: `App para generar menús y lista de la compra de Mercadona según presupuesto y dieta`
   - **Private** ✅ ← **importante**. Es un proyecto personal; que no lo vea todo internet.
   - **NO marques** "Add a README file", ni `.gitignore`, ni licencia. Deja las tres casillas vacías.
4. Botón **Create repository**.

> **¿Por qué no marcar el README?** Porque si GitHub crea archivos por su cuenta, el repositorio de internet y el de tu ordenador arrancan con historiales distintos y al intentar subir da un error feo (`unrelated histories`). Creándolo vacío, los dos parten del mismo sitio.

En la página que te sale después verás una dirección tipo:

```
https://github.com/TU-USUARIO/mercadona-dieta-app.git
```

Guárdala, hace falta en el paso siguiente.

---

## 4. Conectar tu carpeta con GitHub (solo la primera vez)

Desde la carpeta del proyecto:

```powershell
# 1. Convierte esta carpeta en un repositorio de Git.
#    Crea una subcarpeta oculta ".git" con todo el historial.
git init

# 2. La rama principal se llamará "main" (es el nombre estándar hoy).
git branch -M main

# 3. Mete TODOS los archivos en la próxima foto.
#    El punto significa "todo lo de esta carpeta".
#    Los archivos listados en .gitignore se quedan fuera automáticamente.
git add .

# 4. Haz la foto, con su mensaje.
git commit -m "Primer commit: estructura del proyecto y documentacion inicial"

# 5. Apunta a tu repositorio de GitHub y ponle el apodo "origin".
git remote add origin https://github.com/TU-USUARIO/mercadona-dieta-app.git

# 6. Sube todo. El "-u" enlaza tu rama local con la de GitHub,
#    para que a partir de ahora baste con escribir "git push" a secas.
git push -u origin main
```

En el paso 6 se abrirá una **ventana del navegador pidiéndote iniciar sesión en GitHub**. Es normal: lo hace el *Git Credential Manager*, que viene incluido con Git. Inicias sesión una vez y tu ordenador ya no te lo vuelve a preguntar. Nada de contraseñas escritas en la terminal ni de crear *tokens* a mano.

Recarga la página de GitHub: tus archivos ya están ahí.

---

## 5. El ciclo del día a día

Esto es lo que harás continuamente. Son tres comandos y siempre los mismos.

```powershell
# Ver en qué estado estás: qué has cambiado, qué falta por guardar.
# Úsalo sin miedo, no modifica nada. Es el comando que más vas a usar.
git status

# Guardar los cambios en una foto.
git add .
git commit -m "Añadidas 10 recetas veganas"

# Subirla a GitHub.
git push
```

**Sobre los mensajes de commit:** escribe qué has hecho, no qué archivos tocaste. `"Arreglado el calculo de envases cuando el ingrediente es a granel"` es útil dentro de seis meses. `"cambios"` no te dice nada.

**¿Cada cuánto hacer commit?** Cada vez que termines algo que funcione, aunque sea pequeño. Es mejor cinco commits pequeños que uno enorme al final del día: si algo se rompe, puedes volver atrás con precisión.

---

## 6. Trabajar desde dos ordenadores — tu caso real

Esta es la parte que te interesa. Hay una regla que resume todo:

> ### 🔑 `git pull` al empezar. `git push` al terminar.
> Siempre. Sin excepciones. Es un hábito, no una decisión que tomes cada vez.

### Ordenador nuevo, la primera vez

```powershell
# Colócate donde quieras tener el proyecto.
cd "D:\Proyectos"

# Descarga el proyecto entero desde GitHub.
# Esto crea la carpeta "mercadona-dieta-app" con todo dentro.
git clone https://github.com/TU-USUARIO/mercadona-dieta-app.git
cd mercadona-dieta-app

# Prepara Python (esto NO viene de GitHub, hay que hacerlo en cada ordenador,
# porque el entorno virtual está en .gitignore. El porqué, en el doc 02).
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Descarga el catálogo de Mercadona (tampoco viene de GitHub).
python scripts/actualizar_catalogo.py
```

Y ya lo tienes funcionando en el segundo ordenador.

### Cada día, en cualquiera de los dos

```powershell
# AL SENTARTE:
git pull        # trae lo que hiciste en el otro ordenador

#   ... trabajas ...

# AL LEVANTARTE:
git add .
git commit -m "Lo que sea que hayas hecho"
git push        # lo deja disponible para el otro ordenador
```

---

## 7. Cuando algo sale mal

### "Se me olvidó hacer `pull` y ahora `push` da error"

El mensaje será algo así:

```
! [rejected] main -> main (fetch first)
```

Significa: *"en GitHub hay cambios que tú no tienes; no te dejo pisarlos"*. Git te está protegiendo. La solución:

```powershell
git pull
```

Y pasa una de dos cosas:

- **Tocaste archivos distintos en cada ordenador** → Git los junta solo. Ya está, haz `git push`.
- **Tocaste el mismo archivo en los dos** → hay un **conflicto**. Sigue leyendo.

### Resolver un conflicto

Git te avisa de qué archivo tiene el problema y dentro del archivo te deja unas marcas así:

```
<<<<<<< HEAD
precio_maximo = 50      ← lo que tienes en ESTE ordenador
=======
precio_maximo = 80      ← lo que venía de GitHub
>>>>>>> origin/main
```

Abres el archivo, **borras las tres líneas de marcas** (`<<<<<<<`, `=======`, `>>>>>>>`) y dejas escrito el texto que quieras que quede. Luego:

```powershell
git add .
git commit -m "Resuelto conflicto"
git push
```

No es peligroso ni difícil, solo es incómodo. Y con el hábito del `pull` al empezar, casi nunca pasa.

### "He roto algo y quiero volver a como estaba"

```powershell
# Deshacer los cambios de UN archivo (no guardados aún).
# ⚠️ Esto borra tu trabajo en ese archivo, no se puede recuperar.
git restore app/web.py

# Ver el historial de fotos, una por línea.
git log --oneline
```

---

## 8. Qué NO se sube (y por qué)

El archivo [`.gitignore`](../.gitignore) es la lista de lo que Git ignora. Aquí dentro hay dos cosas:

| Carpeta | Por qué no se sube |
|---|---|
| `.venv/` | Son cientos de megas de librerías descargadas. Se recrean con `pip install -r requirements.txt` |
| `datos/` | El catálogo de Mercadona y las imágenes. Se regeneran con `python scripts/actualizar_catalogo.py`. Además **conviene** regenerarlo en cada ordenador, así los precios están frescos |

La regla general: **si puedo regenerarlo con un comando, no lo subo**. GitHub es para el *código y las decisiones*, no para los datos generados.

Fíjate en la excepción interesante: `app/datos/` (con las recetas, ingredientes y emparejamientos) **sí** se sube, porque eso lo escribes tú a mano y perderlo dolería. La carpeta `datos/` de la raíz, no.

---

## 9. Chuleta

```powershell
git status                    # ¿qué está pasando aquí?  ← el más útil
git add .                     # preparar todos los cambios
git commit -m "mensaje"       # guardar la foto
git push                      # subir a GitHub
git pull                      # bajar de GitHub
git log --oneline             # ver el historial
git clone <url>               # descargar el proyecto en un ordenador nuevo
```
