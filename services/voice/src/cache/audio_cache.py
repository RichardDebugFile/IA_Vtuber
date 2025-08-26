import os, time, json
from collections import OrderedDict
from dataclasses import dataclass

@dataclass
class CacheEntry:
    path: str
    bytes: int
    atime: float

class AudioCache:
    def __init__(self, base_dir: str, max_items: int = 50, max_mb: int = 200):
        self.base = base_dir
        os.makedirs(self.base, exist_ok=True)
        self.max_items = max_items
        self.max_bytes = max_mb * 1024 * 1024
        self._by_key: "OrderedDict[str, CacheEntry]" = OrderedDict()

    def _touch(self, key: str):
        if key in self._by_key:
            ce = self._by_key.pop(key)
            ce.atime = time.time()
            self._by_key[key] = ce

    def get(self, key: str) -> str | None:
        ce = self._by_key.get(key)
        if not ce:
            return None
        if not os.path.exists(ce.path):
            self._by_key.pop(key, None)
            return None
        self._touch(key)
        return ce.path

    def put(self, key: str, path: str):
        size = os.path.getsize(path) if os.path.exists(path) else 0
        ce = CacheEntry(path=path, bytes=size, atime=time.time())
        if key in self._by_key:
            self._by_key.pop(key)
        self._by_key[key] = ce
        self._evict()

    def _evict(self):
        # por número
        while len(self._by_key) > self.max_items:
            _, ce = self._by_key.popitem(last=False)  # LRU
            try: os.remove(ce.path)
            except Exception: pass
        # por tamaño total
        total = sum(c.bytes for c in self._by_key.values())
        while total > self.max_bytes and self._by_key:
            _, ce = self._by_key.popitem(last=False)
            try: os.remove(ce.path)
            except Exception: pass
            total -= ce.bytes
