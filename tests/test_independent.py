"""Offline adversarial probes. Assertions describe REQUIRED safe behavior.
Failing probes are audit findings, not changes to the product."""
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import pytest

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'scripts'),str(REPO/'tests')]
from bitcoin_cycle_analyzer.short_term.binance import BinancePublicFeed
from bitcoin_cycle_analyzer.short_term.health import FeedHealth
from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
from bitcoin_cycle_analyzer.short_term.resilience import ComponentHealth, CONFIG
from bitcoin_cycle_analyzer.short_term.alerting import AlertManager
from bitcoin_cycle_analyzer.short_term.web_api import StateReader
from test_waverun_b2_resilience import _FakeWebsockets
import waverun_live

@pytest.mark.parametrize('market',['spot','futures'])
@pytest.mark.parametrize('failure',['disconnect','connect_hang','silent'])
def test_feed_fault_then_real_event(monkeypatch,market,failure):
    fake=_FakeWebsockets()
    if failure=='connect_hang': fake.plan[market]=lambda n:'hang' if n==1 else 'ok'
    else: fake.recv_plan[market]=lambda n: ('closed' if failure=='disconnect' else 'hang') if fake.attempts[market]==1 else 'frame'
    monkeypatch.setitem(sys.modules,'websockets',fake)
    async def run():
      feed=BinancePublicFeed(include_futures=True,connect_timeout=.15,idle_timeout=.15,reconnect_base_delay=.01,max_reconnect_delay=.05)
      events=[]
      task=asyncio.create_task(feed.run(lambda e: events.append(e)))
      for _ in range(60):
        await asyncio.sleep(.05)
        if fake.attempts[market]>=2 and any(e.payload['market']==market for e in events): break
      task.cancel()
      try: await task
      except asyncio.CancelledError: pass
      assert fake.attempts[market]>=2
      assert any(e.payload['market']==market for e in events)
    asyncio.run(run())

def test_bare_callback_timeout_must_retry():
    async def run():
      feed=BinancePublicFeed(); calls=[]
      async def connection(*a):
        calls.append(1)
        if len(calls)>=2: feed.stop()
        raise TimeoutError('callback timeout')
      feed._run_connection=connection
      await feed._run_market('', 'spot',lambda e:None,asyncio.get_running_loop().time(),None)
      assert len(calls)>1, 'bare TimeoutError silently ends unlimited production market task'
    asyncio.run(run())

def test_handshake_is_not_event(monkeypatch):
    fake=_FakeWebsockets(recv_behaviour=lambda n:'hang'); monkeypatch.setitem(sys.modules,'websockets',fake)
    async def run():
      feed=BinancePublicFeed(idle_timeout=1)
      task=asyncio.create_task(feed._run_connection('spot','spot',lambda e:None))
      await asyncio.sleep(.03)
      count=feed.health['spot'].total_events
      task.cancel()
      try: await task
      except asyncio.CancelledError: pass
      assert count==0,'handshake increments real-event marker'
    asyncio.run(run())

def test_recovery_requires_prediction_progress(tmp_path):
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True)
    now=datetime.now(UTC)
    for name in ('market_events','decision_records'):
      (rt/(name+'.jsonl')).write_text(json.dumps({'timestamp':now.isoformat()})+'\n')
    sup=HealthSupervisor(rt,None,lambda:0)
    sup._recovery_pending.add('binance_spot')
    comps={k:ComponentHealth(k,'HEALTHY') for k in ('binance_spot','decision_pipeline')}
    comps['prediction_persistence']=ComponentHealth('prediction_persistence','OFFLINE')
    sup._verify_recovery(comps,now)
    assert 'binance_spot' in sup._recovery_pending,'RECOVERED without any prediction write'

def test_candidate_fresh_decision_stale_api(tmp_path):
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True); now=datetime.now(UTC)
    (rt/'pre_gate_candidates.jsonl').write_text(json.dumps({'timestamp':now.isoformat()})+'\n')
    (rt/'decision_records.jsonl').write_text(json.dumps({'timestamp':(now-timedelta(hours=1)).isoformat()})+'\n')
    report=StateReader(tmp_path)._resilience(now,'LIVE','CONNECTED','CONNECTED','AVAILABLE')
    assert report['overall']!='LIVE','API substitutes candidate freshness for decision and prediction writes'

def test_prediction_mtime_is_not_write_proof(tmp_path):
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True)
    db=tmp_path/'database';db.mkdir();(db/'waverun_predictions.db').write_bytes(b'')
    sup=HealthSupervisor(rt,None,lambda:0)
    assert sup._prediction_age() is None,'empty non-SQLite file counts as fresh prediction persistence'

def test_pipeline_stall_triggers_repair(tmp_path,monkeypatch):
    monkeypatch.setattr(CONFIG,'repair_cooldown',0)
    sup=HealthSupervisor(tmp_path,None,lambda:0)
    comps={'binance_spot':ComponentHealth('binance_spot','HEALTHY'),'decision_pipeline':ComponentHealth('decision_pipeline','OFFLINE')}
    sup._maybe_repair(comps,None,datetime.now(UTC))
    assert sup._repair.attempts>0,'pipeline stall with healthy spot produces no repair action'

def test_alert_dedupe_survives_manager_restart(tmp_path):
    path=tmp_path/'alerts.jsonl'; args=dict(component='spot',kind='DEGRADED',severity='HIGH',message='offline audit')
    AlertManager(path,telegram_sink=lambda _:{}).notify(**args)
    result=AlertManager(path,telegram_sink=lambda _:{}).notify(**args)
    assert result is None,'dedup state is in-memory only'

def test_level2_does_not_cancel_session():
    async def run():
      class FakeFeed:
        symbol='btcusdt'
        async def run(self,*a): await asyncio.Event().wait()
        def stop(self): pass
      session=object.__new__(waverun_live.LiveSession)
      session.feed=FakeFeed();session._callback=lambda e:None;session._supervisor=None
      session._feed_task=asyncio.create_task(session.feed.run())
      async def session_wait(): await session._feed_task
      main=asyncio.create_task(session_wait());await asyncio.sleep(0)
      # Real repair hook, but replace constructor so no external socket is opened.
      original=waverun_live.BinancePublicFeed; waverun_live.BinancePublicFeed=lambda *a,**k:FakeFeed()
      try:
        await session._recreate_feed_task();await asyncio.sleep(0)
        cancelled=main.cancelled()
        session._feed_task.cancel()
        try: await session._feed_task
        except asyncio.CancelledError: pass
        assert not cancelled,'run() awaits old feed task; L2 cancellation propagates to owning session'
      finally: waverun_live.BinancePublicFeed=original
    asyncio.run(run())
