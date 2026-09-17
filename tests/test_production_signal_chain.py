"""Real production normalization/features/signal/outcome chain, isolated storage."""
from datetime import datetime,UTC,timedelta

import pytest
from fastapi.testclient import TestClient

from bitcoin_cycle_analyzer.short_term.events import normalize_binance_message
from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures
from bitcoin_cycle_analyzer.short_term.journal import Journal,atomic_json
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine
from bitcoin_cycle_analyzer.short_term.web_api import create_app


@pytest.mark.parametrize('sign,direction',[(1,'LONG'),(-1,'SHORT')])
def test_market_pre_live_persistence_api_outcome(tmp_path,sign,direction):
    runtime=tmp_path/'runtime/waverun'
    journal=Journal(runtime/'journal.db')
    outcomes=OutcomeEngine(journal)
    engine=SignalEngine(journal,outcomes)
    features=CausalFeatures()
    start=datetime.now(UTC)
    transitions=[]
    for seconds in range(7):
        now=start+timedelta(seconds=seconds)
        price=77000+sign*seconds*2
        for market in ('spot','futures'):
            for i in range(30):
                stamp=now-timedelta(milliseconds=30-i)
                event=normalize_binance_message({'e':'trade','s':'BTCUSDT','T':int(stamp.timestamp()*1000),'p':str(price+sign*i*.001),'q':'0.01','m':sign<0},stamp,market)
                p=event.payload
                features.trade(market,stamp,p['price'],p['quantity'],p['buyer_is_maker'])
        outcomes.quote(now,price,price+1)
        f=features.snapshot(now,{'bid':price,'ask':price+1},l2=sign*.8,
            feed_health={key:'HEALTHY' for key in ('spot','futures','l2','vantage')},storage_ready=True,outcomes_ready=True,synthetic=True)
        transition=engine.evaluate(now,f)
        if transition:
            transitions.append(transition)
            atomic_json(runtime/'signal.json',engine.snapshot())
            with TestClient(create_app(tmp_path)) as client:
                payload=client.get('/api/state').json()
                assert payload['shadow_signal']['signal']['setup_id']==transition['setup_id']
                assert payload['shadow_signal']['signal']['state_to']==transition['state_to']
    assert [row['state_to'] for row in transitions]==['CANDIDATE','PREWARNING','ARMED','LIVE']
    assert {row['direction'] for row in transitions}=={direction}
    assert len({row['setup_id'] for row in transitions})==1
    assert not journal.rows('outcome')
    for seconds in range(7,307):
        price=77000+sign*seconds*2
        outcomes.quote(start+timedelta(seconds=seconds),price,price+1)
    results=outcomes.resolve_due(start+timedelta(seconds=312))
    live=next(row for row in results if row['kind']=='LIVE' and row['horizon_seconds']==300)
    assert live['status']=='RESOLVED'
    assert live['targets']['300']['hit']
    assert live['executable_outcome']>0
    engine.accept_outcome(live)
    assert engine.snapshot()['state']=='OUTCOME'
    assert len(journal.rows('signal_transition'))==5
