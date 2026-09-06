"""Bounded time-window features. Absence stays absent; only <=T inputs are read."""
from collections import deque
from statistics import pstdev
from .journal import utc,identity

WINDOWS=(1,5,15,30,60)

class CausalFeatures:
    def __init__(self):
        self.trades={'spot':deque(maxlen=200000),'futures':deque(maxlen=200000)}
        self.previous=None

    def trade(self,market,timestamp,price,quantity,buyer_is_maker):
        t=utc(timestamp).timestamp();rows=self.trades[market]
        rows.append((t,price,quantity,-1 if buyer_is_maker else 1))
        while rows and t-rows[0][0]>65:rows.popleft()

    def snapshot(self,timestamp,quote,*,l2=None,feed_health=None,storage_ready=False,outcomes_ready=False,synthetic=False):
        t=utc(timestamp);epoch=t.timestamp();q=quote or {};bid=q.get('bid');ask=q.get('ask')
        result={'timestamp':t.isoformat(),'cause_id':identity('evaluation',t.isoformat()),'bid':bid,'ask':ask,'mid':(bid+ask)/2 if bid is not None and ask is not None else None,'spread':ask-bid if bid is not None and ask is not None else None,'feed_health':feed_health or {},'storage_ready':storage_ready,'outcomes_ready':outcomes_ready,'synthetic':synthetic,'l2_imbalance':l2,'open_interest':None,'funding':None,'liquidations':None,'absorption_proxy':None,'liquidity_changes':None,'feature_version':'causal-windows-v1','windows':{}}
        for window in WINDOWS:
            values={}
            for market,rows in self.trades.items():
                active=[r for r in rows if epoch-window<r[0]<=epoch]
                buy=sum(r[2] for r in active if r[3]>0);sell=sum(r[2] for r in active if r[3]<0)
                prices=[r[1] for r in active]
                values[market]={'buy_volume':buy,'sell_volume':sell,'delta':(buy-sell)/(buy+sell) if buy+sell else None,'trade_count':len(active),'return':prices[-1]/prices[0]-1 if prices else None,'range_usd':max(prices)-min(prices) if prices else None,'realized_volatility':pstdev(prices) if len(prices)>1 else None}
            result['windows'][str(window)]=values
        spot=result['windows']['15']['spot'];futures=result['windows']['15']['futures']
        result.update(spot_delta=spot['delta'] or 0,futures_delta=futures['delta'],momentum=spot['return'] or 0,sample_size=spot['trade_count'],range_usd=spot['range_usd'] or 0,regime='EXPANDING' if (spot['range_usd'] or 0)>max(result['spread'] or 0,1)*2 else 'COMPRESSED')
        previous=self.previous
        result['acceleration']=result['momentum']-previous['momentum'] if previous and previous['timestamp']<result['timestamp'] else None
        self.previous=result
        return result
