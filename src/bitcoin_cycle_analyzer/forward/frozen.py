from __future__ import annotations
import hashlib,json
from pathlib import Path

class FrozenChampion:
    def __init__(self,path):self.path=Path(path);self.payload=json.loads(self.path.read_text(encoding="utf-8"));self._fingerprint=self.fingerprint()
    def fingerprint(self):return hashlib.sha256(json.dumps(self.payload,sort_keys=True).encode()).hexdigest()
    def assert_immutable(self):
        if self.fingerprint()!=self._fingerprint:raise RuntimeError("frozen champion mutated")
        return True
