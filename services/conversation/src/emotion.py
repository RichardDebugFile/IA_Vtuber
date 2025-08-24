# services/conversation/src/emotion.py
import re
import unicodedata

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    # quita tildes/diacríticos pero mantiene emojis y signos
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

# Patrones por emoción (strings sin tildes). Se evaluarán en este orden.
# Ajusta/añade términos a gusto según tu dominio.
_PATTERNS = [
    # --- fuerte/inequivoco primero ---
    ("sleeping",  r"\b(zzz+|me voy a dormir|tengo sueno|somnolient[oa]|dormir[ée]?\b|me duermo)\b|😴"),
    ("love",      r"\b(te amo|te quiero|me encantas|me fascinas|me gustas mucho|amor eterno|mi amor)\b|❤️|💖|🥰|💘"),
    ("excited",   r"\b(emocionad[oa]s?|no puedo esperar|vamos+!|vamo+s!|que ganas|que emocion|woo+|vamo+)\b|🤩"),
    ("surprised", r"\b(guau+|wow+|no me lo creo|increible|anda|oh dios|madre mia|wtf|omg)\b|😲|😮"),
    ("fear",      r"\b(miedo|temor|asustad[oa]s?|p[áa]nico|pavor|terror|auxilio|socorro|ayuda|tengo miedo)\b|😱"),
    ("angry",     r"\b(odio|rabia|furios[oa]s?|coler[ai]|encabronad[oa]|maldit[oa]s?)\b|😡|>:\("),
    ("upset",     r"\b(molest[oa]s?|fastidiad[oa]s?|me molesta|ugh|que coraje|me cae mal)\b"),
    ("sad",       r"\b(triste(s)?|deprimid[oa]s?|pena|llorar[ée]?|llorando|melancol[ii]a|me siento mal)\b|😢|😭"),
    ("bored",     r"\b(aburrid[oa]s?|que aburrimiento|meh|bostezo|nada que hacer|que pereza|pereza)\b|🥱"),
    ("confused",  r"\b(confundid[oa]s?|no entiendo|no comprendo|como asi|que\?|que dices|no se|wtf)\b|🤔"),
    ("thinking",  r"\b(h+mm+|m+mm+|estoy pensando|pensar|pienso|consider[ao]|tal vez|quiza?s?)\b|🤔"),
    ("asco",      r"\b(asco|que asco|repugna|repuls[ii][óo]n|me da cosa|que desagradable|guacala)\b|🤢|🤮"),
    ("happy",     r"\b(gracias|genial|excelente|bien|feliz|content[oa]s?|me gusta|que bueno|que bien|j(e|a){2,}|jaja+|jeje+|xd)\b|😀|😄|🙂"),
]

# Precompila regex (case-insensitive). El texto se normaliza sin tildes.
_COMPILED = [(label, re.compile(pat, re.IGNORECASE)) for (label, pat) in _PATTERNS]

def classify(text: str) -> str:
    t = _strip_accents((text or "").lower())
    for label, regex in _COMPILED:
        if regex.search(t):
            return label
    return "neutral"
