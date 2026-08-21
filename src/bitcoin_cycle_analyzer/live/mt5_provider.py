from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MT5Health:
    status: str
    reason: str | None = None
    terminal_detected: bool = False
    symbol: str | None = None
    terminal_version: str | None = None
    connected: bool | None = None
    logged_in: bool | None = None
    server_utc_offset_seconds: int | None = None


class MT5MarketDataProvider:
    """Read-only MT5 adapter. It deliberately exposes no trading operations."""

    SYMBOL_PRIORITY = ("BTCUSD", "BTCUSD.", "BTCUSDm", "BTCUSDT", "BTCUSD.pro")

    def __init__(self, backend: Any | None = None, values: dict[str, str] | None = None):
        self.values = values or dict(os.environ)
        self.backend = backend
        self._initialized = False
        self.symbol: str | None = None
        self.server_utc_offset_seconds = 0
        if self.backend is None:
            try:
                import MetaTrader5 as mt5  # type: ignore
                self.backend = mt5
            except ImportError:
                self.backend = None

    @property
    def terminal_path(self) -> str:
        return self.values.get("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

    def connect(self) -> MT5Health:
        terminal_detected = os.path.isfile(self.terminal_path)
        if self.values.get("MT5_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
            return MT5Health("DISABLED", "MT5_ENABLED_FALSE", terminal_detected)
        if self.backend is None:
            return MT5Health("UNAVAILABLE", "PYTHON_BRIDGE_NOT_INSTALLED", terminal_detected)
        kwargs = {"path": self.terminal_path} if terminal_detected else {}
        if not self.backend.initialize(**kwargs):
            return MT5Health("UNAVAILABLE", "INITIALIZE_FAILED", terminal_detected)
        self._initialized = True
        self.symbol = self._detect_symbol()
        if not self.symbol:
            return MT5Health("UNAVAILABLE", "BTC_SYMBOL_NOT_FOUND", terminal_detected)
        raw_tick=self.backend.symbol_info_tick(self.symbol)
        if raw_tick is not None and int(raw_tick.time)>0:
            difference=int(raw_tick.time-time.time());rounded=round(difference/3600)*3600
            self.server_utc_offset_seconds=rounded if abs(rounded)<=14*3600 else 0
        terminal=self.backend.terminal_info() if hasattr(self.backend,"terminal_info") else None
        account=self.backend.account_info() if hasattr(self.backend,"account_info") else None
        version=self.backend.version() if hasattr(self.backend,"version") else None
        return MT5Health("ONLINE", terminal_detected=terminal_detected, symbol=self.symbol,
                         terminal_version=".".join(str(x) for x in version[:2]) if version else None,
                         connected=bool(getattr(terminal,"connected",False)),logged_in=bool(getattr(account,"login",0)),server_utc_offset_seconds=self.server_utc_offset_seconds)

    def _detect_symbol(self) -> str | None:
        requested = self.values.get("MT5_BTC_SYMBOL")
        symbols = list(self.backend.symbols_get() or [])
        candidates=[]
        for item in symbols:
            name=item.name; description=str(getattr(item,"description",""))
            upper=f"{name} {description}".upper()
            if not ("BTC" in upper or "BITCOIN" in upper) or ("USD" not in upper and "USDT" not in upper): continue
            if any(term in upper for term in ("CASH","ETF","TRUST","STRATEGY")): continue
            self.backend.symbol_select(name,True)
            tick=self.backend.symbol_info_tick(name)
            valid_tick=bool(tick and float(tick.bid)>0 and float(tick.ask)>=float(tick.bid) and int(tick.time)>0)
            h4=self.backend.copy_rates_from_pos(name,self.backend.TIMEFRAME_H4,1,3)
            d1=self.backend.copy_rates_from_pos(name,self.backend.TIMEFRAME_D1,1,3)
            score=(100 if requested==name else 0)+(30 if valid_tick else 0)+(10 if h4 is not None and len(h4)>0 else 0)+(10 if d1 is not None and len(d1)>0 else 0)+(5 if getattr(item,"visible",False) else 0)-(len(name)/100)
            candidates.append((score,name))
        if not candidates:return None
        chosen=max(candidates)[1];self.backend.symbol_select(chosen,True);return chosen

    def _utc(self,epoch: float) -> pd.Timestamp:
        return pd.Timestamp(datetime.fromtimestamp(epoch-self.server_utc_offset_seconds, tz=UTC))

    def tick(self) -> dict:
        if not self._initialized or not self.symbol:
            return {"status": "UNAVAILABLE", "reason": "NOT_CONNECTED"}
        tick = self.backend.symbol_info_tick(self.symbol)
        for _ in range(8):
            if tick is not None and float(tick.bid)>0 and float(tick.ask)>=float(tick.bid) and int(tick.time)>0:break
            time.sleep(.25);tick=self.backend.symbol_info_tick(self.symbol)
        if tick is None:
            return {"status": "UNAVAILABLE", "reason": "NO_TICK"}
        bid, ask = float(tick.bid), float(tick.ask)
        if bid<=0 or ask<bid or int(tick.time)<=0:return {"status":"UNAVAILABLE","reason":"INVALID_OR_UNINITIALIZED_TICK"}
        time_msc = int(getattr(tick, "time_msc", int(tick.time) * 1000) or int(tick.time) * 1000)
        timestamp = self._utc(time_msc / 1000)
        age_seconds=max(0,(pd.Timestamp.now(tz="UTC")-timestamp).total_seconds())
        freshness="LIVE" if age_seconds<=30 else "DELAYED" if age_seconds<=300 else "STALE"
        return {"status": "AVAILABLE", "provider": "METATRADER_5", "symbol": self.symbol,
                "bid": bid, "ask": ask, "last": float(getattr(tick, "last", 0.0) or 0.0),
                "flags": int(getattr(tick, "flags", 0) or 0), "time_msc": time_msc,
                "mid": (bid + ask) / 2, "spread": ask - bid,
                "timestamp": timestamp,"age_seconds":round(age_seconds,2),"freshness":freshness}

    def confirmed_candles(self, timeframe: str, count: int = 500) -> pd.DataFrame:
        if not self._initialized or not self.symbol:
            return pd.DataFrame()
        constants = {"4h": "TIMEFRAME_H4", "1d": "TIMEFRAME_D1", "1w": "TIMEFRAME_W1", "1mo": "TIMEFRAME_MN1"}
        mt5_tf = getattr(self.backend, constants[timeframe])
        rows = self.backend.copy_rates_from_pos(self.symbol, mt5_tf, 1, count)  # position 0 is intrabar
        if rows is None or len(rows) == 0:
            return pd.DataFrame()
        frame = pd.DataFrame(rows).rename(columns={"tick_volume": "volume"})
        frame.index = pd.to_datetime(frame.pop("time")-self.server_utc_offset_seconds, unit="s", utc=True)
        return frame[["open", "high", "low", "close", "volume"]].sort_index()

    def intrabar_preview(self, timeframe: str) -> dict:
        if not self._initialized or not self.symbol:
            return {"status": "UNAVAILABLE", "confirmed": False}
        constants = {"4h": "TIMEFRAME_H4", "1d": "TIMEFRAME_D1", "1w": "TIMEFRAME_W1", "1mo": "TIMEFRAME_MN1"}
        rows = self.backend.copy_rates_from_pos(self.symbol, getattr(self.backend, constants[timeframe]), 0, 1)
        if rows is None or len(rows) == 0: return {"status": "UNAVAILABLE", "confirmed": False}
        row = dict(rows[0]) if not isinstance(rows[0], dict) else rows[0]
        return {"status": "PREVIEW", "confirmed": False, "timeframe": timeframe, "timestamp": self._utc(row["time"]), **{key: float(row[key]) for key in ("open", "high", "low", "close")}}

    def provenance(self) -> dict:
        account = self.backend.account_info() if self._initialized and self.backend else None
        server = str(getattr(account, "server", ""))
        server_hash = hashlib.sha256(server.encode()).hexdigest()[:12] if server else None
        return {"live_price_provider": "MT5" if self._initialized else "UNAVAILABLE", "h4_provider": "MT5" if self._initialized else "UNAVAILABLE",
                "d1_provider": "MT5" if self._initialized else "UNAVAILABLE", "w1_provider": "MT5" if self._initialized else "UNAVAILABLE", "m1_provider": "MT5" if self._initialized else "UNAVAILABLE", "historical_provider": "BITSTAMP",
                "symbol": self.symbol, "broker_server_hash": server_hash,"server_utc_offset_seconds":self.server_utc_offset_seconds, "execution": "DISABLED"}

    @staticmethod
    def divergence(mt5_price: float | None, spot_price: float | None, warn_pct: float = 1.0) -> dict:
        if not mt5_price or not spot_price:
            return {"status": "UNAVAILABLE", "deviation_pct": None}
        pct = (mt5_price / spot_price - 1) * 100
        absolute=mt5_price-spot_price;ap=abs(pct)
        status="CRITICAL" if ap>warn_pct*3 else "WARNING" if ap>warn_pct else "NORMAL"
        return {"status":status,"absolute_difference":round(absolute,2), "deviation_pct": round(pct, 4), "threshold_pct": warn_pct}

    def close(self):
        if self._initialized and self.backend:
            self.backend.shutdown()
        self._initialized = False
