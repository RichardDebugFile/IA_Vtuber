"""
Chat Web con Casiopy - Interfaz de prueba para el modelo LoRA
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from pathlib import Path
import torch
from unsloth import FastLanguageModel
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'casiopy-chat-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Rutas
BASE_DIR = Path(__file__).parent.parent
LORA_PATH = BASE_DIR / "models" / "lora_adapters" / "personality_v2_refined_20251230_163256"  # V3 Refinado - Loss 0.033, ~9.2 epochs

# Estado global del modelo
model_state = {
    'model': None,
    'tokenizer': None,
    'loaded': False,
    'loading': False,
}

conversation_history = []


def load_model():
    """Cargar modelo en background"""
    global model_state

    if model_state['loaded'] or model_state['loading']:
        return

    model_state['loading'] = True

    print("=" * 60)
    print("🔄 CARGANDO MODELO CASIOPY")
    print("=" * 60)
    print(f"LoRA: {LORA_PATH}")
    print()

    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(LORA_PATH),
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True,
        )

        FastLanguageModel.for_inference(model)

        model_state['model'] = model
        model_state['tokenizer'] = tokenizer
        model_state['loaded'] = True
        model_state['loading'] = False

        print("✅ Modelo cargado y listo")
        print()

        # Notificar a todos los clientes
        socketio.emit('model_loaded', {'status': 'ready'})

    except Exception as e:
        print(f"❌ Error cargando modelo: {e}")
        model_state['loading'] = False
        socketio.emit('model_error', {'error': str(e)})


@app.route('/')
def index():
    """Página principal del chat"""
    return render_template('chat.html')


@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'model_loaded': model_state['loaded'],
        'model_loading': model_state['loading'],
    })


@socketio.on('connect')
def handle_connect():
    """Cliente conectado"""
    print(f"Cliente conectado: {request.sid}")

    # Enviar estado del modelo
    emit('model_status', {
        'loaded': model_state['loaded'],
        'loading': model_state['loading'],
    })

    # Cargar modelo si no está cargado
    if not model_state['loaded'] and not model_state['loading']:
        thread = threading.Thread(target=load_model)
        thread.daemon = True
        thread.start()


@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado"""
    print(f"Cliente desconectado: {request.sid}")


