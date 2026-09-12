import { useState } from "react";
import { useLiveState, useNotificationPermission, useSignalAudio } from "./lib/api";
import { ShadowSignalPanel } from "./components/ShadowSignalPanel";
import { PriceChart } from "./components/PriceChart";
import {
  ExpertPanel,
  PreSignalPanel,
  SourcesPanel,
  TimelinePanel,
  V53Panel,
} from "./components/Panels";
import type { LiveState } from "./lib/types";

type NavKey =
  | "LIVE"
  | "CHART"
  | "SIGNALE"
  | "MEINE_ZONEN"
  | "PAPER_TRADING"
  | "AUSWERTUNG"
  | "DATENQUELLEN"
  | "EINSTELLUNGEN";

const NAV: Array<{ key: NavKey; label: string; ready: boolean }> = [
  { key: "LIVE", label: "LIVE", ready: true },
  { key: "CHART", label: "CHART", ready: true },
  { key: "SIGNALE", label: "SIGNALE", ready: true },
  { key: "MEINE_ZONEN", label: "MEINE ZONEN", ready: false },
  { key: "PAPER_TRADING", label: "PAPER TRADING", ready: false },
  { key: "AUSWERTUNG", label: "AUSWERTUNG", ready: false },
  { key: "DATENQUELLEN", label: "DATENQUELLEN", ready: true },
  { key: "EINSTELLUNGEN", label: "EINSTELLUNGEN", ready: false },
];

const CONNECTION_LABEL: Record<string, string> = {
  LIVE: "FULL LIVE",
  STARTING: "STARTET",
  DEGRADED: "DEGRADIERT",
  RECOVERING: "RECOVERY LÄUFT",
  CRITICAL: "KRITISCH",
  STALE: "VERZÖGERT",
  OFFLINE: "OFFLINE",
};

function connDot(connection: string, streamOk: boolean): string {
  if (!streamOk || connection === "OFFLINE" || connection === "CRITICAL") return "offline";
  if (connection === "DEGRADED" || connection === "RECOVERING" || connection === "STALE" || connection === "STARTING")
    return "warn";
  return "online";
}

function DegradedBanner({ state }: { state: LiveState }) {
  const conn = state.connection;
  if (conn === "LIVE") return null;
  const health = state.health;
  const bad = health
    ? Object.values(health.components).filter(
        (c) => !["HEALTHY", "CONNECTED", "LIVE", "IDLE_FEED_DOWN"].includes(c.state.toUpperCase()),
      )
    : [];
  const dpAge = health?.decision_pipeline_age_seconds;
  return (
    <div className={`degraded-banner ${conn === "CRITICAL" ? "critical" : "warn"}`} role="alert">
      <strong>{CONNECTION_LABEL[conn] ?? conn}</strong>
      <span>
        {conn === "CRITICAL"
          ? "Mindestdatenbasis für neue Decisions fehlt. Auto-Recovery aktiv."
          : "Mindestens eine Quelle/Pipeline ist gestört. Auto-Recovery aktiv."}
      </span>
      {bad.length > 0 && (
        <span className="banner-detail">
          Betroffen: {bad.map((c) => `${c.key}=${c.state}`).join(" · ")}
        </span>
      )}
      {typeof dpAge === "number" && dpAge > 120 && (
        <span className="banner-detail">Decision-Pipeline seit {Math.round(dpAge)}s ohne neue Records.</span>
      )}
      {health && health.recovery.level > 0 && (
        <span className="banner-detail">Recovery-Level: {health.recovery.level}</span>
      )}
    </div>
  );
}

function Header({ state, streamOk }: { state: LiveState | null; streamOk: boolean }) {
  const connection = state?.connection ?? "OFFLINE";
  const dotClass = connDot(connection, streamOk);
  const price = state?.price.mid;
  return (
    <header className="header">
      <div className="brand">
        WAVERUN <span>— LIVE</span>
      </div>
      <span className="conn">
        <span className={`dot ${dotClass}`} />
        {streamOk ? (CONNECTION_LABEL[connection] ?? connection) : "KEINE VERBINDUNG"}
      </span>
      <div className="header-price">
        <span className="symbol">{state?.price.symbol ?? "BTCUSD"}</span>
        <span className="value">
          {price === null || price === undefined
            ? "—"
            : `$${price.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
        </span>
      </div>
    </header>
  );
}

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="coming-soon">
      <h2>{label}</h2>
      <p>In Kürze verfügbar.</p>
    </div>
  );
}

function LiveView({ state }: { state: LiveState }) {
  return (
    <>
      {/* Mobile priority order is enforced by the source order below. */}
      <ShadowSignalPanel state={state} />
      <details><summary>Historische Vorstufenansicht</summary><PreSignalPanel state={state} /></details>
      <div className="grid">
        <div>
          <PriceChart />
        </div>
        <div>
          <TimelinePanel state={state} />
          <SourcesPanel state={state} />
          <V53Panel state={state} />
          <ExpertPanel state={state} />
        </div>
      </div>
    </>
  );
}

/**
 * Compact alert controls: push-notification permission (opt-in, only ever
 * requested from this explicit click) and the signal-audio toggle, on one row.
 */
function AlertControls({ audio }: { audio: { enabled: boolean; toggle: () => void } }) {
  const { permission, request } = useNotificationPermission();
  return (
    <div className="alert-controls">
      <span className="alert-controls-label">ALERTS</span>
      {permission === "default" ? (
        <button type="button" onClick={() => void request()} title="Benachrichtigungen bei echten Zustandswechseln aktivieren">
          Push aktivieren
        </button>
      ) : (
        <span className="alert-controls-state">
          Push {permission === "granted" ? "AN" : "AUS"}
        </span>
      )}
      <button
        type="button"
        aria-pressed={audio.enabled}
        onClick={audio.toggle}
        title="Signalton für neue PREWARNING-/LIVE-Übergänge"
      >
        Ton {audio.enabled ? "AN" : "AUS"}
      </button>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState<NavKey>("LIVE");
  const { state, status } = useLiveState();
  const streamOk = status === "OPEN";
  // Fires only on server-confirmed state transitions, never on every poll.
  const audio = useSignalAudio(state?.shadow_signal, streamOk);

  return (
    <div className="app">
      <Header state={state} streamOk={streamOk} />
      <div className="mode-banner">RESEARCH / SHADOW-MODUS · KEIN ECHTER HANDEL · AUSFÜHRUNG DEAKTIVIERT</div>
      {state ? <DegradedBanner state={state} /> : null}
      <AlertControls audio={audio} />
      <nav className="nav">
        {NAV.map((item) => (
          <button
            key={item.key}
            type="button"
            className={item.key === active ? "active" : ""}
            onClick={() => setActive(item.key)}
          >
            {item.label}
            {item.ready ? null : <span className="soon">in Kürze</span>}
          </button>
        ))}
      </nav>
      <main>
        {!state ? (
          <div className="panel">
            <p className="empty">
              {streamOk
                ? "Warte auf den ersten Live-Zustand der Engine …"
                : "Keine Verbindung zur WAVERUN-API. Läuft der API-Prozess auf Port 8787?"}
            </p>
          </div>
        ) : active === "LIVE" ? (
          <LiveView state={state} />
        ) : active === "CHART" ? (
          <PriceChart />
        ) : active === "SIGNALE" ? (
          <ShadowSignalPanel state={state} />
        ) : active === "DATENQUELLEN" ? (
          <SourcesPanel state={state} />
        ) : (
          <ComingSoon label={NAV.find((item) => item.key === active)?.label ?? ""} />
        )}
      </main>
    </div>
  );
}
