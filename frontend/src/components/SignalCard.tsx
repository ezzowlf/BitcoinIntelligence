import {
  clockTime,
  conflictText,
  evidenceStateText,
  evidenceText,
  evidenceTone,
  EVIDENCE_SOURCES,
  flowPressureText,
  flowValue,
  horizon,
  reasonText,
  seconds,
  stateText,
  usd,
  VANTAGE_MAX_QUOTE_AGE_S,
} from "../lib/language";
import { dataHealthRows } from "../lib/health";
import type { LiveState, ShadowSignal } from "../lib/types";

/**
 * "What should I be watching right now?" — the single most important surface.
 *
 * Every value rendered here comes from the engine's own shadow-signal record.
 * Where the engine reports nothing (confidence is `null` until calibration),
 * the field is omitted rather than filled with a plausible-looking number.
 *
 * A signal transition is a HISTORICAL record. Its feed states are the ones the
 * engine saw at `timestamp`, which by the time anyone reads the card have
 * usually recovered - so evaluation-time evidence and current live health are
 * rendered as two clearly separated blocks and never merged into one verdict.
 */
export function SignalCard({ state }: { state: LiveState }) {
  const shadow = state.shadow_signal;
  const signal = shadow?.signal ?? null;
  const live = signal !== null && signal.state_to === "LIVE";
  const direction = signal?.direction ?? null;

  const missing = signal?.missing_evidence ?? [];
  const reasons = signal?.reasons ?? [];

  return (
    <section className={`signal ${live ? `signal-${direction?.toLowerCase()}` : "signal-none"}`}>
      <div className="signal-top">
        <span className="signal-label">TAKEOFF SIGNAL</span>
        <span className="signal-symbol">{state.price.symbol}</span>
      </div>

      <div className="signal-verdict">
        {live ? (
          <span className={`verdict verdict-${direction?.toLowerCase()}`}>{direction}</span>
        ) : (
          <span className="verdict verdict-none">KEIN SIGNAL</span>
        )}
        <span className="signal-price">{usd(state.price.mid)}</span>
      </div>

      {live && signal ? (
        <LiveSignalBody signal={signal} />
      ) : (
        <NoSignalBody state={state} signal={signal} reasons={reasons} missing={missing} />
      )}

      {signal?.conflicts?.length ? <ConflictBlock signal={signal} /> : null}

      {signal ? <EvidenceBlocks state={state} signal={signal} /> : null}

      {signal ? (
        <details className="signal-tech">
          <summary>Technischer Grund</summary>
          <p className="mono">
            {reasons.length ? reasons.join(" · ") : "—"}
            {missing.length ? ` · ${missing.join(", ")}` : ""}
          </p>
          <p className="mono dim">
            {signal.state_to} · {signal.signal_version}
          </p>
          {missing.includes("vantage") ? (
            <p className="mono dim">
              Das exakte Quote-Alter wird nicht persistiert; nur die Anforderung ist bekannt.
            </p>
          ) : null}
        </details>
      ) : null}

      {shadow?.paused ? <p className="signal-paused">Signalbewertung pausiert.</p> : null}
    </section>
  );
}

// --------------------------------------------------------------- live signal

function LiveSignalBody({ signal }: { signal: ShadowSignal }) {
  const [low, high] = signal.entry_zone ?? [null, null];
  return (
    <>
      <dl className="facts">
        <Fact label="Entry-Zone" value={`${usd(low)} – ${usd(high)}`} />
        <Fact label="Invalidierung" value={usd(signal.invalidation)} />
        <Fact label="Zielklasse" value={signal.expected_move_class ? `$${signal.expected_move_class}` : "—"} />
        <Fact label="Zeithorizont" value={horizon(signal.expected_horizon)} />
        <Fact label="Ausführbare Seite" value={signal.vantage_executable_side ?? "—"} />
        <Fact label="Signalzeit" value={clockTime(signal.timestamp)} />
        <Fact label="Gültig bis" value={clockTime(signal.expires_at)} />
        <Fact label="Kalibrierung" value={signal.calibration_status ?? "—"} />
      </dl>
      {signal.reasons?.length ? (
        <p className="signal-why">{signal.reasons.map(reasonText).join(" · ")}</p>
      ) : null}
      <p className="signal-id">Signal-ID {signal.setup_id.slice(0, 12)}</p>
    </>
  );
}

// ----------------------------------------------------------------- no signal

/**
 * Names the source that was actually missing, instead of restating the engine
 * code. Falls back to the generic wording when the engine named no source.
 */
function missingHeadline(missing: string[], reasons: string[]): string {
  if (missing.includes("vantage")) {
    return "Vantage-Kurs war zum Bewertungszeitpunkt nicht frisch genug.";
  }
  if (missing.length === 1) {
    return `${evidenceText(missing[0])} war zum Bewertungszeitpunkt nicht verfügbar.`;
  }
  if (missing.length > 1) {
    return `Mehrere Quellen fehlten zum Bewertungszeitpunkt: ${missing.map(evidenceText).join(", ")}.`;
  }
  if (reasons.includes("SETUP_INVALIDATED")) return "Das Setup wurde invalidiert.";
  if (reasons.includes("SETUP_EXPIRED")) return "Das Setup ist abgelaufen.";
  return "Die aktuellen Bedingungen erfüllen die Entry-Regeln nicht.";
}

