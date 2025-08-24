from pydantic import BaseModel
from typing import Dict, Optional
import yaml, os

class Marg(BaseModel):
    x: int = 16
    y: int = 16

class Offset(BaseModel):
    x: int = 0
    y: int = 0

class SizeCfg(BaseModel):
    width: int
    height: int
    mode: str = "fit"          # fit | fill | stretch

class Bubble(BaseModel):
    # ---- NUEVOS CAMPOS con defaults ----
    shape: str = "rect"        # rect | (futuro: bubble)
    position: str = "right"    # right | left | above | below | window-top-right
    text_color: str = "#1e1e1e"

    # ---- Campos existentes (compatibles) ----
    enabled: bool = True
    theme: str = "auto"
    max_width: int = 360
    margin: Marg = Marg()
    tail: str = "left"
    offset: Offset = Offset()
    font: str = "fonts/Inter-Regular.ttf"
    font_size: int = 16
    color: str = "#CDB4FF"
    opacity: float = 0.92
    skin: str = ""

class AvatarCfg(BaseModel):
    name: str
    scale: float = 1.0
    anchor: str = "bottom-right"
    offset: Offset = Offset()
    size: Optional[SizeCfg] = None
    emotions: Dict[str, str]
    bubble: Bubble = Bubble()

def load_avatar_cfg(base_path: str) -> AvatarCfg:
    with open(os.path.join(base_path, "avatar.yaml"), "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AvatarCfg(**raw)
