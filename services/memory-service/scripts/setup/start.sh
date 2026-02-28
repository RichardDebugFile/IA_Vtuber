#!/bin/bash
# ============================================================
# START SCRIPT - CASIOPY MEMORY SERVICE
# ============================================================

set -e

echo "🧠 Iniciando Casiopy Memory Service..."
echo ""

# Verificar que existe .env
if [ ! -f .env ]; then
    echo "⚠️  Archivo .env no encontrado"
    echo "   Copiando .env.example a .env..."
    cp .env.example .env
    echo "   ⚠️  IMPORTANTE: Edita .env con tus configuraciones"
    echo ""
fi

# Iniciar PostgreSQL con Docker
echo "🐘 Iniciando PostgreSQL con Docker Compose..."
docker-compose up -d

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL esté listo..."
sleep 5

# Verificar que PostgreSQL está corriendo
if docker ps | grep -q casiopy-memory-db; then
    echo "✅ PostgreSQL iniciado correctamente"
else
    echo "❌ Error: PostgreSQL no está corriendo"
    echo "   Ver logs: docker-compose logs memory-postgres"
    exit 1
fi

# Crear directorio de logs si no existe
mkdir -p logs

# Verificar que Python está instalado
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python no está instalado"
    exit 1
fi

# Verificar dependencias Python
echo "📦 Verificando dependencias Python..."
if [ ! -d "venv" ]; then
    echo "   Creando entorno virtual..."
    python -m venv venv
fi

# Activar entorno virtual
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate

# Instalar/actualizar dependencias
echo "   Instalando dependencias..."
pip install -q -r requirements.txt

# Iniciar el servicio
echo ""
echo "🚀 Iniciando Memory Service API..."
echo "   URL: http://localhost:8820"
echo "   Docs: http://localhost:8820/docs"
echo "   PostgreSQL: localhost:8821"
echo ""

cd src
python main.py
