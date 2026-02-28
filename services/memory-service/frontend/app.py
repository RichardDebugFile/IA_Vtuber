"""
Training Dashboard - Casiopy Personality LoRA
Frontend web para monitorear y controlar el entrenamiento
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from pathlib import Path
import json
import subprocess
import threading
import time
import os
import sys
import psutil
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'casiopy-training-dashboard-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Estado global del entrenamiento
training_state = {
    'status': 'idle',  # idle, validating, training, completed, error
    'progress': 0,
    'current_epoch': 0,
    'total_epochs': 0,
    'current_step': 0,
    'total_steps': 0,
    'loss': 0.0,
    'learning_rate': 0.0,
    'start_time': None,
    'elapsed_time': 0,
    'estimated_time_remaining': 0,
    'logs': [],
    'metrics': {
        'gpu_usage': 0,
        'gpu_memory': 0,
        'cpu_usage': 0,
        'ram_usage': 0,
        'temperature': 0
    },
    'dataset_info': {
        'total_examples': 0,
        'file_size': 0,
        'avg_length': 0
    },
    'process': None
}


def get_serializable_state():
    """Retornar estado sin objetos no-serializables (para enviar al frontend)"""
    state_copy = training_state.copy()
    state_copy.pop('process', None)  # Remover objeto Popen
    return state_copy


# Rutas de archivos
BASE_DIR = Path(__file__).parent.parent
DATASET_PATH = BASE_DIR / "exports" / "personality" / "v1_production" / "casiopy_personality_v1.0.0.jsonl"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def get_system_metrics():
    """Obtener métricas del sistema en tiempo real"""
    try:
        # CPU y RAM
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_percent = ram.percent

        metrics = {
            'cpu_usage': cpu_percent,
            'ram_usage': ram_percent,
            'gpu_usage': 0,
            'gpu_memory': 0,
            'temperature': 0,
            'timestamp': datetime.now().isoformat()
        }

        # Intentar obtener métricas de GPU (NVIDIA)
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)

            # GPU Usage
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            metrics['gpu_usage'] = utilization.gpu

            # GPU Memory
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            metrics['gpu_memory'] = (mem_info.used / mem_info.total) * 100

            # Temperature
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            metrics['temperature'] = temp

            pynvml.nvmlShutdown()
        except:
            pass  # GPU metrics no disponibles

        return metrics
    except Exception as e:
        print(f"Error obteniendo métricas: {e}")
        return training_state['metrics']


def get_python_command():
    """Obtener el comando de Python correcto según el entorno"""
    # Si estamos en Docker, siempre usar sys.executable
    if os.path.exists('/.dockerenv'):
        return sys.executable

    # Si estamos en Windows, intentar usar el venv de entrenamiento
    venv_python = BASE_DIR / '.venv_training' / 'Scripts' / 'python.exe'
    if venv_python.exists() and os.name == 'nt':
        return str(venv_python)

    # Por defecto, usar el Python actual
    return sys.executable


def validate_dataset():
    """Validar dataset antes de entrenar"""
    # El estado ya fue cambiado a 'validating' por el handler
    try:
        # Obtener comando de Python según el entorno
        python_cmd = get_python_command()

        # Ejecutar script de validación
        result = subprocess.run(
            [python_cmd, str(SCRIPTS_DIR / 'validate_dataset.py')],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS_DIR)
        )

        if result.returncode == 0:
            # Parse output para obtener estadísticas
            output_lines = result.stdout.split('\n')

            for line in output_lines:
                if 'Dataset cargado:' in line:
                    examples = int(line.split(':')[1].split()[0])
                    training_state['dataset_info']['total_examples'] = examples
                elif 'Promedio:' in line:
                    avg = float(line.split(':')[1].split()[0])
                    training_state['dataset_info']['avg_length'] = avg
                elif 'Tamano del archivo:' in line:
                    size = float(line.split(':')[1].split()[0])
                    training_state['dataset_info']['file_size'] = size

            training_state['status'] = 'idle'  # IMPORTANTE: Volver a idle después de validar
            training_state['logs'].append({
                'timestamp': datetime.now().isoformat(),
                'level': 'success',
                'message': f'[OK] Dataset validado: {training_state["dataset_info"]["total_examples"]} ejemplos'
            })
            socketio.emit('training_update', get_serializable_state())
            return True
        else:
            training_state['status'] = 'error'
            training_state['logs'].append({
                'timestamp': datetime.now().isoformat(),
                'level': 'error',
                'message': f'[ERROR] Error en validacion: {result.stderr}'
            })
            socketio.emit('training_update', get_serializable_state())
            return False

    except Exception as e:
        training_state['status'] = 'error'
        training_state['logs'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'error',
            'message': f'[ERROR] Excepcion durante validacion: {str(e)}'
        })
        socketio.emit('training_update', get_serializable_state())
        return False


def monitor_training_process(process):
    """Monitorear proceso de entrenamiento en tiempo real"""
    training_state['process'] = process
    training_state['start_time'] = datetime.now().isoformat()

    log_file = LOGS_DIR / f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    with open(log_file, 'w', encoding='utf-8') as f:
        for line in iter(process.stdout.readline, ''):
            if not line:
                break

            # Escribir a archivo de log
            f.write(line)
            f.flush()

            # Parse output para extraer métricas
            line = line.strip()

            # Añadir a logs
            training_state['logs'].append({
                'timestamp': datetime.now().isoformat(),
                'level': 'info',
                'message': line
            })

            # Mantener solo últimos 100 logs en memoria
            if len(training_state['logs']) > 100:
                training_state['logs'].pop(0)

            # Parse métricas específicas
            if 'Epoch' in line and '/' in line:
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'Epoch':
                            epoch_info = parts[i+1].split('/')
                            training_state['current_epoch'] = int(epoch_info[0])
                            training_state['total_epochs'] = int(epoch_info[1])
                except:
                    pass

            if 'Step' in line or 'step' in line.lower():
                try:
                    # Intentar extraer step actual
                    import re
                    match = re.search(r'(\d+)/(\d+)', line)
                    if match:
                        training_state['current_step'] = int(match.group(1))
                        training_state['total_steps'] = int(match.group(2))
                except:
                    pass

            if 'loss' in line.lower():
                try:
                    import re
                    match = re.search(r'loss[:\s=]+([0-9.]+)', line.lower())
                    if match:
                        training_state['loss'] = float(match.group(1))
                except:
                    pass

            if 'lr' in line.lower() or 'learning_rate' in line.lower():
                try:
                    import re
                    match = re.search(r'lr[:\s=]+([0-9.e-]+)', line.lower())
                    if match:
                        training_state['learning_rate'] = float(match.group(1))
                except:
                    pass

            # Calcular progreso
            if training_state['total_steps'] > 0:
                training_state['progress'] = int(
                    (training_state['current_step'] / training_state['total_steps']) * 100
                )

            # Emitir actualización
            socketio.emit('training_update', get_serializable_state())

    # Proceso terminado
    process.wait()

    if process.returncode == 0:
        training_state['status'] = 'completed'
        training_state['progress'] = 100
        training_state['logs'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'success',
            'message': '[OK] Entrenamiento completado exitosamente'
        })
    else:
        training_state['status'] = 'error'
        training_state['logs'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'error',
            'message': f'[ERROR] Entrenamiento termino con error (codigo {process.returncode})'
        })

    training_state['process'] = None
    socketio.emit('training_update', get_serializable_state())


# ============================================================
# RUTAS HTTP
# ============================================================

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Obtener estado actual del entrenamiento"""
    return jsonify(training_state)


