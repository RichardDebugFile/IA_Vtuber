from __future__ import annotations
import argparse
import base64
import io
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

import requests
import wave

# --- Audio backends ---
try:
    import simpleaudio as sa  # pip install simpleaudio
except Exception:
    sa = None

try:
    import winsound  # Windows only
except Exception:
    winsound = None


# --------------------------- Utilidades de métricas ---------------------------
def now() -> float:
    return time.monotonic()

def pct(vals: List[float], q: float) -> float:
    if not vals:
        return 0.0
    xs = sorted(vals)
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


# ------------------------------ Estructuras datos -----------------------------
@dataclass
class Timeline:
    start_delay_ms: int = 0
    gap_min_ms: int = 120
    sec_per_word: float = 1.2

@dataclass
class ChunkRow:
    index: int
    text: str
    words: int = 0
    offset_ms: int = 0          # planificado (desde t0_wall)
    tts_ms: int = 0             # lo que reporta el server (sintetizar)
    duration_ms: int = 0        # duración del WAV (server)
    fetch_ms: int = 0           # tiempo de descarga (url) o 0 si b64
    planned_start_ms: float = 0 # t0_wall + offset
    actual_start_ms: float = 0  # real (desde t0_wall)
    actual_end_ms: float = 0
    lateness_ms: float = 0      # actual_start - planned_start (si > 0: tarde)
    gap_prev_ms: float = 0      # start_i - end_(i-1)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("planned_start_ms", "actual_start_ms", "actual_end_ms", "lateness_ms", "gap_prev_ms"):
            d[k] = round(d[k], 2)
        return d


