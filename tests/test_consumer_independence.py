from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,UTC
import sys
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from waverun_live import LiveSession,TimeSeries
from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures
from bitcoin_cycle_analyzer.short_term.events import MarketEvent,EventType
from bitcoin_cycle_analyzer.short_term.orderbook import OrderBookState


def test_futures_book_and_depth_progress_while_spot_is_busy():
    session=LiveSession.__new__(LiveSession)
    session._spot_lock=threading.Lock()
    session._process_lock=threading.RLock()
    session._data_lock=threading.RLock()
    session._book_samples=TimeSeries(8192)
    session._depth_samples=TimeSeries(8192)
    session.causal_features=CausalFeatures()
    session.flow_buffer={'spot':deque(),'futures':deque()}
    session.book=OrderBookState()
    session.book.seed_snapshot(1,[(77000,2)],[(77001,1)])
    now=datetime.now(UTC)
    def event(kind,payload):return MarketEvent(kind,'BINANCE','BTCUSDT',now,now,payload)
    trade=event(EventType.TRADE,{'market':'futures','price':77000,'quantity':1,'buyer_is_maker':False})
    book=event(EventType.BOOK_TICKER,{'bid':77000,'ask':77001})
    depth=event(EventType.DEPTH,{'first_update_id':2,'final_update_id':2,'bids':[(77000,3)],'asks':[]})
    with session._spot_lock,ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(session._evaluate_locked,trade),pool.submit(session._evaluate_locked,book),pool.submit(session._apply_depth,depth)]
        assert [job.result(timeout=2) for job in jobs]==[None,None,'APPLIED']
        assert session._process_lock.acquire(timeout=1)
        session._process_lock.release()
    assert len(session.causal_features.trades['futures'])==1
    assert session.book.bids[77000]==3
    assert session.last_book is book
