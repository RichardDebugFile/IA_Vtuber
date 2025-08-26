from pydantic import BaseModel, Field
from typing import Optional

class RVCOpts(BaseModel):
    enabled: bool = True
    key: int = 0
    f0_method: str = "rmvpe"
    index_rate: float = 0.3
    volume: float = 1.0

class SpeakRequest(BaseModel):
    text: str = Field(min_length=1)
    emotion: Optional[str] = None
    style: Optional[str] = None
    speaker_id: Optional[str] = "aura"
    rvc: Optional[RVCOpts] = RVCOpts()
    sample_rate: Optional[int] = None  # si lo quieres distinto al default
