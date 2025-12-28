# apps/desktop-pet-qt/src/ipc/ws_client.py
import threading, asyncio, json, websockets

class WSClient:
    def __init__(self, url, on_emotion, on_utterance):
        self.url=url
        self.on_emotion=on_emotion    # pueden ser .emit de Qt
        self.on_utterance=on_utterance
    def start(self):
        threading.Thread(target=lambda: asyncio.run(self._loop()), daemon=True).start()
    async def _loop(self):
        while True:
            try:
                async with websockets.connect(self.url) as ws:
                    await ws.send(json.dumps({"type":"subscribe","topics":["emotion","utterance"]}))
                    async for msg in ws:
                        evt=json.loads(msg)
                        t=evt.get("type")
                        if t=="emotion":   self.on_emotion(evt["data"])
                        elif t=="utterance": self.on_utterance(evt["data"])
            except Exception:
                await asyncio.sleep(1.0)
