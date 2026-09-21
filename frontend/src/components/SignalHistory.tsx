import { useState } from "react";
import { useSignalHistory } from "../lib/api";
import { clockTime, dateTime, evidenceText, horizon, reasonText, usd } from "../lib/language";
import type { SignalHistoryRow } from "../lib/types";

type Filter = "ALL" | "LONG" | "SHORT";

const FILTERS: Filter[] = ["ALL", "LONG", "SHORT"];
const FILTER_LABEL: Record<Filter, string> = { ALL: "ALLE", LONG: "LONG", SHORT: "SHORT" };

/**
 * Signal history as cards, not a table: a phone cannot show a ten-column grid
 * without either horizontal scroll or unreadable type.
 */
export function SignalHistory() {
  const [filter, setFilter] = useState<Filter>("ALL");
  const { rows, available, error } = useSignalHistory(filter);

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">SIGNALE</h2>
        <div className="seg" role="tablist" aria-label="Richtung filtern">
          {FILTERS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={filter === value}
              className={filter === value ? "active" : ""}
              onClick={() => setFilter(value)}
            >
              {FILTER_LABEL[value]}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p className="empty">Verlauf nicht erreichbar: {error}</p>
      ) : !available ? (
        <p className="empty">Verlauf derzeit nicht verfügbar.</p>
      ) : rows.length === 0 ? (
        <p className="empty">Keine Signalübergänge für diesen Filter.</p>
      ) : (
        <ul className="signal-list">
          {rows.map((row) => (
            <SignalRow key={`${row.setup_id}-${row.timestamp}-${row.state_to}`} row={row} />
          ))}
        </ul>
      )}
    </section>
  );
}

const OUTCOME_TONE: Record<string, string> = {
  LIVE: "ok",
  ARMED: "ok",
  PREWARNING: "warn",
  CANDIDATE: "warn",
  OUTCOME: "ok",
  REJECTED: "bad",
  CANCELLED: "bad",
  EXPIRED: "idle",
};

function SignalRow({ row }: { row: SignalHistoryRow }) {
  const [low, high] = row.entry_zone ?? [null, null];
  const stateTone = OUTCOME_TONE[row.state_to] ?? "idle";
  return (
    <li className="signal-item">
      <details>
        <summary>
          <span className="si-main">
            <span className={`si-dir si-${(row.direction ?? "").toLowerCase()}`}>{row.direction ?? "—"}</span>
            <span className="si-time">{dateTime(row.timestamp)}</span>
          </span>
          <span className="si-right">
            {row.synthetic ? <span className="tag tag-warn">TEST</span> : null}
            <span className={`tag tag-${stateTone}`}>{row.state_to}</span>
          </span>
        </summary>
        <dl className="kv">
          <div className="kv-row">
            <dt>Übergang</dt>
            <dd>
              {row.state_from} → {row.state_to}
            </dd>
          </div>
          <div className="kv-row">
            <dt>Entry-Zone</dt>
            <dd>
              {usd(low)} – {usd(high)}
            </dd>
          </div>
          <div className="kv-row">
            <dt>Invalidierung</dt>
            <dd>{usd(row.invalidation)}</dd>
          </div>
          <div className="kv-row">
            <dt>Zielklasse</dt>
            <dd>{row.expected_move_class ? `$${row.expected_move_class}` : "—"}</dd>
          </div>
          <div className="kv-row">
            <dt>Horizont</dt>
            <dd>{horizon(row.expected_horizon)}</dd>
          </div>
          <div className="kv-row">
            <dt>Gültig bis</dt>
            <dd>{clockTime(row.expires_at)}</dd>
          </div>
          {row.reasons.length > 0 && (
            <div className="kv-row">
              <dt>Grund</dt>
              <dd>{row.reasons.map(reasonText).join(" · ")}</dd>
            </div>
          )}
          {row.missing_evidence.length > 0 && (
            <div className="kv-row">
              <dt>Fehlende Daten</dt>
              <dd>{row.missing_evidence.map(evidenceText).join(" · ")}</dd>
            </div>
          )}
          <div className="kv-row">
            <dt>Signal-ID</dt>
            <dd className="mono">{(row.setup_id ?? "").slice(0, 12)}</dd>
          </div>
        </dl>
      </details>
    </li>
  );
}
