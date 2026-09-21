import { useState } from "react";
import { useLiveState, useSignalAudio } from "./lib/api";
import { Header } from "./components/Header";
import { AlertCard } from "./components/AlertCard";
import { SignalCard } from "./components/SignalCard";
import { DataHealth } from "./components/DataHealth";
import { SignalHistory } from "./components/SignalHistory";
import { SystemPage } from "./components/SystemPage";
import { PriceChart } from "./components/PriceChart";

/**
 * Four tabs, because a phone toolbar cannot carry eight and still offer a
 * touch target worth hitting. Research surfaces that were half-built are no
 * longer advertised in the primary navigation (they live on SYSTEM or are
 * simply absent) rather than sitting there labelled "in Kürze".
 */
type Tab = "LIVE" | "SIGNALE" | "CHART" | "SYSTEM";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "LIVE", label: "LIVE" },
  { key: "SIGNALE", label: "SIGNALE" },
  { key: "CHART", label: "CHART" },
  { key: "SYSTEM", label: "SYSTEM" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("LIVE");
  const { state, status } = useLiveState();
  const streamOk = status === "OPEN";
  // Fires only on server-confirmed transitions, never on every stream frame.
  useSignalAudio(state?.shadow_signal, streamOk);

  return (
    <div className="app">
      <Header state={state} streamOk={streamOk} />

      {/* Safety notice stays permanently visible, but compact. */}
      <div className="mode-strip">
        <strong>RESEARCH / SHADOW MODE</strong>
        <span>KEIN ECHTER HANDEL · AUTO-EXECUTION AUS</span>
      </div>

      <main className="main">
        {!state ? (
          <section className="card">
            <p className="empty">
              {streamOk
                ? "Warte auf den ersten Live-Zustand der Engine …"
                : "Keine Verbindung zur TAKEOFF-API."}
            </p>
          </section>
        ) : (
          <>
            <AlertCard state={state} />
            {tab === "LIVE" && (
              <>
                <SignalCard state={state} />
                <DataHealth state={state} />
              </>
            )}
            {tab === "SIGNALE" && (
              <>
                <SignalCard state={state} />
                <SignalHistory />
              </>
            )}
            {tab === "CHART" && (
              <section className="card card-flush">
                <PriceChart />
              </section>
            )}
            {tab === "SYSTEM" && <SystemPage state={state} streamOk={streamOk} />}
          </>
        )}
      </main>

      <nav className="tabbar" aria-label="Hauptnavigation">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            aria-current={tab === item.key ? "page" : undefined}
            className={tab === item.key ? "active" : ""}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
