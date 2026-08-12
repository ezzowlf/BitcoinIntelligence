from __future__ import annotations

from pathlib import Path


class ProcessLock:
    """Single-process lock released automatically by the OS on crash."""

    def __init__(self, path: Path):
        self.path = Path(path); self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if self.handle.tell() == 0: self.handle.write(b"0"); self.handle.flush()
        self.handle.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            self.handle.close(); self.handle = None; return False

    def release(self):
        if self.handle is None: return
        self.handle.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close(); self.handle = None

    def __enter__(self):
        if not self.acquire(): raise RuntimeError("ALREADY_RUNNING")
        return self

    def __exit__(self, *_): self.release()
