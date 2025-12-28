# Guía Rápida - Sistema de Monitoreo

**Versión:** 2.0.0

---

## 🚀 Inicio Rápido

### 1. Iniciar el Servicio de Monitoreo

```bash
cd services/test-service
python -m src.main
```

El servicio estará disponible en: `http://127.0.0.1:8900`

### 2. Acceder al Dashboard de Monitoreo

Abre tu navegador en:
```
http://127.0.0.1:8900/monitoring
```

---

## 📊 Qué Puedes Monitorear

### Servicios
- **Gateway** (puerto 8765)
- **Conversation AI** (puerto 8801)
- **TTS Service** (puerto 8802)
- **Assistant** (puerto 8803)
- **Fish Speech Docker** (puerto 8080)

### Métricas
- ✅ **Uptime %** - Porcentaje de disponibilidad
- ✅ **Response Time** - Latencia de respuesta
- ✅ **Estado actual** - Online/Offline/Error
- ✅ **Consecutive Failures** - Fallos seguidos
- ✅ **State Changes** - Historial de cambios

### Docker & GPU
- ✅ **Container Status** - ¿Está corriendo Fish Speech?
- ✅ **CPU/Memory Usage** - Recursos del contenedor
- ✅ **GPU Utilization** - % de uso de GPU
- ✅ **VRAM Usage** - Memoria GPU usada
- ✅ **GPU Temperature** - Temperatura del chip

---

## 🎯 Funcionalidades Principales

### Dashboard en Tiempo Real

El dashboard se actualiza **automáticamente cada 5 segundos** vía WebSocket, mostrando:

1. **System Health**: Estado general (Healthy/Degraded/Critical)
2. **Services Online**: Cantidad de servicios activos
3. **Overall Uptime**: Promedio de uptime de todos los servicios
4. **Active Alerts**: Alertas pendientes

### Alertas Automáticas

El sistema genera alertas cuando:

| Condición | Tipo | Severidad |
|-----------|------|-----------|
| 3 fallos consecutivos | Service Down | Critical |
| Response time > 5 segundos | Slow Response | Warning |
| Fallos intermitentes | Repeated Failures | Warning |

**Cooldown:** 5 minutos por servicio (evita spam de alertas)

### Visualizaciones

- **Services List**: Estado de cada servicio con progress bar de uptime
- **Alerts Timeline**: Alertas recientes ordenadas por tiempo
- **Response Time Chart**: Gráfico de latencias (últimas 10 mediciones)
- **Docker/GPU Cards**: Stats en tiempo real

---

## 🔌 API REST

### Endpoints Principales

```bash
# Estado de todos los servicios
curl http://127.0.0.1:8900/api/services/status

# Métricas detalladas
curl http://127.0.0.1:8900/api/monitoring/metrics

# Salud del sistema
curl http://127.0.0.1:8900/api/monitoring/system-health

# Alertas recientes
curl http://127.0.0.1:8900/api/monitoring/alerts

# Reporte completo (servicios + métricas + docker + GPU)
curl http://127.0.0.1:8900/api/monitoring/full-report
```

### Endpoints de Docker/GPU

```bash
# Estado del contenedor Fish Speech
curl http://127.0.0.1:8900/api/docker/status

# Recursos del contenedor
curl http://127.0.0.1:8900/api/docker/stats

# Stats de GPU (nvidia-smi)
curl http://127.0.0.1:8900/api/gpu/stats
```

---

## 💡 Casos de Uso

### Verificar si Todos los Servicios Están Activos

**Dashboard:**
1. Abre `http://127.0.0.1:8900/monitoring`
2. Mira el header: "Services Online" debe mostrar 5/5
3. Todos los servicios deben tener badge verde "ONLINE"

**API:**
```bash
curl http://127.0.0.1:8900/api/monitoring/system-health
```

Respuesta OK:
```json
{
  "ok": true,
  "health": {
    "total_services": 5,
    "online": 5,
    "offline": 0,
    "error": 0,
    "health_status": "healthy"
  }
}
```

### Detectar Problemas de Performance

**Dashboard:**
1. Revisa la sección "Response Times"
2. Si algún servicio tiene response time > 1000ms (rojo), investiga

**API:**
```bash
curl http://127.0.0.1:8900/api/monitoring/metrics/tts | jq '.metrics.avg_response_time_ms'
```

### Verificar Estado de Fish Speech Docker

**Dashboard:**
1. Mira la sección "Docker & GPU Stats"
2. "Container Status" debe mostrar "Running"
3. "GPU Utilization" muestra % de uso

**API:**
```bash
# Container
curl http://127.0.0.1:8900/api/docker/status

# GPU
curl http://127.0.0.1:8900/api/gpu/stats
```

### Revisar Alertas Pendientes

**Dashboard:**
1. Sección "Recent Alerts" muestra últimas alertas
2. Las no resueltas aparecen con fondo rojo/naranja

**API:**
```bash
# Solo alertas sin resolver
curl "http://127.0.0.1:8900/api/monitoring/alerts?unresolved_only=true"
```

---

## ⚠️ Troubleshooting

### Dashboard no conecta (muestra "Disconnected")

