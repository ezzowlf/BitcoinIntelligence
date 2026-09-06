"""Read-only HTTP/SSE API in front of the running WAVERUN engine.

This module never computes signals and never places orders. It reads the files the
live engine (``scripts/waverun_live.py``) and the frozen V5.3 Fast V2 forward
collector already persist under ``runtime/`` and republishes them for the web UI.

Execution stays DISABLED: no broker, order or trade code path exists here.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from bitcoin_cycle_analyzer.short_term.presignal_state import (
    Evidence,
    PreSignalStateMachine,
)
from bitcoin_cycle_analyzer.short_term.product import (
    EXECUTION,
    HYPOTHESIS_SHA256,
    read_json,
    tail_jsonl,
)
from bitcoin_cycle_analyzer.short_term.resilience import (
    CONFIG as RES_CONFIG,
)
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.resilience import (
    ComponentHealth,
    age_seconds,
    api_overall_label,
    compute_operating_state,
)

# Discovery-era evidence for the frozen V5.3 Fast V2 hypothesis. This is NOT a live
# result and must always be presented separately from forward validation.
V5_3_DISCOVERY_WIN_RATE = 69.05
V5_3_FORWARD_TARGET = 100

TIMEFRAMES: dict[str, int] = {
    "30s": 30,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}

MAX_TICKS = 400_000
LIVE_MAX_AGE_S = 3.0
STALE_MAX_AGE_S = 30.0


def repo_root() -> Path:
    override = os.environ.get("WAVERUN_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- ticks


@dataclass
class TickCache:
    """Incremental tail reader for ``runtime/waverun/vantage_ticks.jsonl``."""

    path: Path
    offset: int = 0
    ticks: list[dict[str, Any]] = field(default_factory=list)

    def refresh(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return self.ticks
        size = self.path.stat().st_size
        if size < self.offset:  # file rotated/truncated by a restart
            self.offset, self.ticks = 0, []
        if size == self.offset:
            return self.ticks
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read(size - self.offset)
        lines = chunk.split(b"\n")
        # a trailing partial line is left for the next refresh
        self.offset = size - len(lines[-1])
        for line in lines[:-1]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("bid") is None or row.get("ask") is None:
                continue
            self.ticks.append(row)
        if len(self.ticks) > MAX_TICKS:
            del self.ticks[: len(self.ticks) - MAX_TICKS]
        return self.ticks


def _epoch_seconds(tick: dict[str, Any]) -> float:
    time_msc = tick.get("time_msc")
    if time_msc is not None:
        return float(time_msc) / 1000.0
    return datetime.fromisoformat(str(tick["timestamp"])).timestamp()


def build_candles(ticks: list[dict[str, Any]], seconds: int, limit: int) -> list[dict[str, float]]:
    """OHLC bars from Vantage mid prices. Vantage ticks carry no volume.

    Buckets are keyed so that out-of-order ticks (engine restarts append a fresh
    run to the same file) cannot produce duplicated or interleaved bars.
    """
    buckets: dict[int, dict[str, float]] = {}
    for tick in ticks:
        stamp = _epoch_seconds(tick)
        mid = (float(tick["bid"]) + float(tick["ask"])) / 2.0
        start = int(stamp // seconds) * seconds
        current = buckets.get(start)
        if current is None:
            buckets[start] = {"time": start, "open": mid, "high": mid, "low": mid, "close": mid}
            continue
        current["high"] = max(current["high"], mid)
        current["low"] = min(current["low"], mid)
        current["close"] = mid
    return [buckets[key] for key in sorted(buckets)][-limit:]


# --------------------------------------------------------------------- read models


def _feed_state(feeds: dict[str, Any], key: str) -> str:
    return str((feeds.get(key) or {}).get("state", "OFFLINE"))


def _online(state: str) -> bool:
    return state in {"LIVE", "ONLINE", "CONNECTED", "AVAILABLE", "RUNNING"}


def _signal(decision: dict[str, Any], name: str) -> dict[str, Any]:
    for row in decision.get("signals", []) or []:
        if row.get("name") == name:
            return row
    return {}


def proximity_score(
    *,
    setup_state: str,
    direction: str,
    pressure: float,
    flow_agreement: str,
    l2_aligned: bool | None,
    sources_online: int,
    sources_total: int,
) -> dict[str, Any]:
    """Deterministic 0-100 SIGNALNÄHE composite.

    This is an explicitly heuristic proximity/readiness score built from engine
    fields. It is NOT a probability and must never be labelled as one.
    """
    # Weights are chosen so that a perfect reading sums to exactly 100.
    state_points = {
        "NEUTRAL": 0.0,
        "WATCH_CANCELLED": 4.0,
        "SIGNAL_INVALIDATED": 4.0,
        "WATCH": 12.0,
        "ARMED": 22.0,
        "SIGNAL": 30.0,
        "EXIT": 8.0,
    }.get(setup_state, 0.0)
    direction_points = 15.0 if direction in {"LONG", "SHORT"} else 0.0
    pressure_points = max(0.0, min(25.0, pressure / 100.0 * 25.0))
    flow_points = {"CONFIRMED": 12.0, "DIVERGENT": 0.0}.get(flow_agreement, 4.0)
    l2_points = 8.0 if l2_aligned else 0.0
    quality_points = 0.0 if not sources_total else 10.0 * sources_online / sources_total
    components = {
        "marktzustand": round(state_points, 1),
        "richtungs_bias": round(direction_points, 1),
        "druck": round(pressure_points, 1),
        "flow_bestaetigung": round(flow_points, 1),
        "l2_ausrichtung": round(l2_points, 1),
        "datenqualitaet": round(quality_points, 1),
    }
    return {
        "score": round(sum(components.values()), 1),
        "components": components,
        "label": "SIGNALNÄHE-SCORE",
        "is_probability": False,
    }


_DIRECTION_DE = {"LONG": "aufwärts", "SHORT": "abwärts", "NEUTRAL": "richtungslos"}
_STATE_DE = {
    "NEUTRAL": "Der Markt ist neutral. Es baut sich derzeit kein Setup auf.",
    "WATCH": "Der Markt wird beobachtet. Erste Bedingungen für ein Setup bauen sich auf.",
    "ARMED": "Ein Setup ist vorbereitet. Die Auslösebedingung fehlt noch.",
    "SIGNAL": "Ein Setup ist aktiv. Die Engine führt es als Schatten-Signal.",
    "WATCH_CANCELLED": "Ein beobachtetes Setup wurde verworfen, bevor es scharf wurde.",
    "SIGNAL_INVALIDATED": "Ein aktives Setup wurde invalidiert.",
    "EXIT": "Die Engine ist in einem Ausstiegszustand.",
}


def assessment_text(
    *,
    setup_state: str,
    direction: str,
    pressure: float,
    momentum: dict[str, Any],
    flow_agreement: str,
    spot_direction: str,
    futures_direction: str,
    live_state: str,
) -> str:
    """Deterministic German assessment. No model, no LLM, no free text."""
    parts: list[str] = [_STATE_DE.get(setup_state, f"Zustand: {setup_state}.")]
    if direction in {"LONG", "SHORT"}:
        parts.append(
            f"Der aktuelle Richtungs-Bias der Engine zeigt {_DIRECTION_DE[direction]} "
            f"({direction}) bei einem Druckwert von {pressure:.0f} von 100."
        )
    else:
        parts.append("Es liegt kein eindeutiger Richtungs-Bias vor.")

    returns = (momentum or {}).get("returns") or {}
    ret60 = returns.get("60") if isinstance(returns, dict) else None
    if ret60 is None and isinstance(returns, dict):
        ret60 = returns.get(60)
    if isinstance(ret60, (int, float)):
        tendency = "gestiegen" if ret60 > 0 else "gefallen" if ret60 < 0 else "unverändert geblieben"
        parts.append(f"Über die letzten 60 Sekunden ist der Preis um {abs(ret60) * 100:.3f}% {tendency}.")

    expansion = (momentum or {}).get("range_expansion")
    if isinstance(expansion, (int, float)):
        if expansion >= 1.5:
            parts.append("Die Handelsspanne weitet sich deutlich aus — die Bewegung nimmt an Umfang zu.")
        elif expansion <= 0.6:
            parts.append("Die Handelsspanne ist eng — der Markt komprimiert.")

    if flow_agreement == "CONFIRMED":
        parts.append(
            f"Spot- und Futures-Orderflow zeigen in dieselbe Richtung ({spot_direction}) — "
            "die Bestätigung durch Futures liegt vor."
        )
    elif flow_agreement == "DIVERGENT":
        parts.append(
            f"Spot-Orderflow ({spot_direction}) und Futures-Orderflow ({futures_direction}) "
            "widersprechen sich — es fehlt die Bestätigung durch Futures."
        )
    else:
        parts.append("Der Orderflow ist derzeit nicht eindeutig bestätigt.")

    if live_state != "LIVE":
        parts.append(
            "Achtung: der Vantage-Datenstrom ist aktuell nicht live "
            f"(Status {live_state}) — die Einschätzung kann veraltet sein."
        )
    parts.append("Ausführung ist deaktiviert. Dies ist ausschließlich eine Research-Einschätzung.")
    return " ".join(parts)


def why_no_signal(
    *,
    setup_state: str,
    direction: str,
    final_decision: str,
    flow_agreement: str,
    l2_aligned: bool | None,
    contradictions: list[str],
    sources: list[dict[str, Any]],
    spread: float | None,
    live_state: str,
) -> list[dict[str, str]]:
    """Checklist rows: status is one of MET / MISSING / RISK."""
    offline = [s["label"] for s in sources if not s["online"]]
    rows: list[dict[str, str]] = [
        {
            "label": "Datenquellen vollständig online",
            "status": "MET" if not offline else "MISSING",
            "detail": "Alle Quellen liefern Daten." if not offline else "Offline: " + ", ".join(offline),
        },
        {
            "label": "Vantage-Preis ist live",
            "status": "MET" if live_state == "LIVE" else "RISK" if live_state == "STALE" else "MISSING",
            "detail": f"Status des Vantage-Ticks: {live_state}.",
        },
        {
            "label": "Marktzustand mindestens ARMED",
            "status": "MET" if setup_state in {"ARMED", "SIGNAL"} else "MISSING",
            "detail": f"Aktueller Zustand der Zustandsmaschine: {setup_state}.",
        },
        {
            "label": "Eindeutiger Richtungs-Bias",
            "status": "MET" if direction in {"LONG", "SHORT"} else "MISSING",
            "detail": f"Richtungs-Bias: {direction}.",
        },
        {
            "label": "Futures bestätigen den Spot-Orderflow",
            "status": "MET" if flow_agreement == "CONFIRMED" else "MISSING",
            "detail": {
                "CONFIRMED": "Spot und Futures zeigen in dieselbe Richtung.",
                "DIVERGENT": "Spot und Futures widersprechen sich.",
            }.get(flow_agreement, "Orderflow ist neutral oder unvollständig."),
        },
        {
            "label": "Orderbuch (L2) stützt die Richtung",
            "status": "MET" if l2_aligned else "MISSING" if l2_aligned is not None else "RISK",
            "detail": "L2-Imbalance ist mit dem Richtungs-Bias ausgerichtet."
            if l2_aligned
            else "L2-Imbalance stützt den Richtungs-Bias nicht."
            if l2_aligned is not None
            else "Keine L2-Daten verfügbar.",
        },
        {
            "label": "Keine Widersprüche in den Signalen",
            "status": "MET" if not contradictions else "RISK",
            "detail": "Keine Widersprüche erfasst." if not contradictions else "; ".join(contradictions[:3]),
        },
        {
            "label": "Spread im akzeptablen Bereich",
            "status": "MET" if spread is not None and spread <= 25 else "RISK" if spread is not None else "MISSING",
            "detail": "Kein Spread verfügbar." if spread is None else f"Aktueller Spread: {spread:.2f} USD.",
        },
        {
            "label": "Endgültige Engine-Freigabe",
            "status": "MET" if final_decision not in {"BLOCKED", ""} else "MISSING",
            "detail": f"Entscheidung der Engine: {final_decision or 'UNBEKANNT'}.",
        },
    ]
    return rows


def _candidate_age_seconds(stamp: Any, now: datetime) -> float | None:
    """Age of the frozen collector's last candidate, or None when there is none."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0.0, now.timestamp() - parsed.timestamp())


