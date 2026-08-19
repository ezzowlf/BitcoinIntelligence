from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

TICK_COLUMNS = ("time", "time_msc", "bid", "ask", "last", "volume", "flags", "volume_real")


class MT5TickHistory:
    """Read-only, chunked MT5 tick history adapter. It does not expose trading calls."""

    def __init__(self, backend: Any, symbol: str = "BTCUSD"):
        self.backend, self.symbol = backend, symbol

    def _frame(self, rows: Any, downloaded_at: datetime) -> pd.DataFrame:
        if rows is None or len(rows) == 0:
            return pd.DataFrame(columns=(*TICK_COLUMNS, "downloaded_at"))
        frame = pd.DataFrame(rows)
        for column in TICK_COLUMNS:
            if column not in frame:
                frame[column] = pd.NA
        frame = frame.loc[:, [*TICK_COLUMNS]].copy()
        if frame["time_msc"].isna().all() and frame["time"].notna().any():
            frame["time_msc"] = pd.to_numeric(frame["time"], errors="coerce") * 1000
        frame["timestamp"] = pd.to_datetime(frame["time_msc"], unit="ms", utc=True, errors="coerce")
        frame["downloaded_at"] = downloaded_at
        return frame

    def range(self, start: datetime, end: datetime) -> pd.DataFrame:
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise ValueError("start/end must be ordered timezone-aware datetimes")
        rows = self.backend.copy_ticks_range(self.symbol, start.astimezone(UTC), end.astimezone(UTC), self.backend.COPY_TICKS_ALL)
        return self._frame(rows, datetime.now(UTC))

    def backward(self, end: datetime, *, days: int = 1, max_chunks: int = 3650) -> pd.DataFrame:
        if end.tzinfo is None or days <= 0:
            raise ValueError("end must be timezone-aware and days positive")
        chunks: list[pd.DataFrame] = []
        cursor = end.astimezone(UTC)
        for _ in range(max_chunks):
            start = cursor - timedelta(days=days)
            frame = self.range(start, cursor)
            if frame.empty:
                break
            chunks.append(frame)
            oldest = frame["timestamp"].min()
            if pd.isna(oldest) or oldest >= pd.Timestamp(start):
                cursor = start
            else:
                cursor = oldest.to_pydatetime() - timedelta(milliseconds=1)
        if not chunks:
            return pd.DataFrame(columns=(*TICK_COLUMNS, "timestamp", "downloaded_at"))
        result = pd.concat(chunks, ignore_index=True).sort_values("timestamp")
        return result.drop_duplicates(subset=["time_msc", "bid", "ask", "last", "volume"], keep="first").reset_index(drop=True)

    @staticmethod
    def audit(frame: pd.DataFrame) -> dict[str, Any]:
        if frame.empty:
            return {"rows": 0, "start": None, "end": None, "duplicate_ticks": 0, "backwards_timestamps": 0, "zero_quotes": 0, "crossed_quotes": 0, "gap_count": 0}
        ts = pd.to_datetime(frame["timestamp"], utc=True)
        deltas = ts.diff().dt.total_seconds()
        valid_spread = frame["bid"].notna() & frame["ask"].notna()
        return {"rows": len(frame), "start": ts.min().isoformat(), "end": ts.max().isoformat(),
                "duplicate_ticks": int(frame.duplicated(subset=["time_msc", "bid", "ask", "last", "volume"]).sum()),
                "backwards_timestamps": int((deltas < 0).sum()), "zero_quotes": int(((frame["bid"].fillna(0) <= 0) | (frame["ask"].fillna(0) <= 0)).sum()),
                "crossed_quotes": int((valid_spread & (frame["ask"] < frame["bid"])).sum()),
                "gap_count": int((deltas > 60).sum())}