# ---------------------------------- Tester -----------------------------------
class ChunkStreamTester:
    """
    Cliente de prueba para /api/assistant/stream-chunks (SSE).
    - Reproduce cada chunk respetando offset_ms.
    - Mide métricas y las resume al final.
    - Soporta out=url (descarga) y out=b64 (decodifica).
    """

    _ev_pat = re.compile(r"^event:\s*(.+?)\s*$")
    _da_pat = re.compile(r"^data:\s*(.+)\s*$")

    def __init__(self, assistant_base: str, out_mode: str = "url", keep_files: bool = False, verbose: bool = True, save_report: Optional[str] = None):
        self.assistant_base = assistant_base.rstrip("/")
        self.endpoint = f"{self.assistant_base}/api/assistant/stream-chunks"
        self.out_mode = out_mode.lower()
        self.keep_files = keep_files
        self.verbose = verbose
        self.save_report = save_report

        if self.out_mode not in ("url", "b64"):
            raise ValueError("out_mode debe ser 'url' o 'b64'")

        self.timeline = Timeline()
        self.t0_wall: Optional[float] = None
        self.rows: List[ChunkRow] = []

    def _log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _play_wav_bytes(self, audio_bytes: bytes) -> float:
        start = now()
        if sa is not None:
            try:
                with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    obj = sa.WaveObject(frames, wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
                play = obj.play()
                play.wait_done()
                return now() - start
            except Exception as e:
                self._log(f"[warn] simpleaudio falló: {e}")

        if winsound is not None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                winsound.PlaySound(tmp_path, winsound.SND_FILENAME | winsound.SND_SYNC)
                if not self.keep_files:
                    try: os.remove(tmp_path)
                    except Exception: pass
                return now() - start
            except Exception as e:
                self._log(f"[warn] winsound falló: {e}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        self._log(f"[info] WAV guardado en: {tmp_path} (reprodúcelo manualmente).")
        return now() - start

    def _fetch_wav_from_url(self, maybe_rel: str) -> bytes:
        url = maybe_rel if maybe_rel.lower().startswith("http") else urljoin(self.assistant_base + "/", maybe_rel.lstrip("/"))
        t0 = now()
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        ms = (now() - t0) * 1000.0
        self._last_fetch_ms = int(ms)
        return r.content

    @staticmethod
    def _wav_duration_s(b: bytes) -> float:
        try:
            with wave.open(io.BytesIO(b), "rb") as wf:
                return wf.getnframes() / max(1, wf.getframerate())
        except Exception:
            return 0.0

    def _iter_sse(self, resp):
        event = None
        for raw in resp.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            line = raw.strip("\r\n")
            if not line:
                continue
            m_ev = self._ev_pat.match(line)
            if m_ev:
                event = m_ev.group(1)
                continue
            m_da = self._da_pat.match(line)
            if m_da and event:
                try:
                    obj = json.loads(m_da.group(1))
                except Exception:
                    continue
                yield event, obj

    # ---------- ejecución principal ----------
    def run(self, text: str) -> None:
        self._log(f"[info] POST {self.endpoint}  out={self.out_mode}")
        payload = {"text": text, "out": self.out_mode}
        headers = {"Content-Type": "application/json"}

        with requests.post(self.endpoint, json=payload, headers=headers, stream=True) as resp:
            resp.raise_for_status()

            self.rows.clear()
            self.t0_wall = None
            self._last_fetch_ms = 0

            last_end_ms = 0.0

            for event, obj in self._iter_sse(resp):
                if event == "timeline":
                    self.timeline.start_delay_ms = int(obj.get("start_delay_ms", 0))
                    self.timeline.gap_min_ms = int(obj.get("gap_min_ms", 120))
                    self.timeline.sec_per_word = float(obj.get("sec_per_word", self.timeline.sec_per_word))
                    self._log(f"[timeline] start_delay={self.timeline.start_delay_ms}ms  gap_min={self.timeline.gap_min_ms}ms  sec_per_word≈{self.timeline.sec_per_word:.1f}")
                    self.t0_wall = now() + (self.timeline.start_delay_ms / 1000.0)

                elif event == "segment":
                    idx = int(obj.get("index", 0))
                    txt = obj.get("text", "")
                    off = int(obj.get("offset_ms", 0))
                    tts_ms = int(obj.get("tts_ms", 0))
                    dur_ms = int(obj.get("duration_ms", 0))
                    words = len(re.findall(r"\w+", txt, flags=re.UNICODE))

                    while len(self.rows) <= idx:
                        self.rows.append(ChunkRow(index=len(self.rows), text=""))
                    row = self.rows[idx]
                    row.index = idx
                    row.text = txt
                    row.words = words
                    row.offset_ms = off
                    row.tts_ms = tts_ms or row.tts_ms
                    row.duration_ms = dur_ms or row.duration_ms

                    self._log(f"[segment {idx+1}] offset={off}ms  tts_ms={row.tts_ms}  duration_ms={row.duration_ms} :: {txt}")

                elif event == "audio":
                    if self.t0_wall is None:
                        self.t0_wall = now()

                    idx = int(obj.get("index", 0))
                    off_ms = int(obj.get("offset_ms", 0))
                    while len(self.rows) <= idx:
                        self.rows.append(ChunkRow(index=len(self.rows), text=""))
                    row = self.rows[idx]
                    if off_ms:
                        row.offset_ms = off_ms

                    b = b""
                    self._last_fetch_ms = 0
                    if "audio_url" in obj:
                        b = self._fetch_wav_from_url(obj["audio_url"])
                        row.fetch_ms = self._last_fetch_ms
                    else:
                        b64 = obj.get("audio_b64", "")
                        t0f = now()
                        b = base64.b64decode(b64) if b64 else b""
                        row.fetch_ms = int((now() - t0f) * 1000.0)

                    dur_s = self._wav_duration_s(b)
                    dur_ms_calc = int(dur_s * 1000.0)
                    row.duration_ms = obj.get("duration_ms", row.duration_ms or dur_ms_calc)

                    planned_start_wall = (self.t0_wall + (row.offset_ms / 1000.0)) if self.t0_wall is not None else now()
                    sleep_s = max(0.0, planned_start_wall - now())
                    if sleep_s > 0:
                        time.sleep(sleep_s)

                    t_play_start = now()
                    real_play_s = self._play_wav_bytes(b)
                    t_play_end = now()

                    row.planned_start_ms = (planned_start_wall - self.t0_wall) * 1000.0 if self.t0_wall else 0.0
                    row.actual_start_ms = (t_play_start - self.t0_wall) * 1000.0 if self.t0_wall else 0.0
                    row.actual_end_ms = (t_play_end - self.t0_wall) * 1000.0 if self.t0_wall else 0.0
                    row.lateness_ms = row.actual_start_ms - row.planned_start_ms
                    row.gap_prev_ms = 0.0 if idx == 0 else max(0.0, row.actual_start_ms - last_end_ms)

                    last_end_ms = row.actual_end_ms

                    self._log(f"[audio {idx}] start={row.actual_start_ms:.0f}ms  late={row.lateness_ms:.0f}ms  gap_prev={row.gap_prev_ms:.0f}ms  dur≈{row.duration_ms}ms  fetch={row.fetch_ms}ms")

                elif event == "done":
                    total = int(obj.get("total", 0))
                    self._log(f"[done] total={total}")
                    break

        self._print_summary()
        if self.save_report:
            self._save_report(self.save_report)

    # -------------------------- resumen y guardado ----------------------------
    def _print_summary(self) -> None:
        if not self.rows:
            print("\n[summary] No hay chunks.")
            return

        lateness = [max(0.0, r.lateness_ms) for r in self.rows]
        gaps = [r.gap_prev_ms for r in self.rows[1:]]
        tts = [float(r.tts_ms) for r in self.rows if r.tts_ms > 0]
        dur = [float(r.duration_ms) for r in self.rows if r.duration_ms > 0]
        fetch = [float(r.fetch_ms) for r in self.rows]

        total_chunks = len(self.rows)
        wall_total_ms = self.rows[-1].actual_end_ms - self.rows[0].actual_start_ms if total_chunks > 0 else 0.0
        audio_total_ms = sum(dur) if dur else 0.0
        missed = sum(1 for x in lateness if x > 0.0)
        severe = sum(1 for x in lateness if x > 200.0)
        below_gap = sum(1 for g in gaps if g + 1e-6 < self.timeline.gap_min_ms)

        def avg(xs: List[float]) -> float:
            return (sum(xs) / len(xs)) if xs else 0.0

        print("\n======================= SUMMARY =======================")
        print(f"Chunks:     {total_chunks}")
        print(f"Wall time:  {wall_total_ms/1000.0:.2f}s   (audio sum: {audio_total_ms/1000.0:.2f}s)")
        print(f"Gap target: {self.timeline.gap_min_ms} ms    Start delay: {self.timeline.start_delay_ms} ms")
        print(f"sec/word≈   {self.timeline.sec_per_word:.3f}")
        print("------------------------------------------------------")
        print(f"Lateness ms  avg={avg(lateness):.1f}  p50={pct(lateness,0.5):.1f}  p90={pct(lateness,0.9):.1f}  p95={pct(lateness,0.95):.1f}  max={max(lateness) if lateness else 0:.1f}")
        print(f"Missed deadlines: {missed}/{total_chunks}   severe(>200ms): {severe}")
        print(f"Gaps ms     avg={avg(gaps):.1f}  min={min(gaps) if gaps else 0:.1f}  below_target={below_gap}")
        if tts:
            print(f"TTS ms      avg={avg(tts):.0f}  p50={pct(tts,0.5):.0f}  p90={pct(tts,0.9):.0f}  p95={pct(tts,0.95):.0f}  max={max(tts):.0f}")
        if dur:
            print(f"Dur ms      avg={avg(dur):.0f}  p50={pct(dur,0.5):.0f}  p90={pct(dur,0.9):.0f}  p95={pct(dur,0.95):.0f}  max={max(dur):.0f}")
        if fetch:
            print(f"Fetch ms    avg={avg(fetch):.0f}  p90={pct(fetch,0.9):.0f}  max={max(fetch):.0f}")
        print("======================================================\n")

        print("idx  words  off(ms)  plan(ms)  start(ms)  late(ms)  gap_prev  dur(ms)  tts(ms)  fetch(ms)  text")
        for r in self.rows:
            print(f"{r.index:>3}  {r.words:>5}  {r.offset_ms:>7}  {r.planned_start_ms:>8.0f}  {r.actual_start_ms:>9.0f}  "
                  f"{r.lateness_ms:>7.0f}  {r.gap_prev_ms:>7.0f}  {r.duration_ms:>7}  {r.tts_ms:>7}  {r.fetch_ms:>8}  {r.text[:60]}")

    def _save_report(self, path: str) -> None:
        data = {
            "timeline": {
                "start_delay_ms": self.timeline.start_delay_ms,
                "gap_min_ms": self.timeline.gap_min_ms,
                "sec_per_word": self.timeline.sec_per_word,
            },
            "chunks": [r.to_dict() for r in self.rows],
            "summary": {
                "total_chunks": len(self.rows),
                "wall_time_ms": (self.rows[-1].actual_end_ms - self.rows[0].actual_start_ms) if self.rows else 0.0,
            }
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[report] guardado → {path}")


# -------------------------------- Entrypoint ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Cliente de prueba para /api/assistant/stream-chunks con métricas")
    ap.add_argument("--assistant", default="http://127.0.0.1:8810", help="Base URL del assistant")
    ap.add_argument("--out", choices=["url", "b64"], default="url", help="Modo de audio: url o b64")
    ap.add_argument("--keep-files", action="store_true", help="Mantener WAVs temporales (winsound)")
    ap.add_argument("--quiet", action="store_true", help="Silenciar logs")
    ap.add_argument("--report", default="", help="Ruta JSON para guardar el reporte (opcional)")
    ap.add_argument("--text", required=True, help="Texto de entrada para probar")
    args = ap.parse_args()

    tester = ChunkStreamTester(
        assistant_base=args.assistant,
        out_mode=args.out,
        keep_files=args.keep_files,
        verbose=not args.quiet,
        save_report=(args.report or None),
    )
    tester.run(args.text)


if __name__ == "__main__":
    main()
