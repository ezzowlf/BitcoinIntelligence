# Bitcoin Market Intelligence Validation Report

Stand: 2026-08-09  
Basis: reale Bitstamp BTC/USD-Historie, Datenversion `bitstamp-btcusd-v1`

## Implementierte Module

- probabilistische Cycle Engine mit Halving- und ATH-Kontext
- zehn Regimezustände mit Primär- und Alternativszenarien
- Monats-, Wochentags-, Monatswechsel- und Quartalsstatistik
- Thanksgiving-, Black-Friday-, Weihnachts- und Neujahrsfenster
- regimeabhängige Seasonality-Ausgabe
- zeitkausaler `observed_at`/`available_at`-Datenvertrag
- ETF-, Funding-, OI-, Basis-, Liquidations- und Optionsschnittstellen
- On-Chain-Provider für 21 angeforderte Metriken
- Makro- und Economic-Calendar-Schnittstellen
- News-Eventmodell und geopolitische Wirkungskette
- Evidence Score und redundanzarme Confluence Engine
- getrennte Long-Term-Value-, Swing-, Timing- und Risk-Dimensionen
- standardisierter Service-Payload und nicht ausführender Alert-Builder
- erweitertes Dashboard mit zwölf Bereichen

## Datenverfügbarkeit

| Modul | Status | Bemerkung |
|---|---|---|
| BTC Price/Volume | AVAILABLE | Bitstamp, letzter abgeschlossener Daily-Bar 07.08.2026 UTC |
| Cycle | AVAILABLE | aus kanonischer BTC-Historie |
| Technical | AVAILABLE | bestehende validierte Engine |
| Seasonality | AVAILABLE | 15 vollständige Monatsbeobachtungen je Kalendermonat |
| On-Chain | UNAVAILABLE | kein lizenzierter Point-in-Time-Feed konfiguriert |
| ETF | UNAVAILABLE | kein verifizierter Flow-Feed konfiguriert |
| Derivatives | UNAVAILABLE | keine Funding/OI/Options-Zeitreihe konfiguriert |
| Macro | UNAVAILABLE | kein revisionssicherer Release-Feed konfiguriert |
| News | UNAVAILABLE | MeanPulse-Anbindung nur als Schnittstelle vorbereitet |

Es wurden keine Werte geschätzt oder aus Kursdaten als Ersatz für fehlende externe Daten rekonstruiert.

## Aktueller echter Snapshot

- BTC/USD Close: 64.877,77 USD
- ATH bis zum Stichtag: 124.728,00 USD am 06.10.2025
- Drawdown: -48,0 %
- Tage seit ATH: 305
- letztes Halving: 20.04.2024
- Tage seit Halving: 839
- Primärregime: `TRANSITION`, relative regelbasierte Confidence 15,6 %
- Alternativen: `BEAR` 12,9 %, `EARLY_BEAR` 11,3 %, `ACCUMULATION` 10,5 %
- Opportunity / Long-Term Value: 72,51 / 100
- Entry Timing: `WAIT`
- Seasonality: 35,02 / 100
- Evidence: 74,17 / 100, Label `MODERATE`
- Confluence: 53,8 / 100, Level `LOW`, nur zwei unabhängige verfügbare Gruppen

Die niedrige Regime-Confidence zeigt eine breit verteilte, nicht eindeutige Klassifikation. Sie ist keine Wahrscheinlichkeit für das Eintreten eines Regimes.

## Seasonality – reale Resultate

| Monat | n | Median | Mean | positiv | schlechtester Monats-DD |
|---|---:|---:|---:|---:|---:|
| Jan | 15 | +0,7 % | +4,4 % | 53,3 % | -52,5 % |
| Feb | 15 | +11,1 % | +9,7 % | 66,7 % | -50,2 % |
| Mär | 15 | -1,8 % | +11,6 % | 46,7 % | -54,8 % |
| Apr | 15 | +8,1 % | +11,3 % | 66,7 % | -52,9 % |
| Mai | 15 | +4,7 % | +9,0 % | 53,3 % | -48,0 % |
| Jun | 15 | +2,1 % | -0,1 % | 53,3 % | -44,6 % |
| Jul | 15 | +8,3 % | +9,9 % | 73,3 % | -29,5 % |
| Aug | 15 | -8,3 % | -0,3 % | 33,3 % | -30,4 % |
| Sep | 15 | -3,1 % | -4,0 % | 40,0 % | -40,0 % |
| Okt | 15 | +10,9 % | +14,4 % | 66,7 % | -53,9 % |
| Nov | 15 | +8,8 % | +36,4 % | 60,0 % | -44,9 % |
| Dez | 15 | -3,2 % | +6,2 % | 46,7 % | -65,9 % |

