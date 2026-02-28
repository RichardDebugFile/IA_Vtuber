#!/bin/bash
# ============================================================
# BACKUP DIARIO - CASIOPY MEMORY SERVICE
# ============================================================

set -e

# Configuración
CONTAINER_NAME="casiopy-memory-db"
DB_USER="memory_user"
DB_NAME="casiopy_memory"
BACKUP_DIR="./backups/daily"
RETENTION_DAYS=7

# Crear directorio si no existe
mkdir -p "$BACKUP_DIR"

# Generar timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/memory_daily_${TIMESTAMP}.dump"

echo "🔄 Iniciando backup diario de PostgreSQL..."
echo "   Timestamp: $TIMESTAMP"
echo "   Archivo: $BACKUP_FILE"

# Ejecutar pg_dump en formato custom (comprimido)
docker exec "$CONTAINER_NAME" pg_dump \
    -U "$DB_USER" \
    -Fc \
    "$DB_NAME" > "$BACKUP_FILE"

# Verificar que el backup se creó correctamente
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup completado exitosamente"
    echo "   Tamaño: $BACKUP_SIZE"
else
    echo "❌ Error: Backup no se creó correctamente"
    exit 1
fi

# Limpiar backups antiguos (más de RETENTION_DAYS días)
echo "🧹 Limpiando backups antiguos (> $RETENTION_DAYS días)..."
find "$BACKUP_DIR" -name "memory_daily_*.dump" -mtime +$RETENTION_DAYS -delete

# Mostrar backups actuales
echo ""
echo "📦 Backups diarios disponibles:"
ls -lh "$BACKUP_DIR" | grep "memory_daily"

echo ""
echo "✅ Proceso de backup diario completado"
