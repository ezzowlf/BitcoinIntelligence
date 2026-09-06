import json
from datetime import UTC,datetime,timedelta
from pathlib import Path
import pytest

from bitcoin_cycle_analyzer.short_term.journal import Journal,identity
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine
from bitcoin_cycle_analyzer.short_term.move_tracker import MoveTracker,lead_bucket
from bitcoin_cycle_analyzer.short_term.archive import archive_segment,verify_archive,retain_segment,RawWriter
from bitcoin_cycle_analyzer.short_term.resilience import ComponentHealth,compute_operating_state,REQUIRED_FOR_FULL_LIVE

T=datetime(2026,1,1,tzinfo=UTC)

def test_outcome_delivery_recovers_after_committed_result(tmp_path,monkeypatch):
    journal=Journal(tmp_path/'journal.db');engine=OutcomeEngine(journal)
    engine.register('crash','prediction',T,'NONE',horizons=(30,))
    original=journal.append
    def fail(*args,**kwargs):
        if args[0]=='outcome':raise OSError('simulated crash after outcome commit')
        return original(*args,**kwargs)
    monkeypatch.setattr(journal,'append',fail)
    with pytest.raises(OSError):engine.resolve_due(T+timedelta(seconds=40))
    assert engine.pending_floor() is None
    recovered=OutcomeEngine(Journal(journal.path))
    recovered.resolve_due(T+timedelta(seconds=50))
    recovered.resolve_due(T+timedelta(seconds=60))
    assert len(recovered.journal.rows('outcome'))==1
    assert recovered.journal.rows('outcome')[0]['payload']['status']=='CANCELLED'
    with recovered.journal.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM outcome_outbox').fetchone()[0]==0

@pytest.fixture
def engines(tmp_path):
    journal=Journal(tmp_path/'journal.db');outcomes=OutcomeEngine(journal)
    return journal,outcomes,SignalEngine(journal,outcomes)

def features(t,price=77000,**updates):
    f={'timestamp':t.isoformat(),'bid':price,'ask':price+1,'spot_delta':.8,'futures_delta':.7,'l2_imbalance':.8,'sample_size':30,'momentum':.001,'range_usd':10,'feed_health':{'spot':'HEALTHY','futures':'HEALTHY','vantage':'HEALTHY','l2':'HEALTHY'},'storage_ready':True,'outcomes_ready':True,'cause_id':identity(t),'synthetic':True}
    f.update(updates);return f

def reach(engine):
    return [engine.evaluate(T+timedelta(seconds=s),features(T+timedelta(seconds=s),p)) for s,p in [(0,77000),(1,77000),(5,77000),(6,77002)]]

def test_reachable_signal_contract_and_restart(engines):
    journal,outcomes,engine=engines
    transitions=reach(engine)
    assert [r['state_to'] for r in transitions]==['CANDIDATE','PREWARNING','ARMED','LIVE']
    assert len({r['setup_id'] for r in transitions})==1
    assert all(r['execution']=='DISABLED' and r['confidence'] is None and r['synthetic'] for r in transitions)
    restarted=SignalEngine(journal,outcomes)
    assert restarted.evaluate(T+timedelta(seconds=7),features(T+timedelta(seconds=7),77005)) is None
    assert len(journal.rows('signal_transition'))==4

@pytest.mark.parametrize('stage',['vantage','spot','l2'])
def test_missing_required_blocks_signal(engines,stage):
    j,o,e=engines;f=features(T);f['feed_health'][stage]='UNAVAILABLE'
    e.evaluate(T,f)
    assert e.snapshot()['state']=='REJECTED'
    assert j.rows('signal_transition')[-1]['payload']['reasons']==['REQUIRED_EVIDENCE_UNAVAILABLE']

@pytest.mark.parametrize('ready',['storage_ready','outcomes_ready'])
def test_infrastructure_closes_signal_gate(engines,ready):
    j,o,e=engines;e.evaluate(T,features(T,**{ready:False}));assert e.snapshot()['state']=='REJECTED'

def test_expiry_invalidation_future_and_divergence(engines):
    j,o,e=engines;e.evaluate(T,features(T))
    assert e.evaluate(T+timedelta(seconds=301),features(T+timedelta(seconds=301)))['state_to']=='EXPIRED'
    with pytest.raises(ValueError):e.evaluate(T,features(T+timedelta(seconds=1)))

def test_armed_invalidation(engines):
    j,o,e=engines
    for s in (0,1,5):e.evaluate(T+timedelta(seconds=s),features(T+timedelta(seconds=s)))
    assert e.evaluate(T+timedelta(seconds=6),features(T+timedelta(seconds=6),76900))['state_to']=='CANCELLED'

@pytest.mark.parametrize('direction',['LONG','SHORT'])
def test_executable_outcome_and_restart(engines,direction):
    j,o,e=engines;sgn=1 if direction=='LONG' else -1
    o.quote(T,77000,77001);o.register('x','LIVE',T,direction,horizons=(30,))
    for s in range(1,31):o.quote(T+timedelta(seconds=s),77000+sgn*s*5,77001+sgn*s*5)
    assert o.resolve_due(T+timedelta(seconds=29))==[]
    reopened=OutcomeEngine(j);result=reopened.resolve_due(T+timedelta(seconds=35))[0]
    assert result['status']=='RESOLVED' and result['targets']['100']['hit']
    assert result['executable_outcome']==149
    assert reopened.resolve_due(T+timedelta(seconds=40))==[]

