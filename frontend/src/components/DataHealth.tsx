import { dataHealthRows, type FeedRow } from "../lib/health";
import { age, clockTime, stateText } from "../lib/language";
import type { LiveState } from "../lib/types";

/**
 * Feed-by-feed truth, so a frozen feed is obvious at a glance instead of being
 * inferred from a missing signal. Per-feed diagnostics stay collapsed.
 */
export function DataHealth({ state, title = "DATA HEALTH" }: { state: LiveState; title?: string }) {
  const rows = dataHealthRows(state);
  return (
    <section className="card">
      <h2 className="card-title">{title}</h2>
      <ul className="health-list">
        {rows.map((row) => (
          <HealthRow key={row.key} row={row} />
        ))}
      </ul>
    </section>
  );
}

export function HealthRow({ row }: { row: FeedRow }) {
  const hasDetail = row.lastEventAt || row.detail || row.lastError || row.reconnects > 0;
  return (
    <li className="health-item">
      <details>
        <summary>
          <span className="health-name">
            {row.label}
            {row.optional ? <span className="opt">optional</span> : null}
          </span>
          <span className="health-state">
            <span className="health-age">{row.ageSeconds !== null ? age(row.ageSeconds) : ""}</span>
            <span className={`tag tag-${row.tone}`}>
              <i className={`dot dot-${row.tone}`} aria-hidden="true" />
              {stateText(row.state)}
            </span>
          </span>
        </summary>
        <dl className="kv">
          {row.lastEventAt && (
            <div className="kv-row">
              <dt>Letztes Event</dt>
              <dd>{clockTime(row.lastEventAt)}</dd>
            </div>
          )}
          <div className="kv-row">
            <dt>Alter</dt>
            <dd>{row.ageSeconds !== null ? `${row.ageSeconds.toFixed(1)} s` : "—"}</dd>
          </div>
          <div className="kv-row">
            <dt>Reconnects</dt>
            <dd>{row.reconnects}</dd>
          </div>
          {row.recoveryLevel > 0 && (
            <div className="kv-row">
              <dt>Recovery-Level</dt>
              <dd>{row.recoveryLevel}</dd>
            </div>
          )}
          {row.detail && (
            <div className="kv-row">
              <dt>Detail</dt>
              <dd className="mono">{row.detail}</dd>
            </div>
          )}
          {row.lastError && (
            <div className="kv-row">
              <dt>Letzter Fehler</dt>
              <dd className="mono">{row.lastError}</dd>
            </div>
          )}
          {!hasDetail && (
            <div className="kv-row">
              <dt>Status</dt>
              <dd className="dim">Keine weiteren Angaben</dd>
            </div>
          )}
        </dl>
      </details>
    </li>
  );
}
