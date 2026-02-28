#!/bin/bash
# ============================================================
# BACKUP SEMANAL COMPLETO - CASIOPY MEMORY SERVICE
# ============================================================

set -e

# Configuración
CONTAINER_NAME="casiopy-memory-db"
DB_USER="memory_user"
DB_NAME="casiopy_memory"
BACKUP_DIR="./backups/weekly"
RETENTION_WEEKS=4

# Crear directorio si no existe
mkdir -p "$BACKUP_DIR"

# Generar timestamp y número de semana
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
WEEK_NUMBER=$(date +"%Y_W%U")
BACKUP_FILE="$BACKUP_DIR/memory_week_${WEEK_NUMBER}_${TIMESTAMP}.tar.gz"

echo "🔄 Iniciando backup semanal completo..."
echo "   Semana: $WEEK_NUMBER"
echo "   Timestamp: $TIMESTAMP"
echo "   Archivo: $BACKUP_FILE"

# Crear directorio temporal
TEMP_DIR="./backups/temp_weekly_$TIMESTAMP"
mkdir -p "$TEMP_DIR"

# 1. Backup de la base de datos
echo "📊 Exportando base de datos..."
docker exec "$CONTAINER_NAME" pg_dump \
    -U "$DB_USER" \
    -Fc \
    "$DB_NAME" > "$TEMP_DIR/database.dump"

# 2. Exportar esquema en SQL legible
echo "📄 Exportando esquema SQL..."
docker exec "$CONTAINER_NAME" pg_dump \
    -U "$DB_USER" \
    -s \
    "$DB_NAME" > "$TEMP_DIR/schema.sql"

# 3. Copiar archivos de configuración
echo "⚙️  Copiando configuración..."
cp docker-compose.yml "$TEMP_DIR/" 2>/dev/null || true
cp .env.example "$TEMP_DIR/" 2>/dev/null || true

# 4. Exportar estadísticas de la semana
echo "📈 Exportando estadísticas..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    COUNT(*) as total_interactions,
    COUNT(DISTINCT session_id) as total_sessions,
    AVG(quality_score) as avg_quality,
    COUNT(CASE WHEN is_training_ready THEN 1 END) as training_ready
FROM interactions
WHERE timestamp >= NOW() - INTERVAL '7 days';
" > "$TEMP_DIR/week_stats.txt"

# 5. Comprimir todo
echo "📦 Comprimiendo backup..."
tar -czf "$BACKUP_FILE" -C "$TEMP_DIR" .

# Limpiar directorio temporal
rm -rf "$TEMP_DIR"

# Verificar que el backup se creó correctamente
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup semanal completado exitosamente"
    echo "   Tamaño: $BACKUP_SIZE"
else
    echo "❌ Error: Backup no se creó correctamente"
    exit 1
fi

# Limpiar backups antiguos (más de RETENTION_WEEKS semanas)
echo "🧹 Limpiando backups antiguos (> $RETENTION_WEEKS semanas)..."
find "$BACKUP_DIR" -name "memory_week_*.tar.gz" -mtime +$((RETENTION_WEEKS * 7)) -delete

# Mostrar backups actuales
echo ""
echo "📦 Backups semanales disponibles:"
ls -lh "$BACKUP_DIR" | grep "memory_week"

echo ""
echo "✅ Proceso de backup semanal completado"
echo "   💾 Archivo: $BACKUP_FILE"
