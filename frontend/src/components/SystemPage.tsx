import { allComponents } from "../lib/health";
import { age, clockTime, stateText } from "../lib/language";
import type { LiveState } from "../lib/types";
import { HealthRow } from "./DataHealth";

const PIPELINE_KEYS = [
  "market_event_pipeline",
  "feature_pipeline",
  "candidate_pipeline",
  "decision_pipeline",
  "prediction_persistence",
  "outcome_scheduler",
  "storage",
];

const FEED_KEYS = ["vantage", "binance_spot", "binance_futures", "l2"];

/**
 * Everything technical, moved off the main view. No secrets are rendered here:
 * the API exposes no credentials and this page adds none.
 */
export function SystemPage({ state, streamOk }: { state: LiveState; streamOk: boolean }) {
  const components = allComponents(state);
  const byKey = new Map(components.map((row) => [row.key, row]));
  const feeds = FEED_KEYS.map((key) => byKey.get(key)).filter(Boolean);
  const pipeline = PIPELINE_KEYS.map((key) => byKey.get(key)).filter(Boolean);
  const rest = components.filter(
    (row) => !FEED_KEYS.includes(row.key) && !PIPELINE_KEYS.includes(row.key),
  );
  const health = state.health;

  return (
    <>
      <section className="card">
        <h2 className="card-title">SYSTEM</h2>
        <dl className="kv">
          <div className="kv-row">
            <dt>Gesamtstatus</dt>
            <dd>{stateText(state.connection)}</dd>
          </div>
          <div className="kv-row">
            <dt>Operating State</dt>
            <dd className="mono">{state.operating_state ?? "—"}</dd>
          </div>
          <div className="kv-row">
            <dt>Dashboard-Stream</dt>
            <dd>{streamOk ? "verbunden" : "getrennt"}</dd>
          </div>
          <div className="kv-row">
            <dt>Serverzeit</dt>
            <dd>{clockTime(state.server_time)}</dd>
          </div>
          <div className="kv-row">
            <dt>Health-Report</dt>
            <dd>{age(health?.supervisor_report_age_seconds)}</dd>
          </div>
          <div className="kv-row">
            <dt>Letzte Decision</dt>
            <dd>{age(health?.decision_pipeline_age_seconds)}</dd>
          </div>
          <div className="kv-row">
            <dt>Recovery</dt>
            <dd>
              Level {health?.recovery.level ?? 0} · {health?.recovery.attempts ?? 0} Versuche
            </dd>
          </div>
          <div className="kv-row">
            <dt>Ticks</dt>
            <dd>{state.tick_count?.toLocaleString("de-DE") ?? "—"}</dd>
          </div>
          <div className="kv-row">
            <dt>Ausführung</dt>
            <dd className="tone-bad">{state.execution}</dd>
          </div>
        </dl>
        {health?.reasons?.length ? (
          <p className="alert-codes">Begründung: {health.reasons.join(" · ")}</p>
        ) : null}
      </section>

      <section className="card">
        <h2 className="card-title">FEEDS</h2>
        <ul className="health-list">
          {feeds.map((row) => row && <HealthRow key={row.key} row={row} />)}
        </ul>
      </section>

      <section className="card">
        <h2 className="card-title">PIPELINE</h2>
        <ul className="health-list">
          {pipeline.map((row) => row && <HealthRow key={row.key} row={row} />)}
        </ul>
      </section>

      {rest.length > 0 && (
        <section className="card">
          <h2 className="card-title">WEITERE KOMPONENTEN</h2>
          <ul className="health-list">
            {rest.map((row) => (
              <HealthRow key={row.key} row={row} />
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2 className="card-title">FORSCHUNGSSTAND V5.3</h2>
        <dl className="kv">
          <div className="kv-row">
            <dt>Status</dt>
            <dd className="mono">{state.v5_3.status}</dd>
          </div>
          <div className="kv-row">
            <dt>Forward-Fortschritt</dt>
            <dd>{state.v5_3.forward_progress}</dd>
          </div>
          <div className="kv-row">
            <dt>Verifiziert</dt>
            <dd>{state.v5_3.verified ? "ja" : "nein"}</dd>
          </div>
          <div className="kv-row">
            <dt>Hypothese</dt>
            <dd className="mono">{state.v5_3.hypothesis_sha256.slice(0, 12)}</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
