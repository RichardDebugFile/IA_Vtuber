# 🚀 Inicio Rápido - Monitoring Service

## Arranque en 2 pasos

### 1️⃣ Navega al directorio
```cmd
cd services\monitoring-service
```

### 2️⃣ Ejecuta el script de arranque

**Windows CMD:**
```cmd
start.bat
```

**Windows PowerShell:**
```powershell
.\start.ps1
```

**Linux/Mac:**
```bash
./start.sh
```

---

## ¿Qué hace el script?

✅ Verifica que estés en el directorio correcto
✅ Detecta automáticamente el entorno virtual de Python
✅ Inicia el servidor en puerto **8900**
✅ Habilita auto-reload (los cambios se aplican automáticamente)
✅ Muestra la URL del dashboard

---

## Acceso al Dashboard

Una vez iniciado el servicio, abre tu navegador en:

```
http://127.0.0.1:8900/monitoring
```

---

## Salida esperada

```
========================================
 Monitoring Service - Iniciando
========================================

[OK] Directorio correcto
[OK] Entorno virtual encontrado

Iniciando Monitoring Service en puerto 8900...

Accede al dashboard en:
  http://127.0.0.1:8900/monitoring

Presiona Ctrl+C para detener el servicio
========================================

INFO:     Uvicorn running on http://127.0.0.1:8900
INFO:     Application startup complete.
```

---

## Detener el servicio

Presiona **Ctrl+C** en la terminal donde se está ejecutando.

---

## Troubleshooting

### Error: "No se encuentra src\main.py"

**Causa:** Estás ejecutando el script desde el directorio incorrecto.

**Solución:**
```cmd
cd F:\Documentos F\GitHub\IA_Vtuber\services\monitoring-service
start.bat
```

### Error: "No se encuentra el entorno virtual"

**Causa:** El entorno virtual no está en la ubicación esperada.

**Solución:**
```bash
# Desde la raíz del proyecto
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Puerto 8900 ya en uso

**Causa:** Ya hay una instancia del servicio corriendo.

**Solución:**
1. Busca la terminal donde está corriendo
2. Presiona Ctrl+C para detenerlo
3. O cambia el puerto en el script:
```bash
# En start.bat, cambiar:
--port 8900
# Por:
--port 8901
```

---

## Alternativa: Arranque Manual

Si prefieres arrancar manualmente:

```bash
cd services\monitoring-service
..\..\venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8900 --reload
```

---

## Funcionalidades del Dashboard

Una vez dentro del dashboard podrás:

✅ **Monitorear servicios** en tiempo real
✅ **Ver métricas** de uptime y performance
✅ **Controlar Docker** (Start/Stop/Restart)
✅ **Controlar servicios** (TTS, Gateway, etc.)
✅ **Ver alertas** de fallos
✅ **Estadísticas de GPU** (utilización, VRAM, temperatura)

---

## Páginas Disponibles

| URL | Descripción |
|-----|-------------|
| `/monitoring` | Dashboard de monitoreo avanzado (RECOMENDADO) |
| `/` | Dashboard clásico |
| `/tts` | Testing de síntesis TTS |

---

**¿Necesitas ayuda?** Revisa el [README completo](README.md) o la [documentación técnica](../../ia_docs/monitoring/).
