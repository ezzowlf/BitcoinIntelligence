from test_independent import (asyncio,json,sys,datetime,UTC,timedelta,Path,pytest,BinancePublicFeed,ComponentHealth,CONFIG,HealthSupervisor,waverun_live,_FakeWebsockets)
from bitcoin_cycle_analyzer.short_term.resilience import compute_operating_state
from test_waverun_b2_degraded_e2e import _spot_trade,_futures_trade
import sqlite3, subprocess

@pytest.mark.parametrize('down,expected', [('vantage','DEGRADED_LIVE'),('binance_spot','CRITICAL'),('binance_futures','DEGRADED_LIVE'),('both','CRITICAL'),('decision_pipeline','CRITICAL'),('prediction_persistence','DEGRADED_LIVE')])
def test_rollup_faults(down,expected):
    cs={k:ComponentHealth(k,'HEALTHY') for k in ('vantage','binance_spot','binance_futures','l2','candidate_pipeline','decision_pipeline','prediction_persistence')}
    for k in (('binance_spot','binance_futures') if down=='both' else (down,)):cs[k].state='OFFLINE'
    assert compute_operating_state(cs)[0].value==expected

def test_candidate_stall_precludes_full_live():
    cs={k:ComponentHealth(k,'HEALTHY') for k in ('vantage','binance_spot','binance_futures','l2','candidate_pipeline','decision_pipeline','prediction_persistence')}
    cs['candidate_pipeline'].state='OFFLINE'
    assert compute_operating_state(cs)[0].value!='FULL_LIVE'

def test_task_crash_visible_while_sibling_runs():
    async def run():
        feed=BinancePublicFeed(include_futures=True)
        async def market(url,market,*a):
            if market=='spot':raise ValueError('offline injected crash')
            await asyncio.Event().wait()
        feed._run_market=market
        task=asyncio.create_task(feed.run(lambda e:None));await asyncio.sleep(.03)
        error=feed.health['spot'].last_error
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert error and 'MARKET_LOOP_CRASHED' in error
    asyncio.run(run())

def test_callback_hang_is_bounded(monkeypatch):
    fake=_FakeWebsockets();monkeypatch.setitem(sys.modules,'websockets',fake)
    async def run():
        feed=BinancePublicFeed(idle_timeout=.03,reconnect_base_delay=.01)
        async def cb(e):await asyncio.Event().wait()
        task=asyncio.create_task(feed.run(cb));await asyncio.sleep(.2)
        attempts=fake.attempts['spot'];task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert attempts>1,'callback await is outside read watchdog'
    asyncio.run(run())

def test_repeated_timeouts_and_reconnect_loop(monkeypatch):
    fake=_FakeWebsockets(connect_mode='hang');monkeypatch.setitem(sys.modules,'websockets',fake)
    async def run():
        feed=BinancePublicFeed(connect_timeout=.03,reconnect_base_delay=.01,max_reconnect_delay=.02)
        task=asyncio.create_task(feed.run(lambda e:None));await asyncio.sleep(.3)
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert 3<=fake.attempts['spot']<=9
    asyncio.run(run())

def test_cooldown_and_restart_budget(tmp_path,monkeypatch):
    monkeypatch.setattr(CONFIG,'repair_cooldown',120)
    sup=HealthSupervisor(tmp_path,None,lambda:0)
    cs={'binance_spot':ComponentHealth('binance_spot','OFFLINE')};now=datetime.now(UTC)
    sup._maybe_repair(cs,None,now);sup._maybe_repair(cs,None,now)
    assert sup._repair.attempts==1
    for _ in range(CONFIG.restart_budget+2):sup._request_restart(now)
    assert len(sup._repair.restart_requests)==CONFIG.restart_budget

def test_negative_control_remove_idle_watchdog(monkeypatch):
    import bitcoin_cycle_analyzer.short_term.binance as b
    fake=_FakeWebsockets(recv_behaviour=lambda n:'hang');monkeypatch.setitem(sys.modules,'websockets',fake)
    original=asyncio.wait_for
    async def altered(awaitable,timeout):
        if getattr(awaitable,'cr_code',None) and awaitable.cr_code.co_name=='recv':return await awaitable
        return await original(awaitable,timeout)
    monkeypatch.setattr(b.asyncio,'wait_for',altered)
    async def run():
        feed=BinancePublicFeed(idle_timeout=.03,reconnect_base_delay=.01)
        task=asyncio.create_task(feed.run(lambda e:None));await asyncio.sleep(.2)
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert fake.attempts['spot']==1,'negative control must eliminate retries (safety assertion would be red)'
    asyncio.run(run())

