# Market Factors

## Real-data status in 2.1

- Binance public USD-M Futures: Funding seit September 2019 und ein aktuelles 500-Stunden-OI-Fenster.
- Coin Metrics Community v4: MVRV sowie Exchange Inflows, Outflows und Balance. MVRV ohne historische Statuszeit ist nur aktueller Research-Kontext.
- FRED/ALFRED: vintage-fähiger Provider vorhanden, aber ohne API-Key `UNAVAILABLE`.
- ETF und MeanPulse News: `UNAVAILABLE`, bis eine verifizierte Point-in-time-Quelle konfiguriert ist.
- Der Funding-Ablationstest rechtfertigt kein eigenes Score-Gewicht; Derivate wirken nur auf Risiko und Timing.

| Faktor | Bedeutung | Quelle / Frequenz | Historische Abdeckung | Verwendung | Nicht erlaubt |
|---|---|---|---|---|---|
| BTC OHLCV | Preis, Volumen, Marktstruktur | Bitstamp, 4H/1D; Kraken als zweiter Provider | Bitstamp ab 2011 | technische Analyse, Cycle, Seasonality | Exchange-Serie als globalen Index ausgeben |
| Halving Cycle | Zeit seit bekannten Bitcoin-Halvings | deterministischer Kalender | ab 2012 | Kontext und Zyklusvergleich | festes Top-/Bottom-Datum prognostizieren |
| ATH Cycle | damaliges ATH, Drawdown, Dauer | kausal aus BTC Close | gesamte Preisserie | Value- und Risikokontext | späteres ATH rückwirkend verwenden |
| Market Regime | mehrere plausible Zustände | technische Tagesdaten | nach Indikator-Warm-up | relative regelbasierte Confidence | als kalibrierte Wahrscheinlichkeit darstellen |
| Seasonality | Monats-, Tages- und Eventmuster | kanonische BTC-Historie, täglich | 15 vollständige Jahresbeobachtungen | deskriptiver Kontext, OOS/Ablation | saisonale Mythen fest programmieren |
| On-Chain | Holder- und Bewertungszustand | Provider nicht konfiguriert | `UNAVAILABLE` | Schnittstelle für Realized Price, MVRV, SOPR etc. | Werte rekonstruieren oder erfinden |
| ETF Flows | institutionelle Spot-ETF-Nachfrage | lizenzierter Feed nicht konfiguriert | `UNAVAILABLE` | Daily/5D/20D, Beschleunigung, Divergenz | Veröffentlichung vor `available_at` nutzen |
| Funding | Futures-Positionierung | Feed nicht konfiguriert | `UNAVAILABLE` | historisches Perzentil und Überhitzung | alleinige Long-/Short-Regel |
| Open Interest | Leverage-Aufbau/Abbau | Feed nicht konfiguriert | `UNAVAILABLE` | 24H/7D-Änderung, Kontext | OI ohne Preis/Funding/Spot interpretieren |
| Futures Basis | Carry und institutioneller Futures-Kontext | Feed nicht konfiguriert | `UNAVAILABLE` | annualisierte Spot-Future-Basis | negative/positive Basis isoliert handeln |
| Liquidationen | Zwangsabbau von Leverage | Feed nicht konfiguriert | `UNAVAILABLE` | Long-/Short-Anteile und Cluster | nachträglich bekannte Cluster vorwegnehmen |
| Options | IV, Put/Call, Skew, Laufzeitstruktur | Feed nicht konfiguriert | `UNAVAILABLE` | Risiko- und Positionierungskontext | Max Pain als Kursziel behandeln |
| Spot Demand | Spot CVD versus Futures/OI | Feed nicht konfiguriert | `UNAVAILABLE` | Spot-led vs leverage-led Klassifikation | Preisbewegung ohne Orderflow sicher zuordnen |
| Macro | Rates, Yields, DXY, Inflation, Liquidität, Assets | Point-in-time Feed nicht konfiguriert | `UNAVAILABLE` | release-kausale historische Tests | fixe Korrelation oder revidierte Werte rückwirkend |
| News | geopolitische, geldpolitische und BTC-spezifische Events | MeanPulse-Schnittstelle vorbereitet | `UNAVAILABLE` | Risiko, Unsicherheit, bedingte Wirkungskette | News direkt als Buy/Sell verwenden |
| Evidence | Belastbarkeit der Aussage | abgeleitete Qualitätsmetriken | abhängig von Modul | separat zum Opportunity Score | als Marktwahrscheinlichkeit ausgeben |
| Confluence | unabhängige Übereinstimmung | verfügbare Module | aktuell Technical + Seasonality | gruppierte, redundanzarme Bestätigung | korrelierte Faktoren mehrfach zählen |

## Datenstatus

Jedes Modul meldet Provider, letzten verfügbaren Zeitpunkt und `AVAILABLE`, `DELAYED`, `STALE` oder `UNAVAILABLE`. Das Dashboard zeigt diese Angaben im Bereich `DATA HEALTH`.
