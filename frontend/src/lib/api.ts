import { useEffect, useState } from "react";
import type { CandleResponse, LiveState, Timeframe } from "./types";

// Single point of contact with the backend. The browser never speaks to MT5,
// Binance or any exchange directly.
const BASE = import.meta.env.VITE_WAVERUN_API ?? "";

export type StreamStatus = "CONNECTING" | "OPEN" | "ERROR";

export function useLiveState(): { state: LiveState | null; status: StreamStatus } {
  const [state, setState] = useState<LiveState | null>(null);
  const [status, setStatus] = useState<StreamStatus>("CONNECTING");

  useEffect(() => {
    const source = new EventSource(`${BASE}/api/stream`);
    source.onopen = () => setStatus("OPEN");
    source.onmessage = (event) => {
      try {
        setState(JSON.parse(event.data) as LiveState);
        setStatus("OPEN");
      } catch {
        setStatus("ERROR");
      }
    };
    source.onerror = () => setStatus("ERROR");
    return () => source.close();
  }, []);

  return { state, status };
}

export async function fetchCandles(timeframe: Timeframe, limit = 1000): Promise<CandleResponse> {
  const response = await fetch(`${BASE}/api/candles?timeframe=${timeframe}&limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Kerzendaten konnten nicht geladen werden (HTTP ${response.status})`);
  }
  return (await response.json()) as CandleResponse;
}

/** Poll candles while the chart is visible; the engine appends ticks continuously. */
export function useCandles(timeframe: Timeframe, intervalMs = 5000) {
  const [data, setData] = useState<CandleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // `active` is scoped to this effect run, so a request still in flight from a
    // previous timeframe can never overwrite the newly selected one.
    let active = true;
    let timer: number | undefined;
    const load = async () => {
      try {
        const next = await fetchCandles(timeframe);
        if (!active) return;
        setData(next);
        setError(null);
      } catch (cause) {
        if (!active) return;
        setError((cause as Error).message);
      }
      if (active) timer = window.setTimeout(load, intervalMs);
    };
    void load();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [timeframe, intervalMs]);

  return { data, error };
}
