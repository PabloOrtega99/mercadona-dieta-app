@echo off
REM ===========================================================================
REM  arrancar.bat - Doble clic aqui para abrir la aplicacion.
REM
REM  Un archivo .bat es un guion de comandos de Windows: cada linea es lo que
REM  escribirias tu en la terminal. Existe para no tener que acordarte de
REM  activar el entorno y escribir el comando cada vez.
REM
REM  @echo off  = no vayas escribiendo en pantalla cada linea antes de hacerla.
REM  REM        = comentario, no se ejecuta.
REM ===========================================================================

REM cd /d se coloca en la carpeta de este archivo (%~dp0), incluso si esta en
REM otra unidad de disco (eso es lo que hace el /d). Sin esto, al hacer doble
REM clic Windows podria arrancar desde C:\Windows\System32 y no encontrar nada.
cd /d "%~dp0"

echo.
echo  Arrancando la aplicacion de menus de Mercadona...
echo.

REM Si no existe el entorno virtual, es que el proyecto esta recien clonado.
REM En vez de fallar con un error incomprensible, se explica que hacer.
if not exist ".venv\Scripts\python.exe" (
    echo  [ERROR] No encuentro el entorno virtual ^(.venv^).
    echo.
    echo  Parece que es la primera vez que abres el proyecto en este ordenador.
    echo  Abre PowerShell en esta carpeta y ejecuta, en este orden:
    echo.
    echo      python -m venv .venv
    echo      .\.venv\Scripts\Activate.ps1
    echo      pip install -r requirements.txt
    echo      python scripts/actualizar_catalogo.py
    echo.
    pause
    exit /b 1
)

REM Se llama al python del entorno virtual directamente, sin activarlo. Es
REM equivalente y mas corto.
".venv\Scripts\python.exe" -m app.web

REM pause deja la ventana abierta al terminar. Sin esto, si el programa falla
REM la ventana se cierra al instante y no llegas a leer el error.
echo.
echo  El servidor se ha parado.
pause
