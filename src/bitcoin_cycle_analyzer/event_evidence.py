from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

SOURCE_QUALITY = {"PRIMARY", "HIGH_QUALITY_SECONDARY", "SECONDARY"}
EVENT_CATEGORIES = {"MACRO", "MONETARY_POLICY", "LIQUIDITY", "REGULATION", "ETF", "INSTITUTIONAL", "ADOPTION", "EXCHANGE", "CRYPTO_CREDIT", "STABLECOIN", "MINING", "ONCHAIN", "SECURITY", "GEOPOLITICS", "MARKET_STRUCTURE", "HALVING", "SYSTEMIC_RISK", "BITCOIN_PROTOCOL", "FED", "BANKING_CRISIS"}
EVENT_IMPORTANCE = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
EVENT_STATUS = ("UNVERIFIED", "DEVELOPING", "CONFIRMED", "OFFICIAL")
EXPECTED_DIRECTION = ("BULLISH", "BEARISH", "NEUTRAL", "UNCERTAIN")
# Never a certainty claim — always paired with an explicit uncertainty level in the UI/AI layer.
CAUSALITY_LEVELS = ("UNKNOWN", "TEMPORAL_ASSOCIATION", "PLAUSIBLE_CONTRIBUTOR", "MULTIPLE_PLAUSIBLE_CONTRIBUTORS", "STRONG_EVIDENCE")

# Additive schema extension (Master-Auftrag 3). Existing rows keep NULL for these
# columns rather than being backfilled with guessed values — NULL means "not yet
# classified", never "neutral". This is intentionally additive: the append-only
# historical_events/event_reactions tables and their triggers from Auftrag-0/pre-existing
# WIP are untouched, so no existing data or behaviour is altered.
_NEW_COLUMNS = {
    "importance": "TEXT",
    "subcategory": "TEXT",
    "status": "TEXT",
    "expected_direction": "TEXT",
    "causality_note": "TEXT",
}


class PointInTimeEventDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS historical_events(event_id TEXT PRIMARY KEY,event_time TEXT NOT NULL,first_known_at TEXT NOT NULL,available_at TEXT NOT NULL,source_url TEXT NOT NULL,source_name TEXT NOT NULL,source_quality TEXT NOT NULL,category TEXT NOT NULL,headline TEXT NOT NULL,severity_at_time TEXT,severity_ex_post TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS event_reactions(event_id TEXT NOT NULL,horizon TEXT NOT NULL,asset TEXT NOT NULL,outcome_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(event_id,horizon,asset));
            CREATE TRIGGER IF NOT EXISTS historical_events_no_update BEFORE UPDATE ON historical_events BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS historical_events_no_delete BEFORE DELETE ON historical_events BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS event_reactions_no_update BEFORE UPDATE ON event_reactions BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS event_reactions_no_delete BEFORE DELETE ON event_reactions BEGIN SELECT RAISE(ABORT,'append-only'); END;
            """)
            existing_cols = {row[1] for row in db.execute("PRAGMA table_info(historical_events)")}
            for name, sqltype in _NEW_COLUMNS.items():
                if name not in existing_cols:
                    db.execute(f"ALTER TABLE historical_events ADD COLUMN {name} {sqltype}")

    def append(self, event: dict) -> str:
        required = {"event_time", "first_known_at", "available_at", "source_url", "source_name", "source_quality", "category", "headline"}
        if not required <= event.keys():
            raise ValueError(f"missing event provenance: {sorted(required-event.keys())}")
        event_time, known, available = (pd.Timestamp(event[key]) for key in ("event_time", "first_known_at", "available_at"))
        if known < event_time or available < known:
            raise ValueError("PIT order must be event_time <= first_known_at <= available_at")
        if event["source_quality"] not in SOURCE_QUALITY or not str(event["source_url"]).startswith("https://"):
            raise ValueError("verified HTTPS source and source quality required")
        if event.get("importance") is not None and event["importance"] not in EVENT_IMPORTANCE:
            raise ValueError(f"importance must be one of {EVENT_IMPORTANCE}")
        if event.get("status") is not None and event["status"] not in EVENT_STATUS:
            raise ValueError(f"status must be one of {EVENT_STATUS}")
        if event.get("expected_direction") is not None and event["expected_direction"] not in EXPECTED_DIRECTION:
            raise ValueError(f"expected_direction must be one of {EXPECTED_DIRECTION}")
        eid = hashlib.sha256(f"{event_time.isoformat()}|{event['headline']}|{event['source_url']}".encode()).hexdigest()
        row = (eid, event_time.isoformat(), known.isoformat(), available.isoformat(), event["source_url"], event["source_name"], event["source_quality"], event["category"], event["headline"], event.get("severity_at_time"), event.get("severity_ex_post"), event.get("importance"), event.get("subcategory"), event.get("status"), event.get("expected_direction"), event.get("causality_note"))
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO historical_events VALUES(?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?,?,?,?,?)", row)
        return eid

    def as_of(self, timestamp) -> pd.DataFrame:
        with sqlite3.connect(self.path) as db:
            return pd.read_sql_query("SELECT * FROM historical_events WHERE available_at<=? ORDER BY event_time", db, params=(pd.Timestamp(timestamp).isoformat(),))

    def compute_reactions(self, prices: pd.DataFrame, asset="BTC") -> int:
        if prices.empty:
            return 0
        series = prices.close.sort_index()
        horizons = {"1H": pd.Timedelta(hours=1), "4H": pd.Timedelta(hours=4), "24H": pd.Timedelta(days=1), "3D": pd.Timedelta(days=3), "7D": pd.Timedelta(days=7), "14D": pd.Timedelta(days=14), "30D": pd.Timedelta(days=30)}
        inserted = 0
        with sqlite3.connect(self.path) as db:
            events = db.execute("SELECT event_id,event_time,available_at FROM historical_events").fetchall()
            for eid, event_raw, available_raw in events:
                anchor_time = pd.Timestamp(available_raw)
                before = series.loc[series.index <= anchor_time]
                if before.empty:
                    continue
                anchor_at, anchor = before.index[-1], float(before.iloc[-1])
                for label, delta in horizons.items():
                    future = series.loc[series.index >= anchor_time + delta]
                    if future.empty:
                        continue
                    observed_at, value = future.index[0], float(future.iloc[0])
                    window = series.loc[anchor_at:observed_at]
                    payload = {"anchor_at": anchor_at.isoformat(), "anchor_price": anchor, "observed_at": observed_at.isoformat(), "price": value, "return": value/anchor-1, "max_drawdown": float(window.min()/anchor-1), "resolution": "INTRADAY" if pd.infer_freq(series.index[:10]) in {"h", "H"} else "DAILY_PROXY"}
                    cur = db.execute("INSERT OR IGNORE INTO event_reactions(event_id,horizon,asset,outcome_json) VALUES(?,?,?,?)", (eid, label, asset, json.dumps(payload)))
                    inserted += cur.rowcount
        return inserted

    def health(self) -> dict:
        with sqlite3.connect(self.path) as db:
            events = db.execute("SELECT COUNT(*) FROM historical_events").fetchone()[0]
            reactions = db.execute("SELECT COUNT(*) FROM event_reactions").fetchone()[0]
            coverage = db.execute("SELECT MIN(event_time),MAX(event_time),COUNT(DISTINCT category) FROM historical_events").fetchone()
        return {"status": "AVAILABLE" if events else "INSUFFICIENT_DATA", "events": events, "reactions": reactions, "from": coverage[0], "to": coverage[1], "categories": coverage[2], "append_only": True}

    def reactions(self, event_id: str) -> pd.DataFrame:
        with sqlite3.connect(self.path) as db:
            rows=pd.read_sql_query("SELECT horizon,asset,outcome_json FROM event_reactions WHERE event_id=? ORDER BY horizon",db,params=(event_id,))
        if rows.empty:return rows
        details=rows.pop("outcome_json").map(json.loads).apply(pd.Series)
        return pd.concat([rows,details],axis=1)


def condition_event_context(event_rows: pd.DataFrame, regime: pd.Series, features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for event in event_rows.itertuples():
        ts = pd.Timestamp(event.available_at)
        before = features.loc[features.index <= ts]
        if before.empty:
            continue
        point = before.iloc[-1]
        rows.append({"event_id": event.event_id, "available_at": ts, "regime": None if regime.empty else regime.reindex([ts], method="ffill").iloc[0], "drawdown": point.get("drawdown"), "below_200d": point.get("below_200d"), "below_200w": point.get("below_200w"), "rsi": point.get("weekly_rsi"), "volatility": point.get("volatility")})
    return pd.DataFrame(rows)
