from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol
from datetime import datetime, timezone
import hashlib
import pandas as pd
import requests

try:
    import truststore
except ImportError:  # pragma: no cover - optional outside Windows
    truststore = None

if truststore is not None:
    # Uses the OS certificate store while retaining hostname and chain checks.
    truststore.inject_into_ssl()

OHLCV = ["open", "high", "low", "close", "volume"]


class ProviderError(RuntimeError):
    pass


class DataProvider(Protocol):
    name: str
    source: str
    def fetch(self, timeframe: str, since: pd.Timestamp | None = None) -> pd.DataFrame: ...


class KrakenProvider:
    """Public Kraken OHLC adapter. Kraken returns only a recent rolling window."""

    URL = "https://api.kraken.com/0/public/OHLC"
    INTERVALS = {"4h": 240, "1d": 1440, "1w": 10080}
    name = "kraken"
    source = "Kraken XBT/USD spot"

    def __init__(self, symbol: str = "XBTUSD", timeout: int = 20):
        self.symbol, self.timeout = symbol, timeout

    def fetch(self, timeframe: str, since: pd.Timestamp | None = None) -> pd.DataFrame:
        if timeframe not in self.INTERVALS:
            raise ProviderError(f"Kraken does not directly provide {timeframe}")
        params = {"pair": self.symbol, "interval": self.INTERVALS[timeframe]}
        if since is not None:
            params["since"] = int(pd.Timestamp(since).timestamp())
        try:
            response = requests.get(self.URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError(f"Kraken request failed: {exc}") from exc
        if payload.get("error"):
            raise ProviderError("; ".join(payload["error"]))
        key = next(k for k in payload["result"] if k != "last")
        rows = payload["result"][key]
        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "vwap", "volume", "count"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
        frame = frame.set_index("timestamp")[OHLCV].astype(float)
        return validate_ohlcv(frame)


class BitstampProvider:
    """Paginated public Bitstamp BTC/USD OHLCV history."""

    URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
    STEPS = {"4h": 14_400, "1d": 86_400}
    name = "bitstamp"
    source = "Bitstamp BTC/USD spot"

    def __init__(self, timeout: int = 30, batch_size: int = 1000):
        self.timeout, self.batch_size = timeout, batch_size

    def fetch(self, timeframe: str, since: pd.Timestamp | None = None) -> pd.DataFrame:
        if timeframe not in self.STEPS:
            raise ProviderError(f"Bitstamp does not directly provide {timeframe}")
        step = self.STEPS[timeframe]
        start = pd.Timestamp("2011-08-18", tz="UTC") if since is None else pd.Timestamp(since)
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert("UTC")
        # Re-fetch the last stored candle so revisions replace, not duplicate, it.
        cursor = int(start.timestamp())
        now = int(pd.Timestamp.now(tz="UTC").floor("D").timestamp())
        frames = []
        while cursor <= now:
            end = min(now, cursor + step * (self.batch_size - 1))
            params = {"step": step, "limit": self.batch_size, "start": cursor, "end": end, "exclude_current_candle": "true"}
            try:
                response = requests.get(self.URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()["data"]["ohlc"]
            except (requests.RequestException, ValueError, KeyError) as exc:
                raise ProviderError(f"Bitstamp request failed at {cursor}: {exc}") from exc
            if payload:
                batch = pd.DataFrame(payload)
                batch["timestamp"] = pd.to_datetime(batch["timestamp"].astype("int64"), unit="s", utc=True)
                frames.append(batch.set_index("timestamp")[OHLCV].astype(float))
                last = int(batch["timestamp"].max().timestamp())
                cursor = max(cursor + step, last + step)
            else:
                cursor = end + step
        if not frames:
            return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], name="timestamp", tz="UTC"))
        return validate_ohlcv(pd.concat(frames))


def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(OHLCV) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    result = frame[OHLCV].copy().sort_index()
    if not isinstance(result.index, pd.DatetimeIndex):
        raise ValueError("OHLCV index must be a DatetimeIndex")
    result = result[~result.index.duplicated(keep="last")]
    result = result.dropna(subset=["open", "high", "low", "close"])
    invalid = (result[OHLCV] < 0).any(axis=1) | (result["high"] < result[["open", "close", "low"]].max(axis=1)) | (result["low"] > result[["open", "close", "high"]].min(axis=1))
    if invalid.any():
        raise ValueError("Invalid OHLCV bar detected")
    return result


class OHLCVStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_schema(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS ohlcv (
                timeframe TEXT NOT NULL, timestamp TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                source TEXT NOT NULL DEFAULT 'legacy', provider TEXT NOT NULL DEFAULT 'legacy',
                import_timestamp TEXT NOT NULL DEFAULT '', data_version TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(timeframe, timestamp))""")
            existing = {row[1] for row in con.execute("PRAGMA table_info(ohlcv)")}
            for name, definition in {"source": "TEXT NOT NULL DEFAULT 'legacy'", "provider": "TEXT NOT NULL DEFAULT 'legacy'", "import_timestamp": "TEXT NOT NULL DEFAULT ''", "data_version": "TEXT NOT NULL DEFAULT ''"}.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE ohlcv ADD COLUMN {name} {definition}")

    def upsert(self, timeframe: str, frame: pd.DataFrame, provider: str = "local", source: str = "local import", data_version: str | None = None) -> int:
        frame = validate_ohlcv(frame)
        imported = datetime.now(timezone.utc).isoformat()
        if data_version is None:
            digest = pd.util.hash_pandas_object(frame[OHLCV], index=True).values.tobytes()
            data_version = hashlib.sha256(digest).hexdigest()[:16]
        rows = [(timeframe, ts.isoformat(), *map(float, row), source, provider, imported, data_version) for ts, row in frame[OHLCV].iterrows()]
        with self._connect() as con:
            con.executemany("""INSERT OR REPLACE INTO ohlcv
                (timeframe,timestamp,open,high,low,close,volume,source,provider,import_timestamp,data_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)
        return len(rows)

    def load(self, timeframe: str) -> pd.DataFrame:
        with self._connect() as con:
            frame = pd.read_sql_query("SELECT timestamp,open,high,low,close,volume FROM ohlcv WHERE timeframe=? ORDER BY timestamp", con, params=(timeframe,))
        if frame.empty:
            return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], name="timestamp"))
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp")

    def load_canonical(self, timeframe: str) -> pd.DataFrame:
        with self._connect() as con:
            frame = pd.read_sql_query("SELECT * FROM ohlcv WHERE timeframe=? ORDER BY timestamp", con, params=(timeframe,))
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp")

    def latest(self, timeframe: str) -> pd.Timestamp | None:
        frame = self.load(timeframe)
        return None if frame.empty else frame.index[-1]

    def update(self, timeframe: str, provider: DataProvider) -> int:
        return self.upsert(timeframe, provider.fetch(timeframe, self.latest(timeframe)), provider=provider.name, source=provider.source)


def resample(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rules = {"4h": "4h", "1d": "1D", "1w": "W-MON", "1M": "ME"}
    if timeframe not in rules:
        raise ValueError(f"Unsupported timeframe {timeframe}")
    result = frame.resample(rules[timeframe], label="right", closed="right").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    # A period candle is canonical only once its labelled close is reached.
    result = result[result.index <= frame.index.max()]
    return validate_ohlcv(result)
