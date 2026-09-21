import { useLiveSignals } from "../lib/api";
import { dateTime, horizon, seconds, usd } from "../lib/language";
import type { LiveSignalRow } from "../lib/types";

/**
 * The actual LIVE signals, kept visible independently of the transition feed.
 *
 * The chronological history in SIGNALE mixes every CANDIDATE/PREWARNING/
 * REJECTED row, so at ~28 transitions/hour a LIVE signal leaves a 50-row page
 * within about two hours; measured 2026-09-21, all six real LIVE signals of the
 * preceding 92h had already scrolled out. This list only ever contains
 * committed LIVE transitions.
 */
export function LiveSignalHistory({ liveKey }: { liveKey: string | null }) {
  const { rows, available, error } = useLiveSignals(liveKey);

  return (
    <section className="card">
      <h2 className="card-title">Letzte LIVE-Signale</h2>
      {error ? (
        <p className="empty">Nicht erreichbar: {error}</p>
      ) : !available ? (
        <p className="empty">Verlauf derzeit nicht verfügbar.</p>
      ) : rows.length === 0 ? (
        <p className="empty">Bisher kein LIVE-Signal aufgezeichnet.</p>
      ) : (
        <ul className="signal-list">
          {rows.map((row) => (
            <LiveRow key={`${row.setup_id}-${row.timestamp}`} row={row} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Outcome status in plain language; the raw code stays visible beside it. */
const OUTCOME_TEXT: Record<string, string> = {
  RESOLVED: "Ausgewertet",
  INSUFFICIENT_FUTURE_DATA: "Nicht auswertbar – Kurslücken",
  INVALID_DATA: "Nicht auswertbar – ungültiger Kurs",
  CANCELLED: "Abgebrochen",
};

const OUTCOME_TONE: Record<string, string> = {
  RESOLVED: "ok",
  INSUFFICIENT_FUTURE_DATA: "warn",
  INVALID_DATA: "warn",
  CANCELLED: "idle",
};

function LiveRow({ row }: { row: LiveSignalRow }) {
  const [low, high] = row.entry_zone ?? [null, null];
  const status = row.outcome_status;
  const stillLive = row.live_seconds === null;

  return (
    <li className="signal-item">
      <details>
        <summary>
          <span className="si-main">
            <span className={`si-dir si-${(row.direction ?? "").toLowerCase()}`}>
              {row.direction ?? "—"}
            </span>
            <span className="si-time">{dateTime(row.timestamp)}</span>
          </span>
          <span className="si-right">
            {row.synthetic ? <span className="tag tag-warn">TEST</span> : null}
            {stillLive ? (
              <span className="tag tag-ok">LIVE</span>
            ) : (
              <span className={`tag tag-${OUTCOME_TONE[status ?? ""] ?? "idle"}`}>
                {status ? (OUTCOME_TEXT[status] ? "AUSWERTUNG" : status) : "OFFEN"}
              </span>
            )}
          </span>
        </summary>
        <dl className="kv">
          <div className="kv-row">
            <dt>Zeitpunkt</dt>
            <dd>{dateTime(row.timestamp)}</dd>
          </div>
          <div className="kv-row">
            <dt>Richtung</dt>
            <dd>{row.direction ?? "—"}</dd>
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
            <dt>Zeithorizont</dt>
            <dd>{horizon(row.expected_horizon)}</dd>
          </div>
          <div className="kv-row">
            <dt>LIVE-Dauer</dt>
            <dd>{stillLive ? "läuft noch" : seconds(row.live_seconds, 1)}</dd>
          </div>
          <div className="kv-row">
            <dt>Outcome</dt>
            <dd>
              {status ? OUTCOME_TEXT[status] ?? status : "noch offen"}
              {row.outcome_executable !== null && row.outcome_executable !== undefined ? (
                <span className="kv-sub">Ergebnis {usd(row.outcome_executable)}</span>
              ) : null}
            </dd>
          </div>
          {status === "INSUFFICIENT_FUTURE_DATA" && row.outcome_max_gap_seconds !== null ? (
            <div className="kv-row">
              <dt>Outcome-Grund</dt>
              <dd>
                Grösste Kurslücke {seconds(row.outcome_max_gap_seconds, 2)}
                <span className="kv-sub">erlaubt sind maximal {seconds(5, 2)}</span>
              </dd>
            </div>
          ) : null}
          <div className="kv-row">
            <dt>Signal-ID</dt>
            <dd className="mono">{(row.setup_id ?? "").slice(0, 12)}</dd>
          </div>
        </dl>
      </details>
    </li>
  );
}
