import { useState } from "react";
import type { LiveState, PreSignalState } from "../lib/types";

const DIRECTION_CLASS: Record<string, string> = {
  LONG: "long",
  SHORT: "short",
  BULLISH: "long",
  BEARISH: "short",
};

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

const COMPONENT_LABELS: Record<string, string> = {
  marktzustand: "Marktzustand",
  richtungs_bias: "Richtungs-Bias",
  druck: "Druck",
  flow_bestaetigung: "Flow-Bestätigung",
  l2_ausrichtung: "L2-Ausrichtung",
  datenqualitaet: "Datenqualität",
};

const STATE_LABELS: Record<string, string> = {
  NEUTRAL: "NEUTRAL",
  WATCH: "BEOBACHTUNG",
  ARMED: "SCHARF",
  SIGNAL: "SIGNAL",
  WATCH_CANCELLED: "BEOBACHTUNG ABGEBROCHEN",
  SIGNAL_INVALIDATED: "SIGNAL INVALIDIERT",
  EXIT: "AUSSTIEG",
};

const FLOW_LABELS: Record<string, string> = {
  CONFIRMED: "BESTÄTIGT",
  DIVERGENT: "DIVERGENT",
  NEUTRAL: "NEUTRAL",
  BULLISH: "AUFWÄRTS",
  BEARISH: "ABWÄRTS",
  UNAVAILABLE: "NICHT VERFÜGBAR",
};

export function AssessmentPanel({ state }: { state: LiveState }) {
  const market = state.market_state;
  const directionClass = DIRECTION_CLASS[market.direction_bias] ?? "";
  return (
    <section className="panel">
      <h2 className="panel-title">AKTUELLE EINSCHÄTZUNG</h2>
      <div className="state-row">
        <span className="tag watch">{STATE_LABELS[market.setup_state] ?? market.setup_state}</span>
        <span className={`tag ${directionClass}`}>BIAS: {market.direction_bias}</span>
        <span className="tag">
          FLOW: {FLOW_LABELS[market.flow_agreement] ?? market.flow_agreement}
        </span>
        <span className="tag">ENGINE: {market.final_decision || "—"}</span>
      </div>
      <p className="assessment">{state.assessment}</p>
      <p className="note">
        Dieser Text wird deterministisch aus den Zustandsfeldern der Engine erzeugt. Keine Prognose,
        keine Handelsempfehlung.
      </p>
    </section>
  );
}