**Causas:**
- Test Service no está corriendo
- Firewall bloquea WebSocket

**Solución:**
```bash
# Verificar servicio corriendo
curl http://127.0.0.1:8900/health

# Si no responde, iniciar el servicio
cd services/test-service
python -m src.main
```

### Servicio aparece OFFLINE pero está corriendo

**Causas:**
- El servicio no tiene endpoint `/health`
- El servicio está tomando > 3 segundos en responder

**Solución:**
```bash
# Verificar manualmente el health endpoint
curl http://127.0.0.1:8802/health  # TTS ejemplo

# Si responde lento, revisar logs del servicio
```

### Docker stats no aparecen

**Causas:**
- Container Fish Speech no está corriendo
- `nvidia-smi` no disponible

**Solución:**
```bash
# Verificar container
docker ps -a | grep fish-speech

# Iniciar container si está parado
cd services/tts/docker-ngc
docker-compose up -d

# Verificar nvidia-smi
nvidia-smi
```

### Muchas alertas de "Service Down"

**Causas:**
- Servicio realmente está caído
- Servicio está intermitente
- Threshold muy bajo (3 fallos)

**Solución:**
```bash
# Revisar logs del servicio problemático
# Ejemplo para TTS:
cd services/tts
python -m src.server

# Si es falsa alarma, ajustar threshold en src/monitoring.py:
# "consecutive_failures": 5  # Cambiar de 3 a 5
```

---

## 📈 Interpretar Métricas

### Uptime Percentage

| Valor | Interpretación |
|-------|----------------|
| 100% | Perfecto, sin fallos |
| 95-99% | Muy bueno, algunos fallos menores |
| 90-94% | Aceptable, revisar estabilidad |
| < 90% | Problemático, investigar urgente |

### Response Time

| Valor | Interpretación |
|-------|----------------|
| < 50ms | Excelente |
| 50-200ms | Bueno |
| 200-1000ms | Aceptable |
| > 1000ms | Lento, investigar |
| > 5000ms | Crítico, genera alerta |

### System Health

| Estado | Significado |
|--------|-------------|
| **Healthy** | Todos los servicios online |
| **Degraded** | Al menos 1 servicio offline |
| **Critical** | Todos los servicios offline |

---

## 🔧 Configuración Avanzada

### Ajustar Frecuencia de Checks

Por defecto: **5 segundos**

Para cambiar, edita `src/main.py`:

```python
async def broadcast_monitoring_updates():
    while True:
        await asyncio.sleep(10)  # Cambiar a 10 segundos
        ...
```

### Ajustar Thresholds de Alertas

Edita `src/monitoring.py`:

```python
self.alert_thresholds = {
    "consecutive_failures": 3,      # Alertar tras X fallos
    "slow_response_ms": 5000,       # Alertar si > X ms
    "alert_cooldown_minutes": 5     # No re-alertar antes de X min
}
```

### Agregar Nuevo Servicio al Monitoreo

Edita `src/main.py`, sección `SERVICES`:

```python
SERVICES = {
    "mi_servicio": {
        "name": "Mi Servicio",
        "port": 8804,
        "health_url": "http://127.0.0.1:8804/health",
        "color": "#E91E63",
        "manageable": True
    }
}
```

El servicio aparecerá automáticamente en el dashboard.

---

## 📚 Documentación Completa

Para más detalles técnicos, consulta:

- **Arquitectura completa**: [`ia_docs/monitoring/arquitectura-monitoreo-2025-12-27.md`](../../ia_docs/monitoring/arquitectura-monitoreo-2025-12-27.md)
- **Resumen de implementación**: [`ia_docs/monitoring/resumen-implementacion-2025-12-27.md`](../../ia_docs/monitoring/resumen-implementacion-2025-12-27.md)
- **README del servicio**: [`README.md`](README.md)

---

## 🎯 Checklist de Uso Diario

### Al Iniciar Sesión de Trabajo

- [ ] Abrir dashboard de monitoreo: `http://127.0.0.1:8900/monitoring`
- [ ] Verificar System Health = "HEALTHY"
- [ ] Verificar Services Online = "5/5"
- [ ] Revisar si hay alertas pendientes
- [ ] Verificar Fish Speech container = "Running"

### Al Encontrar Problemas

- [ ] Revisar alertas en dashboard
- [ ] Consultar métricas del servicio problemático
- [ ] Revisar logs del servicio afectado
- [ ] Verificar dependencias (ej: TTS requiere Fish Speech)
- [ ] Reiniciar servicio si es necesario

### Antes de Deployar Cambios

- [ ] Verificar que todos los servicios estén online
- [ ] Guardar snapshot de métricas actuales
- [ ] Después del deploy, verificar que servicios se recuperen
- [ ] Monitorear alertas por 5-10 minutos

---

## 💬 Soporte

Si encuentras problemas o necesitas ayuda:

1. **Revisar logs**: `services/test-service/logs/audit.log`
2. **Consultar troubleshooting** en esta guía
3. **Revisar documentación** técnica completa

---

**Última actualización:** 2025-12-27
**Versión del sistema:** 2.0.0