def test_missing_path_is_not_loss(engines):
    j,o,e=engines;o.quote(T,100,101);o.register('x','LIVE',T,'LONG',horizons=(30,));o.quote(T+timedelta(seconds=30),110,111)
    result=o.resolve_due(T+timedelta(seconds=35))[0]
    assert result['status']=='INSUFFICIENT_FUTURE_DATA' and result['actual_return'] is None

def test_bad_data_cancel_and_invalid_quote(engines):
    j,o,e=engines
    with pytest.raises(ValueError):o.quote(T,101,100)
    o.register('missing','LIVE',T,'LONG',horizons=(30,));o.register('none','candidate',T,'NONE',horizons=(30,))
    assert {x['status'] for x in o.resolve_due(T+timedelta(seconds=35))}=={'INVALID_DATA','CANCELLED'}

def test_false_warning_and_all_horizons_terminal(engines):
    j,o,e=engines;o.quote(T,10000,10001);o.register('w','PREWARNING',T,'LONG')
    # Large immutable fixture in one transaction; quote validation has separate tests.
    with j.connect() as db:
        db.executemany('INSERT INTO quotes VALUES(?,?,?)',[(T.timestamp()+s,10000,10001) for s in range(1,3601)])
    rows=o.resolve_due(T+timedelta(seconds=3605))
    assert len(rows)==9 and all(r['status']=='RESOLVED' for r in rows)
    assert len(j.rows('false_warning'))==1

def test_catchup_transition_registration(engines):
    j,o,e=engines;reach(e)
    with j.connect() as db:db.execute('DELETE FROM observations')
    o.catch_up_registrations()
    with j.connect() as db:assert db.execute('SELECT count(*) FROM observations').fetchone()[0]==36

def test_move_first_missed_and_lead_buckets(engines):
    j,o,e=engines;m=MoveTracker(j,window_seconds=60)
    for s in range(61):m.quote(T+timedelta(seconds=s),10000+min(s,30)*7,10001+min(s,30)*7)
    assert len(j.rows('move'))==1 and len(j.rows('missed_move'))==1
    assert [lead_bucket(v) for v in [30,60,120,180,301]]==['<60s','60-120s','120-180s','180-300s','>300s']

def test_move_gap_cannot_be_counted_as_missed_move(engines):
    j,o,e=engines;m=MoveTracker(j,window_seconds=60)
    m.quote(T,10000,10001);m.quote(T+timedelta(seconds=1),10200,10201)
    m.quote(T+timedelta(seconds=60),10500,10501)
    assert len(j.rows('incomplete_move'))==1
    assert not j.rows('move') and not j.rows('missed_move')

def test_signal_expiry_without_market_and_terminal_outcome(engines):
    j,o,e=engines
    e.evaluate(T,features(T));e.tick(T+timedelta(seconds=301))
    assert e.snapshot()['state']=='EXPIRED'
    e2=SignalEngine(Journal(j.path.parent/'second.db'),o);reach(e2)
    setup=e2.active['setup_id']
    e2.tick(T+timedelta(seconds=400))
    assert e2.snapshot()['state']=='LIVE'
    e2.accept_outcome({'kind':'LIVE','horizon_seconds':300,'observation':{'setup_id':setup},'resolved_at':(T+timedelta(seconds=400)).isoformat(),'status':'INSUFFICIENT_FUTURE_DATA'})
    assert e2.snapshot()['state']=='OUTCOME'
    assert SignalEngine(e2.journal,o).snapshot()['signal']['reasons']==['INSUFFICIENT_FUTURE_DATA']

def test_recovery_requires_fresh_source_specific_commit(engines,tmp_path):
    from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
    j,o,e=engines
    sup=HealthSupervisor(tmp_path,None,lambda:0)
    sup._recovery_pending.add('binance_spot')
    comps={k:ComponentHealth(k,'HEALTHY') for k in ('binance_spot','decision_pipeline')}
    sup._verify_recovery(comps,T)
    stages=('features','candidates','decisions','predictions','outcome_scheduler','storage','feed_futures','vantage')
    for s in stages:j.mark(s,'first',T,committed_at=T)
    sup._verify_recovery(comps,T)
    assert 'binance_spot' in sup._recovery_pending
    j.mark('feed_spot','old-source',T-timedelta(seconds=100),committed_at=T)
    sup._verify_recovery(comps,T)
    assert 'binance_spot' in sup._recovery_pending
    j.mark('feed_spot','real-source',T,committed_at=T)
    sup._verify_recovery(comps,T)
    assert 'binance_spot' not in sup._recovery_pending





def test_normal_full_and_every_required_stage(engines):
    healthy={k:ComponentHealth(k,'HEALTHY') for k in REQUIRED_FOR_FULL_LIVE}
    assert compute_operating_state(healthy)[0].value=='FULL_LIVE'
    for key in REQUIRED_FOR_FULL_LIVE:
        cs=dict(healthy);cs[key]=ComponentHealth(key,'OFFLINE')
        assert compute_operating_state(cs)[0].value!='FULL_LIVE'
