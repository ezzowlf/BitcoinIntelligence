from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from bitcoin_cycle_analyzer.live.mt5_isolated import IsolatedMT5Provider


class Backend:
    TIMEFRAME_H4=4
    TIMEFRAME_D1=1
    def __init__(self, mode='normal', marker=None):self.mode=mode;self.marker=marker
    def initialize(self, **kwargs):
        if self.mode=='initialize_hang':time.sleep(60)
        return self.mode!='unreachable'
    def symbols_get(self):
        if self.marker:
            mode=Path(self.marker).read_text()
            Path(str(self.marker)+'.entered').write_text('entered')
        else:mode=self.mode
        if mode=='hang':time.sleep(60)
        if mode=='slow':time.sleep(.3)
        return [SimpleNamespace(name='BTCUSD',description='Bitcoin USD',visible=True)]
    def symbol_select(self,*args):return True
    def symbol_info_tick(self,*args):
        # Honour the marker file here too, so a test can switch quote freshness
        # mid-flight (the worker only reads symbols_get once, at startup).
        mode=Path(self.marker).read_text() if self.marker else self.mode
        t=time.time()-(100 if mode=='stale' else 0)
        if mode=='future':t+=100
        if mode=='invalid':return SimpleNamespace(bid=102,ask=101,time=int(t),time_msc=int(t*1000))
        return SimpleNamespace(bid=100,ask=101,time=int(t),time_msc=int(t*1000))
    def copy_rates_from_pos(self,*args):return [1]
    def terminal_info(self):return SimpleNamespace(connected=self.mode!='disconnected')
    def account_info(self):
        if self.mode=='account_hang':time.sleep(60)
        return SimpleNamespace(login=0 if self.mode=='logged_out' else 1)
    def version(self):return (5,1,'')
    def shutdown(self):pass


def wait(provider, status=None, reason=None, seconds=15):
    start=time.monotonic()
    while time.monotonic()-start<seconds:
        tick=provider.tick()
        if (status and tick['status']==status) or (reason and tick.get('reason')==reason):return tick
        time.sleep(.02)
    raise AssertionError((provider.reason, provider.timeouts))


@pytest.mark.parametrize('mode',['normal','slow'])
def test_normal_and_slow_preserve_symbol_selection(mode):
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},backend_factory=partial(Backend,mode))
    try:
        assert provider.process is None  # constructor has no native work or child
        tick=wait(provider,status='AVAILABLE')
        assert tick['symbol']=='BTCUSD' and tick['bid']==100
        assert provider.starts==1
    finally:provider.close()
    assert provider.process is None


@pytest.mark.parametrize('mode,reason',[
    ('unreachable','INITIALIZE_FAILED'),('disconnected','MT5_SESSION_UNAVAILABLE'),
    ('logged_out','MT5_SESSION_UNAVAILABLE'),
    ('future','MT5_INVALID_TICK'),('invalid','INVALID_OR_UNINITIALIZED_TICK')])
def test_no_phantom_live(mode,reason):
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},backend_factory=partial(Backend,mode))
    try:
        assert wait(provider,reason=reason)['status']=='UNAVAILABLE'
        assert provider.process is None
        for _ in range(20):assert provider.tick()['status']=='UNAVAILABLE'
        assert provider.starts==1  # backoff, no busy loop
        assert provider.health()['status']=='DEGRADED'
    finally:provider.close()


def test_hang_is_killed_and_later_recovers_without_parallel_workers(tmp_path):
    marker=tmp_path/'mode';marker.write_text('hang')
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},timeout=6,retry_seconds=.2,
                                 backend_factory=partial(Backend,marker=str(marker)))
    provider.tick();child=provider.process
    try:
        tick=wait(provider,reason='MT5_CALL_TIMEOUT')
        assert Path(str(marker)+'.entered').exists()  # timeout really reached symbols_get
        assert tick['status']=='UNAVAILABLE' and provider.timeouts==1
        assert provider.process is None
        with pytest.raises(ValueError):child.is_alive()  # reaped AND handle closed
        marker.write_text('normal');time.sleep(.25)
        assert wait(provider,status='AVAILABLE')['symbol']=='BTCUSD'
        assert provider.starts==2
    finally:provider.close()


def test_disabled_never_spawns():
    provider=IsolatedMT5Provider({'MT5_ENABLED':'false'})
    assert provider.tick()['status']=='UNAVAILABLE'
    assert provider.starts==0
    provider.close()


@pytest.mark.parametrize('mode',['initialize_hang','account_hang'])
def test_other_native_calls_are_also_killable(mode):
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},timeout=6,backend_factory=partial(Backend,mode))
    try:
        assert wait(provider,reason='MT5_CALL_TIMEOUT')['status']=='UNAVAILABLE'
        assert provider.process is None and provider.starts==1
    finally:provider.close()


