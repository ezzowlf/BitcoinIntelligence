from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class ParquetDataLake:
    """Raw/derived partitioned store. It never mutates raw partitions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def partition_path(self, source: str, instrument: str, timestamp: datetime, derived: bool = False) -> Path:
        folder = self.root / ("derived" if derived else "raw") / source / instrument / f"{timestamp:%Y}" / f"{timestamp:%m}"
        return folder / f"{timestamp:%Y-%m-%d}.parquet"

    def write(self, frame: pd.DataFrame, source: str, instrument: str, timestamp: datetime, *, derived: bool = False) -> Path:
        if frame.empty:
            raise ValueError("cannot write an empty data partition")
        path = self.partition_path(source, instrument, timestamp, derived)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            frame.to_parquet(path, compression="zstd", index=False)
        except ImportError as exc:
            raise RuntimeError("Parquet support requires pyarrow or fastparquet; no CSV fallback is allowed") from exc
        return path

    def read(self, source: str, instrument: str, timestamp: datetime, *, derived: bool = False) -> pd.DataFrame:
        path = self.partition_path(source, instrument, timestamp, derived)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    @staticmethod
    def metadata(frame: pd.DataFrame) -> dict[str, Any]:
        return {"rows": len(frame), "columns": list(frame.columns), "memory_bytes": int(frame.memory_usage(deep=True).sum())}
