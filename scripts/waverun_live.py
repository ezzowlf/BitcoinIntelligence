from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import threading
import uuid
import copy
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from waverun_sqlite_diagnostic import install as _install_diagnostic
if __name__ == '__main__':
    _install_diagnostic()

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.live.mt5_isolated import IsolatedMT5Provider
from bitcoin_cycle_analyzer.short_term.api import ForecastSnapshot
from bitcoin_cycle_analyzer.short_term.binance import BinancePublicFeed
from bitcoin_cycle_analyzer.short_term.contracts import MarketTick
from bitcoin_cycle_analyzer.short_term.engine import ShortTermEngine
from bitcoin_cycle_analyzer.short_term.events import EventType
from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
from bitcoin_cycle_analyzer.short_term.resilience import age_seconds as _res_age_seconds
from bitcoin_cycle_analyzer.short_term.journal import Journal,identity,atomic_json
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine,HORIZONS
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine
from bitcoin_cycle_analyzer.short_term.move_tracker import MoveTracker
from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures
from bitcoin_cycle_analyzer.short_term.archive import RawWriter
from bitcoin_cycle_analyzer.short_term.storage_policy import StorageMaintenance
from bitcoin_cycle_analyzer.short_term.orderbook import OrderBookState
from bitcoin_cycle_analyzer.short_term.rolling_bars import RollingTradeBars
from bitcoin_cycle_analyzer.short_term.pressure import (
    completed_bars,
    macd_features,
    momentum_pressure_state,
)
from bitcoin_cycle_analyzer.short_term.storage import ForecastStore
from bitcoin_cycle_analyzer.short_term.v5_3_forward import ForwardV2Collector
from bitcoin_cycle_analyzer.waverun_decision import (
    DecisionInput,
    DecisionSignal,
    fast_decision,
)


class LiveSession:
    def __init__(self, output: Path, database: Path, symbol: str, mt5_values: dict[str, str] | None = None):
        self.output, self.engine, self.store = output, ShortTermEngine(), ForecastStore(database)
        self.feed = BinancePublicFeed(symbol, include_futures=True)
        self.book = OrderBookState()
        self.last_book = None
        self.last_trade = None
        self.decision_path = self.output.with_name("decision_records.jsonl")
        self.event_path = self.output.with_name("market_events.jsonl")
        self.candidate_path = self.output.with_name("pre_gate_candidates.jsonl")
        self.latency_path = self.output.with_name("latency_records.jsonl")
        self.vantage_tick_path = self.output.with_name("vantage_ticks.jsonl")
        self._last_vantage_time_msc = None
        self._last_candidate_heartbeat = 0.0
        self._last_decision_heartbeat = 0.0
        self._last_latency_heartbeat = 0.0
        self._last_journal_heartbeat = 0.0
        self.trade_buffer = deque(maxlen=200_000)
        self.rolling_bars = RollingTradeBars(maxlen=self.trade_buffer.maxlen)
        self.flow_buffer = {"spot": deque(maxlen=100_000), "futures": deque(maxlen=100_000)}
        self.last_evaluation_second = None
        self.mt5 = IsolatedMT5Provider(values=mt5_values)
        self._mt5_last_health_write = 0.0
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.v2_forward = ForwardV2Collector(ROOT / "runtime/waverun_v5_3_fast_v2_forward")
        self._last_v2_bar = None
        # --- B-2 resilience wiring -----------------------------------------
        self._last_vantage_wall: datetime | None = None
        self._feed_task: asyncio.Task | None = None
        self._supervisor: HealthSupervisor | None = None
        self._callback = None
        self.journal=Journal(self.output.parent/'journal.db')
        self.outcomes=OutcomeEngine(self.journal)
        self.signals=SignalEngine(self.journal,self.outcomes)
        self.moves=MoveTracker(self.journal)
        self.causal_features=CausalFeatures()
        self.raw_writer=None
        self._process_lock=threading.RLock()
        self._data_lock=threading.RLock()
        self._spot_lock=threading.Lock()
        self._book_samples=deque(maxlen=8192)
        self._depth_samples=deque(maxlen=8192)
        self._vantage_samples=deque(maxlen=8192)
        self._mt5_lock=threading.RLock()
        self._event_queues={}
        self._worker_error=None
        self._source_marker_second={}
        # --- HOTFIX on 85bc61e: consumer backpressure (was: EVENT_QUEUE_FULL storm) --
        # A full CONSUMER queue is NOT a transport fault. Replaceable high-rate
        # depth/book events are coalesced (drop-oldest); causally required trade
        # events are only shed under genuine severe stall, then counted and used
        # to degrade data quality -> suppress NEW live signals. Never a reconnect
        # storm, never FALSE-LIVE. Memory stays bounded by the fixed queue size.
        self._bp={'coalesced':{}, 'dropped':{}}
        self._bp_severe_until=0.0
        self._bp_last_write=0.0
        self._queue_metrics={}
        self.backpressure_path=self.output.parent/'backpressure.json'

    _ROTATED_KEEP=8  # bounded backlog per stem; rotated files duplicate what journal.db (14-day prune) already retains durably
    _JSONL_HEARTBEAT_S=10.0  # max staleness health_supervisor's _last_jsonl_timestamp can see on a routine (non-candidate) second
    _JOURNAL_HEARTBEAT_S=60.0  # one full routine evaluation is committed per minute; liveness marks still fire every second
    _rotated_since_start:set = set()  # only files THIS process rotated are ever auto-deleted - never a pre-existing backlog

    @staticmethod
    def _append(path: Path, value: dict) -> None:
        if path.exists() and path.stat().st_size>8*1024*1024:
            rotated_path=path.with_name(path.stem+'.'+uuid.uuid4().hex+path.suffix)
            path.rename(rotated_path)
            LiveSession._rotated_since_start.add(str(rotated_path))
            own=sorted((p for p in path.parent.glob(path.stem+'.*'+path.suffix) if str(p) in LiveSession._rotated_since_start),key=lambda p:p.stat().st_mtime)
            for old in (own[:-LiveSession._ROTATED_KEEP] if len(own)>LiveSession._ROTATED_KEEP else []):
                old.unlink(missing_ok=True);LiveSession._rotated_since_start.discard(str(old))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, sort_keys=True, default=str) + "\n")

    def _record_event(self, event) -> None:
        if self.raw_writer:
            return  # full wire frame already entered the bounded raw writer
        self._append(self.event_path, {
            "event_type": event.event_type.value, "exchange": event.exchange, "symbol": event.symbol,
            "exchange_timestamp": event.exchange_timestamp, "received_timestamp": event.received_timestamp,
            "timestamp_source": event.timestamp_source, "payload": event.payload, "execution": "DISABLED",
        })

    def _record_vantage_tick(self) -> None:
        with self._mt5_lock:tick = self.mt5.tick()
        if time.monotonic()-getattr(self,'_mt5_last_health_write',0)>=1 and hasattr(self,'output'):
            atomic_json(self.output.parent/'mt5_health.json',{'timestamp':datetime.now(UTC).isoformat(),**self.mt5.health()})
            self._mt5_last_health_write=time.monotonic()
        if tick.get("status") != "AVAILABLE" or tick.get("time_msc") is None:
            if tick.get('reason') != 'MT5_POLL_PENDING':
                # A causal failure marker supersedes prior quotes only from
                # the moment the failure was observed, never retroactively.
                now=datetime.now(UTC)
                with self._data_lock:
                    self._vantage_samples.append((now,{'status':'UNAVAILABLE','timestamp':now,'reason':tick.get('reason')}))
            return
        time_msc = int(tick["time_msc"])
        if self._last_vantage_time_msc is not None and time_msc <= self._last_vantage_time_msc:
            return
        self._last_vantage_time_msc = time_msc
        with self._data_lock:
            self._vantage_samples.append((datetime.now(UTC),dict(tick)))
        record = {
            "time_msc": time_msc, "timestamp": pd.Timestamp(tick["timestamp"]).tz_convert("UTC").isoformat(),
            "bid": tick["bid"], "ask": tick["ask"], "last": tick.get("last", 0.0),
            "flags": tick.get("flags", 0), "spread": tick["spread"], "symbol": tick.get("symbol"),
            "source": "MT5_VANTAGE", "execution": "DISABLED",
        }
        self._append(self.vantage_tick_path, record)
        self._last_vantage_wall = datetime.now(UTC)
        self.outcomes.quote(record['timestamp'],record['bid'],record['ask'])
        self.journal.mark('vantage',identity(record['time_msc']),record['timestamp'])
        self.moves.quote(record['timestamp'],record['bid'],record['ask'])
        self.v2_forward.record_vantage_tick(record)

    def _flow_delta(self, market: str, now: datetime) -> float:
        with self._data_lock:
            active = [row for row in self.flow_buffer[market] if 0 <= (now - row[0]).total_seconds() <= 10]
        buy = sum(row[1] for row in active)
        sell = sum(row[2] for row in active)
        return (buy - sell) / (buy + sell) if buy + sell else 0.0

    async def _vantage_recorder(self, stop: asyncio.Event) -> None:
        fails=0
        while not stop.is_set():
            try:
                await asyncio.to_thread(self._record_vantage_tick)
                fails=0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # One transient MT5/journal error must not permanently kill this
                # task for the rest of the boot (was: unguarded -> task died ->
                # vantage_ticks.jsonl froze with zero incident/recovery for the
                # remaining process lifetime).
                fails+=1
                if fails<=5 or fails%600==0:
                    self.journal.append('incident',identity('vantage-recorder',time.time()),datetime.now(UTC),
                        {'reason':'VANTAGE_RECORDER_ERROR','error':type(exc).__name__,'fails':fails,'execution':'DISABLED'})
            try:
                await asyncio.wait_for(stop.wait(), timeout=min(5.0,0.1*(1+fails)))
            except TimeoutError:
                pass

    def _flow_signal(self, market: str, now: datetime) -> DecisionSignal | None:
        with self._data_lock:
            buffer = self.flow_buffer[market]
            while buffer and (now - buffer[0][0]).total_seconds() > 10:
                buffer.popleft()
            rows = [row for row in buffer if row[0] <= now]
        if not rows:
            return None
        buy = sum(row[1] for row in rows)
        sell = sum(row[2] for row in rows)
        total = buy + sell
        delta = (buy - sell) / total if total else 0.0
        return DecisionSignal("FLOW", f"{market}_flow_10s", "BULLISH" if delta > .05 else "BEARISH" if delta < -.05 else "NEUTRAL", min(1.0, abs(delta)), f"{market} normalized flow delta={delta:.4f}")

    async def _refresh_book(self) -> None:
        snapshot = await asyncio.to_thread(
            requests.get,
            "https://api.binance.com/api/v3/depth",
            params={"symbol": self.feed.symbol.upper(), "limit": 1000},
            timeout=10,
        )
        snapshot.raise_for_status()
        payload = snapshot.json()
        with self._data_lock:
            self.book.seed_snapshot(
                int(payload["lastUpdateId"]),
                [(float(price), float(quantity)) for price, quantity in payload["bids"]],
                [(float(price), float(quantity)) for price, quantity in payload["asks"]],
            )

    async def on_event(self, event):
        receive_ns = time.perf_counter_ns()
        self._record_event(event)
        if event.event_type == EventType.DEPTH:
            result = await asyncio.to_thread(self._apply_depth,event)
            if result in {"GAP", "NEEDS_SNAPSHOT"}:
                self.feed.health.get('l2',self.feed.health['spot']).gap()
                await self._refresh_book()
            await asyncio.to_thread(self._mark_source,event)
            return
        await asyncio.to_thread(self._evaluate_locked,event)
        await asyncio.to_thread(self._mark_source,event)

    def _mark_source(self,event):
        source='l2' if event.event_type==EventType.DEPTH else event.payload.get('market','spot')
        timestamp=event.exchange_timestamp
        if timestamp is None:return  # receive-only events cannot prove source freshness
        second=int(timestamp.timestamp())
        if second<=self._source_marker_second.get(source,-1):return
        self.journal.mark('feed_'+source,identity(source,timestamp,event.received_timestamp),timestamp)
        self._source_marker_second[source]=second

    def _evaluate_locked(self,event):
        if event.event_type == EventType.TRADE and event.payload.get('market','spot') == 'spot':
            with self._spot_lock:return self._evaluate_event(event)
        return self._evaluate_event(event)

    def _apply_depth(self,event):
        with self._data_lock:
            result=self.book.apply(event)
            self._depth_samples.append((event.received_timestamp,self.book.imbalance(),self.book.synchronized))
            return result

    def _evaluate_event(self,event):
        receive_ns=time.perf_counter_ns()
        if event.event_type == EventType.BOOK_TICKER:
            with self._data_lock:
                self.last_book = event
                self._book_samples.append(event)
            return
        if event.event_type != EventType.TRADE:
            return
        payload = event.payload
        market = payload.get("market", "spot")
        buy = payload["quantity"] if not payload["buyer_is_maker"] else 0.0
        sell = payload["quantity"] if payload["buyer_is_maker"] else 0.0
        with self._data_lock:
            self.causal_features.trade(market,event.received_timestamp,payload['price'],payload['quantity'],payload['buyer_is_maker'])
            self.flow_buffer[market].append((event.received_timestamp, buy, sell))
        if market == "futures":
            return
        self.last_trade = event
        received = event.received_timestamp
        # The collector evaluates once per received second, but Spot can deliver
        # hundreds of trades in that second.  Looking up the causal book/depth/
        # MT5 snapshots for every discarded intra-second trade scanned up to
        # 8,192 entries per stream and made the only Spot consumer fall behind.
        # Preserve every trade in the causal buffers, then resolve snapshots only
        # for the trade that actually creates the one-second evaluation.
        self.trade_buffer.append((received, payload["price"], payload["quantity"], buy, sell))
        self.rolling_bars.append(self.trade_buffer[-1])
        evaluation_second = int(received.timestamp())
        if self.last_evaluation_second == evaluation_second:
            return
        self.last_evaluation_second = evaluation_second
        with self._data_lock:
            last_book=next((row for row in reversed(self._book_samples) if row.received_timestamp<=event.received_timestamp),None)
            bid = last_book.payload['bid'] if last_book else None
            ask = last_book.payload['ask'] if last_book else None
            depth=next((row for row in reversed(self._depth_samples) if row[0]<=event.received_timestamp),None)
            book_imbalance = depth[1] if depth else None
            book_synchronized = depth[2] if depth else False
            quote=next((dict(row) for available,row in reversed(self._vantage_samples)
                        if available<=event.received_timestamp and pd.Timestamp(row['timestamp'])<=event.received_timestamp),{'status':'UNAVAILABLE'})
        exchange_timestamp = event.exchange_timestamp or received
        tick = MarketTick(payload["price"], exchange_timestamp, received, datetime.now(UTC), event.exchange, payload["quantity"], payload["quantity"] if not payload["buyer_is_maker"] else 0.0, payload["quantity"] if payload["buyer_is_maker"] else 0.0, bid, ask, book_imbalance)
        forecasts = self.engine.process(tick, "LIVE", received)
        imbalance = book_imbalance
        signals = []
        if imbalance is not None:
            signals.append(DecisionSignal("L2", "imbalance_10", "BULLISH" if imbalance > .05 else "BEARISH" if imbalance < -.05 else "NEUTRAL", min(1, abs(imbalance) * 5), f"10-level imbalance={imbalance:.4f}"))
        for source_market in ("spot", "futures"):
            flow_signal = self._flow_signal(source_market, received)
            if flow_signal:
                signals.append(flow_signal)
        momentum = None
        if len(self.trade_buffer) >= 10:
            bars = self.rolling_bars.completed(1, pd.Timestamp(received), limit=2)
            if len(bars) >= 2:
                momentum = momentum_pressure_state(bars, l2_imbalance=imbalance)
        features_ready_ns = time.perf_counter_ns()
        decision = fast_decision(DecisionInput("BTCUSDT", received.isoformat(), tuple(signals), 1.0, tick.age_seconds(received), "UNKNOWN", "LIVE", None, False))
        cause=identity('evaluation',received.isoformat())
        states=self.feed.refresh_states(received)
        quote_age=(received-pd.Timestamp(quote['timestamp']).to_pydatetime()).total_seconds() if quote.get('timestamp') else None
        source_states={'spot':'HEALTHY' if states.get('spot')=='CONNECTED' else 'UNAVAILABLE','futures':'HEALTHY' if states.get('futures')=='CONNECTED' else 'UNAVAILABLE','l2':'HEALTHY' if states.get('l2')=='CONNECTED' and book_synchronized else 'UNAVAILABLE','vantage':'HEALTHY' if quote.get('status')=='AVAILABLE' and quote_age is not None and 0<=quote_age<=3 else 'UNAVAILABLE'}
        if time.time()<self._bp_severe_until:
            # Severe consumer backpressure shed causally required trades -> the
            # spot/L2 evidence is no longer trustworthy: the existing data-quality
            # gate in SignalEngine.evaluate() will suppress NEW live signals.
            source_states['spot']='UNAVAILABLE';source_states['l2']='UNAVAILABLE'
        markers=Journal.progress_at(self.journal.path)
        outcome_ready='outcome_scheduler' in markers and 0<=received.timestamp()-markers['outcome_scheduler']['committed_at']<=10
        with self._data_lock:
            compact=self.causal_features.snapshot(received,quote,l2=imbalance,feed_health=source_states,storage_ready=self.raw_writer is not None and self.raw_writer.ready and not getattr(self.feed,'ledger_error',None),outcomes_ready=outcome_ready)
        compact['cause_id']=cause
        with self._process_lock:
            transition=self.signals.evaluate(received,compact)
            signal_snapshot=copy.deepcopy(self.signals.snapshot())
            atomic_json(self.output.with_name('signal.json'),signal_snapshot)
        decision_ns = time.perf_counter_ns()
        self.decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_record = decision.to_record()
        mt5_quote = quote
        self.v2_forward.heartbeat(mt5_quote, self.feed.status())
        bars30 = self.rolling_bars.completed(30, pd.Timestamp(received), limit=35) if len(self.trade_buffer) >= 10 else pd.DataFrame()
        if len(bars30) >= 35 and bars30.index[-1] != self._last_v2_bar:
            self._last_v2_bar = bars30.index[-1]
            macd = macd_features(bars30["close"])
            latest = macd.iloc[-1]
            frozen_inputs = {
                "macd_30s_cross_direction": float(latest["cross_direction"]),
                "macd_30s_histogram": float(latest["histogram"]),
                "macd_30s_histogram_slope": float(latest["histogram_slope"]),
                "macd_30s_histogram_acceleration": float(latest["histogram_acceleration"]),
            }
            self.v2_forward.observe(received, frozen_inputs, self._flow_delta("spot", received), mt5_quote, {
                "spot_state": self.feed.health["spot"].to_dict(),
                "futures_state": self.feed.health["futures"].to_dict(),
                "l2_state": "AVAILABLE" if imbalance is not None else "UNAVAILABLE",
                "source_health": self.feed.status(),
            })
        targets = [100, 150, 200, 300, 400, 500]
        adverse = [25, 50, 75, 100, 150]
        horizons = [60, 90, 120, 180, 300, 600]
        decision_record["causal_input"] = {
            "symbol": "BTCUSDT",
            "timestamp": received.isoformat(),
            "bid": bid,
            "ask": ask,
            "spread": (ask - bid) if bid is not None and ask is not None else None,
            "signals": [
                {"group": s.group, "name": s.name, "direction": s.direction,
                 "strength": s.strength, "explanation": s.explanation, "available": s.available}
                for s in signals
            ],
            "data_quality": 1.0,
            "freshness_seconds": tick.age_seconds(received),
            "timing": "UNKNOWN",
            "regime": "LIVE",
            "expected_edge_after_cost": None,
            "calibrated": False,
            "mt5_quote": mt5_quote,
            "momentum_pressure_state": asdict(momentum) if momentum else None,
        }
        candidate_record = {
            "timestamp": received, "direction_bias": decision.direction,
            "long_pressure_score": max(0.0, decision.directional_edge * 100),
            "short_pressure_score": max(0.0, -decision.directional_edge * 100),
            "targets_usd": targets, "adverse_usd": adverse, "horizons_seconds": horizons,
            "momentum_pressure_state": asdict(momentum) if momentum else None,
            "signals": decision_record["causal_input"]["signals"], "contradictions": decision.contradictions,
            "availability": {"mt5": mt5_quote.get("status"), "l2": "AVAILABLE" if imbalance is not None else "UNAVAILABLE",
                             "spot_flow": "AVAILABLE", "futures_flow": "AVAILABLE" if self.flow_buffer["futures"] else "UNAVAILABLE"},
            "cost_state": {"status": "RESEARCH_PROXY", "spread": mt5_quote.get("spread")},
            "final_decision": decision.decision, "execution": "DISABLED",
        }
        # Result-oriented JSONL persistence (storage gate <=100MB/24h): BLOCKED/WATCH
        # is the routine, non-actionable outcome of fast_decision() on almost every
        # evaluated second. health_supervisor only needs a recent timestamp in these
        # files to judge liveness (_last_jsonl_timestamp), not every second's row, so
        # routine seconds get a heartbeat write at most once per _JSONL_HEARTBEAT_S -
        # an actual candidate/decision (ARMED/APPROVED) always writes immediately,
        # same as before. This is the JSONL-row-count analogue of the journal payload
        # shrink below; nothing here changes fast_decision(), SignalEngine, thresholds
        # or outcome computation.
        relevant = decision.decision not in ('BLOCKED', 'WATCH')
        now_mono = time.monotonic()
        if relevant or now_mono - self._last_candidate_heartbeat >= self._JSONL_HEARTBEAT_S:
            self._append(self.candidate_path, candidate_record)
            self._last_candidate_heartbeat = now_mono
        if relevant or now_mono - self._last_decision_heartbeat >= self._JSONL_HEARTBEAT_S:
            self._append(self.decision_path, decision_record)
            self._last_decision_heartbeat = now_mono
        persisted_ns = time.perf_counter_ns()
        if relevant or now_mono - self._last_latency_heartbeat >= self._JSONL_HEARTBEAT_S:
            self._append(self.latency_path, {
                "timestamp": received, "receive_to_features_ms": (features_ready_ns - receive_ns) / 1e6,
                "features_to_decision_ms": (decision_ns - features_ready_ns) / 1e6,
                "decision_to_persist_ms": (persisted_ns - decision_ns) / 1e6,
                "receive_to_persist_ms": (persisted_ns - receive_ns) / 1e6, "execution": "DISABLED",
            })
            self._last_latency_heartbeat = now_mono
        # Keep the semantic event order but commit the evaluation as one journal
        # transaction.  This prevents a normal one-second evaluation from
        # competing with itself for SQLite's only writer slot. `features` was
        # measured (WAVERUN_JOURNAL_DIAG_MIN_S diagnostic, 2026-09-16/17) to add
        # its own full wait+commit cycle every evaluated second - p50 lock wait
        # 109ms vs p50 hold 63ms, i.e. contention from the number of separate
        # writer sections dominated over any single commit's own cost. Folding
        # it into this same transaction removes one whole cycle per second;
        # nothing reads the features row back before this point in the function.
        #
        # Result-oriented persistence (storage gate <=100MB/24h): BLOCKED/WATCH is
        # the routine, non-actionable outcome of fast_decision() on almost every
        # evaluated second (no qualifying edge). Writing a features/candidate/
        # decision row per second was ~344k permanent rows/day that only ever
        # existed to be pruned again later; the live in-memory state they
        # duplicate is never read back for a routine second.
        #
        # What still happens EVERY second, unchanged: the feature/candidate/
        # decision/prediction liveness marks, which is what feature_pipeline/
        # candidate_pipeline/decision_pipeline health and recovery detection
        # actually read (progress table, via progress_at()). A periodic
        # heartbeat still commits one full routine evaluation per
        # _JOURNAL_HEARTBEAT_S so routine behaviour stays inspectable and
        # unsuccessful/negative context is not silently erased.
        #
        # An actual candidate (ARMED/APPROVED, i.e. `relevant`) always commits
        # the complete payload immediately, exactly as before. Nothing here
        # changes fast_decision(), SignalEngine, thresholds, or how outcomes are
        # computed - only which routine intermediates become permanent rows.
        journal_heartbeat_due = now_mono - self._last_journal_heartbeat >= self._JOURNAL_HEARTBEAT_S
        with self.journal.connect() as db:
            if relevant or journal_heartbeat_due:
                self._last_journal_heartbeat = now_mono
                for entry in (
                    {'kind':'features','id':cause,'timestamp':received,
                     'payload':compact if relevant else {'cause_id':cause,'decision':decision.decision,'state':decision.state},
                     'stage':'features','cause_id':cause},
                    {'kind':'candidate','id':cause,'timestamp':received,
                     'payload':{'legacy_direction':decision.direction,'signal_setup':signal_snapshot} if relevant else {'legacy_direction':decision.direction},
                     'stage':'candidates','cause_id':cause},
                    {'kind':'decision','id':cause,'timestamp':received,
                     'payload':{'legacy':decision.to_record(),'signal':transition,'version':'shadow-flow-l2-v1'} if relevant else {'legacy':{'decision':decision.decision,'state':decision.state,'direction':decision.direction},'version':'shadow-flow-l2-v1'},
                     'stage':'decisions','cause_id':cause},
                ):
                    self.journal.append(connection=db,**entry)
            else:
                for stage in ('features','candidates','decisions'):
                    self.journal.mark_on(db,stage,cause,received)
            self.journal.mark_on(db,'predictions',cause,received)
        # Outcome observations were the single largest persistent producer: 6
        # per-horizon forecast registrations plus one 9-horizon candidate
        # registration every evaluated second = 15 observations/s, each
        # resolving into a permanent `outcome` row (~1.3M rows/day, over half of
        # the 11GB journal.db). A routine BLOCKED/WATCH second has no signal
        # whose result anyone acts on, so its forecast set is sampled on the
        # same heartbeat rather than tracked exhaustively.
        #
        # This is a sampling decision, NOT a survivorship filter: the sample is
        # periodic and taken before the result is known, so routine seconds that
        # would have gone on to be wrong are represented exactly as often as
        # ones that would have gone on to be right. Every `relevant` decision -
        # every real candidate, including the ones that fail - is still
        # registered in full across all horizons, and false_warning/missed_move
        # remain untouched, so signal quality stays honestly measurable.
        if relevant or journal_heartbeat_due:
            self.store.append_many(forecasts)
            forecast_registrations=[
                (identity('prediction',forecast.timestamp.isoformat(),forecast.horizon_seconds),
                 'prediction',forecast.timestamp,
                 'LONG' if forecast.p_up>=forecast.p_down else 'SHORT',None,None,None,
                 (forecast.horizon_seconds,),{'prediction_timestamp':forecast.timestamp.isoformat()})
                for forecast in forecasts
            ]
            forecast_registrations.append((cause,'candidate',received,decision.direction,None,None,None,HORIZONS,None))
            self.outcomes.register_many(forecast_registrations)
        snapshot = ForecastSnapshot.from_forecasts(forecasts, "LIVE", self.feed.status(), payload["price"], tick.age_seconds(received))
        self.output.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _vantage_age(self) -> float | None:
        if getattr(self.mt5,'reason','MT5_CURRENT_TICK')!='MT5_CURRENT_TICK':return None
        return _res_age_seconds(self._last_vantage_wall)

    async def _recreate_feed_task(self) -> None:
        """Ask stable feed owners to replace children; never cancel the session waiter."""
        if hasattr(self.feed,'request_reconnect'):
            for market in self.feed.health:self.feed.request_reconnect(market)

    async def _reinit_subcomponents(self) -> None:
        """Auto-repair Level 3: rebuild the order book and re-seed it; reconnect MT5."""
        with self._data_lock:
            self.book = OrderBookState()
            self.last_book = None
            self._book_samples.clear()
            self._depth_samples.clear()
        try:
            await self._refresh_book()
        except Exception:  # noqa: BLE001
            pass
        await self._recreate_feed_task()

    _BP_SEVERE_HOLD=20.0  # seconds a shed critical event keeps signal generation degraded

    def _bp_bump(self,kind,key):
        table=self._bp[kind]
        table[key]=table.get(key,0)+1

    def _bp_flush(self,force=False):
        now=time.time()
        if not force and now-self._bp_last_write<1.0:return
        self._bp_last_write=now
        payload={'updated_at':datetime.now(UTC).isoformat(),
                 'severe':now<self._bp_severe_until,
                 'queues':{k:{'size':q.qsize(),'capacity':q.maxsize} for k,q in self._event_queues.items()},
                 'coalesced':dict(self._bp['coalesced']),
                 'dropped':dict(self._bp['dropped']),
                 'metrics':getattr(self,'_queue_metrics',{}),
                 'execution':'DISABLED'}
        try:atomic_json(self.backpressure_path,payload)
        except OSError:pass

    def _queue_key(self,event):
        # BOOK_TICKER is the highest-rate, fully-replaceable stream: give it its
        # own coalescing lane so causally required spot/futures TRADEs are never
        # starved out of their queue.
        if event.event_type==EventType.DEPTH:return 'l2'
        if event.event_type==EventType.BOOK_TICKER:return 'book'
        return event.payload.get('market','spot')

    async def _dispatch_event(self,event):
        key=self._queue_key(event)
        if not hasattr(self,'_queue_metrics'):self._queue_metrics={}
        metrics=self._queue_metrics.setdefault(key,{'produced':0,'consumed':0,'failed':0,'processing_seconds':0.0,'max_event_age_seconds':0.0})
        metrics['produced']+=1
        queue=self._event_queues[key]
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Bounded backpressure: evict the OLDEST queued event and enqueue the
            # newest. Memory stays bounded; the freshest market state is kept. A
            # full consumer queue is NEVER a transport disconnect and NEVER
            # triggers a reconnect (that was the EVENT_QUEUE_FULL storm).
            try:
                stale=queue.get_nowait();queue.task_done()
            except asyncio.QueueEmpty:
                stale=None
            if stale is not None and stale.event_type==EventType.TRADE:
                # A causally required trade was shed: visible + counted, and it
                # degrades data quality (suppresses NEW live signals) instead of
                # being silently lost.
                self._bp_bump('dropped',key)
                self._bp_severe_until=time.time()+self._BP_SEVERE_HOLD
            else:
                # depth / bookTicker are replaceable high-frequency state -> coalesce
                self._bp_bump('coalesced',key)
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._bp_bump('dropped' if event.event_type==EventType.TRADE else 'coalesced',key)
                if event.event_type==EventType.TRADE:
                    self._bp_severe_until=time.time()+self._BP_SEVERE_HOLD
        self._bp_flush()

    async def _consume_events(self,key,stop):
        fails=deque(maxlen=64)
        while not stop.is_set():
            event=await self._event_queues[key].get()
            started=time.perf_counter()
            try:
                await asyncio.wait_for(self.on_event(event),timeout=10)
                metrics=getattr(self,'_queue_metrics',{}).get(key)
                if metrics is not None:
                    metrics['consumed']+=1
                    metrics['processing_seconds']+=time.perf_counter()-started
                    metrics['last_event_age_seconds']=max(0,(datetime.now(UTC)-event.received_timestamp).total_seconds())
                    metrics['max_event_age_seconds']=max(metrics['max_event_age_seconds'],metrics['last_event_age_seconds'])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                import traceback
                metrics=getattr(self,'_queue_metrics',{}).get(key)
                if metrics is not None:metrics['failed']+=1
                now=time.time();fails.append(now);recent=sum(1 for x in fails if now-x<=30)
                self._worker_error='WORKER_FAILED:'+key+':'+type(exc).__name__
                self.journal.append('incident',identity(self._worker_error,now),datetime.now(UTC),
                    {'reason':self._worker_error,'traceback':traceback.format_exc()[-1800:],'recent_30s':recent})
                if recent>=12:
                    # genuinely broken consumer -> hand recovery to the process watchdog
                    self.feed.health.get(key,self.feed.health['spot']).disconnect(self._worker_error)
                    return
                continue  # one poison event/window must not freeze the whole feed
            finally:self._event_queues[key].task_done()

    async def _outcome_scheduler(self,stop):
        fails=0
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.outcomes.catch_up_registrations)
                # A post-outage backlog must not monopolize SQLite's sole
                # writer long enough to stall live market consumers.  Each
                # pass is deliberately bounded; the loop immediately resumes
                # on the next tick and outcome delivery remains idempotent.
                await asyncio.to_thread(self.outcomes.resolve_due,datetime.now(UTC),limit=100)
                cursor=await asyncio.to_thread(self.journal.state,'forecast_outcome_cursor',0)
                events=await asyncio.to_thread(self.journal.rows,'outcome',after=cursor,limit=1000)
                if events:
                    await asyncio.to_thread(self._apply_outcome_events,events)
                await asyncio.to_thread(self._signal_maintenance)
                fails=0
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # A transient SQLite-busy / IO error must not permanently kill the
                # outcome scheduler (was: task died -> outcome_scheduler marker
                # frozen -> operating_state stuck off FULL_LIVE).
                fails+=1
                import traceback
                if fails<=5 or fails%600==0:
                    self.journal.append('incident',identity('outcome-sched',time.time()),datetime.now(UTC),
                        {'reason':'OUTCOME_SCHEDULER_ERROR','error':type(exc).__name__,'fails':fails,'traceback':traceback.format_exc()[-1200:],'execution':'DISABLED'})
                await asyncio.sleep(min(10.0,1.0*fails))

    def _apply_outcome_events(self,events):
        predictions=[(e['payload']['observation']['prediction_timestamp'],e['payload']['horizon_seconds'],e['payload'])
                     for e in events if e['payload']['kind']=='prediction']
        if predictions:self.store.apply_resolutions(predictions)
        with self._process_lock:
            for event in events:
                # Only LIVE resolutions can change SignalEngine state.
                if event['payload']['kind']=='LIVE':self.signals.accept_outcome(event['payload'])
            self.signals.tick(datetime.now(UTC))
            atomic_json(self.output.parent/'signal.json',self.signals.snapshot())
        # Persist cursor only after every consumer succeeded; replay is idempotent.
        self.journal.save('forecast_outcome_cursor',events[-1]['seq'])

    def _signal_maintenance(self,row=None):
        with self._process_lock:
            if row:self.signals.accept_outcome(row)
            self.signals.tick(datetime.now(UTC))
            atomic_json(self.output.parent/'signal.json',self.signals.snapshot())

    async def run(self, duration: float | None):
        print("WAVERUN ENGINE STARTING\nDATA FEEDS CONNECTING\nFEATURE ENGINE READY\nPREDICTION ENGINE READY")
        stop = asyncio.Event()
        recorder = asyncio.create_task(self._vantage_recorder(stop))
        self._callback = self.on_event
        supervisor_task: asyncio.Task | None = None
        workers=[];outcome_task=None
        try:
            try:
                await self._refresh_book()
            except Exception as exc:  # noqa: BLE001 - a transient REST failure must not kill startup
                print(f"WARN initial order-book snapshot failed ({type(exc).__name__}); will seed on first depth gap")
            if duration is None:
                self.raw_writer=RawWriter(self.output.parent/'raw',self.journal)
                # expire_archives_dry_run=True: the existing production raw/ backlog
                # predates this expiry mechanism and largely qualifies as unpinned/
                # WARM-aged right away. Ship this counting what it WOULD delete
                # (storage_health.json.raw_archives_expirable_dry_run) first, so the
                # backlog's impact is reviewed before a separate explicit decision
                # turns live deletion on - never a silent first-run mass delete of
                # pre-existing history.
                maintenance=StorageMaintenance(self.raw_writer.root,self.journal,self.outcomes,expire_archives_dry_run=True)
                self.raw_writer.maintenance=maintenance.run
                self.raw_writer.start()
                self.feed=BinancePublicFeed(self.feed.symbol,include_futures=True,separate_l2=True)
                # Result-oriented persistence (2026-09-17, storage gate <=100MB/24h):
                # the full Binance wire-frame stream (every spot/futures trade, every
                # L2 depth update) is no longer archived continuously - measured
                # ~3.85GB/day and nothing in production ever read it back at runtime;
                # the signal engine computes entirely off the live in-memory buffers
                # (trade_buffer/rolling_bars/book/flow_buffer) below, never off raw/.
                # The market snapshot at an actual signal/candidate T0 is already
                # captured durably by the compact features/decision/signal_transition
                # journal rows (bid/ask/l2/mt5 quote), which is what a relevant-event
                # snapshot means here. raw_writer/archiver keep running unfed so their
                # health/ready reporting and existing-backlog archival are unaffected;
                # they just receive nothing new to write.
                self.feed.lifecycle_sink=lambda row:self.journal.append('feed_lifecycle',identity(row,time.time()),row['timestamp'],row)
                # Trade evidence is non-replaceable.  Size the independent
                # lanes for a bounded SQLite/IO pause; bookTicker remains a
                # replaceable lane and is intentionally smaller.
                self._event_queues={key:asyncio.Queue(maxsize=32768) for key in self.feed.health}
                self._event_queues['book']=asyncio.Queue(maxsize=8192)  # replaceable bookTicker lane
                workers=[asyncio.create_task(self._consume_events(key,stop),name='consume-'+key) for key in self._event_queues]
                outcome_task=asyncio.create_task(self._outcome_scheduler(stop))
                self._callback=self._dispatch_event
                # Production path: run the feed as a supervised task and start the
                # independent health supervisor (Phases 7-10).
                self._feed_task = asyncio.create_task(self.feed.run(self._callback, None))
                self._supervisor = HealthSupervisor(
                    runtime_dir=self.output.parent,
                    feed=self.feed,
                    vantage_age=self._vantage_age,
                    recreate_feed_task=self._recreate_feed_task,
                    reinit_subcomponents=self._reinit_subcomponents,
                )
                supervisor_task = asyncio.create_task(self._supervisor.run())
                await self._feed_task
            else:
                await self.feed.run(self.on_event, duration)
        finally:
            stop.set()
            for task in workers:task.cancel()
            if outcome_task:outcome_task.cancel()
            await asyncio.gather(*workers,*([outcome_task] if outcome_task else []),return_exceptions=True)
            if self.raw_writer:await asyncio.to_thread(self.raw_writer.close)
            if self._supervisor is not None:
                self._supervisor.stop()
            if supervisor_task is not None:
                supervisor_task.cancel()
                try:
                    await supervisor_task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            await recorder
            self.mt5.close()


def main():
    parser = argparse.ArgumentParser(description="WAVERUN observation-only Binance live prototype")
    parser.add_argument("--duration", type=float, default=None, help="stop after N seconds; default runs until interrupted")
    parser.add_argument("--symbol", default="btcusdt")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "waverun" / "latest.json")
    parser.add_argument("--database", type=Path, default=ROOT / "database" / "waverun_predictions.db")
    parser.add_argument("--mt5-enabled", action="store_true", help="enable read-only MT5 market data")
    parser.add_argument("--mt5-terminal-path", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    args = parser.parse_args()
    try:
        mt5_values = {"MT5_ENABLED": "true", "MT5_TERMINAL_PATH": args.mt5_terminal_path} if args.mt5_enabled else None
        asyncio.run(LiveSession(args.output, args.database, args.symbol, mt5_values).run(args.duration))
    except KeyboardInterrupt:
        print("WAVERUN ENGINE STOPPED")


if __name__ == "__main__":
    main()