def test_collector_constructor_does_not_connect_and_health_keeps_writing(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import waverun_live
    from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},timeout=6,backend_factory=partial(Backend,'hang'))
    monkeypatch.setattr(waverun_live,'ROOT',tmp_path)
    monkeypatch.setattr(waverun_live,'IsolatedMT5Provider',lambda **kwargs:provider)
    started=time.monotonic()
    session=waverun_live.LiveSession(tmp_path/'runtime/latest.json',tmp_path/'forecasts.db','btcusdt')
    assert time.monotonic()-started<3
    assert provider.starts==0
    supervisor=HealthSupervisor(tmp_path/'runtime',session.feed,session._vantage_age)
    session._record_vantage_tick()
    try:
        snapshots=[]
        for _ in range(3):
            snapshots.append(supervisor.tick())
            time.sleep(.05)
        assert len({s['server_time'] for s in snapshots})==3
        assert all(s['components']['vantage']['state']=='OFFLINE' for s in snapshots)
        assert session._last_vantage_wall is None
        assert not session.journal.rows('signal_transition')
    finally:provider.close()


def test_collector_observable_and_failure_invalidates_causal_quote(tmp_path,monkeypatch):
    import sys
    import threading
    from collections import deque
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import waverun_live
    from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
    from bitcoin_cycle_analyzer.short_term.binance import BinancePublicFeed
    marker=tmp_path/'mode';marker.write_text('hang')
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},timeout=6,backend_factory=partial(Backend,marker=str(marker)))
    session=waverun_live.LiveSession.__new__(waverun_live.LiveSession)
    session.mt5=provider;session._mt5_lock=threading.RLock();session._data_lock=threading.RLock()
    session._last_vantage_wall=None;session._vantage_samples=waverun_live.TimeSeries(8192)
    health=HealthSupervisor(tmp_path,BinancePublicFeed('btcusdt',include_futures=True),session._vantage_age)
    try:
        session._record_vantage_tick()
        # Owner stays callable while native worker sleeps. No tick/persistence
        # paths are needed or invoked before a valid quote exists.
        for _ in range(3):
            assert session._vantage_age() is None
            assert health._age_state(session._vantage_age(),30,60) not in {'LIVE','HEALTHY'}
        wait(provider,reason='MT5_CALL_TIMEOUT')
        session._record_vantage_tick()
        assert list(session._vantage_samples)[-1]['status']=='UNAVAILABLE'
        assert session._last_vantage_wall is None
    finally:provider.close()


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows process ownership')
def test_native_child_dies_when_owner_crashes(tmp_path):
    import os
    import subprocess
    import sys
    import ctypes
    from ctypes import wintypes
    script=tmp_path/'owner.py'
    script.write_text('''import multiprocessing, os, time
from bitcoin_cycle_analyzer.live.mt5_job import own_process
if __name__ == '__main__':
    p=multiprocessing.get_context('spawn').Process(target=time.sleep,args=(60,))
    p.start()
    release=own_process(p)
    print(p.pid,flush=True)
    time.sleep(.5)
    os._exit(0)
''')
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    owner=subprocess.Popen([sys.executable,str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=None
    try:
        pid=int(owner.stdout.readline())
        handle=kernel.OpenProcess(0x100000,False,pid)
        assert handle
        owner.wait(timeout=10)
        assert kernel.WaitForSingleObject(handle,3000)==0
    finally:
        if owner.poll() is None:owner.kill();owner.wait(timeout=5)
        if handle:kernel.CloseHandle(handle)


def test_stale_quote_is_reported_but_never_restarts_the_worker():
    """Regression (production 2026-09-18): a well-formed quote older than
    max_tick_age was treated as a worker fault, so the bridge was terminated -
    which guaranteed the next quote was stale too. `starts` climbed ~6/minute
    and vantage flapped OFFLINE while valid current bid/ask were arriving.

    Staleness must be reported (never phantom-LIVE) while the worker stays up.
    """
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},backend_factory=partial(Backend,'stale'))
    try:
        tick=wait(provider,reason='MT5_STALE_TICK')
        assert tick['status']=='UNAVAILABLE'          # never phantom-live
        assert tick['age_seconds']>provider.max_tick_age
        starts_after_first=provider.starts
        for _ in range(20):
            assert provider.tick()['status']=='UNAVAILABLE'
        assert provider.starts==starts_after_first, 'a stale quote must not respawn the bridge'
        assert provider.process is not None, 'the worker must stay alive through staleness'
        assert provider.failures==0, 'staleness is not a failure'
        assert provider.health()['status']=='DEGRADED'
    finally:provider.close()


def test_stale_then_fresh_recovers_without_a_restart(tmp_path):
    """The point of keeping the worker alive: when the book prints again the
    quote recovers immediately, with no respawn in between."""
    marker=tmp_path/'mode';marker.write_text('stale')
    provider=IsolatedMT5Provider({'MT5_ENABLED':'true'},backend_factory=partial(Backend,marker=str(marker)))
    try:
        wait(provider,reason='MT5_STALE_TICK')
        starts=provider.starts
        marker.write_text('normal')
        assert wait(provider,status='AVAILABLE')['status']=='AVAILABLE'
        assert provider.starts==starts, 'recovery must not need a respawn'
        assert provider.health()['status']=='HEALTHY'
    finally:provider.close()
