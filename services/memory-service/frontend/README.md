# 🎮 Casiopy Training Dashboard

Frontend web interactivo para monitorear y controlar el entrenamiento del LoRA de personalidad de Casiopy.

---

## 🌟 Características

### 📊 Monitoreo en Tiempo Real
- ✅ **Métricas del Sistema**: GPU, VRAM, CPU, RAM, Temperatura
- ✅ **Progreso del Entrenamiento**: Epochs, Steps, Loss, Learning Rate
- ✅ **Gráficas en Vivo**: Loss history y uso de recursos
- ✅ **Logs en Tiempo Real**: Output del entrenamiento con timestamps

### 🎮 Control del Entrenamiento
- ✅ **Validación de Dataset**: Verificar integridad antes de entrenar
- ✅ **Configuración Flexible**: Epochs, Batch Size, Learning Rate
- ✅ **Inicio/Detención**: Control completo del proceso
- ✅ **Información del Dataset**: Ejemplos, tamaño, estadísticas

### 📡 Tecnología
- **Backend**: Flask + Flask-SocketIO (WebSockets)
- **Frontend**: HTML5 + CSS3 + JavaScript Vanilla
- **Gráficas**: Chart.js
- **Comunicación**: Socket.IO (tiempo real)

---

## 🚀 Instalación

### 1. Instalar Dependencias

```bash
cd frontend
pip install -r requirements.txt
```

### 2. (Opcional) GPU Monitoring

Si tienes GPU NVIDIA y quieres monitoreo detallado:

```bash
pip install nvidia-ml-py3
```

---

## 🎯 Uso

### Iniciar Dashboard

```bash
# Desde la carpeta frontend
python app.py
```

O usar el script de inicio:

```bash
# Windows
start_dashboard.bat

# Linux/Mac
./start_dashboard.sh
```

### Acceder al Dashboard

Abrir en el navegador:
```
http://localhost:5000
```

---

## 📖 Guía de Uso

### 1. Validar Dataset

Antes de entrenar, **siempre valida el dataset**:

1. Click en **"🔍 Validar Dataset"**
2. Espera confirmación en logs
3. Verifica estadísticas del dataset

### 2. Configurar Parámetros

Ajusta según tu hardware:

- **Epochs**: 3-5 recomendado para inicio
- **Batch Size**:
  - RTX 5060 Ti (16GB): 4-8
  - GPU menores: 2-4
- **Learning Rate**: `2e-4` por defecto (bueno para LoRA)

### 3. Iniciar Entrenamiento

1. Click en **"▶️ Iniciar Entrenamiento"**
2. Observa métricas en tiempo real
3. Monitorea gráficas de Loss y recursos

### 4. Detener si es Necesario

- Click en **"⏹️ Detener"** para abortar entrenamiento
- El modelo se guardará en el último checkpoint

---

## 🎨 Interfaz del Dashboard

### Panel Superior
- **Estado**: Badge de color indica estado actual
- **Conexión**: Indicador de conexión WebSocket

### Métricas del Sistema (Izquierda)
- GPU Usage (%)
- VRAM Usage (%)
- CPU Usage (%)
- RAM Usage (%)
- Temperatura GPU (°C)

### Progreso del Entrenamiento (Centro)
- Barra de progreso visual
- Epoch actual/total
- Step actual/total
- Loss actual
- Learning Rate actual

### Dataset (Derecha)
- Total de ejemplos
- Tamaño del archivo
- Promedio de palabras por respuesta
- Ruta del archivo

### Configuración y Controles
- Inputs para ajustar parámetros
- Botones de validación e inicio/detención
- Tiempo transcurrido

### Gráficas
- **Loss**: Evolución de la pérdida durante entrenamiento
- **Recursos**: GPU/CPU/RAM en tiempo real

### Logs
- Salida en tiempo real del proceso
- Color-coded por nivel (info/success/warning/error)
- Auto-scroll al último log

---

## 🔧 API REST

El dashboard también expone una API REST:

### GET /api/status
Obtener estado actual del entrenamiento

```bash
curl http://localhost:5000/api/status
```

