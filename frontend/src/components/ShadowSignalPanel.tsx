import type { LiveState } from "../lib/types";

const money = (n: number | null | undefined) => n == null ? "Nicht verfügbar" : `$${n.toLocaleString("de-DE", { maximumFractionDigits: 2 })}`;

// The engine's own state machine (see waverun_live.py SignalEngine): a setup
// walks OBSERVING -> CANDIDATE -> {REJECTED|CANCELLED|EXPIRED|PREWARNING} ->
// {ARMED} -> LIVE. Anything other than PREWARNING/ARMED/LIVE means the engine
// is running and evaluating, but has no active signal right now — that is a
// normal, frequent, correct state and must never be shown as if the engine
// itself were unavailable.
const NO_ACTIVE_SIGNAL_STATES = new Set([
  "OBSERVING", "CANDIDATE", "REJECTED", "CANCELLED", "EXPIRED", "IDLE",
]);
const ACTIVE_SIGNAL_STATES = new Set(["PREWARNING", "ARMED", "LIVE"]);

/**
 * Engine availability and "is there a signal right now" are two independent
 * facts and must never be collapsed into one hardcoded label. `shadow` is only
 * absent when the API has not yet delivered a shadow_signal payload at all
 * (e.g. right after page load, or the engine process itself is down) — that
 * is the ONLY case allowed to say the engine is unavailable.
 */
function engineStatus(shadow: LiveState["shadow_signal"]): { engineLive: boolean; label: string; detail: string } {
  if (!shadow) {
    return { engineLive: false, label: "SIGNALENGINE · KEINE DATEN", detail: "Signaldaten nicht verfügbar." };
  }
  if (shadow.paused) {
    return { engineLive: true, label: "SIGNALENGINE · PAUSIERT", detail: "Engine läuft, Auswertung pausiert." };
  }
  const raw = shadow.state ?? "";
  if (ACTIVE_SIGNAL_STATES.has(raw)) {
    return { engineLive: true, label: `SIGNALENGINE · LIVE`, detail: raw === "PREWARNING" ? "VORWARNUNG" : raw === "ARMED" ? "SCHARF" : "AKTIVES SIGNAL" };
  }
  if (NO_ACTIVE_SIGNAL_STATES.has(raw) || raw === "") {
    return { engineLive: true, label: "SIGNALENGINE · LIVE", detail: "KEIN AKTIVES SIGNAL" };
  }
  // Unknown-but-present state: still evaluating, show it verbatim rather than guessing.
  return { engineLive: true, label: "SIGNALENGINE · LIVE", detail: raw };
}

export function ShadowSignalPanel({ state }: { state: LiveState }) {
  const shadow = state.shadow_signal;
  const signal = shadow?.signal;
  const status = engineStatus(shadow);
  return <section className="panel shadow-signal" aria-label="TAKEOFF Signalengine">
    <h2>{status.label}</h2>
    <p><strong>{status.detail}</strong>
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
    </> : <p className="note">{status.engineLive ? "Engine wertet kontinuierlich aus. Ein ruhiger Markt kann legitim kein Signal erzeugen." : "Warte auf Verbindung zur Engine."}</p>}
    <details><summary>Quellen und Verarbeitungsschritte</summary>
      <ul>{Object.values(state.health?.components ?? {}).map(c => <li key={c.key}>{c.key}: <strong>{c.state}</strong>{c.age_seconds == null ? "" : ` · ${Math.round(c.age_seconds)}s`}</li>)}</ul>
    </details>
  </section>;
}
