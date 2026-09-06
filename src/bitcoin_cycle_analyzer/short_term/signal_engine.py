"""Versioned, uncalibrated shadow setup contract; no outcome inputs or orders."""
from __future__ import annotations

from dataclasses import asdict,dataclass
from datetime import timedelta
import math

from .journal import Journal,identity,utc
from .outcome_engine import OutcomeEngine


@dataclass(frozen=True)
class SignalPolicy:
    version:str='shadow-flow-l2-v1'
    feature_version:str='causal-windows-v1'
    flow_candidate:float=.30
    flow_confirm:float=.50
    l2_confirm:float=.20
    minimum_samples:int=20
    arm_min_seconds:float=5
    expiry_seconds:float=300
    cooldown_seconds:float=300
    max_spread_usd:float=30
    target_usd:int=100
    horizon_seconds:int=300


class SignalEngine:
    def __init__(self,journal:Journal,outcomes:OutcomeEngine,policy=None):
        self.journal=journal;self.outcomes=outcomes;self.policy=policy or SignalPolicy()
        stored=journal.state('signal_policy')
        if stored and stored!=asdict(self.policy):raise ValueError('new policy requires explicit versioned research session')
        journal.save('signal_policy',asdict(self.policy))
        self.active=journal.state('active_setup')
        self.cooldown=journal.state('signal_cooldown',{})
        self.last_transition=journal.state('last_signal_transition')
        self.last_evaluated=journal.state('signal_last_evaluated')

    def _transition(self,state,t,f,reasons,missing=(),conflicts=()):
        a=self.active;p=self.policy;previous=a['state'];a['state']=state
        bid,ask=f.get('bid'),f.get('ask');sign=1 if a['direction']=='LONG' else -1
        entry=ask if sign==1 else bid
        row={'setup_id':a['setup_id'],'timestamp':t.isoformat(),'state_from':previous,'state_to':state,'direction':a['direction'],'reasons':list(reasons),'evidence':f,'missing_evidence':list(missing),'conflicts':list(conflicts),'market_regime':f.get('regime','UNKNOWN'),'feed_health':f.get('feed_health',{}),'feature_version':p.feature_version,'signal_version':p.version,'confidence':None,'calibration_status':'UNCALIBRATED_RESEARCH','mode':'SHADOW','execution':'DISABLED','expected_move_class':p.target_usd,'expected_start_window':[(t+timedelta(seconds=60)).isoformat(),(t+timedelta(seconds=300)).isoformat()],'expected_horizon':p.horizon_seconds,'entry_zone':[bid,ask],'vantage_executable_side':'ASK' if sign==1 else 'BID','invalidation':a.get('invalidation'),'why_now':list(reasons),'expires_at':a['expires_at'],'synthetic':bool(f.get('synthetic',False))}
        transition_id=identity(a['setup_id'],state)
        if state in {'CANDIDATE','PREWARNING','ARMED','LIVE'}:a[state.lower()+'_at']=t.isoformat()
        self.journal.append('signal_transition',transition_id,t,row,stage='signal_transition',cause_id=f.get('cause_id',transition_id),state_updates={'active_setup':a,'last_signal_transition':row})
        self.last_transition=row
        if state in {'CANDIDATE','PREWARNING','ARMED','LIVE'}:
            self.outcomes.register(transition_id,state,t,a['direction'],bid=bid,ask=ask,invalidation=a.get('invalidation'),payload={'setup_id':a['setup_id'],'version':p.version})
        return row

    def evaluate(self,timestamp,features):
        t=utc(timestamp);f=dict(features);p=self.policy
        if utc(f['timestamp'])>t:raise ValueError('future features rejected')
        if self.last_evaluated and t<utc(self.last_evaluated):raise ValueError('out-of-order decision rejected')
        self.last_evaluated=t.isoformat()
        self.journal.save('signal_last_evaluated',self.last_evaluated)
        missing=[k for k in ('vantage','spot','l2') if f.get('feed_health',{}).get(k)!='HEALTHY']
        if not f.get('storage_ready',False):missing.append('storage')
        if not f.get('outcomes_ready',False):missing.append('outcomes')
        bid,ask=f.get('bid'),f.get('ask')
        if bid is None or ask is None or not all(math.isfinite(x) and x>0 for x in (bid,ask)) or bid>ask:missing.append('executable_quote')
        flow=f.get('spot_delta',0);direction='LONG' if flow>0 else 'SHORT';sign=1 if direction=='LONG' else -1
        conflicts=[]
        if f.get('futures_delta') is not None and flow*f['futures_delta']<0:conflicts.append('SPOT_FUTURES_DIVERGENCE')
        if self.active and self.active['state']=='LIVE':return None
        if self.active and self.active['state'] in {'OUTCOME','CANCELLED','REJECTED','EXPIRED'}:
            if (t-utc(self.active['timestamp'])).total_seconds()<p.cooldown_seconds:return None
            self.active=None
        if self.active:
            if t>=utc(self.active['expires_at']):return self._transition('EXPIRED',t,f,['SETUP_EXPIRED'])
            a=self.active;sgn=1 if a['direction']=='LONG' else -1
            if missing:return self._transition('CANCELLED',t,f,['REQUIRED_EVIDENCE_UNAVAILABLE'],missing,conflicts)
            price=(bid+ask)/2
            if (sgn==1 and price<=a['invalidation']) or (sgn==-1 and price>=a['invalidation']) or sgn*flow<0:
                return self._transition('CANCELLED',t,f,['SETUP_INVALIDATED'],(),conflicts)
            if conflicts:return None
            age=(t-utc(a['timestamp'])).total_seconds()
            if a['state']=='CANDIDATE' and age>=1:return self._transition('PREWARNING',t,f,['DIRECTIONAL_FLOW_PERSISTS'])
            if a['state']=='PREWARNING' and age>=p.arm_min_seconds and sgn*flow>=p.flow_confirm and sgn*f.get('l2_imbalance',0)>=p.l2_confirm:
                a['armed_reference']=price
                return self._transition('ARMED',t,f,['FLOW_AND_DEPTH_CONFIRM'])
            if a['state']=='ARMED' and t>utc(a['armed_at']) and sgn*(price-a['armed_reference'])>=max(ask-bid,.01) and sgn*f.get('momentum',0)>0 and ask-bid<=p.max_spread_usd:
                return self._transition('LIVE',t,f,['CAUSAL_RECLAIM','EXECUTABLE_SPREAD_VALID'])
            return None
        if abs(flow)<p.flow_candidate or f.get('sample_size',0)<p.minimum_samples:return None
        # Reject observable candidate, do not manufacture absent required evidence.
        price=(bid+ask)/2 if bid is not None and ask is not None else None
        invalidation=price-sign*max(2*(ask-bid),f.get('range_usd',0),1) if price else None
        self.active={'setup_id':identity(p.version,t.isoformat(),direction),'timestamp':t.isoformat(),'state':'OBSERVING','direction':direction,'expires_at':(t+timedelta(seconds=p.expiry_seconds)).isoformat(),'invalidation':invalidation}
        row=self._transition('CANDIDATE',t,f,['FLOW_CANDIDATE'],missing,conflicts)
        if missing:self._transition('REJECTED',t,f,['REQUIRED_EVIDENCE_UNAVAILABLE'],missing,conflicts)
        return row

    def snapshot(self):
        return {'state':self.active['state'] if self.active else 'OBSERVING','setup':self.active,'signal':self.last_transition,'policy':asdict(self.policy),'confidence':None,'execution':'DISABLED','mode':'SHADOW'}

    def tick(self,timestamp):
        """Expire without new market callbacks; LIVE remains until a terminal outcome."""
        t=utc(timestamp)
        if not self.active or self.active['state'] not in {'CANDIDATE','PREWARNING','ARMED'}:return None
        if t>=utc(self.active['expires_at']):
            return self._transition('EXPIRED',t,{},['SETUP_EXPIRED_WITHOUT_NEW_EVENT'])

    def accept_outcome(self,row):
        if not self.active or self.active['state']!='LIVE':return None
        if row.get('kind')!='LIVE' or row.get('horizon_seconds')!=self.policy.horizon_seconds:return None
        if row.get('observation',{}).get('setup_id')!=self.active['setup_id']:return None
        return self._transition('OUTCOME',utc(row['resolved_at']),{'outcome':row},[row['status']])