### GET /api/metrics
Obtener métricas del sistema en tiempo real

```bash
curl http://localhost:5000/api/metrics
```

### GET /api/dataset/info
Información del dataset

```bash
curl http://localhost:5000/api/dataset/info
```

### GET /api/logs
Obtener logs recientes

```bash
curl http://localhost:5000/api/logs?limit=100
```

### GET /api/logs/list
Listar archivos de log guardados

```bash
curl http://localhost:5000/api/logs/list
```

---

## 📡 WebSocket Events

### Client → Server

- `start_validation`: Iniciar validación del dataset
- `start_training`: Iniciar entrenamiento (envía config)
- `stop_training`: Detener entrenamiento
- `request_metrics`: Solicitar métricas del sistema

### Server → Client

- `training_update`: Estado completo del entrenamiento
- `metrics_update`: Métricas del sistema actualizadas
- `error`: Mensajes de error

---

## 📂 Estructura de Archivos

```
frontend/
├── app.py                    # Servidor Flask + SocketIO
├── requirements.txt          # Dependencias Python
├── README.md                 # Este archivo
├── start_dashboard.bat       # Script de inicio Windows
├── start_dashboard.sh        # Script de inicio Linux/Mac
│
├── templates/
│   └── dashboard.html        # Template del dashboard
│
└── static/                   # (Futuro: CSS/JS separados)
```

---

## 🎯 Estados del Entrenamiento

| Estado | Color | Descripción |
|--------|-------|-------------|
| `idle` | Gris | Esperando inicio |
| `validating` | Amarillo | Validando dataset |
| `training` | Azul (pulsante) | Entrenamiento activo |
| `completed` | Verde | Completado exitosamente |
| `error` | Rojo | Error durante proceso |

---

## 🔍 Troubleshooting

### "No se puede conectar al servidor"
- Verifica que `app.py` esté corriendo
- Check que el puerto 5000 no esté en uso
- Firewall puede estar bloqueando

### "GPU metrics no disponibles"
- Instala `nvidia-ml-py3`
- Verifica que tengas GPU NVIDIA
- Check drivers NVIDIA actualizados

### "Entrenamiento no inicia"
- Valida dataset primero
- Verifica que el script `train_personality_lora.py` exista
- Check logs para errores específicos

### "WebSocket desconectado"
- Refresca la página
- Verifica conexión de red
- Restart el servidor

---

## 🚀 Próximas Características

### Planeadas para v1.1
- [ ] Guardar/cargar configuraciones preestablecidas
- [ ] Comparación de múltiples entrenamientos
- [ ] Exportar métricas a CSV/JSON
- [ ] Notificaciones push cuando termine entrenamiento
- [ ] Estimación de tiempo restante mejorada
- [ ] Reiniciar desde checkpoint
- [ ] Modo oscuro/claro toggle

### Planeadas para v2.0
- [ ] Multi-GPU support
- [ ] Distributed training monitoring
- [ ] Integration con TensorBoard
- [ ] Auto-tuning de hiperparámetros
- [ ] A/B testing de configuraciones

---

## 📝 Notas Técnicas

### Performance
- Actualización de métricas: 1 segundo
- Logs mantienen últimos 100 en memoria
- Gráficas muestran últimos 60-100 puntos

### Seguridad
- ⚠️ **Dashboard solo para uso local**
- No exponer a internet sin autenticación
- Cambiar `SECRET_KEY` en producción

### Compatibilidad
- Tested en Chrome, Firefox, Edge
- Requiere JavaScript habilitado
- Responsive design para tablets

---

## 🤝 Contribución

Para añadir features:

1. Fork del repositorio
2. Crear branch feature
3. Hacer cambios
4. Submit pull request

---

## 📄 Licencia

Parte del Proyecto Quimera CASIOPY
© 2024 Richard (AlfitaXR)

---

## 🆘 Soporte

Para issues y preguntas:
- Check logs en `services/memory-service/logs/`
- Revisar console del navegador (F12)
- Verificar output del servidor Flask

---

**Desarrollado con ❤️ para Casiopy**
**IA Asistente**: Claude Sonnet 4.5
