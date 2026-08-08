# Bitcoin Market Intelligence Architecture

## Designziel

Die Engine trennt Marktattraktivität, Timing, Risiko und Evidenz. Externe Module dürfen ausfallen, ohne technische Analyse oder historische Validierung zu blockieren. Es gibt keinen automatischen Handel und keinen einzelnen Super-Score.

## Schichten

```text
Canonical BTC/USD OHLCV
        |
        +-- existing technical engine
        |     swings, structure, Fibonacci, Elliott, similarity, score
        |
        +-- core/cycle_engine.py
        |     halving context, ATH context, probabilistic regimes
        |
        +-- seasonality/
        |     months, weekdays, turns, quarters, holiday windows
        |
External point-in-time feeds
        |
        +-- onchain/       provider abstraction, explicit UNAVAILABLE
        +-- derivatives/   funding, OI, basis, liquidations, options
        +-- flows/         ETF and spot-vs-leverage classification
        +-- macro/         release-timestamp-aware observations
        +-- news/          available-at events and impact chains
        |
        +-- scoring/evidence.py
        +-- scoring/confluence.py
        |
        +-- core/market_state.py
              independent state dimensions and service payload
```

## Zeitkausaler Datenvertrag

Jede externe Beobachtung besitzt mindestens:

- `metric`
- `value`
- `observed_at`
- `available_at`
- `provider`
- `status`
- erwartete Verzögerung und Quelle, sofern bekannt

Backtests filtern nach `available_at`, nicht nach dem wirtschaftlichen Bezugsdatum. Damit können ETF-Schlussmeldungen, Makro-Releases, On-Chain-Verzögerungen und News nicht vor ihrer tatsächlichen Verfügbarkeit verwendet werden.

## Market State

Die Hauptausgabe enthält getrennt:

- Cycle-Regime mit Alternativen
- Long-Term Value
- Swing Opportunity
- Technical Timing / Entry Timing
- Risk
- On-Chain
- Institutional Flows
- Derivatives
- Macro
- Seasonality
- News Risk
- Evidence

`None` bedeutet nicht neutral, sondern nicht bewertet. Fehlende Daten tragen `UNAVAILABLE`.

## Confluence

Jeder Faktor erhält eine Redundanzgruppe. Pro Gruppe zählt nur der betragsmäßig stärkste Faktor. RSI und ein weiterer Momentum-Oszillator würden beispielsweise nicht doppelt zählen. Nicht verfügbare Gruppen erhöhen die Confluence nicht.

## Evidence

Evidence misst:

- historische Sample Size
- Datenqualität
- Modulübereinstimmung
- Out-of-Sample-Qualität
- Providerabdeckung

Evidence misst keine Marktrichtung und ist keine Eintrittswahrscheinlichkeit.

## Erweiterbarkeit

`public_payload()` erzeugt eine standardisierte, rein analytische Schnittstelle für spätere Anbindungen an MeanPulse, MeanPulse News, MT5 oder PolyMarketPulse. `alerts.py` erzeugt nur Watch-Objekte; `execution` bleibt fest `DISABLED`.

