import type { LiveState } from "../lib/types";

const money = (n: number | null | undefined) => n == null ? "Nicht verfügbar" : `$${n.toLocaleString("de-DE", { maximumFractionDigits: 2 })}`;

export function ShadowSignalPanel({ state }: { state: LiveState }) {
  const shadow = state.shadow_signal;
  const signal = shadow?.signal;
  return <section className="panel shadow-signal" aria-label="TAKEOFF Signalengine">
    <h2>Signalengine · LIVE</h2>
    <p><strong>{shadow?.paused ? "PAUSIERT" : shadow?.state ?? "NICHT VERFÜGBAR"}</strong>
      {shadow?.paused && signal ? ` · letzter Zustand: ${signal.state_to}` : ""}</p>
    <p>Live-Produktionssignal zur manuellen Nutzung · Unkalibriert, keine nachgewiesene Trefferquote · Automatische Ausführung deaktiviert</p>
    {signal ? <>
      <dl className="signal-details">
        <dt>Richtung / Zielklasse</dt><dd>{signal.direction} · {money(signal.expected_move_class)}</dd>
        <dt>Erwarteter Beginn</dt><dd>{signal.expected_start_window.map(t => new Date(t).toLocaleTimeString("de-DE")).join(" – ")} · Horizont {signal.expected_horizon}s</dd>
        <dt>Vantage Bid / Ask</dt><dd>{signal.entry_zone.map(money).join(" / ")} · Einstieg über {signal.vantage_executable_side}</dd>
        <dt>Invalidierung</dt><dd>{money(signal.invalidation)}</dd>
        <dt>Warum jetzt?</dt><dd>{signal.reasons.join(" · ") || "Keine Bestätigung"}</dd>
        <dt>Fehlende Evidenz</dt><dd>{signal.missing_evidence.join(" · ") || "Keine gemeldet"}</dd>
        <dt>Konflikte</dt><dd>{signal.conflicts.join(" · ") || "Keine gemeldet"}</dd>
        <dt>Gültig bis</dt><dd>{new Date(signal.expires_at).toLocaleString("de-DE")}</dd>
        <dt>Setup / Version</dt><dd className="signal-id">{signal.setup_id} · {signal.signal_version}</dd>
      </dl>
    </> : <p>Warte auf einen durch die Engine belegten Zustandswechsel.</p>}
    <details><summary>Quellen und Verarbeitungsschritte</summary>
      <ul>{Object.values(state.health?.components ?? {}).map(c => <li key={c.key}>{c.key}: <strong>{c.state}</strong>{c.age_seconds == null ? "" : ` · ${Math.round(c.age_seconds)}s`}</li>)}</ul>
    </details>
  </section>;
}
