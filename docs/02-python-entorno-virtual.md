# 02 · Python y el entorno virtual

Documento corto. Explica dos cosas: **qué es un entorno virtual** y **cómo arrancar el proyecto**.

---

## 1. El problema que resuelve el entorno virtual

Cuando instalas una librería con `pip install flask`, por defecto se instala **en tu Python de Windows, para todo el ordenador**. Eso trae dos problemas:

1. **Los proyectos se pisan.** Este proyecto usa Flask 3.1. Si dentro de un año haces otro proyecto que necesita Flask 2.0, al instalarlo rompes este. No puedes tener las dos versiones a la vez.
2. **No sabes qué necesita tu proyecto.** Con 40 librerías instaladas por todos lados, ¿cuáles hacen falta para *esta* app? Sin saberlo, no puedes montarla en otro ordenador.

Un **entorno virtual** es una carpeta (`.venv`) que contiene **una copia de Python solo para este proyecto**, con sus propias librerías, aislada del resto.

> Analogía: es un cajón cerrado con las herramientas de este proyecto. Lo que metes en él no anda suelto por la casa, y lo que hay en otros cajones no te estorba.

---

## 2. Crear y usar el entorno

### Crearlo (una sola vez por ordenador)

```powershell
python -m venv .venv
```

Esto crea la carpeta `.venv`. **No se sube a GitHub** (está en `.gitignore`): pesa mucho y se regenera en segundos.

### Activarlo (cada vez que abres una terminal nueva)

```powershell
.\.venv\Scripts\Activate.ps1
```

Sabrás que ha funcionado porque a la izquierda del cursor te aparece `(.venv)`:

```
(.venv) PS D:\Proyectos Claude\mercadona-dieta-app>
```

A partir de ahí, `python` y `pip` se refieren a los del cajón, no a los de Windows.

> **Si PowerShell te da un error rojo de "ejecución de scripts está deshabilitada":**
> Windows bloquea por defecto los scripts. Se desbloquea para tu usuario con:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> Solo hay que hacerlo una vez.

### Instalar las librerías

```powershell
pip install -r requirements.txt
```

`-r requirements.txt` significa "lee la lista de ese archivo e instálalo todo". Por eso ese archivo **sí** se sube a GitHub: es la receta para reconstruir el cajón en cualquier ordenador.

### Salir

```powershell
deactivate
```

O simplemente cierra la terminal.

---

## 3. Las librerías que usa el proyecto

Están en [`requirements.txt`](../requirements.txt):

| Librería | Para qué |
|---|---|
| **Flask** | El servidor web. Recibe lo que pides en el navegador y devuelve la página |
| **requests** | Hablar con internet. La usamos para pedirle los productos a Mercadona |
| **Pillow** | Manipular imágenes. Monta el collage de cada receta |

Fíjate en lo que **no** hace falta instalar, porque ya viene con Python:

- **`sqlite3`** — la base de datos donde guardamos el catálogo. Viene incluida.
- **`json`** — leer y escribir los archivos de recetas e ingredientes.
- **`math`, `unicodedata`, `pathlib`...** — utilidades varias.

Menos dependencias = menos cosas que se rompen.

---

## 4. Arrancar la aplicación

### La forma fácil

Doble clic en **`arrancar.bat`**. Ese archivo activa el entorno, lanza el servidor y abre el navegador solo. Es lo que usarás el 99 % de las veces.

### La forma manual (para ver los mensajes de error)

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.web
```

Y abres `http://localhost:8000` en el navegador.

> **¿Qué es `localhost`?** Es tu propio ordenador. El servidor web se está ejecutando en tu máquina y solo tú puedes verlo: no está publicado en internet. `8000` es el número de puerta (*puerto*) por la que escucha.

Para pararlo, `Ctrl + C` en la terminal.

### La primera vez, antes de nada

La app necesita el catálogo de Mercadona, que **no viene de GitHub**. Hay que descargarlo:

```powershell
python scripts/actualizar_catalogo.py
```

Tarda unos 3 minutos. Solo hay que repetirlo cuando quieras precios frescos (una vez a la semana está bien).

---

## 5. Resumen: de cero a funcionando en un ordenador nuevo

```powershell
git clone https://github.com/TU-USUARIO/mercadona-dieta-app.git
cd mercadona-dieta-app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/actualizar_catalogo.py
python -m app.web
```
