"""Bounded read-only bridge probe, credential-free summaries only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def child():
    import MetaTrader5 as mt5
    def call(name, fn, summarize):
        print(json.dumps({'call':name,'phase':'start','time':time.time()}),flush=True)
        started=time.monotonic()
        value=fn()
        print(json.dumps({'call':name,'phase':'end','seconds':time.monotonic()-started,'result':summarize(value)}),flush=True)
        return value
    ok=call('initialize',lambda:mt5.initialize(path=r'C:\Program Files\MetaTrader 5\terminal64.exe',timeout=5000),bool)
    if not ok:return
    call('terminal_info',mt5.terminal_info,lambda x: {'available':x is not None,'connected':bool(x and x.connected)})
    call('account_info',mt5.account_info,lambda x:{'available':x is not None,'logged_in':bool(x and x.login),'vantage_server':bool(x and 'vantage' in str(x.server).lower())})
    call('symbol_info_BTCUSD',lambda:mt5.symbol_info('BTCUSD'),lambda x:{'exists':x is not None,'visible':bool(x and x.visible)})
    call('symbol_info_tick_BTCUSD',lambda:mt5.symbol_info_tick('BTCUSD'),lambda x:{'available':x is not None,'valid_spread':bool(x and 0<x.bid<=x.ask),'raw_age_seconds':time.time()-x.time if x else None})
    symbols=call('symbols_get',mt5.symbols_get,lambda x:{'count':len(x or []),'btc_symbols':[s.name for s in (x or []) if 'BTC' in s.name.upper()]})
    call('shutdown',mt5.shutdown,lambda _:True)

def parent():
    import threading
    import queue
    root=Path(__file__).resolve().parents[1]
    target=root/'ops/b2-mt5-probe.jsonl'
    messages=queue.Queue()
    proc=subprocess.Popen([sys.executable,'-u',__file__,'--child'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    def read():
        for line in proc.stdout:messages.put(line)
    reader=threading.Thread(target=read,daemon=True);reader.start()
    deadline=time.monotonic()+12
    with target.open('x') as output:
        while proc.poll() is None or not messages.empty():
            try:
                line=messages.get(timeout=.1);row=json.loads(line)
                output.write(line);output.flush();print(line.strip(),flush=True)
                deadline=time.monotonic()+12
            except queue.Empty:pass
            if time.monotonic()>deadline:
                proc.kill();proc.wait(timeout=5)
                row={'probe':'TIMEOUT','deadline_seconds':12,'owned_probe_killed':True}
                output.write(json.dumps(row)+'\n');print(json.dumps(row),flush=True);break
    reader.join(1)

if __name__=='__main__':
    child() if '--child' in sys.argv else parent()
