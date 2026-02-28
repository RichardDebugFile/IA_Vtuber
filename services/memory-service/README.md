# 🧠 Casiopy Memory Service

Sistema de memoria persistente y evolutiva para Casiopy VTuber AI.

## 📋 Características

- **Capa 0 (Core Memory)**: Memoria inmutable - identidad, gustos, personalidad permanente
- **Capa 1 (LoRA Personality)**: Entrenamiento de personalidad estática con dataset natural
- **🆕 Training Dashboard**: Interfaz web para monitorear entrenamiento en tiempo real
- **Almacenamiento de interacciones**: Captura completa de conversaciones para análisis
- **Sistema de calidad**: Scoring automático para determinar qué guardar
- **Backups automáticos**: Multi-nivel (horario, diario, semanal)
- **Exportación para fine-tuning**: Formatos compatibles con Unsloth/Hermes-3
- **API RESTful**: FastAPI con documentación automática

---

## ⚡ Inicio Rápido - Training Dashboard

**¿Quieres entrenar la personalidad de Casiopy?** El sistema está completamente configurado:

1. **Instalar dependencias:**
   ```bash
   cd frontend
   pip install -r requirements.txt
   ```

2. **Iniciar dashboard:**
   ```bash
   start_dashboard.bat  # Windows
   # o
   python app.py
   ```

3. **Abrir en navegador:** http://localhost:5000

📖 **Guía completa:** [TRAINING_SETUP_COMPLETE.md](TRAINING_SETUP_COMPLETE.md)

---

## 🏗️ Arquitectura

```
Core Memory (PostgreSQL)
    ↓
Interactions Storage
    ↓
Quality Scoring
    ↓
Training Export
    ↓
LoRA Fine-tuning (Unsloth)
```

## 🚀 Instalación Rápida

### 1. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 2. Iniciar PostgreSQL con Docker

```bash
docker-compose up -d
```

Esto iniciará:
- PostgreSQL 16 con pgvector (puerto 8821)
- Backup automático cada hora

### 3. Instalar dependencias Python

```bash
pip install -r requirements.txt
```

### 4. Iniciar el servicio

```bash
cd src
python main.py
```

El servicio estará disponible en: `http://localhost:8820`

## 📚 Documentación API

Una vez iniciado el servicio, accede a:

- **Swagger UI**: http://localhost:8820/docs
- **ReDoc**: http://localhost:8820/redoc

## 🔧 Endpoints Principales

### Core Memory (Capa 0)

```bash
# Obtener toda la core memory
GET /core-memory

# Obtener por categoría
GET /core-memory/{category}

# Generar system prompt
GET /core-memory/system-prompt/generate

# Agregar entrada
POST /core-memory
{
  "category": "like",
  "key": "language_rust",
  "value": "Rust es fascinante",
  "is_mutable": false
}
```

### Sessions & Interactions

```bash
# Crear sesión
POST /sessions
{
  "user_id": "user123",
  "opt_out_training": false
}

# Almacenar interacción
POST /interactions
{
  "session_id": "uuid-here",
  "input_text": "Hola Casiopy",
  "output_text": "*suspiro* Hola... qué necesitas?",
  "input_emotion": "neutral",
  "output_emotion": "sarcastic"
}

# Finalizar sesión
POST /sessions/{session_id}/end
```

### Training Data

```bash
# Obtener interacciones listas para entrenamiento
GET /interactions/training-ready?min_quality=0.6

# Actualizar quality score
PUT /interactions/{interaction_id}/quality
{
  "quality_score": 0.85
}
```

## 💾 Sistema de Backups

### Backups Automáticos

El contenedor `memory-backup` realiza backups automáticamente:
- **Cada hora**: Backup incremental
- **Retención**: 7 días, 4 semanas, 6 meses

### Backups Manuales

```bash
# Backup diario
./backup_daily.sh

# Backup semanal completo
./backup_weekly.sh

# Restaurar desde backup
./restore_backup.sh ./backups/daily/memory_daily_YYYYMMDD_HHMMSS.dump
```

## 📊 Estructura de la Base de Datos

### Tablas Principales

1. **core_memory**: Memoria inmutable (Capa 0)
2. **sessions**: Agrupación de conversaciones
3. **interactions**: Cada input/output con embeddings
4. **topics**: Temas detectados automáticamente
5. **feedback**: Retroalimentación del usuario
6. **training_exports**: Registro de exportaciones
7. **lora_versions**: Control de versiones de LoRA

## 🧪 Testing

```bash
# Verificar que PostgreSQL está corriendo
docker ps | grep casiopy-memory-db

# Test de conexión
curl http://localhost:8820/health

# Ver estadísticas
curl http://localhost:8820/stats
```

## 🔐 Seguridad

- Las contraseñas se almacenan en `.env` (no committear)
- Anonimización de datos de usuario antes de export
- Soporte para opt-out de entrenamiento
- Backups encriptados (configurar en producción)

