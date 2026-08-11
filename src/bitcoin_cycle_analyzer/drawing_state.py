"""User Drawing State (P1 Chart Interaction pass).

Pure annotation layer. NEVER imported by decision_intelligence, event_intelligence,
or any engine — drawings cannot influence a Decision, Evidence Family, Elliott
count, or any BUY/SELL output. This module only stores and retrieves what the
user drew; nothing here computes market analysis.

Technical note (see the pass's report for the full audit): `st.plotly_chart`
does not expose Plotly's shape-relayout events to Python (`on_select` only
covers point/box/lasso *data* selection), so free-hand mouse-drawn shapes from
the native drawing toolbar cannot be captured and persisted without a custom
JS component. This module instead persists FORM-DEFINED drawings (numeric
price/date inputs), which achieves real, reliable persistence entirely within
the existing Streamlit + Plotly stack — no migration, no custom component.
"""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

DRAWING_TYPES = ("HLINE", "RECTANGLE", "FIB")
FIB_RATIOS = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_fib_levels(price_a: float, price_b: float) -> list[dict]:
    """Point A is the anchor the retracement is measured FROM (e.g. the swing
    low in an uptrend), Point B is measured TO. Direction is inferred from
    which is higher — this is a plain arithmetic retracement, not an Elliott
    or engine-derived target (see MY FIB vs SYSTEM FIB distinction)."""
    span = price_b - price_a
    return [{"ratio": r, "price": round(price_a + span * r, 2)} for r in FIB_RATIOS]


class UserDrawingStore:
    """One JSON file per symbol under runtime/drawings/ — reuses the existing
    runtime/ directory convention (already used by ai_cache, production8)
    rather than introducing a new database just for annotations."""

    def __init__(self, root: Path, symbol: str = "BTCUSD"):
        self.path = Path(root) / "runtime" / "drawings" / f"{symbol}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _write(self, drawings: list[dict]) -> None:
        self.path.write_text(json.dumps(drawings, indent=2), encoding="utf-8")

    def list(self, timeframe: str | None = None) -> list[dict]:
        drawings = self._read()
        if timeframe is None:
            return drawings
        return [d for d in drawings if d.get("timeframe") in (timeframe, "ALL_TIMEFRAMES")]

    def add(self, drawing_type: str, timeframe: str, coordinates: dict, text: str = "", style: dict | None = None) -> dict:
        if drawing_type not in DRAWING_TYPES:
            raise ValueError(f"drawing_type must be one of {DRAWING_TYPES}")
        drawing = {
            "drawing_id": uuid.uuid4().hex[:12],
            "type": drawing_type,
            "timeframe": timeframe,
            "coordinates": coordinates,
            "text": text,
            "locked": False,
            "style": style or {},
            "created_at": _now(),
            "updated_at": _now(),
        }
        drawings = self._read()
        drawings.append(drawing)
        self._write(drawings)
        return drawing

    def update(self, drawing_id: str, **fields) -> dict | None:
        drawings = self._read()
        for d in drawings:
            if d["drawing_id"] == drawing_id:
                if d.get("locked") and "locked" not in fields:
                    raise ValueError("drawing is locked — unlock before editing")
                d.update(fields)
                d["updated_at"] = _now()
                self._write(drawings)
                return d
        return None

    def delete(self, drawing_id: str) -> dict | None:
        drawings = self._read()
        target = next((d for d in drawings if d["drawing_id"] == drawing_id), None)
        if target is None:
            return None
        if target.get("locked"):
            raise ValueError("drawing is locked — unlock before deleting")
        self._write([d for d in drawings if d["drawing_id"] != drawing_id])
        return target

    def restore(self, drawing: dict) -> dict:
        """Re-insert a previously deleted drawing (used by Undo)."""
        drawings = self._read()
        drawings.append(drawing)
        self._write(drawings)
        return drawing
