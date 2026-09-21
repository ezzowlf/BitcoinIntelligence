import { problemSummary } from "../lib/health";
import { age, stateText } from "../lib/language";
import type { LiveState } from "../lib/types";

/**
 * Compact replacement for the full-width CRITICAL block.
 *
 * The technical diagnosis is not removed — it moves behind <details> so it is
 * one tap away without owning the screen. Nothing here softens the state: a
 * critical system still renders in the critical colour with the word shown.
 */
export function AlertCard({ state }: { state: LiveState }) {
  const problem = problemSummary(state);
  if (!problem) return null;

  const health = state.health;
  const dpAge = health?.decision_pipeline_age_seconds ?? null;

  return (
    <section className={`alert ${problem.critical ? "alert-bad" : "alert-warn"}`} role="alert">
      <div className="alert-head">
        <span className="alert-icon" aria-hidden="true">
          {problem.critical ? "▲" : "!"}
        </span>
        <span className="alert-title">{problem.headline}</span>
      </div>
      <p className="alert-body">{problem.body}</p>

      <details className="alert-details">
        <summary>Details</summary>
        <dl className="kv">
          {problem.affected.map((row) => (
            <div className="kv-row" key={row.key}>
              <dt>{row.label}</dt>
              <dd>
                <span className={`tag tag-${row.tone}`}>{stateText(row.state)}</span>
                <span className="kv-sub">
                  {row.ageSeconds !== null ? age(row.ageSeconds) : "—"}
                  {row.reconnects > 0 ? ` · ${row.reconnects} Reconnects` : ""}
                </span>
                {row.detail ? <span className="kv-note">{row.detail}</span> : null}
                {row.lastError ? <span className="kv-note">{row.lastError}</span> : null}
              </dd>
            </div>
          ))}
          {dpAge !== null && (
            <div className="kv-row">
              <dt>Decision-Pipeline</dt>
              <dd>
                <span className="kv-sub">letzter Record {age(dpAge)}</span>
              </dd>
            </div>
          )}
          {health && health.recovery.level > 0 && (
            <div className="kv-row">
              <dt>Recovery</dt>
              <dd>
                <span className="kv-sub">
                  Level {health.recovery.level} · {health.recovery.attempts} Versuche
                </span>
              </dd>
            </div>
          )}
        </dl>
        {health?.reasons?.length ? (
          <p className="alert-codes">
            Technisch: {health.reasons.join(" · ")}
          </p>
        ) : null}
      </details>
    </section>
  );
}
