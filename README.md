# Bitcoin Cycle Analyzer

> Version 2.1 ergänzt echte Binance-Funding/OI- und Coin-Metrics-Community-Daten mit strengem `available_at`-Vertrag. ETF, Makro und News bleiben ohne verifizierte Konfiguration ehrlich `UNAVAILABLE`. Details: `REAL_MARKET_DATA_VALIDATION_REPORT.md`.

Version 2.2 erweitert die OI-Historie über das offizielle Binance-Vision-Archiv bis September 2020, ergänzt ALFRED-Vintage-, ETF- und MeanPulse-Verträge sowie Evidence/Confluence 2.2. Der reale Status und verbleibende Zugangshürden stehen in `BITCOIN_INTELLIGENCE_2_2_VALIDATION_REPORT.md`.

Ein lokales, transparentes Research-System ausschließlich für Bitcoin. Es bewertet historische und zyklische Konstellationen, erzeugt aber **keine Anlageberatung** und kein automatisches Buy/Sell-Signal.

## Schnellstart (Windows / PowerShell)

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install -e '.[dev,dashboard]'
& $python scripts/update_data.py
& $python scripts/data_quality_report.py
& $python scripts/run_real_validation.py
& $python scripts/run_intelligence_validation.py
& $python scripts/run_analysis.py
& $python -m streamlit run dashboard/app.py
```

Tests:

```powershell
& $python -m pytest -q
```

## Architektur

- `data_provider.py`: validierte OHLCV-Schnittstelle, Kraken-Adapter, SQLite-Upsert, Resampling
- `indicators.py`: RSI, EMA 20/50/100/200, SMA 200, ATR, Volumen, ATH-Drawdown
- `swing_detection.py`: timeframe-parametrisierte, erst nach rechtsseitiger Bestätigung bekannte Pivots
- `market_structure.py`: HH/HL/LH/LL, Trend, Support und Widerstand
- `fibonacci.py`: Retracements, Extensions und Cluster/Confluence
- `elliott_wave.py`: mehrere regelbasierte, probabilistische Szenarien mit Invalidierung
- `similarity.py`: stichtagsbezogene Features, historische Nachbarn und Forward-Return-Verteilungen
- `opportunity_score.py`: zentral gewichteter 0–100-Score mit Einzelbeiträgen
- `backtesting.py`: Ausführung auf der nächsten Kerze, Vergleich mit Buy & Hold und DCA
- `walk_forward.py`: getrennte Train/Test-Fenster und Out-of-Sample-Auswertung
- `zones.py`: gestaffelte Zonen mit Risiko und Invalidierung
- `audit.py`: versionierte JSON-Snapshots jeder Analyse
- `dashboard/app.py`: lokales Streamlit-/Plotly-Dashboard

## Market Intelligence 2.0

Die bestehende technische Engine wird durch neue, getrennte Ebenen ergänzt:

- `core/`: Halving-/ATH-Zyklus, probabilistische Regimes und Market State Matrix
- `seasonality/`: Monate, Wochentage, Quartale, Monatswechsel und Feiertagsfenster
- `onchain/`, `derivatives/`, `flows/`, `macro/`, `news/`: zeitkausale Provider-Schnittstellen
- `scoring/evidence.py`: Belastbarkeit getrennt vom Opportunity Score
- `scoring/confluence.py`: unabhängige Faktoren ohne Doppelzählung korrelierter Inputs
- `validation/ablation.py`: inkrementeller Informationswert einzelner Faktoren
- `alerts.py`: Watch-Alerts ohne Orderausführung

Nicht konfigurierte externe Feeds liefern ausdrücklich `UNAVAILABLE`; sie werden weder neutral gesetzt noch geschätzt. Architektur und Faktorgrenzen stehen in `BITCOIN_INTELLIGENCE_ARCHITECTURE.md` und `MARKET_FACTORS.md`. Die echte Seasonality-/OOS-Auswertung steht in `BITCOIN_INTELLIGENCE_VALIDATION_REPORT.md`.

## Zeitkausalität

Ein Pivot bei `pivot_time` ist erst bei `confirmed_at` verwendbar. Indikatoren sind rückwärtsgerichtet; Similarity schneidet Daten am `as_of`-Zeitpunkt ab; Backtest-Signale werden erst zum Open der folgenden Kerze ausgeführt. Tests mutieren gezielt zukünftige Daten und prüfen, dass historische Ergebnisse unverändert bleiben.

## Datenquellen und Grenzen

Primär wird die öffentliche Bitstamp-BTC/USD-OHLC-API ab 2011 verwendet. Kraken bleibt als zweiter Provider verfügbar. Alle Kerzen werden mit Provider, Quelle, Importzeitpunkt und Datenversion in SQLite gespeichert; 1W und 1M entstehen ausschließlich aus abgeschlossenen kanonischen Daily-Kerzen. Lizenz- und Nutzungsgrenzen sowie die echte Mehrzyklusvalidierung stehen in `REAL_DATA_VALIDATION_REPORT.md`.

Elliott-Wellen bleiben subjektiv: Die Engine liefert nur plausible regelbasierte Szenarien, Confidence und Invalidierungen. On-chain-Daten, Derivate und ETF-Flows sind Erweiterungspunkte, aber nicht Teil dieses MVP.

### Makro- und News-Datenstatus

Das Dashboard zeigt unter SYSTEM/DATEN den Status `AVAILABLE`/`UNAVAILABLE` für jedes Datenmodul. Diese Werte kommen ausschließlich aus dem echten Runtime-State (`state["data_status"]`), niemals hardcodiert.

- **MAKRO**: 20 vorbereitete Makroserien (`src/bitcoin_cycle_analyzer/macro/engine.py::MACRO_METRICS`), 18 davon direkt über die FRED-API abrufbar (`macro/fred_provider.py`), vintage-sicher gecacht in `database/macro.db` (`macro/store.py`). Benötigt `FRED_API_KEY` in `.env` (kostenlos unter fred.stlouisfed.org). **Ohne Key**: `MAKRO = UNAVAILABLE`, Grund `FRED_API_KEY_MISSING_OR_NO_RELEASES` — kein Absturz, kein vorgetäuschter Wert. Ist bereits einmal erfolgreich ein Fetch gelaufen, nutzt das System den letzten Cache aus `macro.db`, auch ohne aktiven Key.
- **NEWS**: verwendet die lokale, quellenbelegte Ereignis-Datenbank (`database/historical_event_evidence.db`, `event_evidence.PointInTimeEventDatabase`) — keine externe News-API. `NEWS = AVAILABLE`, sobald die Datenbank mindestens einen Eintrag enthält. Das ist bewusst getrennt von der Frage, ob es *aktuell relevante* Ereignisse gibt (siehe „WICHTIGE NEWS / EREIGNISSE“ im Dashboard, das die letzten 90 Tage separat prüft). `MEANPULSE_NEWS_URL`/`MEANPULSE_NEWS_FILE` in `.env.example` sind ein vorgesehener, aber noch nicht implementierter Anschlusspunkt für einen echten Live-News-Feed.

Lokal prüfen: `python -c "from bitcoin_cycle_analyzer.macro import load_macro_series, analyze_macro; ..."` oder im Dashboard den Tab SYSTEM öffnen.

## Backtest-Interpretation

Der echte Mehrzykluslauf liegt lokal unter `data/reports/` und ist in `REAL_DATA_VALIDATION_REPORT.md` vollständig zusammengefasst. Die Resultate zeigen deskriptiven Wert, aber keinen robusten Beweis einer stabilen Überlegenheit gegenüber Buy & Hold oder einfachen Regeln.
Externe Daten aktualisieren und validieren:

```powershell
.\.venv\Scripts\python.exe scripts\update_external_data.py
.\.venv\Scripts\python.exe scripts\run_market_data_validation.py
```
