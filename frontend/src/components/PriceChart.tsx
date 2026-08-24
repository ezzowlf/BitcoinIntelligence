import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useCandles } from "../lib/api";
import { TIMEFRAMES, type Timeframe } from "../lib/types";

// TradingView Lightweight Charts™ (Apache-2.0). Attribution is required by the
// licence and is rendered below the chart. See frontend/TRADINGVIEW_DECISION.md.
export function PriceChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>("1m");
  const { data, error } = useCandles(timeframe);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const fittedFor = useRef<string | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = createChart(host, {
      width: host.clientWidth || 800,
      height: host.clientHeight || 460,
      layout: {
        background: { type: ColorType.Solid, color: "#11151c" },
        textColor: "#8592a3",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#1b222d" },
        horzLines: { color: "#1b222d" },
      },
      rightPriceScale: { borderColor: "#232b38" },
      timeScale: { borderColor: "#232b38", timeVisible: true, secondsVisible: true },
      crosshair: { mode: 0 },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#2eb87e",
      downColor: "#d95c66",
      wickUpColor: "#2eb87e",
      wickDownColor: "#d95c66",
      borderVisible: false,
    });
    chartRef.current = chart;
    seriesRef.current = series;

    // Explicit resize handling keeps the chart correct on window resize and on
    // the mobile breakpoints, without relying on the library's autoSize option.
    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: host.clientWidth, height: host.clientHeight });
    });
    observer.observe(host);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !data) return;
    series.setData(
      data.candles.map((candle) => ({
        time: candle.time as UTCTimestamp,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      })),
    );
    if (fittedFor.current !== timeframe) {
      fittedFor.current = timeframe;
      chartRef.current?.timeScale().fitContent();
    }
  }, [data, timeframe]);

  return (
    <section className="panel">
      <h2 className="panel-title">CHART — BTCUSD (VANTAGE)</h2>
      <div className="chart-toolbar">
        {TIMEFRAMES.map((item) => (
          <button
            key={item}
            type="button"
            className={`tf ${item === timeframe ? "active" : ""}`}
            onClick={() => setTimeframe(item)}
          >
            {item}
          </button>
        ))}
        <span className="spacer">
          {data ? `${data.candles.length} Kerzen · ${data.tick_count.toLocaleString("de-DE")} Ticks` : "lädt …"}
        </span>
      </div>
      <div className="chart-host" ref={hostRef} />
      {error ? <p className="note" style={{ color: "var(--short)" }}>{error}</p> : null}
      {data && data.candles.length === 0 ? (
        <p className="empty">Noch keine Kerzen für diesen Zeitrahmen — die Engine sammelt Ticks.</p>
      ) : null}
      <p className="attribution">
        Kerzen aus persistierten Vantage-BTCUSD-Ticks (kein Volumen verfügbar). Charts von{" "}
        <a href="https://www.tradingview.com" target="_blank" rel="noreferrer noopener">
          TradingView
        </a>{" "}
        — Lightweight Charts™.
      </p>
    </section>
  );
}