@app.route('/api/metrics')
def get_metrics():
    """Obtener métricas del sistema en tiempo real"""
    metrics = get_system_metrics()
    training_state['metrics'] = metrics
    return jsonify(metrics)


@app.route('/api/dataset/info')
def get_dataset_info():
    """Obtener información del dataset"""
    try:
        if DATASET_PATH.exists():
            stat = DATASET_PATH.stat()

            # Contar líneas (ejemplos)
            with open(DATASET_PATH, 'r', encoding='utf-8') as f:
                examples = sum(1 for _ in f)

            return jsonify({
                'path': str(DATASET_PATH),
                'exists': True,
                'size_mb': stat.st_size / (1024 * 1024),
                'examples': examples,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        else:
            return jsonify({
                'exists': False,
                'error': 'Dataset no encontrado'
            }), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs')
def get_logs():
    """Obtener logs del entrenamiento"""
    limit = request.args.get('limit', 100, type=int)
    return jsonify(training_state['logs'][-limit:])


@app.route('/api/logs/download/<filename>')
def download_log(filename):
    """Descargar archivo de log"""
    return send_from_directory(LOGS_DIR, filename, as_attachment=True)


@app.route('/api/logs/list')
def list_logs():
    """Listar todos los archivos de log"""
    try:
        logs = []
        for log_file in LOGS_DIR.glob('training_*.log'):
            stat = log_file.stat()
            logs.append({
                'filename': log_file.name,
                'size_kb': stat.st_size / 1024,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        return jsonify(sorted(logs, key=lambda x: x['created'], reverse=True))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# WEBSOCKET EVENTS
# ============================================================

@socketio.on('connect')
def handle_connect():
    """Cliente conectado"""
    emit('training_update', get_serializable_state())
    print(f"Cliente conectado: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado"""
    print(f"Cliente desconectado: {request.sid}")


@socketio.on('start_validation')
def handle_start_validation():
    """Iniciar validación del dataset"""
    if training_state['status'] not in ['idle', 'completed', 'error']:
        emit('error', {'message': 'Ya hay un proceso en ejecución'})
        return

    # Cambiar estado INMEDIATAMENTE para prevenir race conditions
    training_state['status'] = 'validating'
    training_state['logs'].append({
        'timestamp': datetime.now().isoformat(),
        'level': 'info',
        'message': 'Iniciando validación del dataset...'
    })
    emit('training_update', get_serializable_state())

    # Ejecutar validación en thread separado
    thread = threading.Thread(target=validate_dataset)
    thread.daemon = True
    thread.start()


@socketio.on('start_training')
def handle_start_training(data):
    """Iniciar entrenamiento"""
    if training_state['status'] not in ['idle', 'completed', 'error']:
        emit('error', {'message': 'Ya hay un proceso en ejecución'})
        return

    # Verificar que el dataset tenga información (fue validado)
    if training_state['dataset_info']['total_examples'] == 0:
        emit('error', {'message': 'Por favor, valida el dataset primero'})
        return

    # Reset estado
    training_state['status'] = 'training'
    training_state['progress'] = 0
    training_state['current_epoch'] = 0
    training_state['current_step'] = 0
    training_state['logs'] = []

    # Parámetros de entrenamiento
    epochs = data.get('epochs', 3)
    batch_size = data.get('batch_size', 2)  # Default 2 para RTX 5060 Ti (16GB)
    learning_rate = data.get('learning_rate', 2e-4)

    training_state['total_epochs'] = epochs

    training_state['logs'].append({
        'timestamp': datetime.now().isoformat(),
        'level': 'info',
        'message': f'Iniciando entrenamiento: {epochs} epochs, batch_size={batch_size}, lr={learning_rate}'
    })

    # Comando de entrenamiento
    # Obtener comando de Python según el entorno
    python_cmd = get_python_command()

    cmd = [
        python_cmd,
        str(SCRIPTS_DIR / 'train_personality_lora.py'),
        '--dataset', str(DATASET_PATH),
        '--epochs', str(epochs),
        '--batch_size', str(batch_size),
        '--learning_rate', str(learning_rate)
    ]

    # Ejecutar en subprocess
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_DIR)
        )

        # Monitorear en thread separado
        thread = threading.Thread(target=monitor_training_process, args=(process,))
        thread.daemon = True
        thread.start()

        # Emitir actualización inicial
        emit('training_update', get_serializable_state())

    except Exception as e:
        training_state['status'] = 'error'
        training_state['logs'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'error',
            'message': f'Error iniciando entrenamiento: {str(e)}'
        })
        emit('training_update', get_serializable_state())


@socketio.on('stop_training')
def handle_stop_training():
    """Detener entrenamiento"""
    if training_state['process']:
        training_state['process'].terminate()
        training_state['status'] = 'idle'
        training_state['logs'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'warning',
            'message': '[WARNING] Entrenamiento detenido por el usuario'
        })
        emit('training_update', get_serializable_state())


@socketio.on('request_metrics')
def handle_request_metrics():
    """Cliente solicita métricas del sistema"""
    metrics = get_system_metrics()
    training_state['metrics'] = metrics
    emit('metrics_update', metrics)


# ============================================================
# BACKGROUND TASKS
# ============================================================

def background_metrics_updater():
    """Actualizar métricas del sistema cada segundo"""
    while True:
        time.sleep(1)
        metrics = get_system_metrics()
        training_state['metrics'] = metrics
        socketio.emit('metrics_update', metrics)


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    # Iniciar actualizador de métricas en background
    metrics_thread = threading.Thread(target=background_metrics_updater)
    metrics_thread.daemon = True
    metrics_thread.start()

    print("\n" + "="*60)
    print("CASIOPY TRAINING DASHBOARD")
    print("="*60)
    print(f"Dataset: {DATASET_PATH}")
    print(f"Scripts: {SCRIPTS_DIR}")
    print(f"Logs: {LOGS_DIR}")
    print("="*60)
    print("Dashboard disponible en: http://localhost:5000")
    print("="*60 + "\n")

    # Iniciar servidor
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