class StateReader:
    def __init__(self, root: Path):
        self.root = root
        self.runtime = root / "runtime"
        self.ticks = TickCache(self.runtime / "waverun/vantage_ticks.jsonl")
        self.health_path = self.runtime / "waverun/health.json"
        self.latest_path = self.runtime / "waverun/latest.json"
        self.candidates_path = self.runtime / "waverun/pre_gate_candidates.jsonl"
        self.decisions_path = self.runtime / "waverun/decision_records.jsonl"
        # Pre-signal presentation layer. In-memory, process lifetime only. It reads
        # the fields below and never feeds anything back into the engine.
        self.presignal = PreSignalStateMachine()

    # ------------------------------------------------------------ resilience health

    def _decision_pipeline_age(self, now: datetime) -> float | None:
        """Age of the newest decision-pipeline write. A quiet market still writes
        one pre_gate record per evaluation second, so a large age here means the
        pipeline stopped processing, not that the market was quiet."""
        stamp = None
        latest = read_json(self.latest_path) or {}
        if latest.get("generated_at"):
            stamp = latest["generated_at"]
        rows = tail_jsonl(self.decisions_path, 1)
        if rows and rows[-1].get("timestamp"):
            stamp = rows[-1]["timestamp"]
        else:
            stamp = None
        return age_seconds(stamp, now)

    def _resilience(self, now: datetime, vantage_state: str, spot_state: str, futures_state: str, l2_state: str) -> dict[str, Any]:
        """Prefer the independent supervisor's health.json; fall back to an
        API-side computation so a stale decision pipeline is never shown as LIVE
        even if the supervisor is not (yet) running."""
        report = read_json(self.health_path) or {}
        report_age = age_seconds(report.get("server_time"), now)
        fresh = report_age is not None and report_age <= max(30.0, RES_CONFIG.supervisor_interval * 4)

        decision_age = self._decision_pipeline_age(now)
        if fresh and report.get("components"):
            comps = report["components"]
            overall = api_overall_label(compute_operating_state({k: ComponentHealth(**v) for k,v in comps.items()})[0])
            recovery = report.get("recovery", {})
        else:
            # Fallback: derive from the freshness signals the API already has.
            def st(state: str) -> str:
                return {"AVAILABLE": "HEALTHY", "LIVE": "HEALTHY", "CONNECTED": "HEALTHY"}.get(state, state)

            dp_state = (
                "HEALTHY" if decision_age is not None and decision_age <= RES_CONFIG.decision_stale_after
                else "STALE" if decision_age is not None and decision_age <= RES_CONFIG.decision_offline_after
                else "OFFLINE"
            )
            comps = {
                "vantage": ComponentHealth("vantage", st(vantage_state)).to_dict(),
                "binance_spot": ComponentHealth("binance_spot", st(spot_state)).to_dict(),
                "binance_futures": ComponentHealth("binance_futures", st(futures_state)).to_dict(),
                "l2": ComponentHealth("l2", st(l2_state)).to_dict(),
                "decision_pipeline": ComponentHealth("decision_pipeline", dp_state, age_seconds=decision_age).to_dict(),
                "prediction_persistence": ComponentHealth("prediction_persistence", 'UNKNOWN').to_dict(),
            }
            op_state, _ = compute_operating_state({k: ComponentHealth(**v) for k, v in comps.items()})
            overall = api_overall_label(op_state)
            recovery = {"level": 0, "attempts": 0}

        # Independently verify actual committed stage markers, even for a fresh report.
        progress=Journal.progress_at(self.runtime/'waverun/journal.db')
        for key,stage in [('binance_spot','feed_spot'),('binance_futures','feed_futures'),('l2','feed_l2'),('vantage','vantage')]:
            marker=progress.get(stage)
            age=max(now.timestamp()-marker['committed_at'],now.timestamp()-marker['event_at']) if marker else None
            if age is None or not 0<=age<=5:
                comps[key]=ComponentHealth(key,'OFFLINE',age_seconds=age,detail='source-specific freshness not proven').to_dict()
        if vantage_state not in {'AVAILABLE','LIVE','HEALTHY'}:
            comps['vantage']=ComponentHealth('vantage',vantage_state).to_dict()
        for key,stage in [('feature_pipeline','features'),('candidate_pipeline','candidates'),('decision_pipeline','decisions'),('prediction_persistence','predictions'),('outcome_scheduler','outcome_scheduler'),('storage','storage')]:
            marker=progress.get(stage)
            age=max(now.timestamp()-marker['committed_at'],now.timestamp()-marker['event_at']) if marker else None
            state='HEALTHY' if age is not None and 0<=age<=RES_CONFIG.decision_stale_after else 'OFFLINE'
            comps[key]=ComponentHealth(key,state,age_seconds=age).to_dict()
        if not fresh:
            comps['disk']=ComponentHealth('disk','UNKNOWN').to_dict()
        writer_path=self.runtime/'waverun/writer_health.json'
        if writer_path.exists():
            writer=read_json(writer_path) or {}
            writer_age=age_seconds(writer.get('timestamp'),now)
            if not writer.get('ready') or writer_age is None or writer_age>5:
                comps['storage']=ComponentHealth('storage','OFFLINE',detail='writer/archiver not ready or stale').to_dict()
        if decision_age is not None and decision_age>RES_CONFIG.decision_stale_after:
            comps['decision_pipeline']=ComponentHealth('decision_pipeline','OFFLINE' if decision_age>RES_CONFIG.decision_offline_after else 'STALE',age_seconds=decision_age,detail='decision record disagrees with progress marker').to_dict()
        op_state,reasons=compute_operating_state({k:ComponentHealth(**v) for k,v in comps.items()})
        overall=api_overall_label(op_state)
        # Defence in depth: never allow a global healthy label while the decision
        # pipeline is demonstrably stale, whatever health.json claims.
        if decision_age is not None and decision_age > RES_CONFIG.decision_stale_after and overall in {"LIVE", "STARTING"}:
            overall = "CRITICAL" if decision_age > RES_CONFIG.decision_offline_after else "DEGRADED"

        return {
            "overall": overall,
            "operating_state": op_state.value,
            "decision_pipeline_age_seconds": None if decision_age is None else round(decision_age, 1),
            "components": comps,
            "recovery": recovery,
            "supervisor_report_age_seconds": None if report_age is None else round(report_age, 1),
            "reasons": reasons,
        }

    def snapshot(self) -> dict[str, Any]:
        ticks = self.ticks.refresh()
        latest_tick = ticks[-1] if ticks else {}
        forecast_snapshot = read_json(self.runtime / "waverun/latest.json") or {}
        validation = read_json(self.runtime / "waverun_v5_3_fast_v2_forward/status.json") or {}
        decisions = tail_jsonl(self.runtime / "waverun/pre_gate_candidates.jsonl", 1)
        decision = decisions[-1] if decisions else {}

        now = datetime.now(UTC)
        age = None
        if latest_tick:
            age = max(0.0, now.timestamp() - _epoch_seconds(latest_tick))
        live_state = (
            "OFFLINE"
            if age is None
            else "LIVE"
            if age <= LIVE_MAX_AGE_S
            else "STALE"
            if age <= STALE_MAX_AGE_S
            else "OFFLINE"
        )

        health = validation.get("source_health", {}) or {}
        feeds = health.get("feeds", {}) or {}
        availability = decision.get("availability", {}) or {}
        spot_state = _feed_state(feeds, "spot")
        futures_state = _feed_state(feeds, "futures")
        l2_state = str(availability.get("l2", "UNAVAILABLE"))
        vantage_state = "AVAILABLE" if live_state == "LIVE" else "STALE" if live_state == "STALE" else "OFFLINE"

        # The V5.3 status.json feed block freezes together with the spot trade
        # path. Prefer the independent supervisor's live feed_health.json when it
        # is fresher, so a dead spot feed is never masked by a stale "CONNECTED".
        supervisor_feeds = read_json(self.runtime / "waverun/feed_health.json") or {}
        if age_seconds(supervisor_feeds.get("server_time"), now) is not None and (
            age_seconds(supervisor_feeds.get("server_time"), now) <= max(30.0, RES_CONFIG.supervisor_interval * 4)
        ):
            sf = supervisor_feeds.get("feeds", {}) or {}
            if sf.get("spot", {}).get("state"):
                spot_state = str(sf["spot"]["state"])
            if sf.get("futures", {}).get("state"):
                futures_state = str(sf["futures"]["state"])

        sources = [
            {"key": "vantage", "label": "Vantage (MT5)", "state": vantage_state, "online": _online(vantage_state)},
            {"key": "binance_spot", "label": "Binance Spot", "state": spot_state, "online": _online(spot_state)},
            {"key": "binance_futures", "label": "Binance Futures", "state": futures_state, "online": _online(futures_state)},
            {"key": "orderbook_l2", "label": "Orderbuch L2", "state": l2_state, "online": _online(l2_state)},
            {
                "key": "forward_validator",
                "label": "Forward-Validator",
                "state": str(validation.get("recorder_health", "OFFLINE")),
                "online": _online(str(validation.get("recorder_health", "OFFLINE"))),
            },
        ]

        setup_state = str(forecast_snapshot.get("state", "NEUTRAL"))
        direction = str(decision.get("direction_bias", "NEUTRAL") or "NEUTRAL")
        final_decision = str(decision.get("final_decision", ""))
        long_score = float(decision.get("long_pressure_score", 0.0) or 0.0)
        short_score = float(decision.get("short_pressure_score", 0.0) or 0.0)
        pressure = long_score if direction == "LONG" else short_score if direction == "SHORT" else max(long_score, short_score)
        momentum = decision.get("momentum_pressure_state") or {}

        spot = _signal(decision, "spot_flow_10s")
        futures = _signal(decision, "futures_flow_10s")
        spot_direction = str(spot.get("direction", "UNAVAILABLE"))
        futures_direction = str(futures.get("direction", "UNAVAILABLE"))
        if spot_direction in {"BULLISH", "BEARISH"} and spot_direction == futures_direction:
            flow_agreement = "CONFIRMED"
        elif spot_direction in {"BULLISH", "BEARISH"} and futures_direction in {"BULLISH", "BEARISH"}:
            flow_agreement = "DIVERGENT"
        else:
            flow_agreement = "NEUTRAL"

        imbalance = momentum.get("l2_imbalance")
        l2_aligned: bool | None = None
        if isinstance(imbalance, (int, float)) and direction in {"LONG", "SHORT"}:
            l2_aligned = (imbalance > 0) if direction == "LONG" else (imbalance < 0)

        bid, ask = latest_tick.get("bid"), latest_tick.get("ask")
        spread = latest_tick.get("spread")
        price = (float(bid) + float(ask)) / 2.0 if bid is not None and ask is not None else None

        resolved = int(validation.get("resolved_signals", 0) or 0)

        checklist = why_no_signal(
            setup_state=setup_state,
            direction=direction,
            final_decision=final_decision,
            flow_agreement=flow_agreement,
            l2_aligned=l2_aligned,
            contradictions=list(decision.get("contradictions", []) or []),
            sources=sources,
            spread=float(spread) if isinstance(spread, (int, float)) else None,
            live_state=live_state,
        )

        # TESTSIGNAL mirrors the frozen V5.3 collector's own last candidate. We only
        # read its timestamp; candidate selection and veto logic stay untouched.
        candidate_age = _candidate_age_seconds(validation.get("last_candidate_timestamp"), now)
        returns = momentum.get("returns") if isinstance(momentum, dict) else None
        return_60s = None
        if isinstance(returns, dict):
            raw_return = returns.get("60", returns.get(60))
            if isinstance(raw_return, (int, float)):
                return_60s = float(raw_return)

        presignal = self.presignal.update(
            Evidence(
                setup_state=setup_state,
                direction=direction,
                pressure=pressure,
                flow_agreement=flow_agreement,
                l2_aligned=l2_aligned,
                return_60s=return_60s,
                range_expansion=momentum.get("range_expansion") if isinstance(momentum, dict) else None,
                sources_online=all(source["online"] for source in sources),
                price_live=live_state == "LIVE",
                contradictions=tuple(str(item) for item in (decision.get("contradictions") or [])),
                v5_3_candidate_age_s=candidate_age,
                v5_3_candidate_accepted=candidate_age is not None
                and int(validation.get("accepted_signals", 0) or 0) > 0,
            )
        )

        res = self._resilience(now, vantage_state, spot_state, futures_state, l2_state)

        return {
            "server_time": now.isoformat(),
            # `connection` is the rolled-up operating state, NOT bare vantage
            # freshness. A stale decision pipeline can no longer read as "LIVE".
            "connection": res["overall"],
            "vantage_connection": live_state,
            "overall": res["overall"],
            "operating_state": res["operating_state"],
            "health": {
                "overall": res["overall"],
                "operating_state": res["operating_state"],
                "decision_pipeline_age_seconds": res["decision_pipeline_age_seconds"],
                "supervisor_report_age_seconds": res["supervisor_report_age_seconds"],
                "reasons": res["reasons"],
                "components": res["components"],
                "recovery": res["recovery"],
            },
            "recovery": res["recovery"],
            "price": {
                "symbol": latest_tick.get("symbol", "BTCUSD"),
                "mid": price,
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "age_seconds": None if age is None else round(age, 2),
                "timestamp": latest_tick.get("timestamp"),
            },
            "market_state": {
                "setup_state": setup_state,
                "direction_bias": direction,
                "final_decision": final_decision,
                "long_pressure_score": round(long_score, 1),
                "short_pressure_score": round(short_score, 1),
                "flow_agreement": flow_agreement,
                "spot_flow": spot_direction,
                "futures_flow": futures_direction,
                "l2_imbalance": imbalance if isinstance(imbalance, (int, float)) else None,
                "range_expansion": momentum.get("range_expansion"),
                "realized_volatility": momentum.get("realized_volatility"),
                "flow_pressure": momentum.get("flow_pressure"),
            },
            "assessment": assessment_text(
                setup_state=setup_state,
                direction=direction,
                pressure=pressure,
                momentum=momentum,
                flow_agreement=flow_agreement,
                spot_direction=spot_direction,
                futures_direction=futures_direction,
                live_state=live_state,
            ),
            "proximity": proximity_score(
                setup_state=setup_state,
                direction=direction,
                pressure=pressure,
                flow_agreement=flow_agreement,
                l2_aligned=l2_aligned,
                sources_online=sum(1 for s in sources if s["online"]),
                sources_total=len(sources),
            ),
            "checklist": checklist,
            "presignal": presignal,
            "alerts": self.presignal.alerts(),
            "sources": sources,
            "v5_3": {
                "discovery_win_rate": V5_3_DISCOVERY_WIN_RATE,
                "discovery_label": "Discovery",
                "forward_resolved": resolved,
                "forward_target": V5_3_FORWARD_TARGET,
                "forward_progress": str(validation.get("progress_to_100", f"0/{V5_3_FORWARD_TARGET}")),
                "forward_wins": int(validation.get("successes_100_5m", 0) or 0),
                "accepted_signals": int(validation.get("accepted_signals", 0) or 0),
                "veto_blocked_signals": int(validation.get("veto_blocked_signals", 0) or 0),
                "provisional_rate": validation.get("provisional_rate"),
                "verified": False,
                "status": str(validation.get("status", "PROVISIONAL")),
                "hypothesis_sha256": HYPOTHESIS_SHA256,
            },
            "execution": EXECUTION,
            "tick_count": len(ticks),
        }


