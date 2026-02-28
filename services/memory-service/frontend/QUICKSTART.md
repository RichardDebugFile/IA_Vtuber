# 🚀 Quick Start - Casiopy Training Dashboard

Guía rápida para poner en marcha el dashboard de entrenamiento.

---

## ⚡ Instalación Rápida (2 minutos)

### 1. Instalar Dependencias

```bash
cd "F:\Documentos F\GitHub\IA_Vtuber\services\memory-service\frontend"
pip install -r requirements.txt
```

### 2. (Opcional) GPU Monitoring

Si tienes NVIDIA GPU:

```bash
pip install nvidia-ml-py3
```

### 3. Iniciar Dashboard

**Windows**:
```bash
start_dashboard.bat
```

**Linux/Mac**:
```bash
chmod +x start_dashboard.sh
./start_dashboard.sh
```

O directamente:
```bash
python app.py
```

### 4. Abrir en Navegador

```
http://localhost:5000
```

---

## 🎯 Primer Uso

### Paso 1: Validar Dataset
1. Click en **"🔍 Validar Dataset"**
2. Espera mensaje de confirmación
3. Verifica estadísticas (658 ejemplos, ~1.7MB)

### Paso 2: Configurar Entrenamiento

**Configuración Recomendada para RTX 5060 Ti (16GB)**:
- **Epochs**: 3
- **Batch Size**: 4
- **Learning Rate**: 2e-4

**Configuración Conservadora (GPU menor)**:
- **Epochs**: 3
- **Batch Size**: 2
- **Learning Rate**: 2e-4

### Paso 3: Iniciar
1. Click en **"▶️ Iniciar Entrenamiento"**
2. Monitorea métricas en tiempo real
3. Espera a que complete (status: COMPLETED)

### Paso 4: Revisar Resultados
- Check logs finales
- Verifica que Loss bajó
- Modelo guardado en `models/lora/`

---

## 📊 Qué Observar

### Métricas Normales
- **GPU Usage**: 70-95% (si está bajo, aumenta batch_size)
- **VRAM**: 8-14GB usado en RTX 5060 Ti
- **Loss**: Debe bajar progresivamente (2.0 → 0.5 aprox)
- **Temperature**: <85°C es seguro

### Señales de Alerta
- 🔴 **GPU Usage <30%**: Batch size muy pequeño
- 🔴 **VRAM >95%**: Batch size muy grande, reducir
- 🔴 **Loss aumenta**: Learning rate muy alto o datos malos
- 🔴 **Temperature >90°C**: Mejorar ventilación

---

## 🐛 Problemas Comunes

### Dashboard no inicia
```bash
# Verificar que Flask esté instalado
pip install Flask flask-socketio

# Verificar puerto 5000 libre
netstat -ano | findstr :5000

# Matar proceso si está ocupado (Windows)
taskkill /PID <PID> /F
```

### No se ven métricas de GPU
```bash
# Instalar nvidia-ml-py3
pip install nvidia-ml-py3

# Verificar drivers NVIDIA
nvidia-smi
```

### Entrenamiento no inicia
```bash
# Verificar que exista el script de entrenamiento
cd ../scripts
ls train_personality_lora.py

# Verificar que el dataset exista
cd ../exports/personality/v1_production
ls casiopy_personality_v1.0.0.jsonl
```

### Error de memoria (CUDA OOM)
- Reducir **batch_size** a 2 o 1
- Cerrar otras aplicaciones
- Verificar VRAM disponible con `nvidia-smi`

---

## 📝 Logs

### Ver logs en tiempo real
- Visibles en el dashboard
- Auto-scroll al último mensaje

### Descargar logs
- Guardados en `services/memory-service/logs/`
- Formato: `training_YYYYMMDD_HHMMSS.log`
- Acceder desde dashboard: `/api/logs/list`

---

## ⚙️ Configuraciones Avanzadas

### Para debugging
```python
# En app.py, línea final:
socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

### Para producción
```python
# Cambiar SECRET_KEY en app.py
app.config['SECRET_KEY'] = 'tu-secret-key-unica-aqui'

# Ejecutar con Gunicorn
pip install gunicorn
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 app:app
```

### Cambiar puerto
```python
# En app.py, última línea:
socketio.run(app, host='0.0.0.0', port=8080)  # Cambiar 5000 a tu puerto
```

---

## 🎓 Tips de Entrenamiento

### Cuándo detener manualmente
- Loss deja de bajar (~10 epochs sin mejora)
- Overfitting (loss baja mucho pero modelo responde raro)
- Temperatura GPU >90°C sostenida

### Cuándo re-entrenar
- Agregar nuevo conocimiento al dataset
- Corregir personalidad
- Mejorar respuestas específicas

### Backup antes de entrenar
```bash
# Hacer backup del modelo anterior
cp -r models/lora models/lora_backup_$(date +%Y%m%d)
```

---

## 📚 Recursos Adicionales

- **README completo**: `frontend/README.md`
- **Dataset v1.0.0**: `exports/personality/v1_production/README.md`
- **Historia de Casiopy**: `ia_docs/tareas/datasetInicial.txt`

---

## 🆘 Necesitas Ayuda?

1. **Check logs** del dashboard
2. **Revisar console** del navegador (F12)
3. **Verificar output** del servidor Flask
4. **Buscar error** en Google/StackOverflow

---

## ✅ Checklist Pre-Entrenamiento

- [ ] Dashboard instalado y funcionando
- [ ] Dataset validado (658 ejemplos)
- [ ] GPU detectada correctamente
- [ ] Configuración ajustada a tu hardware
- [ ] Espacio en disco suficiente (>2GB)
- [ ] No hay otras apps usando GPU
- [ ] Ventilación adecuada

---

## 🎉 Próximos Pasos Después del Entrenamiento

1. **Probar el modelo**:
   ```bash
   python test_trained_model.py
   ```

2. **Integrar con sistema**:
   - Cargar LoRA en servidor de conversación
   - Combinar con Core Memory (Capa 0)
   - Probar respuestas en vivo

3. **Iterar**:
   - Añadir más ejemplos al dataset
   - Ajustar hiperparámetros
   - Re-entrenar con mejoras

---

**¡Listo para entrenar! 🚀**

Si todo está configurado, haz click en "▶️ Iniciar Entrenamiento" y observa a Casiopy aprender su personalidad.
