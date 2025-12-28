# Constantes de topics
TOPIC_UTTERANCE = "utterance"
TOPIC_EMOTION = "emotion"
TOPIC_AVATAR_ACTION = "avatar-action"

# Helpers (opcional)
def evt_utterance(text: str) -> dict:
    return {"type": TOPIC_UTTERANCE, "data": {"text": text}}

def evt_emotion(label: str) -> dict:
    return {"type": TOPIC_EMOTION, "data": {"label": label}}
