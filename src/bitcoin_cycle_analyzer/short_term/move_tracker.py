"""Move-first labels, kept downstream of signal decisions and never fed back."""
from datetime import timedelta
import math
from .journal import identity,utc

def lead_bucket(seconds):
    if seconds<60:return '<60s'
    if seconds<120:return '60-120s'
    if seconds<180:return '120-180s'
    if seconds<=300:return '180-300s'
    return '>300s'


class MoveTracker:
    def __init__(self,journal,window_seconds=600,max_gap_seconds=5):
        self.journal=journal;self.window=window_seconds
        self.state=journal.state('move_tracker',{'LONG':None,'SHORT':None})
        self.max_gap=max_gap_seconds
        self.last_quote=journal.state('move_tracker_last_quote')

    def quote(self,timestamp,bid,ask):
        t=utc(timestamp)
        if not all(math.isfinite(x) and x>0 for x in (bid,ask)) or bid>ask:raise ValueError('invalid move quote')
        if self.last_quote:
            gap=(t-utc(self.last_quote)).total_seconds()
            if gap<0:raise ValueError('out-of-order move quote')
            if gap>self.max_gap:
                for a in self.state.values():
                    if a and a.get('detected'):
                        self.journal.append('incomplete_move',a['move_id'],t,{**a,'status':'INSUFFICIENT_FUTURE_DATA','gap_seconds':gap})
                self.state={'LONG':None,'SHORT':None}
        for direction in ('LONG','SHORT'):
            sign=1 if direction=='LONG' else -1
            entry=ask if sign==1 else bid;exit=bid if sign==1 else ask
            a=self.state[direction]
            if a and (t-utc(a['start'])).total_seconds()>=self.window:
                if a.get('detected'):self._finish(a,t)
                a=None
            if a is None or not a.get('detected') and sign*(entry-a['entry'])<0:
                a={'direction':direction,'start':t.isoformat(),'entry':entry,'magnitude':0,'detected':False,'targets':{},'regime':'UNCLASSIFIED'}
            amount=sign*(exit-a['entry'])
            a['magnitude']=max(a['magnitude'],amount)
            for target in (100,150,200,300,500):
                if amount>=target and str(target) not in a['targets']:a['targets'][str(target)]=t.isoformat()
            if amount>=100 and not a['detected']:
                a['detected']=True;a['detected_at']=t.isoformat();a['move_id']=identity('vantage-extrema-600-v1',direction,a['start'])
            self.state[direction]=a
        self.journal.save('move_tracker',self.state)
        self.last_quote=t.isoformat()
        self.journal.save('move_tracker_last_quote',self.last_quote)

    def _finish(self,move,now):
        start=utc(move['start']);matches=[]
        for row in self.journal.rows('signal_transition',start=start-timedelta(seconds=600),end=start,limit=10000):
            p=row['payload']
            if p['direction']==move['direction'] and p['state_to'] in {'CANDIDATE','PREWARNING','ARMED','LIVE'}:matches.append(p)
        # One setup per move: earliest prewarning in window, otherwise earliest candidate.
        warnings=[p for p in matches if p['state_to']=='PREWARNING']
        selected=min(warnings or matches,key=lambda p:utc(p['timestamp'])) if matches else None
        setup=selected['setup_id'] if selected else None
        progression=[p for p in matches if p['setup_id']==setup]
        leads={}
        for state in ('CANDIDATE','PREWARNING','ARMED','LIVE'):
            rows=[p for p in progression if p['state_to']==state]
            if rows:
                first=min(utc(p['timestamp']) for p in rows);seconds=(start-first).total_seconds()
                leads[state]={'timestamp':first.isoformat(),'seconds':seconds,'bucket':lead_bucket(seconds)}
        payload={**move,'duration':self.window,'measured_at':now.isoformat(),'setup_id':setup,'lead_times':leads,'definition':'independent executable-side extrema, first $100 crossing; no nested moves per direction in 600s','execution':'DISABLED'}
        self.journal.append('move',move['move_id'],now,payload)
        if 'PREWARNING' not in leads:
            self.journal.append('missed_move',move['move_id'],now,{**payload,'why_no_candidate':'NO_MATCHING_PREWARNING_BEFORE_MOVE_START','blocking_gates':[p.get('missing_evidence',[]) for p in matches],'available_features':[p.get('evidence',{}) for p in progression[-1:]]})