Means sind durch die frühe Bitcoin-Rechtsschiefe stark verzerrt. Die aktuelle August-Statistik ist historisch negativ, aber n=15 reicht nicht für eine harte Prognose.

### Eventfenster -14/+14 Tage

| Event | n | Median Return | positiv | schlechtester DD |
|---|---:|---:|---:|---:|
| Thanksgiving | 15 | +7,3 % | 53,3 % | -46,7 % |
| Black Friday | 15 | +7,4 % | 60,0 % | -49,2 % |
| Weihnachten | 15 | +0,2 % | 53,3 % | -56,5 % |
| Neujahr | 15 | +4,2 % | 60,0 % | -51,3 % |

Keines der Fenster rechtfertigt einen saisonalen Mythos oder ein eigenständiges Signal. Die regimeabhängigen Untergruppen sind im JSON-Validierungsartefakt enthalten und wegen kleiner Samples besonders vorsichtig zu interpretieren.

## Ablation und Walk-Forward

Seasonality wurde als fester 10-%-Proxy neben dem unveränderten technischen Score getestet. Dies ist eine Diagnose, keine Gewichtsoptimierung.

- Rangkorrelation des kombinierten Proxys zum 365-Tage-Return: 0,0097
- Rangkorrelation ohne Seasonality: 0,0167
- Beobachtungen: 5.069

Seasonality lieferte damit **keinen zusätzlichen historischen Ranginformationswert**.

| OOS Fold | Technical Signale | Technical 365d positiv | mit Seasonality Signale | mit Seasonality 365d positiv |
|---:|---:|---:|---:|---:|
| 2016–2020 | 16 | 87,5 % | 9 | 88,9 % |
| 2020–2024 | 34 | 76,5 % | 25 | 80,0 % |
| 2024–2026 | 27 / n=16 auswertbar | 50,0 % | 15 / n=9 auswertbar | 33,3 % |

Der jüngste OOS-Fold verschlechtert sich deutlich. Seasonality wird deshalb angezeigt, aber nicht als bestätigter Entscheidungsfaktor gewichtet.

Für On-Chain, ETF, Derivatives, Macro und News lautet das Ablation-Ergebnis `UNAVAILABLE: no verified point-in-time history`. Ein Backtest ohne reale Daten wäre Scheingenauigkeit.

## Tests

`pytest -q`: **31 passed**.

Neue Tests decken ab:

- Cycle-Confidence und Future-Mutation
- Halving- und ATH-Kontext
- Calendar/Seasonality und Holiday-Fenster ohne Zukunftsdaten
- ETF-, Funding- und OI-Release-Kausalität
- On-Chain-UNAVAILABLE-Verhalten
- Makro-Release-Timestamps
- News-`available_at`
- Evidence Score
- redundanzarme Confluence
- Ablation
- vollständige Market-State-Degradation ohne externe Feeds

Alle bisherigen 18 Tests bleiben grün.

## Schwächen und Fazit

Die Architektur ist bereit für eine umfassendere Intelligence Engine, aber der aktuelle echte Informationsumfang bleibt Technical + Cycle + Seasonality. Fünf wichtige externe Ebenen sind mangels lizenzierter, revisionssicherer Point-in-Time-Daten nicht bewertet.

Der einzige neue real getestete Faktor, Seasonality, liefert keinen robusten zusätzlichen OOS-Wert und wird folgerichtig nicht hochgewichtet. Das System beantwortet heute Zyklus, historische Bewertung, Timing, Risiko und Datenwidersprüche transparenter; institutionelle Flows, On-Chain, Derivate, Makrotreiber und aktuelle News kann es erst nach Anschluss verifizierter Feeds seriös beurteilen.

Es werden keine Orders erzeugt oder versendet.