@pytest.mark.parametrize('repo,expected',[('parent','LIVE'),('candidate','CRITICAL')])
def test_old_new_false_live_control(tmp_path,repo,expected):
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True)
    now=datetime.now(UTC);old=(now-timedelta(hours=1)).isoformat()
    (rt/'vantage_ticks.jsonl').write_text(json.dumps({'timestamp':now.isoformat(),'bid':77000,'ask':77010,'time_msc':int(now.timestamp()*1000)})+'\n')
    (rt/'pre_gate_candidates.jsonl').write_text(json.dumps({'timestamp':old})+'\n')
    (rt/'decision_records.jsonl').write_text(json.dumps({'timestamp':old})+'\n')
    src=(Path(__file__).resolve().parents[1]/'audit'/'parent'/'src') if repo=='parent' else (Path(__file__).resolve().parents[1]/'src')
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from pathlib import Path;from datetime import datetime,UTC;from bitcoin_cycle_analyzer.short_term.web_api import StateReader;p=Path(sys.argv[2])/"runtime/waverun/vantage_ticks.jsonl";r=json.loads(p.read_text());now=datetime.now(UTC);r.update(timestamp=now.isoformat(),time_msc=int(now.timestamp()*1000));p.write_text(json.dumps(r)+"\\n");print(json.dumps(StateReader(Path(sys.argv[2])).snapshot()["connection"]))'
    result=subprocess.check_output([sys.executable,'-c',code,str(src),str(tmp_path)],text=True)
    assert json.loads(result)==expected

def test_actual_pipeline_recovery_including_prediction_commit(tmp_path):
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True);(tmp_path/'database').mkdir()
    db=tmp_path/'database'/'waverun_predictions.db'
    s=waverun_live.LiveSession(output=rt/'latest.json',database=db,symbol='btcusdt',mt5_values={'MT5_ENABLED':'false'})
    s.mt5.tick=lambda:{'status':'AVAILABLE','bid':77000.,'ask':77010.,'timestamp':datetime.now(UTC).isoformat(),'time_msc':int(datetime.now(UTC).timestamp()*1000)}
    def counts():
        with sqlite3.connect(db) as con:n=con.execute('select count(*) from predictions').fetchone()[0]
        return tuple(sum(1 for _ in (rt/f'{name}.jsonl').open()) for name in ('market_events','pre_gate_candidates','decision_records','latency_records'))+(n,)
    async def run():
        t=datetime(2026,1,1,tzinfo=UTC)
        for i in range(40):await s.on_event(_spot_trade(t+timedelta(seconds=i),77000+i))
        a=counts()
        for i in range(10):await s.on_event(_futures_trade(t+timedelta(seconds=100+i),77200+i))
        b=counts();assert b[0]>a[0] and b[1:]==a[1:]
        for i in range(40):await s.on_event(_spot_trade(t+timedelta(seconds=200+i),77400+i))
        c=counts();assert all(y>x for x,y in zip(b,c))
        with sqlite3.connect(db) as con:assert con.execute('select max(timestamp) from predictions').fetchone()[0]>t.isoformat()
    asyncio.run(run())

def test_socket_to_committed_prediction_recovery(tmp_path,monkeypatch):
    import dataclasses
    monkeypatch.setattr(waverun_live,'ROOT',tmp_path)
    rt=tmp_path/'runtime'/'waverun';rt.mkdir(parents=True);(tmp_path/'database').mkdir()
    db=tmp_path/'database'/'waverun_predictions.db'
    s=waverun_live.LiveSession(output=rt/'latest.json',database=db,symbol='btcusdt',mt5_values={'MT5_ENABLED':'false'})
    fake=_FakeWebsockets();fake.recv_plan['spot']=lambda n:'hang' if fake.attempts['spot']==1 and n>3 else 'frame'
    monkeypatch.setitem(sys.modules,'websockets',fake)
    def count():
        with sqlite3.connect(db) as c:return c.execute('select count(*) from predictions').fetchone()[0]
    async def run():
        feed=BinancePublicFeed(idle_timeout=.1,callback_timeout=10,reconnect_base_delay=.01,max_reconnect_delay=.02)
        n=0;before=None;after=None
        async def cb(e):
            nonlocal n,before,after
            n+=1;t=datetime(2026,1,1,tzinfo=UTC)+timedelta(seconds=n)
            await s.on_event(dataclasses.replace(e,exchange_timestamp=t,received_timestamp=t))
            if fake.attempts['spot']==1:before=count()
            else:after=count()
        task=asyncio.create_task(feed.run(cb))
        for _ in range(400):
            await asyncio.sleep(.05)
            if after and before and after>before:break
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert before and after and after>before
        for name in ('pre_gate_candidates','decision_records','latency_records'):
            assert sum(1 for _ in (rt/(name+'.jsonl')).open())>=4
    asyncio.run(run())
