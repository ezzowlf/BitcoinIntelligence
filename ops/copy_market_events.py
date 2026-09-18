"""Phase 6: copy the FULL market_events.jsonl to the transfer, computing size,
line count, first/last timestamp and SHA-256 in ONE streaming pass (no sampling,
no rewrite, no extra scans). Read-only on the source.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:\TAKEOFF")
STAMP = sys.argv[1]
DEST = ROOT / "exports" / f"WAVERUN_FULL_TRANSFER_{STAMP}" / "04_market_events_full"
SRC = ROOT / "runtime" / "waverun" / "market_events.jsonl"
OUT = DEST / "market_events.jsonl"


def _ts(line: bytes) -> str | None:
    try:
        row = json.loads(line)
        return str(row.get("received_timestamp") or row.get("timestamp") or "")
    except Exception:
        return None


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    snapshot_time = datetime.now(UTC).isoformat()
    t0 = time.time()
    h = hashlib.sha256()
    total = 0
    lines = 0
    first_ts = None
    tail = b""  # keep the last partial+complete line region to recover last_ts
    buf = 8 << 20
    with SRC.open("rb") as fin, OUT.open("wb") as fout:
        first_chunk = True
        while True:
            chunk = fin.read(buf)
            if not chunk:
                break
            fout.write(chunk)
            h.update(chunk)
            total += len(chunk)
            lines += chunk.count(b"\n")
            if first_chunk:
                nl = chunk.find(b"\n")
                first_ts = _ts(chunk[:nl] if nl != -1 else chunk)
                first_chunk = False
            tail = (tail + chunk)[-65536:]
    last_ts = None
    for ln in reversed(tail.split(b"\n")):
        ln = ln.strip()
        if ln:
            last_ts = _ts(ln)
            if last_ts:
                break
    digest = h.hexdigest()
    meta = {
        "file": "market_events.jsonl",
        "source_path": str(SRC),
        "snapshot_time_utc": snapshot_time,
        "size_bytes": total,
        "line_count": lines,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "sha256": digest,
        "elapsed_seconds": round(time.time() - t0, 1),
        "note": "FULL copy - not sampled, not aggregated, not rewritten",
        "execution": "DISABLED",
    }
    (DEST / "market_events.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
