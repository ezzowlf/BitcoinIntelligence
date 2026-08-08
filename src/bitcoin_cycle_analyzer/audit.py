from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone


def save_analysis(payload: dict, directory: str | Path = "data/analyses") -> Path:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    path = target / f"analysis-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.json"
    document = {"saved_at": timestamp.isoformat(), **payload}
    path.write_text(json.dumps(document, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    return path