def create_app(root: Path | None = None) -> FastAPI:
    reader = StateReader(root or repo_root())
    app = FastAPI(title="WAVERUN Web API", version="1.0.0", docs_url="/api/docs")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "OK",
            "root": str(reader.root),
            "execution": EXECUTION,
            "server_time": datetime.now(UTC).isoformat(),
        }

    @app.get("/api/timeframes")
    def timeframes() -> dict[str, Any]:
        return {
            "timeframes": [{"key": key, "seconds": value} for key, value in TIMEFRAMES.items()],
            "source": "VANTAGE_BTCUSD_TICKS",
            "has_volume": False,
        }

    @app.get("/api/candles")
    def candles(
        timeframe: str = Query("1m"),
        limit: int = Query(500, ge=10, le=5000),
    ) -> dict[str, Any]:
        if timeframe not in TIMEFRAMES:
            raise HTTPException(status_code=400, detail=f"unsupported timeframe: {timeframe}")
        ticks = reader.ticks.refresh()
        rows = build_candles(ticks, TIMEFRAMES[timeframe], limit)
        return {
            "symbol": "BTCUSD",
            "source": "VANTAGE_MT5",
            "timeframe": timeframe,
            "has_volume": False,
            "tick_count": len(ticks),
            "candles": rows,
            "execution": EXECUTION,
        }

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return reader.snapshot()

    @app.get("/api/presignal")
    def presignal() -> dict[str, Any]:
        """Pre-signal state plus the deduplicated alert events the UI may announce."""
        snapshot = reader.snapshot()
        return {
            "server_time": snapshot["server_time"],
            "presignal": snapshot["presignal"],
            "alerts": snapshot["alerts"],
            "execution": EXECUTION,
        }

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        async def events():
            while True:
                payload = await asyncio.to_thread(reader.snapshot)
                yield f"data: {json.dumps(payload, default=str)}\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