## 📁 Estructura del Proyecto

```
memory-service/
├── src/
│   ├── main.py                 # FastAPI application
│   ├── database.py             # DB connection
│   ├── core_memory.py          # Core Memory manager
│   └── interaction_manager.py  # Interactions manager
├── init-scripts/
│   ├── 01_init_schema.sql      # DB schema
│   └── 02_populate_core_memory.sql  # Initial data
├── backups/                    # Backup storage
│   ├── hourly/
│   ├── daily/
│   ├── weekly/
│   └── wal/
├── exports/                    # Training exports
├── lora_adapters/             # Trained LoRAs
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```

## 🔄 Flujo de Trabajo

### 1. Captura de Interacciones

```python
# Desde el Conversation Service
response = httpx.post("http://localhost:8820/interactions", json={
    "session_id": session_id,
    "input_text": user_input,
    "output_text": casiopy_response,
    "input_emotion": detected_emotion,
    "output_emotion": "sarcastic",
    "model_version": "hermes-3-week-05"
})
```

### 2. Procesamiento Semanal

```bash
# Exportar datos de la semana
GET /interactions/training-ready?min_quality=0.6

# Generar dataset para Unsloth
python scripts/export_training_data.py --format chatml --output ./exports/week_05.jsonl
```

### 3. Fine-tuning con Unsloth

Ver documentación en: `ia_docs/memory-service/MEMORIA_PERSONALIDAD.md`

## ⚙️ Configuración Avanzada

### Cambiar puerto

Editar `.env`:
```
API_PORT=8820  # Puerto por defecto del Memory Service
```

### Habilitar debug SQL

Editar `src/database.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Ver todas las queries SQL
    ...
)
```

## 🐛 Troubleshooting

### PostgreSQL no inicia

```bash
docker-compose logs memory-postgres
docker-compose down
docker-compose up -d
```

### Error de conexión

Verificar que los puertos no estén en uso:
```bash
netstat -an | grep 8820  # API
netstat -an | grep 8821  # PostgreSQL
```

### Permisos de backup scripts

```bash
chmod +x backup_daily.sh
chmod +x backup_weekly.sh
chmod +x restore_backup.sh
```

## 📈 Próximos Pasos

1. ✅ Setup inicial completo
2. ✅ API funcionando
3. ✅ Sistema de embeddings (sentence-transformers)
4. ✅ Scripts de exportación para training
5. ✅ Training pipeline con Unsloth
6. 🔄 Integración con Conversation Service
7. ⏳ Exportación automática semanal (cron job)

## 🎓 Training de LoRAs

Este servicio incluye un **sistema completo de entrenamiento multicapa** para crear y mantener la personalidad de Casiopy.

### Configuración Rápida

```bash
# Windows
setup_training.bat

# Linux/Mac
chmod +x setup_training.sh
./setup_training.sh
```

### Arquitectura de Capas

- **Capa 0** (PostgreSQL): Core Memory - identidad, gustos, amigos
- **Capa 1** (LoRA Static): Personalidad - sarcasmo, actitud (se entrena UNA vez)
- **Capa 2** (LoRA Dynamic): Episódico - conversaciones semanales
- **Capa 3** (LoRA On-Demand): Habilidades técnicas (opcional)

### Scripts de Training

```bash
cd scripts

# 1. Exportar datos
python export_training_data.py --type personality
python export_training_data.py --type episodic --week 5

# 2. Entrenar LoRAs
python train_personality_lora.py --dataset ../exports/personality/*.jsonl
python train_episodic_lora.py --dataset ../exports/episodic/*.jsonl --week 5

# 3. Desplegar a Ollama
python deploy_to_ollama.py --week 5

# 4. Validar (anti-lobotomía)
python test_personality.py --model casiopy:week05 --save-report
```

### Documentación Completa

Ver [TRAINING_WORKFLOW.md](TRAINING_WORKFLOW.md) para el workflow completo paso a paso.

## 🤝 Integración con Sistema Quimera

Este servicio es parte del **Sistema Quimera** y se integra con:

- **Conversation Service**: Envía interacciones
- **Gateway**: Routing de requests
- **Monitoring**: Métricas y logs

Para más información, ver: `ia_docs/memory-service/ARQUITECTURA_MEMORIA.md`

## 📝 Notas Importantes

- **NUNCA** modificar core_memory con `is_mutable=false`
- **SIEMPRE** hacer backup antes de cambios mayores
- **VERIFICAR** opt-out antes de exportar para training
- **PERSONALIZAR** `02_populate_core_memory.sql` con información real

## 🆘 Soporte

Para reportar issues o contribuir:
1. Revisar logs en `./logs/memory_service.log`
2. Verificar estado de DB con `/stats` endpoint
3. Consultar documentación completa en `ia_docs/memory-service/`
