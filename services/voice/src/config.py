from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Voice service
    voice_host: str = Field(default="127.0.0.1", alias="VOICE_HOST")
    voice_port: int = Field(default=8810, alias="VOICE_PORT")

    # Fish
    fish_enable: bool = Field(default=True, alias="FISH_ENABLE")
    fish_base: str = Field(default="http://127.0.0.1:9080", alias="FISH_BASE")
    fish_tts_path: str | None = Field(default="/v1/tts", alias="FISH_TTS_PATH")  # <- default útil
    fish_lang: str = Field(default="es", alias="FISH_LANG")
    fish_sr: int = Field(default=24000, alias="FISH_SR")
    fish_timeout: float = Field(default=120.0, alias="FISH_TIMEOUT")             # <- float

    # RVC (w-okada)
    rvc_enable: bool = Field(default=True, alias="RVC_ENABLE")
    rvc_mode: str = Field(default="webapi", alias="RVC_MODE")
    rvc_key: int = Field(default=0, alias="RVC_KEY")
    rvc_f0_method: str = Field(default="rmvpe", alias="RVC_F0_METHOD")
    rvc_index_rate: float = Field(default=0.66, alias="RVC_INDEX_RATE")
    rvc_volume: float = Field(default=1.0, alias="RVC_VOLUME")
    wokada_url: str = Field(default="http://127.0.0.1:18888", alias="WOKADA_URL")

    # Output/cache
    save_wav_dir: str = Field(default="out", alias="SAVE_WAV_DIR")
    cache_max_items: int = Field(default=50, alias="CACHE_MAX_ITEMS")
    cache_max_mb: int = Field(default=300, alias="CACHE_MAX_MB")
    publish_audio_events: bool = Field(default=False, alias="PUBLISH_AUDIO_EVENTS")


    # rvc añadimos nombres de dispositivos si quieres usarlos en pipeline
    # (o puedes leerlos directo en rvc_client.py como arriba):
    # rvc_play_to: str = Field(default="CABLE Input (VB-Audio Virtual Cable)", alias="RVC_PLAY_TO")
    # rvc_tap_from: str = Field(default="CABLE B Input (VB-Audio Virtual Cable B)", alias="RVC_TAP_FROM")
    # rvc_sr: int = Field(default=48000, alias="RVC_SR")
    # rvc_pad_ms: int = Field(default=180, alias="RVC_PAD_MS")


SETTINGS = Settings()
