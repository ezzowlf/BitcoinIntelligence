import { useState } from "react";
import { useAlertAnnouncer, useLiveState, useNotificationPermission } from "./lib/api";
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
  { key: "SIGNALE", label: "SIGNALE", ready: false },
  { key: "MEINE_ZONEN", label: "MEINE ZONEN", ready: false },
  { key: "PAPER_TRADING", label: "PAPER TRADING", ready: false },
  { key: "AUSWERTUNG", label: "AUSWERTUNG", ready: false },
  { key: "DATENQUELLEN", label: "DATENQUELLEN", ready: true },
  { key: "EINSTELLUNGEN", label: "EINSTELLUNGEN", ready: false },
];

const CONNECTION_LABEL: Record<string, string> = {
  LIVE: "LIVE",
  STALE: "VERZÖGERT",
  OFFLINE: "OFFLINE",
};

function Header({ state, streamOk }: { state: LiveState | null; streamOk: boolean }) {
  const connection = state?.connection ?? "OFFLINE";
  const dotClass = !streamOk || connection === "OFFLINE" ? "offline" : connection === "STALE" ? "warn" : "online";
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
      <PreSignalPanel state={state} />
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

/** Opt-in banner. The permission prompt only ever runs from this click. */
function AlertOptIn() {
  const { permission, request } = useNotificationPermission();
  if (permission !== "default") return null;
  return (
    <div className="alert-optin">
      <span>Benachrichtigungen bei echten Zustandswechseln aktivieren?</span>
      <button type="button" onClick={() => void request()}>
        Aktivieren
      </button>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState<NavKey>("LIVE");
  const { state, status } = useLiveState();
  const streamOk = status === "OPEN";
  // Fires only on server-confirmed state transitions, never on every poll.
  useAlertAnnouncer(state?.alerts, true);

  return (
    <div className="app">
      <Header state={state} streamOk={streamOk} />
      <div className="mode-banner">RESEARCH / SHADOW-MODUS · KEIN ECHTER HANDEL · AUSFÜHRUNG DEAKTIVIERT</div>
      <AlertOptIn />
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
        ) : active === "DATENQUELLEN" ? (
          <SourcesPanel state={state} />
        ) : (
          <ComingSoon label={NAV.find((item) => item.key === active)?.label ?? ""} />
        )}
      </main>
    </div>
  );
}
