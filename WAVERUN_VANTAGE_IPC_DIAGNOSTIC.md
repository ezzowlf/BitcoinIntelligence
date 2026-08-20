# WAVERUN Vantage IPC Diagnostic

- Terminal executable: `C:\Program Files\MetaTrader 5\terminal64.exe`
- Observed process: `terminal64`, PID 29224
- Process state: responding; no visible main-window title
- Configured symbol: `BTCUSD`
- Bounded initialize duration: 0.646 seconds
- IPC result: `(-10003, 'IPC initialize failed, MetaTrader 5 x64 not found')`
- Historical Bid/Ask/Spread activation: unavailable
- Orders: none
- Execution: `DISABLED`

This differs from the earlier 61-second `(-10005, IPC timeout)` failure but does not change the conclusion: Vantage historical execution validation remains unavailable. Binance results remain a `BINANCE RESEARCH PROXY`, not a Vantage trading edge.