function flowAgreementText(value: string): string {
  if (value === "CONFIRMED") return "Bestätigt";
  if (value === "DIVERGENT") return "Divergent";
  if (value === "NEUTRAL") return "Neutral";
  return value || "—";
}

function NoSignalBody({
  state,
  signal,
  reasons,
  missing,
}: {
  state: LiveState;
  signal: ShadowSignal | null;
  reasons: string[];
  missing: string[];
}) {
  const market = state.market_state;
  const evidence = signal?.evidence;
  // The quote the engine decided on. entry_zone carries the same bid/ask pair,
  // so evidence is preferred and entry_zone is the fallback.
  const bid = evidence?.bid ?? signal?.entry_zone?.[0] ?? null;
  const ask = evidence?.ask ?? signal?.entry_zone?.[1] ?? null;
  const vantageMissing = missing.includes("vantage");

  return (
    <>
      <p className="signal-headline">{missingHeadline(missing, reasons)}</p>

      {vantageMissing && (bid !== null || ask !== null) ? (
        <div className="quote-block">
          <span className="quote-title">Letzter Quote</span>
          <dl className="facts">
            <Fact label="Bid" value={usd(bid)} />
            <Fact label="Ask" value={usd(ask)} />
            <Fact label="Erforderlich" value={`≤ ${seconds(VANTAGE_MAX_QUOTE_AGE_S)}`} />
            <Fact label="Quote-Alter" value="nicht erfasst" tone="idle" />
          </dl>
        </div>
      ) : null}

      <dl className="facts">
        <Fact label="Marktlage" value={market.direction_bias || "—"} />
        {signal?.direction ? (
          <Fact label="Nächste mögliche Richtung" value={signal.direction} />
        ) : null}
        <Fact label="Flussübereinstimmung" value={flowAgreementText(market.flow_agreement)} />
      </dl>
    </>
  );
}

// ------------------------------------------------------------------ conflict

/**
 * The engine's conflict rule compares signed order-flow imbalance on spot vs
 * futures and fires when the signs oppose. It never compares prices, so this
 * block shows the two flow values and deliberately avoids price wording.
 */
function ConflictBlock({ signal }: { signal: ShadowSignal }) {
  const spot = signal.evidence?.spot_delta;
  const futures = signal.evidence?.futures_delta;
  const hasFlows = spot !== undefined || futures !== undefined;

  return (
    <div className="conflict">
      <p className="conflict-text">{signal.conflicts.map(conflictText).join(" · ")}</p>
      {hasFlows ? (
        <dl className="facts">
          <Fact label="Spot Flow" value={`${flowValue(spot)} · ${flowPressureText(spot)}`} />
          <Fact label="Futures Flow" value={`${flowValue(futures)} · ${flowPressureText(futures)}`} />
        </dl>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ evidence

/**
 * Two separate blocks, never merged: what the ENGINE saw when it decided, and
 * what the feeds are doing NOW. Conflating them is what made a correct
 * CANCELLED look like it contradicted a green dashboard.
 */
function EvidenceBlocks({ state, signal }: { state: LiveState; signal: ShadowSignal }) {
  const feedHealth = signal.feed_health ?? {};
  const hasEvidence = Object.keys(feedHealth).length > 0;

  const currentRows = dataHealthRows(state).filter((row) => row.key !== "decision_pipeline");
  const notLive = currentRows.filter((row) => row.tone !== "ok");

  return (
    <div className="evidence">
      {hasEvidence ? (
        <div className="evidence-block">
          <span className="evidence-title">
            Zum Zeitpunkt der Bewertung · {clockTime(signal.timestamp)}
          </span>
          <ul className="evidence-list">
            {EVIDENCE_SOURCES.filter((key) => feedHealth[key] !== undefined).map((key) => (
              <li key={key}>
                <span className="evidence-name">{evidenceText(key)}</span>
                <span className={`tag tag-${evidenceTone(feedHealth[key])}`}>
                  {evidenceStateText(feedHealth[key])}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="evidence-block">
        <span className="evidence-title">Aktuell</span>
        {notLive.length === 0 ? (
          <p className="evidence-ok">
            <i className="dot dot-ok" aria-hidden="true" /> Alle Datenfeeds LIVE
          </p>
        ) : (
          <ul className="evidence-list">
            {currentRows.map((row) => (
              <li key={row.key}>
                <span className="evidence-name">{row.label}</span>
                <span className={`tag tag-${row.tone}`}>{stateText(row.state)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Fact({ label, value, tone: factTone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd className={factTone ? `tone-${factTone}` : undefined}>{value}</dd>
    </div>
  );
}