export function ProximityPanel({ state }: { state: LiveState }) {
  const { score, components } = state.proximity;
  const color =
    state.market_state.direction_bias === "LONG"
      ? "var(--long)"
      : state.market_state.direction_bias === "SHORT"
        ? "var(--short)"
        : "var(--neutral)";
  return (
    <section className="panel">
      <h2 className="panel-title">SIGNALNÄHE</h2>
      <div className="score-head">
        <div className="score-value">{formatNumber(score, 0)}</div>
        <div className="score-max">SIGNALNÄHE-SCORE · 0–100</div>
      </div>
      <div className="bar">
        <div
          className="bar-fill"
          style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: color }}
        />
      </div>
      <p className="note">
        Der SIGNALNÄHE-SCORE misst, wie weit die Bedingungen der Engine fortgeschritten sind. Er ist
        ausdrücklich keine Wahrscheinlichkeit und keine Trefferquote.
      </p>
      <div className="components">
        {Object.entries(components).map(([key, value]) => (
          <div className="row" key={key}>
            <span className="muted">{COMPONENT_LABELS[key] ?? key}</span>
            <span className="value">{formatNumber(value, 1)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * The calm default view. Strong colour is reserved for SIGNAL_NAHE/TESTSIGNAL —
 * everything below that stays neutral so the page does not feel like it is
 * permanently "almost signalling".
 */
export function PreSignalPanel({ state }: { state: LiveState }) {
  const pre = state.presignal;
  const loud = pre.state === "SIGNAL_NAHE" || pre.state === "TESTSIGNAL";
  const tone: Record<PreSignalState, string> = {
    RUHIG: "calm",
    BEOBACHTEN: "calm",
    SETUP_ENTSTEHT: "watch",
    SIGNAL_NAHE: DIRECTION_CLASS[pre.direction] ?? "watch",
    TESTSIGNAL: DIRECTION_CLASS[pre.direction] ?? "watch",
    INVALIDIERT: "calm",
  };
  const minutes = Math.floor(pre.seconds_in_state / 60);
  const since =
    minutes >= 1 ? `seit ${minutes} min` : `seit ${Math.round(pre.seconds_in_state)} s`;

  return (
    <section className={`panel presignal ${loud ? "loud" : ""}`}>
      <h2 className="panel-title">ZUSTAND</h2>
      <div className="presignal-head">
        <span className={`state-label ${tone[pre.state] ?? "calm"}`}>{pre.label}</span>
        <span className="muted">{since}</span>
      </div>
      <p className="presignal-headline">{pre.headline}</p>
      {pre.show_checklist ? (
        <div className="components">
          {pre.conditions.map((row) => (
            <div className={`check ${row.status.toLowerCase()}`} key={row.key}>
              <span className="mark">{row.status === "MET" ? "✓" : "✗"}</span>
              <div className="body">
                <div className="label">{row.label}</div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <p className="note">
        Research- und Schatten-Modus. Keine Prognose, keine Handelsempfehlung, Ausführung
        deaktiviert.
      </p>
    </section>
  );
}

export function TimelinePanel({ state }: { state: LiveState }) {
  const events = state.presignal.timeline;
  return (
    <section className="panel">
      <h2 className="panel-title">VERLAUF</h2>
      {events.length === 0 ? (
        <p className="empty small">Seit dem Start des Servers gab es keinen Zustandswechsel.</p>
      ) : (
        events.map((event) => (
          <div className="timeline-row" key={`${event.to}-${event.timestamp}`}>
            <span className="time">
              {new Date(event.timestamp).toLocaleTimeString("de-DE", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <div className="body">
              <div className="label">{event.label}</div>
              <div className="detail">{event.reason}</div>
            </div>
          </div>
        ))
      )}
    </section>
  );
}

/** Everything numeric and restless lives behind this collapsed section. */
export function ExpertPanel({ state }: { state: LiveState }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="panel">
      <button type="button" className="expert-toggle" onClick={() => setOpen((value) => !value)}>
        <span className="panel-title">EXPERTENMODUS</span>
        <span className="chev">{open ? "▲" : "▼"}</span>
      </button>
      {open ? (
        <div className="expert-body">
          <AssessmentPanel state={state} />
          <ProximityPanel state={state} />
          <ChecklistPanel state={state} />
          <MarketDetailPanel state={state} />
        </div>
      ) : null}
    </section>
  );
}

const MARKS: Record<string, string> = { MET: "✓", MISSING: "✗", RISK: "⚠" };

export function ChecklistPanel({ state }: { state: LiveState }) {
  return (
    <section className="panel">
      <h2 className="panel-title">WARUM (NOCH) KEIN SIGNAL?</h2>
      {state.checklist.map((row) => (
        <div className={`check ${row.status.toLowerCase()}`} key={row.label}>
          <span className="mark">{MARKS[row.status] ?? "·"}</span>
          <div className="body">
            <div className="label">{row.label}</div>
            <div className="detail">{row.detail}</div>
          </div>
        </div>
      ))}
    </section>
  );
}

export function SourcesPanel({ state }: { state: LiveState }) {
  return (
    <section className="panel">
      <h2 className="panel-title">DATENQUELLEN</h2>
      {state.sources.map((source) => (
        <div className="row" key={source.key}>
          <span>
            <span className={`dot ${source.online ? "online" : "offline"}`} style={{ marginRight: ".5rem" }} />
            {source.label}
          </span>
          <span className="value" style={{ color: source.online ? "var(--long)" : "var(--short)" }}>
            {source.online ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      ))}
      {state.health ? (
        <>
          <h2 className="panel-title" style={{ marginTop: "0.75rem" }}>PIPELINE</h2>
          {(["decision_pipeline", "prediction_persistence", "candidate_pipeline"] as const).map((key) => {
            const c = state.health!.components[key];
            if (!c) return null;
            const ok = ["HEALTHY", "CONNECTED", "IDLE_FEED_DOWN"].includes(c.state.toUpperCase());
            return (
              <div className="row" key={key}>
                <span>
                  <span className={`dot ${ok ? "online" : "offline"}`} style={{ marginRight: ".5rem" }} />
                  {key.replace(/_/g, " ")}
                </span>
                <span className="value" style={{ color: ok ? "var(--long)" : "var(--short)" }}>
                  {c.state}
                  {typeof c.age_seconds === "number" ? ` · ${Math.round(c.age_seconds)}s` : ""}
                </span>
              </div>
            );
          })}
          <p className="note">
            Betriebszustand: {state.health.operating_state ?? state.connection}
            {state.health.reasons?.length ? ` — ${state.health.reasons.join("; ")}` : ""}
          </p>
        </>
      ) : null}
      <p className="note">Rohstatus der Engine: {state.sources.map((s) => `${s.label}=${s.state}`).join(" · ")}</p>
    </section>
  );
}

export function MarketDetailPanel({ state }: { state: LiveState }) {
  const market = state.market_state;
  const rows: Array<[string, string]> = [
    ["Vantage Bid", state.price.bid === null ? "—" : `$${formatNumber(state.price.bid)}`],
    ["Vantage Ask", state.price.ask === null ? "—" : `$${formatNumber(state.price.ask)}`],
    ["Spread", state.price.spread === null ? "—" : `$${formatNumber(state.price.spread)}`],
    ["Tick-Alter", state.price.age_seconds === null ? "—" : `${formatNumber(state.price.age_seconds, 1)} s`],
    ["Druck LONG", formatNumber(market.long_pressure_score, 0)],
    ["Druck SHORT", formatNumber(market.short_pressure_score, 0)],
    ["Spot-Orderflow", FLOW_LABELS[market.spot_flow] ?? market.spot_flow],
    ["Futures-Orderflow", FLOW_LABELS[market.futures_flow] ?? market.futures_flow],
    ["L2-Imbalance", market.l2_imbalance === null ? "—" : formatNumber(market.l2_imbalance, 4)],
    ["Spannen-Ausweitung", market.range_expansion === null ? "—" : formatNumber(market.range_expansion, 2)],
  ];
  return (
    <section className="panel">
      <h2 className="panel-title">MARKTDETAILS</h2>
      {rows.map(([label, value]) => (
        <div className="row" key={label}>
          <span className="muted">{label}</span>
          <span className="value">{value}</span>
        </div>
      ))}
    </section>
  );
}

export function V53Panel({ state }: { state: LiveState }) {
  const v53 = state.v5_3;
  return (
    <section className="panel">
      <h2 className="panel-title">V5.3 FAST V2</h2>
      <div className="split">
        <div className="figure">
          <div className="cap">DISCOVERY</div>
          <div className="big">{formatNumber(v53.discovery_win_rate, 2)} %</div>
          <p className="note">Historische Entdeckungsphase. Kein Live-Ergebnis.</p>
        </div>
        <div className="figure">
          <div className="cap">LIVE-VALIDIERUNG</div>
          <div className="big">
            {v53.forward_resolved} / {v53.forward_target}
          </div>
          <p className="note">Aufgelöste Forward-Signale seit Start.</p>
        </div>
      </div>
      <div className="warn-note">NOCH NICHT VERIFIZIERT — die Live-Validierung läuft.</div>
      <div className="components">
        <div className="row">
          <span className="muted">Akzeptierte Signale</span>
          <span className="value">{v53.accepted_signals}</span>
        </div>
        <div className="row">
          <span className="muted">Durch Veto blockiert</span>
          <span className="value">{v53.veto_blocked_signals}</span>
        </div>
        <div className="row">
          <span className="muted">Treffer $100 / 5 min</span>
          <span className="value">{v53.forward_wins}</span>
        </div>
        <div className="row">
          <span className="muted">Status</span>
          <span className="value">{v53.status}</span>
        </div>
      </div>
      <p className="note">Hypothesen-Hash: {v53.hypothesis_sha256.slice(0, 16)}…</p>
    </section>
  );
}
