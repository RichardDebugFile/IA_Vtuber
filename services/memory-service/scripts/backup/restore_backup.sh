#!/bin/bash
# ============================================================
# RESTAURAR BACKUP - CASIOPY MEMORY SERVICE
# ============================================================

set -e

# Configuración
CONTAINER_NAME="casiopy-memory-db"
DB_USER="memory_user"
DB_NAME="casiopy_memory"

# Función de ayuda
show_help() {
    echo "Uso: ./restore_backup.sh <archivo_backup>"
    echo ""
    echo "Ejemplos:"
    echo "  ./restore_backup.sh ./backups/daily/memory_daily_20240115_120000.dump"
    echo "  ./restore_backup.sh ./backups/weekly/memory_week_2024_W02_20240115_120000.tar.gz"
    echo ""
    echo "Tipos de backup soportados:"
    echo "  - .dump   : Backup diario de PostgreSQL (pg_dump)"
    echo "  - .tar.gz : Backup semanal completo"
}

# Verificar argumentos
if [ $# -eq 0 ]; then
    echo "❌ Error: Debe especificar un archivo de backup"
    echo ""
    show_help
    exit 1
fi

BACKUP_FILE="$1"

# Verificar que el archivo existe
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Error: El archivo '$BACKUP_FILE' no existe"
    exit 1
fi

# Detectar tipo de backup
if [[ "$BACKUP_FILE" == *.dump ]]; then
    BACKUP_TYPE="daily"
elif [[ "$BACKUP_FILE" == *.tar.gz ]]; then
    BACKUP_TYPE="weekly"
else
    echo "❌ Error: Tipo de archivo no soportado"
    echo "    Archivos válidos: .dump o .tar.gz"
    exit 1
fi

echo "🔄 Iniciando restauración de backup..."
echo "   Archivo: $BACKUP_FILE"
echo "   Tipo: $BACKUP_TYPE"
echo ""

# Confirmación
read -p "⚠️  ADVERTENCIA: Esto SOBRESCRIBIRÁ la base de datos actual. ¿Continuar? (yes/no): " confirmation
if [ "$confirmation" != "yes" ]; then
    echo "❌ Restauración cancelada"
    exit 0
fi

if [ "$BACKUP_TYPE" == "daily" ]; then
    # Restaurar backup diario (.dump)
    echo "📥 Restaurando backup diario..."

    # Primero, eliminar conexiones existentes
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '$DB_NAME'
          AND pid <> pg_backend_pid();
    "

    # Eliminar y recrear la base de datos
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"

    # Restaurar el dump
    cat "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" pg_restore \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose

elif [ "$BACKUP_TYPE" == "weekly" ]; then
    # Restaurar backup semanal (.tar.gz)
    echo "📥 Restaurando backup semanal..."

    # Crear directorio temporal
    TEMP_DIR="./backups/temp_restore_$(date +%s)"
    mkdir -p "$TEMP_DIR"

    # Extraer el archivo
    echo "📦 Extrayendo backup..."
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

    # Verificar que database.dump existe
    if [ ! -f "$TEMP_DIR/database.dump" ]; then
        echo "❌ Error: No se encontró database.dump en el backup"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    # Eliminar conexiones existentes
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '$DB_NAME'
          AND pid <> pg_backend_pid();
    "

    # Eliminar y recrear la base de datos
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"

    # Restaurar el dump
    cat "$TEMP_DIR/database.dump" | docker exec -i "$CONTAINER_NAME" pg_restore \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose

    # Limpiar directorio temporal
    rm -rf "$TEMP_DIR"
fi

# Verificar restauración
echo ""
echo "🔍 Verificando restauración..."
INTERACTION_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM interactions;")
SESSION_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM sessions;")
CORE_MEMORY_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM core_memory;")

echo "✅ Restauración completada exitosamente"
echo ""
echo "📊 Estadísticas de la base de datos restaurada:"
echo "   - Core Memory: $CORE_MEMORY_COUNT entradas"
echo "   - Sesiones: $SESSION_COUNT"
echo "   - Interacciones: $INTERACTION_COUNT"
