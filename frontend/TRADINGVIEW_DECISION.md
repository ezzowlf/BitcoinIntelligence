# Chart-Bibliothek: Entscheidung (Phase 1)

**Entscheidung: TradingView Lightweight Charts™ (npm `lightweight-charts`, v5.2.1).**
Advanced Charts / Charting Library wurde geprüft und verworfen.

## Bewertete Optionen

### 1. Lightweight Charts™ — GEWÄHLT

- **Lizenz:** Apache License 2.0, Quellcode offen auf GitHub (`tradingview/lightweight-charts`).
- **Zugang:** Freie npm-Installation. Keine Antragstellung, keine Freigabe, kein Vertrag.
- **Auflagen:** Die Apache-2.0-Bedingungen von TradingView verlangen eine sichtbare Attribution
  mit Link auf tradingview.com. Diese ist unter dem Chart platziert
  (`frontend/src/components/PriceChart.tsx`, Klasse `.attribution`). Das eingebaute
  Herstellerlogo (`attributionLogo`) ist deaktiviert, weil die Attribution stattdessen als
  Textlink im Panel steht — der Link darf nicht entfernt werden.
- **Kein iframe:** Die Bibliothek rendert lokal auf `<canvas>`. Es werden keine Kursdaten von
  TradingView bezogen und keine externen Requests ausgelöst. Alle Kerzen stammen aus der
  eigenen WAVERUN-API.

### 2. Advanced Charts / Charting Library — VERWORFEN

- **Lizenz:** Proprietär. Der Quellcode wird nicht ausgeliefert.
- **Zugang:** Nur auf Antrag und nach Freigabe durch TradingView. TradingView stellt Advanced
  Charts ausdrücklich **nicht** für private Nutzung, Hobby, Studium oder Tests bereit — die
  Lizenz richtet sich an Unternehmen mit einem öffentlichen Web-Projekt oder einer öffentlichen
  Anwendung.
- **Konsequenz für WAVERUN:** WAVERUN ist derzeit ein privates Research- und Shadow-Trading-
  System ohne öffentliches Produkt. Es gibt keinen Beleg dafür, dass Advanced Charts für diesen
  Einsatz frei verfügbar wäre. Ohne erteilte Lizenz darf die Bibliothek nicht verwendet werden.

### 3. Nacktes TradingView-Widget im iframe — AUSGESCHLOSSEN

Ausdrücklich außerhalb des Auftrags: keine Kontrolle über die dargestellten Daten, die Kerzen
kämen von TradingView statt aus der eigenen Vantage-Tickhistorie, und Zeichnungen ließen sich in
späteren Phasen nicht persistieren.

Quellen: <https://github.com/tradingview/lightweight-charts/blob/master/LICENSE>,
<https://www.tradingview.com/free-charting-libraries/>, <https://www.tradingview.com/advanced-charts/>

## Auswirkungen auf spätere Phasen

### Zeichenwerkzeuge (Phase „MEINE ZONEN")

Lightweight Charts bringt **keine** interaktiven Zeichenwerkzeuge mit — das ist der wesentliche
Funktionsunterschied zu Advanced Charts. Für eigene Zonen, Trendlinien und Rechtecke gilt daher:

- Preislinien und horizontale Zonen sind direkt abbildbar
  (`createPriceLine`, Series-Primitives ab v4/v5).
- Freie Rechtecke, Trendlinien und Text-Labels müssen über die **Series-Primitives-API**
  (`attachPrimitive`) oder über ein Overlay-Canvas selbst implementiert werden. Das ist
  Mehraufwand gegenüber Advanced Charts, aber machbar und wurde bereits von anderen Projekten
  so umgesetzt.
- Maus-Interaktion (Ziehen, Auswählen, Löschen) ist ebenfalls selbst zu bauen; die Bibliothek
  liefert dafür `subscribeClick`, `subscribeCrosshairMove` sowie Koordinaten-Umrechnung über
  `priceToCoordinate` / `coordinateToPrice` und die entsprechenden Zeit-Pendants.

### Persistenz

Da Zeichnungen ohnehin selbst verwaltet werden, gibt es **keine** Bindung an ein proprietäres
Speicherformat. Zonen werden als eigene Datensätze über die WAVERUN-API gespeichert (geplant:
`runtime/waverun/` bzw. `database/waverun_product.db`) und beim Laden neu gezeichnet. Das ist für
den späteren Lern-Datensatz sogar günstiger als das undurchsichtige Save/Load-Adapter-Modell von
Advanced Charts.

### Falls Advanced Charts später doch lizenziert wird

Der Wechsel wäre auf `frontend/src/components/PriceChart.tsx` und den Datenadapter begrenzt: die
API liefert bereits ein generisches OHLC-Format (`/api/candles`), das sich unverändert auf einen
UDF-/Datafeed-Adapter abbilden lässt.

## Bekannte Datenlücken (Stand Phase 1)

- **Kein Volumen.** Vantage-MT5-Ticks enthalten Bid/Ask, aber kein handelbares Volumen
  (`last` ist 0). Es wird daher bewusst **keine** Volumenreihe gezeichnet, statt eine erfundene
  darzustellen. Binance-Volumen wäre eine andere Instrumentenreihe und darf nicht unter das
  Vantage-BTCUSD-Chart gemischt werden.
- **Begrenzte Historie für große Zeitrahmen.** Die Kerzen werden aus
  `runtime/waverun/vantage_ticks.jsonl` aggregiert. Diese Datei enthält nur die Ticks, die seit
  dem letzten Start der Engine geschrieben wurden — zum Zeitpunkt der Umsetzung rund 10 Stunden
  mit Lücken durch Engine-Neustarts. **30s, 1m, 3m, 5m und 15m sind belastbar**, **1h liefert nur
  wenige Kerzen und 4h praktisch nur eine bis vier**. Beide bleiben implementiert, weil sie mit
  wachsender Tickhistorie automatisch besser werden, sind aktuell aber nicht aussagekräftig.
- **Lücken statt Interpolation.** Zeiträume ohne Ticks erzeugen keine Kerze. Es wird bewusst
  nichts interpoliert, damit Ausfälle der Engine im Chart sichtbar bleiben.
