# WAVERUN Web-Frontend (Phase 1)

React + TypeScript + Vite. Ersetzt schrittweise das Streamlit-Cockpit
(`dashboard/app.py`), das bis zur vollständigen Feature-Parität als Fallback bestehen bleibt.

**Ausführung ist deaktiviert.** Weder Backend noch Frontend enthalten einen Pfad, der eine Order
auslösen könnte. Das Frontend spricht ausschließlich mit der WAVERUN-API — niemals direkt mit
MT5, Vantage oder Binance.

## Voraussetzungen

Die Live-Engine muss laufen, damit Daten vorhanden sind:

```powershell
./START_WAVERUN.ps1
```

Sie schreibt nach `runtime/waverun/` und `runtime/waverun_v5_3_fast_v2_forward/`.

## Start

Zwei Prozesse, zwei Terminals.

**1. Read-only API (Port 8787):**

```bash
python scripts/waverun_web_api.py --port 8787
# aus einem Worktree oder anderem Checkout heraus zusätzlich:
python scripts/waverun_web_api.py --port 8787 --root /pfad/zum/repo/mit/runtime
```

**2. Frontend (Port 5173):**

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Aufruf: <http://127.0.0.1:5173> — `/api/*` wird von Vite auf `127.0.0.1:8787` weitergeleitet.

Produktions-Build: `npm run build --prefix frontend` (Ausgabe in `frontend/dist/`).

## API-Endpunkte

| Endpunkt | Zweck |
| --- | --- |
| `GET /api/health` | Status und aktives Repository-Root |
| `GET /api/timeframes` | unterstützte Zeitrahmen |
| `GET /api/candles?timeframe=1m&limit=1000` | OHLC-Kerzen aus Vantage-BTCUSD-Ticks |
| `GET /api/state` | vollständiger Live-Zustand (einmalig) |
| `GET /api/stream` | SSE-Strom, ein Zustand pro Sekunde |
| `GET /api/docs` | OpenAPI |

## Navigation

Funktionsfähig in Phase 1: **LIVE**, **CHART**, **DATENQUELLEN**.
Als „in Kürze" markiert: SIGNALE, MEINE ZONEN, PAPER TRADING, AUSWERTUNG, EINSTELLUNGEN.

## Chart-Bibliothek

Siehe [`TRADINGVIEW_DECISION.md`](./TRADINGVIEW_DECISION.md).