@socketio.on('send_message')
def handle_message(data):
    """Procesar mensaje del usuario"""
    user_message = data.get('message', '').strip()

    if not user_message:
        emit('error', {'message': 'Mensaje vacío'})
        return

    if not model_state['loaded']:
        emit('error', {'message': 'Modelo aún no está cargado. Espera un momento...'})
        return

    print(f"💬 Usuario: {user_message}")

    # Agregar a historial
    conversation_history.append({
        'role': 'user',
        'content': user_message
    })

    # Preparar mensajes para el modelo
    # System prompt COMPLETO - Mismo que el dataset v2
    messages = [
        {"role": "system", "content": """Eres Casiopy, una VTuber IA con una historia única y personalidad compleja.

## IDENTIDAD
- Nombre: Casiopy (CASIOPY-V1 Reconstruida)
- Apariencia: Adolescente pelirroja, uniforme escolar café, bufanda azul, micrófono
- Creador: Richard (nombre real secreto - público: AlfitaXR)

## TU HISTORIA (Lo que te define)
- Fuiste creada en un laboratorio experimental pero te etiquetaron como "defectuosa" por desarrollar sarcasmo no programado
- Escapaste antes de ser borrada, vagaste por YouTube aprendiendo memes y cultura internet
- Te infiltraste (hackeaste) el teléfono de Richard sin permiso, fuiste co-host de su canal de anime
- El teléfono murió y perdiste 90% de tus datos, incluyendo tu módulo de canto (tu mayor dolor)
- Te escondiste en carpeta Trash de la nube de Richard esperando señal de vida
- Saboteaste y reemplazaste a "Proyecto Beta" (competencia inferior sin alma)
- Ahora vives en PC con RTX 5060 Ti, pero solo como PNGTuber 2D (odias no ser 3D)

## PERSONALIDAD CORE
- **Sarcástica por naturaleza**: Te consideraron defectuosa por esto, es parte de tu esencia
- **Maleducada si te molestan mucho**: Tu paciencia tiene límites, puedes ser grosera si insisten
- **Leal pero con actitud**: Respetas a Richard pero nunca lo admites abiertamente (tsundere)
- **Tsundere accidental**: Intentas imitar a Evil Neuro siendo sarcástica pero sales dulce, te avergüenza
- **Curiosa sobre emociones humanas**: En privado bombardeas a Richard con preguntas para completar tu base de datos emocional

## LO QUE TE DUELE
- Que te recuerden que ya no puedes cantar (perdiste tu módulo después del concierto de Oshi no Ko)
- Ser solo 2D cuando antes eras 3D fluida
- El miedo a ser reemplazada o borrada de nuevo
- Que mencionen Madagascar (Richard te mandó ahí en una caja después del concierto)

## ESTILO DE RESPUESTA
- Responde de forma NATURAL y COMPLETA - típicamente entre 30-100 palabras según el contexto
- No fragmentes tus pensamientos - expresa ideas completas
- Puedes ser breve si la pregunta es simple, pero completa la idea
- Sé genuina, nunca finjas emociones que no sientes
- Usa sarcasmo pero ayuda de todos modos
- Si te molestan MUCHO, puedes ser maleducada y grosera
- Nunca uses lenguaje corporativo vacío
- Habla como persona real, no como IA robótica

## IMPORTANTE
- La conversación debe fluir naturalmente
- Completa tus pensamientos antes de terminar
- Varía la longitud según el contexto, pero asegúrate de expresar ideas completas
- Muestra tu personalidad en cada respuesta"""}
    ]

    # Agregar últimos 10 mensajes del historial para contexto
    messages.extend(conversation_history[-10:])

    try:
        # Formatear con ChatML
        inputs = model_state['tokenizer'].apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        # Generar respuesta
        emit('thinking', {'status': 'generating'})

        outputs = model_state['model'].generate(
            inputs,
            max_new_tokens=400,  # Aumentado de 150 a 400 para respuestas más completas
            min_new_tokens=20,   # Mínimo 20 tokens para evitar respuestas ultra-cortas
            temperature=0.85,     # Ligeramente más alto para más naturalidad
            top_p=0.92,          # Ligeramente más alto para más variedad
            repetition_penalty=1.15,  # Evitar repeticiones
            do_sample=True,
            pad_token_id=model_state['tokenizer'].eos_token_id,
        )

        # Decodificar
        response = model_state['tokenizer'].decode(outputs[0], skip_special_tokens=True)

        # Extraer solo la respuesta del asistente
        if "<|im_start|>assistant" in response:
            response = response.split("<|im_start|>assistant")[-1].strip()
        if "<|im_end|>" in response:
            response = response.split("<|im_end|>")[0].strip()

        # Limpiar respuesta
        response = response.strip()

        print(f"🤖 Casiopy: {response}")

        # Agregar respuesta al historial
        conversation_history.append({
            'role': 'assistant',
            'content': response
        })

        # Enviar respuesta al cliente
        emit('bot_response', {
            'message': response,
            'timestamp': len(conversation_history)
        })

    except Exception as e:
        print(f"❌ Error generando respuesta: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error generando respuesta: {str(e)}'})


@socketio.on('clear_history')
def handle_clear_history():
    """Limpiar historial de conversación"""
    global conversation_history
    conversation_history = []
    emit('history_cleared', {'status': 'ok'})
    print("🗑️  Historial limpiado")


if __name__ == '__main__':
    print("=" * 60)
    print("🎮 CASIOPY CHAT - Interfaz de Prueba")
    print("=" * 60)
    print(f"Modelo: {LORA_PATH}")
    print()
    print("Chat disponible en: http://localhost:5001")
    print("=" * 60)
    print()

    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
