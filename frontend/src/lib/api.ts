import { useCallback, useEffect, useRef, useState } from "react";
import type { AlertEvent, CandleResponse, LiveState, Timeframe } from "./types";
import { SignalAnnouncements } from "./signalAnnouncements";

// Single point of contact with the backend. The browser never speaks to MT5,
// Binance or any exchange directly.
const BASE = import.meta.env.VITE_WAVERUN_API ?? "";

export type StreamStatus = "CONNECTING" | "OPEN" | "ERROR";

export function useSignalAudio(shadow: LiveState["shadow_signal"], connected: boolean) {
  const [enabled, setEnabled] = useState(() => {
    try { return localStorage.getItem("waverun.signal.audio") === "true"; } catch { return false; }
  });
  const controller = useRef<SignalAnnouncements | null>(null);
  useEffect(() => {
    try {
      controller.current ??= new SignalAnnouncements(localStorage);
      const stage = controller.current.accept(shadow?.signal, enabled && connected && !shadow?.paused, Date.now());
      if (stage) beep(stage === "LIVE");
    } catch { /* storage unavailable: remain silent */ }
  }, [shadow, enabled, connected]);
  const toggle = () => {
    const next = !enabled;
    try { localStorage.setItem("waverun.signal.audio", String(next)); setEnabled(next); } catch { setEnabled(false); }
  };
  return { enabled, toggle };
}

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

/** Short sine beep. No audio asset, no autoplay on load — only on a real transition. */
function beep(strong: boolean) {
  try {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;
    const ctx = new Ctor();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = strong ? 880 : 620;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(strong ? 0.16 : 0.08, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
    osc.onended = () => void ctx.close();
  } catch {
    /* audio is a nicety; never let it break the view */
  }
}

/**
 * Announce server-computed alert events exactly once each.
 *
 * The server already emits one alert per confirmed transition, so deduplication
 * here is only about the first stream frame after a reload: everything already
 * in the buffer at mount is marked as seen and never announced retroactively.
 * We never call `Notification.requestPermission()` on our own — that needs a
 * user gesture, exposed via `requestNotifications`.
 */
export function useAlertAnnouncer(alerts: AlertEvent[] | undefined, enabled: boolean) {
  const seen = useRef<Set<string> | null>(null);

  useEffect(() => {
    if (!alerts) return;
    if (seen.current === null) {
      // first frame: adopt history silently
      seen.current = new Set(alerts.map((alert) => alert.id));
      return;
    }
    if (!enabled) {
      for (const alert of alerts) seen.current.add(alert.id);
      return;
    }
    // oldest first so a burst is announced in chronological order
    for (const alert of [...alerts].reverse()) {
      if (seen.current.has(alert.id)) continue;
      seen.current.add(alert.id);
      if (alert.sound) beep(alert.severity === "CRITICAL");
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try {
          new Notification(alert.title, { body: alert.body, tag: alert.id });
        } catch {
          /* some browsers require a service worker; silently skip */
        }
      }
    }
  }, [alerts, enabled]);
}

export type NotificationPermissionState = "unsupported" | "default" | "granted" | "denied";

export function useNotificationPermission() {
  const [permission, setPermission] = useState<NotificationPermissionState>(() =>
    typeof Notification === "undefined" ? "unsupported" : (Notification.permission as NotificationPermissionState),
  );

  // Only ever called from an explicit click, never on mount.
  const request = useCallback(async () => {
    if (typeof Notification === "undefined") return;
    setPermission((await Notification.requestPermission()) as NotificationPermissionState);
  }, []);

  return { permission, request };
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
