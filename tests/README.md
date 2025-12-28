# Tests - IA_Vtuber

Este directorio contiene los tests de integración y end-to-end para el proyecto IA_Vtuber.

## Estructura

```
tests/
├── __init__.py
├── conftest.py           # Fixtures compartidos para todos los tests
├── test_integration.py   # Tests de integración entre servicios
└── README.md            # Este archivo
```

## Tests Disponibles

### Tests de Integración

Los tests de integración verifican que múltiples servicios funcionen correctamente juntos:

- **Gateway Pub/Sub**: Verifica publicación y suscripción de eventos
- **Conversation Flow**: Prueba el flujo completo de conversación con LLM
- **TTS Flow**: Prueba la síntesis de voz con diferentes emociones
- **Service Interaction**: Verifica la comunicación entre servicios

### Tests End-to-End

Los tests E2E prueban el flujo completo de la aplicación:

- **Complete Conversation Flow**: Usuario → LLM → Emoción → TTS → Audio
- **Assistant Streaming**: Verifica el streaming SSE de respuestas
- **Error Handling**: Prueba el manejo de errores a lo largo del pipeline

## Ejecutar Tests

### Tests de Integración

```bash
# Ejecutar todos los tests de integración
pytest -m integration

# Ejecutar tests específicos
pytest tests/test_integration.py::TestGatewayPubSub
pytest tests/test_integration.py::TestConversationFlow
```

### Tests End-to-End

**Nota**: Los tests E2E requieren que todos los servicios estén corriendo.

```bash
# Iniciar servicios
make all-up

# Ejecutar tests E2E
pytest -m e2e

# Detener servicios
make all-down
```

### Ejecutar con Coverage

```bash
pytest tests/ --cov --cov-report=html
```

## Requisitos

### Para Tests de Integración

- Gateway service corriendo (puerto 8765)
- Conversation service corriendo (puerto 8801)
- TTS service corriendo (puerto 8802)
- Assistant service corriendo (puerto 8810)

### Para Tests End-to-End

- Todos los servicios de integración
- Ollama LLM server (puerto 11434)
- Fish Audio TTS server (puerto 8080)

## Fixtures Compartidos

Los fixtures definidos en `conftest.py` están disponibles para todos los tests:

- `gateway_url`: URL del servicio Gateway
- `conversation_url`: URL del servicio Conversation
- `tts_url`: URL del servicio TTS
- `assistant_url`: URL del servicio Assistant
- `http_client`: Cliente HTTP asíncrono
- `check_service_health`: Función para verificar salud de servicios
- `sample_emotions`: Lista de emociones válidas
- `sample_text_spanish`: Textos de ejemplo en español

## Marcadores de Tests

Los tests usan los siguientes marcadores:

- `@pytest.mark.integration`: Tests de integración
- `@pytest.mark.e2e`: Tests end-to-end
- `@pytest.mark.requires_ollama`: Requiere Ollama corriendo
- `@pytest.mark.requires_fish`: Requiere Fish Audio corriendo
- `@pytest.mark.slow`: Tests lentos (>5 segundos)

## Saltar Tests si Servicios no Disponibles

Los tests automáticamente saltarán si los servicios requeridos no están disponibles:

```python
@pytest.mark.requires_ollama
async def test_conversation(conversation_url):
    # Se salta automáticamente si Ollama no está corriendo
    pass
```

## Debugging

Para debugging detallado:

```bash
# Verbose output
pytest tests/ -vv

# Mostrar print statements
pytest tests/ -s

# Detener en primer fallo
pytest tests/ -x

# Mostrar variables locales en fallos
pytest tests/ -l
```

## Ver Documentación Completa

Para más información sobre testing, ver [TESTING.md](../TESTING.md) en la raíz del proyecto.
