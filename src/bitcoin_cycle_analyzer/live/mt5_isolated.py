"""One supervised, killable read-only MT5 process; no native calls in collector."""
from __future__ import annotations

from datetime import UTC, datetime
import math
import multiprocessing
import os
import time


def _worker(pipe, values, backend_factory=None):
    # Import native bridge only in the disposable child, never in its owner.
    from .mt5_provider import MT5MarketDataProvider
    provider = MT5MarketDataProvider(backend_factory() if backend_factory else None, values)
    try:
        while pipe.recv() == 'tick':
            tick = provider.tick()
            if tick.get('status') != 'AVAILABLE':
                pipe.send(tick)
                continue
            # Connection metadata alone is never sufficient for LIVE.
            terminal = provider.backend.terminal_info() if provider._initialized else None
            account = provider.backend.account_info() if provider._initialized else None
            if not (terminal and terminal.connected and account and account.login):
                tick = {'status': 'UNAVAILABLE', 'reason': 'MT5_SESSION_UNAVAILABLE'}
            pipe.send(tick)
    except (EOFError, BrokenPipeError):
        pass
    finally:
        provider.close()
        pipe.close()


class IsolatedMT5Provider:
    """tick() polls without waiting; deadline includes process spawn and connect.

    Timeout destroys the owned process before recovery is allowed. A failed
    kill blocks recovery, so a second native caller can never be created.
    Symbol discovery/ranking in MT5MarketDataProvider remains unchanged.
    """
    max_tick_age = 3.0  # seconds a quote may lag before it counts as stale (not as a fault)
    collect_timeout = 0.08  # bounded wait for an in-flight response, so a quote costs one poll, not two

    def __init__(self, values=None, *, timeout=10.0, retry_seconds=5.0,
                 backend_factory=None, context=None):
        self.values = dict(os.environ) if values is None else dict(values)
        self.timeout = timeout
        self.retry_seconds = retry_seconds
        self.backend_factory = backend_factory
        self.context = context or multiprocessing.get_context('spawn')
        self.process = None
        self.pipe = None
        self.deadline = None
        self.retry_at = 0.0
        self.closed = False
        self.reason = 'MT5_NOT_STARTED'
        self.timeouts = 0
        self.starts = 0
        self.failures = 0
        self._release_job = None
        self.last_tick_at = None

    def _retire(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(.25)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(.25)
            if self.process.is_alive():
                self.reason = 'MT5_WORKER_TERMINATION_FAILED'
                return False
            if self.process.pid is not None:self.process.join(0)
            self.process.close()
            self.process = None
        if self._release_job:
            self._release_job()
            self._release_job = None
        if self.pipe is not None:
            self.pipe.close()
            self.pipe = None
        self.deadline = None
        return True

    def _fail(self, reason):
        self.reason = reason
        self.last_tick_at = None
        self._retire()
        # A dead or hung terminal is external to TAKEOFF.  Retrying every five
        # seconds spawned hundreds of disposable bridge processes and added
        # needless CPU/IO pressure to the collector.  Keep recovery automatic,
        # but back off per consecutive failure and reset immediately on a valid
        # quote.  Binance/L2 never depend on this lane.
        self.failures += 1
        self.retry_at = time.monotonic() + min(60.0, self.retry_seconds * (2 ** min(self.failures - 1, 4)))
        return {'status': 'UNAVAILABLE', 'reason': self.reason}

    def tick(self):
        if self.closed:
            return {'status': 'UNAVAILABLE', 'reason': 'MT5_CLOSED'}
        if self.values.get('MT5_ENABLED', 'false').lower() not in {'true','1','on','yes'}:
            return {'status': 'UNAVAILABLE', 'reason': 'MT5_DISABLED'}
        now = time.monotonic()
        if self.reason == 'MT5_WORKER_TERMINATION_FAILED':
            return {'status': 'UNAVAILABLE', 'reason': self.reason}
        if now < self.retry_at:
            return {'status': 'UNAVAILABLE', 'reason': self.reason}
        try:
            if self.process is None:
                self.pipe, child = self.context.Pipe()
                self.process = self.context.Process(target=_worker, args=(child,self.values,self.backend_factory), daemon=True)
                self.deadline = now + self.timeout
                try:self.process.start()
                finally:child.close()
                if os.name=='nt':
                    from .mt5_job import own_process
                    self._release_job=own_process(self.process)
                self.starts += 1
                self.pipe.send('tick')
                self.reason = 'MT5_CONNECTING'
            elif self.deadline is None:
                self.pipe.send('tick')
                self.deadline = now + self.timeout
            if now >= self.deadline:
                self.timeouts += 1
                return self._fail('MT5_CALL_TIMEOUT')
            if not self.process.is_alive():
                return self._fail('MT5_WORKER_EXITED')
            # Wait briefly for the in-flight response instead of giving up
            # immediately. Returning straight away meant a quote always cost
            # two recorder iterations - send on one, collect on the next - so
            # the caller's poll interval was added to every quote's observed
            # age (measured 2026-09-18: the collector never saw a tick fresher
            # than exactly its own 100ms loop sleep). This runs on a worker
            # thread, never the event loop, and the spawn/hang deadline below
            # is unchanged, so a wedged terminal is still detected.
            if not self.pipe.poll(self.collect_timeout):
                return {'status': 'UNAVAILABLE', 'reason': 'MT5_POLL_PENDING'}
            tick = self.pipe.recv()
            self.deadline = None
            if tick.get('status') != 'AVAILABLE':
                return self._fail(tick.get('reason','MT5_UNAVAILABLE'))
            stamp = tick['timestamp']
            age = (datetime.now(UTC)-stamp).total_seconds()
            bid, ask = float(tick['bid']), float(tick['ask'])
            # A malformed or future-dated quote means the bridge/terminal or the
            # clock is genuinely wrong - that is a fault worth restarting for.
            if not (math.isfinite(bid) and math.isfinite(ask) and 0 < bid <= ask and age >= 0):
                return self._fail('MT5_INVALID_TICK')
            # A well-formed quote that is merely OLD is not a fault: Vantage's
            # CFD book legitimately goes seconds without a new print in quiet
            # hours. Treating that as a worker failure retired the bridge, which
            # guaranteed the next quote was stale too - an endless restart loop
            # (observed 2026-09-18: `starts` climbing ~6/minute with valid,
            # current bid/ask arriving only once per respawn). Report staleness
            # and keep the worker alive so the next print can actually arrive.
            # last_tick_at deliberately stays at the real last print, so health()
            # and _vantage_age() degrade on true age and no stale quote can
            # reach a signal.
            if age > self.max_tick_age:
                self.reason = 'MT5_STALE_TICK'
                self.last_tick_at = stamp
                return {'status': 'UNAVAILABLE', 'reason': self.reason, 'age_seconds': age}
            self.reason = 'MT5_CURRENT_TICK'
            self.last_tick_at = stamp
            self.failures = 0
            return tick
        except (OSError, EOFError, ValueError, KeyError, TypeError):
            return self._fail('MT5_WORKER_IO_ERROR')

    def close(self):
        self.closed = True
        self._retire()

    def health(self):
        age=(datetime.now(UTC)-self.last_tick_at).total_seconds() if self.last_tick_at is not None else None
        current=self.reason=='MT5_CURRENT_TICK' and age is not None and 0<=age<=3 and not self.closed
        return {'status':'HEALTHY' if current else 'DEGRADED','reason':self.reason,
                'age_seconds':age,'worker_pid':self.process.pid if self.process else None,
                'timeouts':self.timeouts,'starts':self.starts,'failures':self.failures,'execution':'DISABLED'}
