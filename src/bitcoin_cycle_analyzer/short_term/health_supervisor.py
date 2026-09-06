"""Independent health supervisor + pipeline watchdog + staged auto-repair
(Phases 7-10, 14, 16).

The supervisor runs as its own periodic asyncio task. It NEVER depends on a
market-event callback: it derives every component state from age of the last
valid event / last runtime write, so it keeps working even when every feed is
frozen. It:

  * refreshes feed freshness (age-based, socket object is not proof),
  * watches the intelligence pipeline itself (candidate / decision / prediction
    writes) and distinguishes "quiet market" from "pipeline not processing",
  * rolls components up into one OperatingState,
  * records every transition to the incident log and raises deduplicated alerts,
  * runs staged auto-repair (Level 1 feed-internal .. Level 4 restart request),
  * only declares RECOVERED after real new data flow is verified,
  * continuously writes runtime/waverun/health.json (the independent freshness
    writer) so the API and an external monitor never see a false LIVE.

No signal maths, thresholds or V5.3 rules are touched. Execution stays DISABLED.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from .alerting import (
    CRITICAL,
    CRITICAL_ALERT,
    DEGRADED,
    HIGH,
    INFO,
    RECOVERY_WARNING,
    WARNING,
    AlertManager,
)
from .incident_log import IncidentLog
from .journal import Journal, atomic_json, identity
from .resilience import (
    CONFIG,
    ComponentHealth,
    OperatingState,
    age_seconds,
    api_overall_label,
    compute_operating_state,
)

EXECUTION = "DISABLED"


def _last_jsonl_timestamp(path: Path, field_names=("received_timestamp", "timestamp")) -> str | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size == 0:
        return None
    with path.open("rb") as handle:
        handle.seek(max(0, size - 65536))
        chunk = handle.read()
    for line in reversed(chunk.split(b"\n")):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        for name in field_names:
            if row.get(name):
                return str(row[name])
    return None


@dataclass
class _RepairState:
    level: int = 0
    attempts: int = 0
    last_action_at: float = 0.0
    restart_requests: list[float] = field(default_factory=list)


@dataclass
class HealthSupervisor:
    runtime_dir: Path
    feed: Any                                   # BinancePublicFeed
    # callables the collector provides so the supervisor can act without importing it
    vantage_age: Callable[[], float | None]
    recreate_feed_task: Callable[[], Awaitable[None]] | None = None
    reinit_subcomponents: Callable[[], Awaitable[None]] | None = None
    alert_manager: AlertManager | None = None
    incident_log: IncidentLog | None = None
    interval: float = CONFIG.supervisor_interval
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    _prev: dict[str, str] = field(default_factory=dict)
    _recovery_baselines: dict = field(default_factory=dict)
    _repair: _RepairState = field(default_factory=_RepairState)
    _started_at: float = field(default_factory=time.monotonic)
    _last_seen_market_ts: str | None = None
    _last_seen_decision_ts: str | None = None
    _recovery_pending: set[str] = field(default_factory=set)
    _running: bool = True
    last_report: dict[str, Any] = field(default_factory=dict)
    _loop: Any = None

    def __post_init__(self) -> None:
        self.runtime_dir = Path(self.runtime_dir)
        self.runtime_dir.mkdir(parents=True,exist_ok=True)
        self.journal_path=self.runtime_dir/'journal.db'
        try:
            saved=json.loads((self.runtime_dir/'restart_budget.json').read_text())
            self._repair.restart_requests=saved.get('requests',[])
        except (OSError,ValueError):pass
        if self.incident_log is None:
            self.incident_log = IncidentLog(self.runtime_dir / "incidents.jsonl")
        if self.alert_manager is None:
            self.alert_manager = AlertManager(self.runtime_dir / "alerts.jsonl", incident_log=self.incident_log)

    # --------------------------------------------------------------- lifecycle

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._loop=asyncio.get_running_loop()
        while self._running:
            try:
                await asyncio.to_thread(self.tick)
            except Exception as exc:  # noqa: BLE001 - the supervisor must never die
                try:
                    self.incident_log.record(
                        component="health_supervisor", previous_state="RUNNING", new_state="TICK_ERROR",
                        reason=f"{type(exc).__name__}: {exc}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(self.interval)

    # ------------------------------------------------------------------- tick

    def collect(self) -> dict[str, ComponentHealth]:
        now = self.clock()
        components: dict[str, ComponentHealth] = {}

        # feeds: age-based refresh; works with zero events flowing
        feed_states = self.feed.refresh_states(now)
        for market in ("spot", "futures"):
            fh = self.feed.health[market]
            components[f"binance_{market}"] = ComponentHealth(
                key=f"binance_{market}",
                state=feed_states.get(market, fh.state),
                last_event_at=fh.last_event_at.isoformat() if fh.last_event_at else None,
                age_seconds=fh.age_seconds(now),
                reconnect_count=fh.reconnects,
                last_error=fh.last_error,
                recovery_level=self._repair.level if market == "spot" else 0,
            )

        # vantage (independent recorder thread)
        v_age = self.vantage_age()
        components["vantage"] = ComponentHealth(
            key="vantage",
            state=self._age_state(v_age, CONFIG.feed_stale_after, CONFIG.feed_offline_after),
            age_seconds=v_age,
        )

        # L2 rides on the spot depth stream
        spot_state = components["binance_spot"].state
        l2=self.feed.health.get('l2')
        components["l2"] = ComponentHealth(
            key="l2",
            state=l2.refresh(now) if l2 else 'UNKNOWN',
            detail="independent depth connection and sequence validation",
        )

        # pipeline watchdog (Phase 8): only meaningful while the driving feed is fresh
        rt = self.runtime_dir
        market_ts = _last_jsonl_timestamp(rt / "market_events.jsonl")
        candidate_ts = _last_jsonl_timestamp(rt / "pre_gate_candidates.jsonl")
        decision_ts = _last_jsonl_timestamp(rt / "decision_records.jsonl")
        pred_age = self._prediction_age()

        spot_fresh = components["binance_spot"].state in {"CONNECTED", "HEALTHY"}
        components["decision_pipeline"] = ComponentHealth(
            key="decision_pipeline",
            state=self._pipeline_state(decision_ts, candidate_ts, spot_fresh, now),
            last_event_at=decision_ts,
            age_seconds=age_seconds(decision_ts, now),
            detail="quiet market is not a fault; state only degrades when spot is fresh but writes stopped",
        )
        components["candidate_pipeline"] = ComponentHealth(
            key="candidate_pipeline",
            state=self._pipeline_state(candidate_ts, market_ts, spot_fresh, now),
            last_event_at=candidate_ts,
            age_seconds=age_seconds(candidate_ts, now),
        )
        components["prediction_persistence"] = ComponentHealth(
            key="prediction_persistence",
            state=self._age_state(
                pred_age, CONFIG.prediction_stale_after, CONFIG.prediction_offline_after
            ) if spot_fresh else "IDLE_FEED_DOWN",
            age_seconds=pred_age,
        )
        markers=Journal.progress_at(self.journal_path)
        # market_event_pipeline: the monolithic market_events.jsonl was retired in
        # favour of the RawWriter/journal. Track the newest per-market feed marker
        # (feed_spot/feed_futures/feed_l2), falling back to writer_health.json.
        _feed_marks=[markers.get(s) for s in ('feed_spot','feed_futures','feed_l2')]
        _feed_ts=max((m['committed_at'] for m in _feed_marks if m), default=None)
        _wh_age=None
        try:
            _wh=json.loads((rt/'writer_health.json').read_text())
            _wh_age=age_seconds(_wh.get('timestamp'),now) if _wh.get('ready') else None
        except (OSError,ValueError):
            pass
        _mep_age=(max(0.0,now.timestamp()-_feed_ts) if _feed_ts is not None else _wh_age)
        components["market_event_pipeline"] = ComponentHealth(
            key="market_event_pipeline",
            state=self._age_state(_mep_age, CONFIG.feed_stale_after, CONFIG.feed_offline_after),
            last_event_at=(datetime.fromtimestamp(_feed_ts,UTC).isoformat() if _feed_ts is not None else None),
            age_seconds=_mep_age,
            detail="journal feed_* markers + writer_health (market_events.jsonl retired)",
        )
        # consumer_backpressure: a full processing queue is separate from transport
        # health. Coalescing replaceable book/depth is fine; shedding causally
        # required trades degrades data quality (and suppresses new LIVE signals).
        try:
            _bp=json.loads((rt/'backpressure.json').read_text())
            _bp_age=age_seconds(_bp.get('updated_at'),now)
            _dropped=sum(int(v) for v in (_bp.get('dropped') or {}).values())
            _coalesced=sum(int(v) for v in (_bp.get('coalesced') or {}).values())
            if _bp_age is not None and _bp_age<=30:
                _bp_state='CRITICAL' if _bp.get('severe') else ('DEGRADED' if _dropped>0 else 'HEALTHY')
            else:
                _bp_state='HEALTHY'
            components['consumer_backpressure']=ComponentHealth(
                'consumer_backpressure',_bp_state,age_seconds=_bp_age,
                detail=f"dropped_trades={_dropped} coalesced={_coalesced} severe={bool(_bp.get('severe'))}")
        except (OSError,ValueError):
            components['consumer_backpressure']=ComponentHealth('consumer_backpressure','HEALTHY',detail='no backpressure telemetry yet')
        for key,stage in [('feature_pipeline','features'),('candidate_pipeline','candidates'),('decision_pipeline','decisions'),('prediction_persistence','predictions'),('outcome_scheduler','outcome_scheduler'),('storage','storage')]:
            marker=markers.get(stage)
            if marker:
                age=max(0,now.timestamp()-marker['committed_at'])
                event_age=max(0,now.timestamp()-marker['event_at'])
                components[key]=ComponentHealth(key,self._age_state(max(age,event_age),CONFIG.decision_stale_after,CONFIG.decision_offline_after),age_seconds=max(age,event_age),last_event_at=datetime.fromtimestamp(marker['event_at'],UTC).isoformat(),detail='committed sequence '+str(marker['seq']))
            elif key not in components:
                components[key]=ComponentHealth(key,'OFFLINE',detail='no durable progress marker')

        # disk
        writer_path=rt/'writer_health.json'
        if writer_path.exists():
            try:
                writer=json.loads(writer_path.read_text())
                if not writer.get('ready') or (age_seconds(writer.get('timestamp'),now) or 0)>5:
                    components['storage']=ComponentHealth('storage','OFFLINE',detail=writer.get('error') or 'writer/archiver not ready')
            except (OSError,ValueError):components['storage']=ComponentHealth('storage','OFFLINE',detail='writer health unreadable')
        if getattr(self.feed,'ledger_error',None):
            components['storage']=ComponentHealth('storage','OFFLINE',detail=self.feed.ledger_error)
        try:
            free_gb = shutil.disk_usage(str(rt)).free / 1e9
        except OSError:
            free_gb = None
        components["disk"] = ComponentHealth(
            key="disk",
            state="HEALTHY" if (free_gb is not None and free_gb >= CONFIG.disk_min_free_gb) else "OFFLINE",
            detail=None if free_gb is None else f"{free_gb:.1f} GB free",
        )
        disk_path=rt/'storage_health.json'
        if disk_path.exists():
            try:
                disk_state=json.loads(disk_path.read_text())
                if not disk_state.get('new_signals_allowed',False):components['disk']=ComponentHealth('disk','OFFLINE',detail='disk budget '+str(disk_state.get('tier')))
            except (OSError,ValueError):components['disk']=ComponentHealth('disk','OFFLINE',detail='disk budget unreadable')
        return components

    def tick(self) -> dict[str, Any]:
        now = self.clock()
        starting = (time.monotonic() - self._started_at) < CONFIG.startup_grace
        components = self.collect()
        op_state, reasons = compute_operating_state(components, starting=starting)

        # transitions -> incident log + alerts
        self._diff_and_alert(components, op_state, now)
        self._maybe_repair(components, op_state, now)
        self._verify_recovery(components, now)

        report = {
            'boot_id':os.environ.get('WAVERUN_BOOT_ID'),
            "server_time": now.isoformat(),
            "operating_state": op_state.value,
            "overall": api_overall_label(op_state),
            "reasons": reasons,
            "execution": EXECUTION,
            "starting": starting,
            "recovery": {"level": self._repair.level, "attempts": self._repair.attempts},
            "components": {k: c.to_dict() for k, c in components.items()},
        }
        self.last_report = report
        self._write_health_json(report)
        return report

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _age_state(age: float | None, stale_after: float, offline_after: float) -> str:
        if age is None:
            return "OFFLINE"
        if age > offline_after:
            return "OFFLINE"
        if age > stale_after:
            return "STALE"
        return "HEALTHY"

    def _pipeline_state(self, this_ts: str | None, driver_ts: str | None, driver_fresh: bool, now: datetime) -> str:
        """A pipeline stage is only 'bad' when its driver is fresh but it stopped
        advancing. If the driver (spot) is itself down, the stage is CRITICAL by
        way of the driver, not blamed here -> report DEGRADED (feed-driven)."""
        this_age = age_seconds(this_ts, now)
        if not driver_fresh:
            return "DEGRADED"  # nothing to process; the real fault is upstream
        if this_age is None:
            return "OFFLINE"
        if this_age > CONFIG.decision_offline_after:
            return "OFFLINE"
        if this_age > CONFIG.decision_stale_after:
            return "STALE"
        return "HEALTHY"

    def _prediction_age(self) -> float | None:
        marker=Journal.progress_at(self.journal_path).get('predictions')
        if marker:return max(0,self.clock().timestamp()-marker['committed_at'])
        for db in (
            self.runtime_dir.parent.parent / "database" / "waverun_predictions.db",
            self.runtime_dir.parent / "database" / "waverun_predictions.db",
        ):
            try:
                if not db.exists():continue
                conn=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=.2)
                try:row=conn.execute('SELECT MAX(timestamp) FROM predictions').fetchone()
                finally:conn.close()
                return age_seconds(row[0],self.clock()) if row and row[0] else None
            except (OSError,sqlite3.Error):
                continue
        return None

    def _diff_and_alert(self, components: dict[str, ComponentHealth], op_state: OperatingState, now: datetime) -> None:
        _healthy = {"HEALTHY", "CONNECTED", "LIVE", "IDLE_FEED_DOWN", "UNKNOWN"}
        for key, comp in components.items():
            prev = self._prev.get(key)
            if prev == comp.state:
                continue
            self._prev[key] = comp.state
            if prev is None:
                if comp.state in _healthy:
                    continue  # first observation of a healthy component: no incident
                prev = "UNKNOWN"  # collector started with this component already unhealthy
            self.incident_log.record(
                component=key, previous_state=prev, new_state=comp.state,
                reason=comp.last_error or comp.detail or "state change",
                last_event_age=comp.age_seconds, operating_state=op_state.value,
            )
            # alert policy
            if comp.state in {"STALE", "DEGRADED"} and key in {"binance_spot", "binance_futures", "vantage", "decision_pipeline", "candidate_pipeline", "prediction_persistence", "market_event_pipeline"}:
                sev = HIGH if key in {"binance_spot", "decision_pipeline"} else WARNING
                self.alert_manager.notify(
                    component=key, kind=DEGRADED, severity=sev,
                    message=f"{key} {comp.state} (age {comp.age_seconds}s).",
                    detail={
                        "vantage": components["vantage"].state,
                        "binance_spot": components["binance_spot"].state,
                        "binance_futures": components["binance_futures"].state,
                        "decision_pipeline": components["decision_pipeline"].state,
                        "operating_state": op_state.value,
                        "auto_recovery": "ACTIVE",
                    },
                )
            elif comp.state == "OFFLINE" and key in {"binance_spot", "decision_pipeline", "vantage"}:
                self.alert_manager.notify(
                    component=key, kind=CRITICAL_ALERT, severity=CRITICAL,
                    message=f"{key} OFFLINE. Minimum data basis for new decisions is not available.",
                    detail={
                        "last_valid_event": comp.last_event_at,
                        "operating_state": op_state.value,
                        "recovery_action": f"auto-repair level {self._repair.level}",
                    },
                )
                self._recovery_pending.add(key)
            elif comp.state in {"CONNECTED", "HEALTHY"} and prev in {"STALE", "DEGRADED", "OFFLINE", "RECONNECTING", "CONNECTING"}:
                # candidate for RECOVERED, but only after data-flow verification
                self._recovery_pending.add(key)

    def _maybe_repair(self, components: dict[str, ComponentHealth], op_state: OperatingState, now: datetime) -> None:
        spot = components["binance_spot"]
        stalled=[k for k in ('decision_pipeline','candidate_pipeline','prediction_persistence','feature_pipeline','outcome_scheduler','storage') if components.get(k) and components[k].state in {'OFFLINE','STALE','DEGRADED'}]
        unhealthy = bool(stalled) or spot.state in {"OFFLINE"} or (spot.state in {"STALE", "DEGRADED", "RECONNECTING"} and (spot.age_seconds or 0) > CONFIG.alert_degraded_after)
        if not unhealthy:
            if self._repair.level and spot.state in {"CONNECTED", "HEALTHY"}:
                self._repair.level = 0
                self._repair.attempts = 0
            return

        if (time.monotonic() - self._repair.last_action_at) < CONFIG.repair_cooldown:
            return
        self._repair.last_action_at = time.monotonic()
        self._repair.attempts += 1

        # Level 1 is the feed's own internal reconnect loop (already running).
        if self._repair.level == 0:
            self._repair.level = 1
        elif self._repair.level == 1 and self._repair.attempts >= CONFIG.repair_level1_max:
            self._repair.level = 2
            self._escalate("recreate feed task", 2, now)
            if self.recreate_feed_task:
                self._schedule(self.recreate_feed_task)
        elif self._repair.level == 2 and self._repair.attempts >= CONFIG.repair_level1_max + CONFIG.repair_level2_max:
            self._repair.level = 3
            self._escalate("re-init subcomponents", 3, now)
            if self.reinit_subcomponents:
                self._schedule(self.reinit_subcomponents)
        elif self._repair.level == 3 and self._repair.attempts >= CONFIG.repair_level1_max + CONFIG.repair_level2_max + CONFIG.repair_level3_max:
            self._request_restart(now)
        elif self._repair.level >= 4:
            # keep requesting a controlled restart on each cooldown; the budget
            # check inside _request_restart is what enforces loop protection.
            self._request_restart(now)

    def _schedule(self,coro_factory):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._safe(coro_factory),self._loop)
        else:asyncio.get_running_loop().create_task(self._safe(coro_factory))

    async def _safe(self, coro_factory: Callable[[], Awaitable[None]]) -> None:
        try:
            await asyncio.wait_for(coro_factory(),timeout=10)
        except Exception as exc:  # noqa: BLE001
            self.incident_log.record(
                component="auto_repair", previous_state=f"LEVEL_{self._repair.level}", new_state="ACTION_FAILED",
                reason=f"{type(exc).__name__}: {exc}",
            )

    def _escalate(self, action: str, level: int, now: datetime) -> None:
        self.incident_log.record(
            component="binance_spot", previous_state=f"LEVEL_{level - 1}", new_state=f"LEVEL_{level}",
            reason="repeated recovery failure", recovery_action=action,
        )
        if self._repair.attempts >= CONFIG.alert_recovery_warning_failures:
            self.alert_manager.notify(
                component="binance_spot", kind=RECOVERY_WARNING, severity=HIGH,
                message=f"Binance Spot not restored after {self._repair.attempts} attempts. Engine running DEGRADED.",
                detail={"recovery_level": level, "next_action": action},
            )

    def _request_restart(self, now: datetime) -> None:
        # restart-loop protection: bounded number of Level-4 requests per window
        window_start = now.timestamp() - CONFIG.restart_budget_window
        self._repair.restart_requests = [t for t in self._repair.restart_requests if t >= window_start]
        if len(self._repair.restart_requests) >= CONFIG.restart_budget:
            self.incident_log.record(
                component="auto_repair", previous_state="LEVEL_3", new_state="LEVEL_4_SUPPRESSED",
                reason=f"restart budget exhausted ({CONFIG.restart_budget}/{CONFIG.restart_budget_window:.0f}s)",
                recovery_result="MANUAL_INTERVENTION_REQUIRED",
            )
            self.alert_manager.notify(
                component="collector", kind=CRITICAL_ALERT, severity=CRITICAL,
                message="Auto-repair exhausted restart budget. Manual intervention required.",
                detail={"recovery_level": 4},
            )
            return
        self._repair.restart_requests.append(now.timestamp())
        atomic_json(self.runtime_dir/'restart_budget.json',{'requests':self._repair.restart_requests,'execution':EXECUTION})
        self._repair.level = 4
        payload = {
            'boot_id':os.environ.get('WAVERUN_BOOT_ID'),
            'request_id':identity(os.environ.get('WAVERUN_BOOT_ID'),now.isoformat(),len(self._repair.restart_requests)),
            "timestamp": now.isoformat(),
            "reason": "auto-repair level 4: binance_spot unrecovered after levels 1-3",
            "requests_in_window": len(self._repair.restart_requests),
            "execution": EXECUTION,
        }
        try:
            atomic_json(self.runtime_dir/'restart_request.json',payload)
        except OSError:
            pass
        self.incident_log.record(
            component="collector", previous_state="LEVEL_3", new_state="LEVEL_4",
            reason="controlled collector restart requested", recovery_action="write restart_request.json",
        )

    def _verify_recovery(self, components: dict[str, ComponentHealth], now: datetime) -> None:
        """RECOVERED only after real new data flow (Phase 10)."""
        if not self._recovery_pending:
            return
        progress=Journal.progress_at(self.journal_path)
        required=('features','candidates','decisions','predictions','outcome_scheduler','storage','feed_spot','vantage')
        for key in self._recovery_pending:
            if key not in self._recovery_baselines:
                self._recovery_baselines[key]={s:progress.get(s,{}).get('seq',0) for s in required}
        eligible=set()
        for key in self._recovery_pending:
            baseline=self._recovery_baselines[key]
            if all(s in progress and progress[s]['seq']>baseline[s] and 0<=now.timestamp()-progress[s]['committed_at']<=CONFIG.decision_stale_after and 0<=now.timestamp()-progress[s]['event_at']<=(5 if s in {'feed_spot','vantage'} else CONFIG.decision_stale_after) for s in required):
                causes={progress[s]['cause_id'] for s in ('features','candidates','decisions','predictions')}
                if len(causes)==1:eligible.add(key)
        if not eligible:return

        for key in list(self._recovery_pending):
            if key not in eligible:continue
            comp = components.get(key)
            if comp is None:
                self._recovery_pending.discard(key)
                self._recovery_baselines.pop(key,None)
                continue
            healthy = comp.state in {"CONNECTED", "HEALTHY"}
            verified = healthy and components['decision_pipeline'].state in {'HEALTHY','CONNECTED'}
            if verified:
                self.alert_manager.resolve(
                    component=key, kind=DEGRADED,
                    message=f"{key} back to LIVE. Post-reconnect data flow confirmed.",
                    detail={"eventflow": "confirmed", "pipeline": components["decision_pipeline"].state},
                )
                self.alert_manager.resolve(component=key, kind=CRITICAL_ALERT, message=f"{key} recovered.", detail={"eventflow": "confirmed"})
                self.incident_log.record(
                    component=key, previous_state="RECOVERING", new_state="RECOVERED",
                    reason="data flow verified after reconnect", recovery_result="DATA_FLOW_RECOVERED",
                    last_event_age=comp.age_seconds,
                )
                self._recovery_pending.discard(key)
                self._recovery_baselines.pop(key,None)
                if key == "binance_spot":
                    self._repair.level = 0
                    self._repair.attempts = 0


    def _write_health_json(self, report: dict[str, Any]) -> None:
        for name in ("health.json",):
            try:
                atomic_json(self.runtime_dir/name,report)
            except OSError:
                pass
        # compact feed_health.json for lightweight external consumers / API back-compat
        try:
            feeds = {
                k.replace("binance_", ""): v for k, v in report["components"].items() if k.startswith("binance_")
            }
            (self.runtime_dir / "feed_health.json").write_text(
                json.dumps({"server_time": report["server_time"], "operating_state": report["operating_state"], "feeds": feeds}, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass
