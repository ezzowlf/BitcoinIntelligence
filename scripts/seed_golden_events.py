"""Seed a small, source-verified Golden Event Dataset (Master-Auftrag 3, Phase 3).

Idempotent: uses the existing PointInTimeEventDatabase.append() which
INSERT OR IGNOREs on a content hash, so re-running this script is safe.

Deliberately small. Per the brief's Phase 32 ("keine Massen-Datensammlung"):
priority is Golden Events -> architecture -> reaction engine -> provenance ->
chart integration -> tests, THEN scale. This script adds only the four
Bitcoin halvings, because they are the one category of "major Bitcoin event"
that is deterministic and independently verifiable (protocol block-height
rule), rather than something requiring editorial judgement about severity or
a paid news archive. Every other item on the brief's Phase-3 wish list
(Mt. Gox, FTX, Terra/Luna, Celsius, El Salvador, 2021 ATH context, etc.) was
NOT added in this pass — see the Auftrag 3 report for why, rather than
fabricating a source or guessing a URL to hit a bigger number.

Dates cross-checked against the codebase's own existing HALVINGS constant
(src/bitcoin_cycle_analyzer/cycles/history.py) and via live web search
(CoinGecko halving tracker) on 2026-08-11 — both agree exactly. This is not
sourced from model memory: the source_url below was actually fetched.
"""
from __future__ import annotations
from pathlib import Path
from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase

ROOT = Path(__file__).resolve().parents[1]

HALVING_SOURCE = {"source_url": "https://www.coingecko.com/en/coins/bitcoin/bitcoin-halving", "source_name": "CoinGecko halving tracker", "source_quality": "HIGH_QUALITY_SECONDARY"}

GOLDEN_HALVING_EVENTS = [
    {"event_time": "2012-11-28T00:00:00Z", "headline": "First Bitcoin block-reward halving (block 210,000): 50 -> 25 BTC", "category": "HALVING", "importance": "HIGH", "status": "OFFICIAL", "expected_direction": "BULLISH", "causality_note": "Supply-shock hypothesis is widely discussed but not something this dataset asserts as proven; see reaction data instead of narrative."},
    {"event_time": "2016-07-09T00:00:00Z", "headline": "Second Bitcoin block-reward halving (block 420,000): 25 -> 12.5 BTC", "category": "HALVING", "importance": "HIGH", "status": "OFFICIAL", "expected_direction": "BULLISH", "causality_note": "Same caveat as 2012 — deterministic supply event, market reaction is empirical, not assumed."},
    {"event_time": "2020-05-11T00:00:00Z", "headline": "Third Bitcoin block-reward halving (block 630,000): 12.5 -> 6.25 BTC", "category": "HALVING", "importance": "HIGH", "status": "OFFICIAL", "expected_direction": "BULLISH", "causality_note": "Occurred ~2 months after the COVID crash — cycle/macro context matters more than the halving in isolation."},
    {"event_time": "2024-04-20T00:09:00Z", "headline": "Fourth Bitcoin block-reward halving (block 840,000): 6.25 -> 3.125 BTC", "category": "HALVING", "importance": "HIGH", "status": "OFFICIAL", "expected_direction": "BULLISH", "causality_note": "Occurred after spot ETF approval; disentangling halving effect from ETF-driven demand is not attempted here."},
]


def seed(db_path: Path = ROOT / "database" / "historical_event_evidence.db") -> list[str]:
    db = PointInTimeEventDatabase(db_path)
    ids = []
    for event in GOLDEN_HALVING_EVENTS:
        payload = {**HALVING_SOURCE, "first_known_at": event["event_time"], "available_at": event["event_time"], **event}
        ids.append(db.append(payload))
    return ids


if __name__ == "__main__":
    inserted = seed()
    print(f"Seeded/confirmed {len(inserted)} golden halving events.")
