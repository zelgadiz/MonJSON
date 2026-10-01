#!/bin/bash

set -e

APP_DIR="/opt/monjson"
VENV_DIR="$APP_DIR/venv"
REQUIREMENTS="$APP_DIR/requirements.txt"

echo "=========================================="
echo " Configuración del entorno MonJSON"
echo "=========================================="

# ------------------------------------------------------------
# Comprobar root
# ------------------------------------------------------------

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Este script debe ejecutarse como root."
    exit 1
fi

# ------------------------------------------------------------
# Comprobar directorio
# ------------------------------------------------------------

if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: No existe $APP_DIR"
    exit 1
fi

cd "$APP_DIR"

echo "[1/5] Verificando Python..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 no está instalado."
    exit 1
fi

python3 --version

# ------------------------------------------------------------
# Instalar soporte para venv
# ------------------------------------------------------------

echo "[2/5] Verificando python3-venv..."

if ! dpkg -s python3-venv >/dev/null 2>&1; then

    echo "Instalando python3-venv..."

    apt-get update
    apt-get install -y python3-venv

fi

# ------------------------------------------------------------
# Crear entorno virtual
# ------------------------------------------------------------

echo "[3/5] Creando entorno virtual..."

if [ ! -x "$VENV_DIR/bin/python" ]; then

    echo "Creando: $VENV_DIR"

    python3 -m venv "$VENV_DIR"

else

    echo "El entorno virtual ya existe."

fi

# ------------------------------------------------------------
# Actualizar pip
# ------------------------------------------------------------

echo "[4/5] Actualizando pip..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip

# ------------------------------------------------------------
# Instalar requirements
# ------------------------------------------------------------

echo "[5/5] Instalando dependencias..."

if [ ! -f "$REQUIREMENTS" ]; then

    echo "ERROR: No existe:"
    echo "       $REQUIREMENTS"

    exit 1

fi

"$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS"

# ------------------------------------------------------------
# Verificación
# ------------------------------------------------------------

echo
echo "=========================================="
echo " Verificando instalación"
echo "=========================================="

"$VENV_DIR/bin/python" -c "
import fastapi
import psutil
import uvicorn

print('FastAPI :', fastapi.__version__)
print('psutil  :', psutil.__version__)
print('uvicorn :', uvicorn.__version__)
print()
print('Dependencias instaladas correctamente.')
"

echo
echo "=========================================="
echo " CONFIGURACIÓN COMPLETADA"
echo "=========================================="
echo
echo "Python del entorno:"
echo "  $VENV_DIR/bin/python"
echo
echo "Para ejecutar MonJSON:"
echo
echo "  $VENV_DIR/bin/python $APP_DIR/main.py"
echo
echo "O directamente:"
echo
echo "  $VENV_DIR/bin/python main.py"
echo
echo "=========================================="
